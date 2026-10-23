#!/usr/bin/env python3
"""Create a *staged*, URL-only SWSI CDN release candidate outside the Git worktree.

Never updates the existing repo, database or network. This tool is *not* a deployer.
It requires exact Git-blob preimages before changing any source_url field.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

SOURCE = 'https://wwwq.moex.gov.tw/exam/wHandExamQandA_File.ashx'
SESSION_COUNT = 22


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def encode(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')


def load_unique_json(raw: bytes) -> dict:
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError('duplicate JSON field')
            out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=unique)


def render_session(raw: bytes, session: str, cfg: dict) -> tuple[bytes, int]:
    if git_blob(raw) != cfg['expected_sessions_before_git_blobs'][session]:
        raise ValueError(f'{session}: input shard has drifted from exact candidate preimage')
    doc = load_unique_json(raw)
    if len(doc['questions']) != 200 or doc['question_count'] != 200:
        raise ValueError(f'{session}: unexpected question count')
    legacy = set(cfg['retain_c_first_ids'])
    mapping = cfg['mapping']
    seen = set()
    changed = 0
    for q in doc['questions']:
        qid = q['id']
        if qid in seen:
            raise ValueError(f'{session}: duplicate question id')
        seen.add(qid)
        old_url = q['source_url']
        parts = urlsplit(old_url)
        if parts.scheme != 'https' or parts.netloc != 'wwwq.moex.gov.tw' or parts.path != '/exam/wHandExamQandA_File.ashx':
            raise ValueError(f'{session}: invalid official-source host/path')
        fields = parse_qsl(parts.query, keep_blank_values=True)
        if len(fields) != 5 or len(dict(fields)) != 5:
            raise ValueError(f'{session}: duplicated/unknown URL query parameters')
        values = dict(fields)
        if set(values) != {'c', 'code', 'q', 's', 't'} or values['t'] != 'Q' or values['q'] != '1' or values['code'] != q['source_exam_code']:
            raise ValueError(f'{session}: unexpected official-source query identity')
        key = f"{values['code']}/{values['s']}"
        replacement = mapping.get(key)
        if replacement is None:
            if qid in legacy:
                raise ValueError(f'{session}: legacy-order marker for unchanged ID')
            continue
        c, s = replacement
        if (values['c'], values['s']) == (c, s):
            raise ValueError(f'{session}: matched mapping that would be no-op')
        if qid in legacy:
            query = f"c={c}&code={values['code']}&q=1&s={s}&t=Q"
        else:
            query = f"t=Q&code={values['code']}&c={c}&s={s}&q=1"
        q['source_url'] = f'{SOURCE}?{query}'
        changed += 1
    after = encode(doc)
    if changed != cfg['expected_changed_counts'][session]:
        raise ValueError(f'{session}: changed rows {changed} != expected')
    if git_blob(after) != cfg['expected_sessions_after_git_blobs'][session]:
        raise ValueError(f'{session}: candidate byte-level target mismatch')
    return after, changed


def stage(root: Path, cfg: dict) -> tuple[dict[str, bytes], dict]:
    if cfg.get('schema') != 'swsi-source-url-promotion-review-v1' or cfg.get('status') != 'QA_ONLY_NOT_AUTHORIZED_FOR_PRODUCTION':
        raise ValueError('unrecognized release candidate and gate')
    expected = cfg['expected_sessions_before_git_blobs']
    if len(expected) != SESSION_COUNT or set(expected) != set(cfg['expected_sessions_after_git_blobs']):
        raise ValueError('expected 22 historical shards')
    if len(cfg['retain_c_first_ids']) != len(set(cfg['retain_c_first_ids'])):
        raise ValueError('duplicate legacy query-format markers')
    output: dict[str, bytes] = {}
    changed_total = 0
    for session in sorted(expected):
        raw = (root / f'cdn/question-shards/{session}.json').read_bytes()
        output[f'{session}.json'], changed = render_session(raw, session, cfg)
        changed_total += changed
    if changed_total != cfg['expected_total_changed'] or len(cfg['retain_c_first_ids']) != cfg['expected_kept_legacy_query_order']:
        raise ValueError('total number of source URL changes differs')
    manifest_raw = (root / 'cdn/question-shards/manifest.json').read_bytes()
    if git_blob(manifest_raw) != cfg['expected_manifest_before_git_blob']:
        raise ValueError('manifest before-image drift')
    manifest = load_unique_json(manifest_raw)
    if manifest['total_questions'] != 4800 or manifest['shard_count'] != 24:
        raise ValueError('unexpected manifest dimensions')
    manifest['dataset_revision'] = cfg['target_manifest_revision']
    manifest['generated_at'] = cfg['target_manifest_generated_at']
    manifest['source'] = cfg['target_manifest_source']
    manifest['total_uncompressed_bytes'] = cfg['target_manifest_total_bytes']
    # Keep the exact field order of the existing manifest entries.
    manifest['shards'] = [
        {key: replacement[key] for key in current}
        for current, replacement in zip(manifest['shards'], cfg['target_manifest_shards'])
    ]
    # Manifest also includes two latest-exam shards excluded from URL updates.
    # Refuse to stage a manifest claiming unchanged data when either file drifted.
    for item in manifest['shards']:
        file = item['file']
        raw = output.get(file)
        if raw is None:
            if file not in ('115-1.json', '115-2.json'):
                raise ValueError(f'{file}: unexpected unverified shard in manifest')
            raw = (root / 'cdn/question-shards' / file).read_bytes()
        if item['sha256'] != hashlib.sha256(raw).hexdigest() or item['bytes'] != len(raw):
            raise ValueError(f'{file}: manifest SHA256/bytes mismatch (staged or unchanged)')
    output['manifest.json'] = encode(manifest)
    if git_blob(output['manifest.json']) != cfg['expected_manifest_after_git_blob']:
        raise ValueError('manifest target does not match reviewed candidate')
    return output, {'status': 'STAGED_QA_ONLY_NOT_DEPLOYED', 'sessions_verified': len(expected), 'historical_questions': 4400,
                    'changed_source_urls': changed_total, 'other_fields_changed': 0, 'manifest_matched': True,
                    'production_db_written': False, 'main_shards_written': False, 'owner_approval_needed': True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[1] / 'data/source_url_promotion_config.json')
    parser.add_argument('--out', type=Path, help='write candidate into an OUTSIDE-repo staging directory')
    args = parser.parse_args()
    root = args.root.resolve()
    cfg = load_unique_json(args.config.read_bytes())
    outputs, report = stage(root, cfg)
    if args.out:
        out = args.out.resolve()
        if root == out or root in out.parents:
            raise SystemExit('REFUSED: staging output must not be inside the repository')
        if out.exists() and any(out.iterdir()):
            raise SystemExit('REFUSED: output directory must be empty')
        out.mkdir(parents=True, exist_ok=True)
        for name, raw in outputs.items():
            (out / name).write_bytes(raw)
        (out / 'STAGED_QA_ONLY.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())