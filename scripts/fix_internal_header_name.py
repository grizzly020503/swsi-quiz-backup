#!/usr/bin/env python3
from pathlib import Path
p=Path('supabase/functions/analyze-pending-questions/index.ts')
text=p.read_text(encoding='utf-8')
old='"x-internal-key": internalKey'
new='"X-SWSI-Internal-Key": internalKey'
if old not in text:
    raise SystemExit('old internal header marker not found')
text=text.replace(old,new,1)
if new not in text:
    raise SystemExit('header replacement failed')
p.write_text(text,encoding='utf-8')
print('Internal AI proxy header aligned with Worker.')
