#!/usr/bin/env python3
from pathlib import Path

PATH = Path('monthly_patch_parts/00.part')
text = PATH.read_text(encoding='utf-8')

old_write = "idbPut('question-shard:'+meta.file,{payload,sha256:meta.sha256,savedAt:Date.now()}).catch(()=>{});"
new_write = "idbPut('question-shard:'+meta.file,{payload,sha256:meta.sha256,verified_sha256:true,savedAt:Date.now()}).catch(()=>{});"
old_read = "if(rec && rec.payload && (!rec.sha256 || rec.sha256 === meta.sha256)){"
new_read = "if(rec && rec.payload && rec.verified_sha256 === true && rec.sha256 === meta.sha256){"

if old_write in text:
    text = text.replace(old_write, new_write, 1)
elif new_write not in text:
    raise SystemExit('Verified shard cache write target not found; refusing to guess.')

if old_read in text:
    text = text.replace(old_read, new_read, 1)
elif new_read not in text:
    raise SystemExit('Verified shard cache read target not found; refusing to guess.')

if text.count('verified_sha256:true') != 1:
    raise SystemExit('Expected exactly one verified_sha256 write marker.')
if text.count('rec.verified_sha256 === true') != 1:
    raise SystemExit('Expected exactly one verified_sha256 read guard.')

PATH.write_text(text, encoding='utf-8')
print('Patched IndexedDB shard provenance: offline cache now requires byte-verification marker.')
