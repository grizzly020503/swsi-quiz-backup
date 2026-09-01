#!/usr/bin/env python3
from pathlib import Path

FILES = [
    Path('monthly_patch_parts/89.public-branding-info.part'),
    Path('cdn/monthly_patch.js'),
]

for p in FILES:
    s = p.read_text(encoding='utf-8')
    old = "return '<div class=\"swsi-public-info-dialog\" role=\"dialog\" aria-modal=\"true\" aria-labelledby=\"swsi-public-info-title\" onclick=\"event.stopPropagation()\">'+"
    new = "return '<div class=\"swsi-public-info-dialog\" role=\"dialog\" aria-modal=\"true\" aria-labelledby=\"swsi-public-info-title\">'+"
    if old not in s:
        raise SystemExit(f'{p}: dialog propagation marker not found')
    s = s.replace(old, new, 1)

    old = "ov.onclick=closeInfo;"
    new = "ov.onclick=function(ev){if(ev.target===ov)closeInfo();};"
    if old not in s:
        raise SystemExit(f'{p}: backdrop click marker not found')
    s = s.replace(old, new, 1)

    old = "window.SWSI_PUBLIC_INFO={version:'2026-09-01.monitoring-v1',marker:'SWSI Public Branding / Monitoring Center V1 2026-09-01'};"
    new = "window.SWSI_PUBLIC_INFO={version:'2026-09-01.monitoring-v1.1',marker:'SWSI Public Branding / Monitoring Center V1.1 2026-09-01'};"
    if old not in s:
        raise SystemExit(f'{p}: monitoring version marker not found')
    s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')

p = Path('scripts/browser_interaction_smoke.js')
s = p.read_text(encoding='utf-8')
anchor = "  await assertCompactHomeFooter();\n\n"
block = r'''  // Public monitoring controls must remain clickable inside the modal.
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.getByRole('button', { name: '監測', exact: true }).click();
  await page.waitForSelector('#swsi-public-monitor', { timeout: 10000 });
  await page.waitForFunction(() => {
    const root = document.querySelector('#swsi-public-monitor');
    return root && root.dataset.running === '0';
  }, null, { timeout: 15000 });
  const refresh = page.locator('[data-swsi-monitor-refresh]');
  assert.strictEqual(await refresh.count(), 1, 'monitor refresh button missing');
  await refresh.click();
  await page.waitForFunction(() => {
    const root = document.querySelector('#swsi-public-monitor');
    return root && root.dataset.running === '1';
  }, null, { timeout: 5000 });
  await page.waitForFunction(() => {
    const root = document.querySelector('#swsi-public-monitor');
    return root && root.dataset.running === '0';
  }, null, { timeout: 15000 });
  await page.getByRole('button', { name: '隱私', exact: true }).click();
  await page.waitForFunction(() => {
    const h = document.querySelector('#swsi-public-info-title');
    return h && /隱私說明/.test(h.textContent || '');
  }, null, { timeout: 5000 });
  await page.locator('.swsi-public-info-close').click();
  await page.waitForSelector('#swsi-public-info-backdrop', { state: 'detached' });
  await page.evaluate(() => window.scrollTo(0, 0));

'''
if block in s:
    raise SystemExit('browser regression block already present')
if anchor not in s:
    raise SystemExit('browser interaction insertion anchor not found')
s = s.replace(anchor, anchor + block, 1)
p.write_text(s, encoding='utf-8')

print('monitoring refresh hotfix staged')
