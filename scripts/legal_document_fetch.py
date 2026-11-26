#!/usr/bin/env python3
"""Read-only: print official documents needed for a per-question legal review.

Reads the `documents` list of audit/legal_document_requests.json. Each entry
names a government download URL (https hosts under .gov.tw or .gov.taipei
only) and asks either for the whole text (`full`) or for the passages around
some terms (`terms`). Entries marked `"fetched": true` are skipped.

Prints, per document: one @@DOC line (URL, final URL, HTTP status, type, size,
SHA-256 of the downloaded bytes, or the error), one @@DOCHEAD line (the first
characters, to identify the version), then @@DOCTXT chunks or @@DOCHIT
passages, and @@DOCLINK lines for download links found on an HTML page. The
job log is the evidence channel; no repository, database or website writes.
"""
import hashlib
import html
import io
import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / 'audit/legal_document_requests.json'
UA = 'swsi-legal-document-fetch/1.0 (+educational question bank)'
ALLOWED_SUFFIXES = ('.gov.tw', '.gov.taipei')
MAX_BYTES = 60 * 1024 * 1024
CHUNK = 3000
HEAD = 1500


def allowed(url):
    parts = urlparse(url)
    host = (parts.hostname or '').lower()
    return parts.scheme == 'https' and any(host.endswith(s) for s in ALLOWED_SUFFIXES)


def download(url):
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=120, headers={'User-Agent': UA}, allow_redirects=True)
            for hop in list(r.history) + [r]:
                if not allowed(hop.url):
                    raise RuntimeError('redirected outside the allowed hosts: ' + hop.url)
            r.raise_for_status()
            if len(r.content) > MAX_BYTES:
                raise RuntimeError('document too large: %d bytes' % len(r.content))
            return r
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(10 * (attempt + 1))
    raise last


def clean(text):
    text = html.unescape(text).replace('\r', '\n').replace('　', ' ')
    lines = [re.sub(r'[ \t\f\v]+', ' ', line).strip() for line in text.split('\n')]
    return '\n'.join(line for line in lines if line)


def xml_text(xml, para_end, tab, breaks):
    xml = re.sub(para_end, '\n', xml)
    xml = re.sub(tab, '\t', xml)
    xml = re.sub(breaks, '\n', xml)
    return clean(re.sub(r'<[^>]+>', '', xml))


def html_text(page):
    page = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', '', page)
    page = re.sub(r'(?i)<br\s*/?>|</(p|div|tr|li|h[1-6]|table)>', '\n', page)
    page = re.sub(r'(?i)</t[dh]>', '\t', page)
    return clean(re.sub(r'<[^>]+>', '', page))


def html_links(page, base):
    out = []
    for m in re.finditer(r'(?is)<a\b[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', page):
        href = urljoin(base, html.unescape(m.group(1)))
        if re.search(r'(dl-\d+|\.pdf|\.odt|\.docx?|FileLoad|LawExport|/File/)', href, re.I):
            out.append({'href': href, 'text': clean(re.sub(r'<[^>]+>', '', m.group(2)))[:120]})
    return out


def run(cmd, data, suffix):
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / ('doc' + suffix)
        src.write_bytes(data)
        done = subprocess.run(cmd + [str(src)] + (['-'] if cmd[0] == 'pdftotext' else []),
                              capture_output=True, timeout=300)
        if done.returncode != 0:
            raise RuntimeError(cmd[0] + ' failed: ' + done.stderr.decode('utf-8', 'replace')[:300])
        return clean(done.stdout.decode('utf-8', 'replace'))


def extract(resp):
    data = resp.content
    if data[:5] == b'%PDF-':
        if not shutil.which('pdftotext'):
            raise RuntimeError('pdftotext is not installed')
        return 'pdf', run(['pdftotext', '-enc', 'UTF-8'], data, '.pdf'), []
    if data[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set(z.namelist())
            if 'content.xml' in names:
                xml = z.read('content.xml').decode('utf-8', 'replace')
                xml = re.sub(r'<text:s(?: text:c="(\d+)")?\s*/>', lambda m: ' ' * int(m.group(1) or 1), xml)
                return 'odt', xml_text(xml, r'</text:(p|h)>', r'<text:tab\s*/>', r'<text:line-break\s*/>'), []
            if 'word/document.xml' in names:
                xml = z.read('word/document.xml').decode('utf-8', 'replace')
                return 'docx', xml_text(xml, r'</w:p>', r'<w:tab\s*/>', r'<w:br\s*/>'), []
        raise RuntimeError('unsupported zip document')
    if data[:4] == b'\xd0\xcf\x11\xe0':
        if not shutil.which('antiword'):
            raise RuntimeError('antiword is not installed')
        return 'doc', run(['antiword', '-m', 'UTF-8.txt', '-w', '0'], data, '.doc'), []
    encoding = resp.encoding if resp.encoding and resp.encoding.lower() not in ('iso-8859-1',) else None
    page = None
    for enc in [e for e in (encoding, 'utf-8', 'cp950') if e]:
        try:
            page = data.decode(enc)
            break
        except (LookupError, UnicodeDecodeError):
            continue
    if page is None:
        page = data.decode('utf-8', 'replace')
    return 'html', html_text(page), html_links(page, resp.url)


def emit(tag, payload):
    print(tag, json.dumps(payload, ensure_ascii=False), flush=True)


def main():
    req = json.loads(REQUESTS.read_text(encoding='utf-8'))
    ok = failed = 0
    for doc in req['documents']:
        if doc.get('fetched'):
            continue
        key, url = doc['key'], doc['url']
        meta = {'key': key, 'url': url, 'purpose': doc.get('purpose')}
        try:
            if not allowed(url):
                raise RuntimeError('host not allowed (https .gov.tw / .gov.taipei only)')
            time.sleep(2)
            resp = download(url)
            kind, text, links = extract(resp)
            meta.update({'final_url': resp.url, 'status': resp.status_code,
                         'content_type': resp.headers.get('Content-Type'),
                         'content_disposition': resp.headers.get('Content-Disposition'),
                         'bytes': len(resp.content), 'sha256': hashlib.sha256(resp.content).hexdigest(),
                         'kind': kind, 'chars': len(text)})
        except Exception as exc:  # noqa: BLE001
            meta['error'] = '%s: %s' % (type(exc).__name__, str(exc)[:300])
            emit('@@DOC', meta)
            failed += 1
            continue
        emit('@@DOC', meta)
        emit('@@DOCHEAD', {'key': key, 'text': text[:HEAD]})
        if doc.get('full'):
            for n, start in enumerate(range(0, len(text), CHUNK)):
                emit('@@DOCTXT', {'key': key, 'part': n, 'text': text[start:start + CHUNK]})
        window = int(doc.get('window') or 800)
        for term in doc.get('terms') or []:
            hits = [m.start() for m in re.finditer(re.escape(term), text)][:int(doc.get('max_hits') or 8)]
            emit('@@DOCTERM', {'key': key, 'term': term, 'hits': len(hits)})
            for pos in hits:
                emit('@@DOCHIT', {'key': key, 'term': term, 'pos': pos,
                                  'text': text[max(0, pos - window): pos + window]})
        for link in links[:200]:
            emit('@@DOCLINK', {'key': key, **link})
        ok += 1
    print('DOCUMENT FETCH SUMMARY: ok=%d failed=%d' % (ok, failed))


if __name__ == '__main__':
    main()
