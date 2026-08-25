#!/usr/bin/env python3
from pathlib import Path

INDEX = Path('index.html')
RADAR_INSTALLER = Path('scripts/install_current_affairs_ui.py')
README = Path('README.md')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'missing expected marker: {label}')
    return text.replace(old, new, 1)


def main() -> None:
    text = INDEX.read_text(encoding='utf-8')

    # Public site is student-facing only. Maintenance stays in backend tooling.
    text = replace_once(
        text,
        '      <button class="gear" onclick="go(\'admin\')" title="管理">⚙</button>\n',
        '',
        'admin gear button',
    )
    text = replace_once(
        text,
        "  if(view==='admin') return renderAdmin();",
        "  if(view==='admin') { view='home'; return renderHome(); }",
        'admin route',
    )

    # Align public-facing wording with the actual free/open product direction.
    text = replace_once(
        text,
        '© 2026 熊品澄 · 版權所有<br>本平台為私人非營利學習用途，僅供授權同學使用，禁止外傳、複製或商業利用',
        '© 2026 熊品澄 · 免費公開學習工具<br>社工師國考題目以考選部官方資料為準；AI 回饋僅供練習參考，不作為官方評分',
        'public footer',
    )

    # Remove an obsolete rescue-era filename from the student error message.
    text = replace_once(
        text,
        '請確認 essays_2.js 與 index.html 放在同一資料夾。',
        '申論題資料暫時無法載入，請重新整理或稍後再試。',
        'obsolete essay error',
    )

    # Privacy/ethics warning before typed or photographed AI feedback.
    ai_marker = '  return `<div style="margin-top:14px;border-top:1px dashed var(--line);padding-top:12px">\n    <div class="aihelp"'
    ai_replacement = '  return `<div style="margin-top:14px;border-top:1px dashed var(--line);padding-top:12px">\n    <div class="aihelp" style="color:var(--wrong);margin-bottom:9px;background:var(--wrong-bg);border:1px solid var(--line);border-radius:8px;padding:9px 12px">🔒 隱私提醒：請勿輸入或上傳真實個案的姓名、電話、地址、身分證號、病歷或其他可識別個資；需要舉例時請先匿名化。</div>\n    <div class="aihelp"'
    text = replace_once(text, ai_marker, ai_replacement, 'AI privacy warning')

    # Radar cards use category templates, not per-article AI analysis.
    text = text.replace('怎麼變成申論考點？', '此類事件常見的申論思考方向')

    INDEX.write_text(text, encoding='utf-8')

    installer = RADAR_INSTALLER.read_text(encoding='utf-8')
    installer = installer.replace('怎麼變成申論考點？', '此類事件常見的申論思考方向')
    RADAR_INSTALLER.write_text(installer, encoding='utf-8')

    readme = README.read_text(encoding='utf-8')
    readme = replace_once(
        readme,
        '3. Supabase anon key 可存在前端，但 service-role key 絕不能寫進 GitHub 或網站。',
        '3. Supabase anon key 可存在前端，但 service-role key 絕不能寫進 GitHub 或網站。\n4. 學生端對 `questions`／`essays` 僅有 SELECT 權限；公開網站不提供管理登入或 CSV 寫入入口，更新由後台自動化／Supabase 管理端處理。',
        'README security rule',
    )
    readme = readme.replace('4. AI 申論批改依賴 Cloudflare Worker；', '5. AI 申論批改依賴 Cloudflare Worker；', 1)
    readme = readme.replace('5. GitHub commit history 是版本歷史；', '6. GitHub commit history 是版本歷史；', 1)
    README.write_text(readme, encoding='utf-8')

    # Safety assertions: fail the workflow instead of silently shipping a partial patch.
    final = INDEX.read_text(encoding='utf-8')
    checks = {
        'admin button removed': "onclick=\"go('admin')\" title=\"管理\"" not in final,
        'privacy warning present': '🔒 隱私提醒' in final,
        'public footer present': '免費公開學習工具' in final,
        'obsolete filename removed': 'essays_2.js' not in final,
        'radar wording corrected': '此類事件常見的申論思考方向' in final,
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise SystemExit('frontend hardening checks failed: ' + ', '.join(failed))
    print('Public frontend hardening complete.')


if __name__ == '__main__':
    main()
