(() => {
  'use strict';

  const SUPABASE_URL = 'https://yumjtrdctaxyczpspuyo.supabase.co';
  const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_6KL-X7KfkcfyP1kLxfokhA_0h2YuYMr';
  const ADMIN_ENDPOINT = SUPABASE_URL + '/functions/v1/swsi-admin';
  const AUTH_STORAGE_KEY = 'sb-yumjtrdctaxyczpspuyo-auth-token';
  const GITHUB_PREFIX = 'https://github.com/grizzly020503/swsi-quiz-backup/';

  const riskLabel = {
    high: '高風險・人工確認',
    medium: '中風險・人工確認',
    low: '低風險・可自動草擬',
    untriaged: '尚待自動分流',
  };

  function tokenFromStorage() {
    try {
      const raw = localStorage.getItem(AUTH_STORAGE_KEY);
      if (!raw) return '';
      const parsed = JSON.parse(raw);
      return parsed?.access_token || parsed?.currentSession?.access_token || '';
    } catch (_e) {
      return '';
    }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = String(text);
    return node;
  }

  function safeGitHubLink(value, label) {
    if (typeof value !== 'string' || !value.startsWith(GITHUB_PREFIX)) return null;
    const a = el('a', 'swsi-cluster-link', label);
    a.href = value;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    return a;
  }

  function addStyles() {
    if (document.getElementById('swsi-cluster-style')) return;
    const style = document.createElement('style');
    style.id = 'swsi-cluster-style';
    style.textContent = `
      .swsi-cluster-summary{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 14px}
      .swsi-cluster-chip{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;padding:7px 10px;background:#fff;font-size:12px;font-weight:700;color:#475467}
      .swsi-cluster-list{display:grid;gap:12px}
      .swsi-cluster-card{border:1px solid var(--line);border-radius:16px;background:#fff;padding:15px}
      .swsi-cluster-head{display:flex;gap:10px;justify-content:space-between;align-items:flex-start}
      .swsi-cluster-title{font-weight:780;line-height:1.45}
      .swsi-cluster-risk{display:inline-flex;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:760;white-space:nowrap;background:#eef0f3;color:#475467}
      .swsi-cluster-risk.high{background:#feeceb;color:#9f221a}
      .swsi-cluster-risk.medium{background:#fff4d6;color:#7a5200}
      .swsi-cluster-risk.low{background:#e8f7ef;color:#12663f}
      .swsi-cluster-meta{font-size:12px;color:var(--muted);line-height:1.65;margin-top:7px}
      .swsi-cluster-desc{line-height:1.65;margin-top:10px;white-space:pre-wrap}
      .swsi-cluster-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:11px}
      .swsi-cluster-link{color:var(--accent);font-weight:700;text-decoration:none}
      .swsi-cluster-link:hover{text-decoration:underline}
      .swsi-cluster-empty{border:1px dashed #cfd4dc;border-radius:16px;padding:24px;text-align:center;color:var(--muted)}
      @media(max-width:540px){.swsi-cluster-head{display:block}.swsi-cluster-risk{margin-top:8px}}
    `;
    document.head.appendChild(style);
  }

  function ensureUi() {
    const tabs = document.querySelector('.tabs');
    const main = document.querySelector('#adminView main');
    if (!tabs || !main) return null;
    let tab = document.getElementById('swsiClusterTab');
    if (!tab) {
      tab = el('button', 'tab', '問題群組');
      tab.id = 'swsiClusterTab';
      tab.type = 'button';
      tab.dataset.tab = 'clusters';
      const feedbackTab = tabs.querySelector('[data-tab="feedback"]');
      if (feedbackTab?.nextSibling) tabs.insertBefore(tab, feedbackTab.nextSibling);
      else tabs.appendChild(tab);
    }
    let section = document.getElementById('tab-clusters');
    if (!section) {
      section = el('section', 'hidden');
      section.id = 'tab-clusters';
      const heading = el('div', 'row section');
      heading.appendChild(el('h2', '', '問題群組'));
      const spacer = el('div', 'spacer');
      heading.appendChild(spacer);
      const refresh = el('button', 'btn', '重新整理群組');
      refresh.type = 'button';
      refresh.id = 'swsiClusterRefresh';
      heading.appendChild(refresh);
      section.appendChild(heading);
      const summary = el('div', 'swsi-cluster-summary');
      summary.id = 'swsiClusterSummary';
      section.appendChild(summary);
      const list = el('div', 'swsi-cluster-list');
      list.id = 'swsiClusterList';
      section.appendChild(list);
      main.appendChild(section);
    }
    return { tab, section };
  }

  function showClusterTab() {
    const ui = ensureUi();
    if (!ui) return;
    document.querySelectorAll('.tabs .tab').forEach((node) => node.classList.toggle('active', node === ui.tab));
    ['overview', 'feedback', 'analytics'].forEach((name) => {
      const node = document.getElementById('tab-' + name);
      if (node) node.classList.add('hidden');
    });
    ui.section.classList.remove('hidden');
    loadClusters();
  }

  function hideClusterTab() {
    document.getElementById('tab-clusters')?.classList.add('hidden');
  }

  function renderSummary(data) {
    const box = document.getElementById('swsiClusterSummary');
    if (!box) return;
    box.replaceChildren();
    const clusters = Array.isArray(data?.feedback_clusters) ? data.feedback_clusters : [];
    const pending = Number(data?.summary?.feedback_pending || 0);
    const total = Number(data?.summary?.feedback_total || 0);
    const windowCount = Number(data?.summary?.feedback_window_count || 0);
    box.appendChild(el('span', 'swsi-cluster-chip', `${clusters.length} 個問題群組`));
    box.appendChild(el('span', 'swsi-cluster-chip', `${pending} 筆待處理`));
    box.appendChild(el('span', 'swsi-cluster-chip', `${total} 筆累計回報`));
    if (total > windowCount) box.appendChild(el('span', 'swsi-cluster-chip', `目前彙整最新 ${windowCount} 筆`));
  }

  function renderClusters(data) {
    renderSummary(data);
    const list = document.getElementById('swsiClusterList');
    if (!list) return;
    list.replaceChildren();
    const clusters = Array.isArray(data?.feedback_clusters) ? data.feedback_clusters : [];
    if (!clusters.length) {
      list.appendChild(el('div', 'swsi-cluster-empty', '目前沒有需要顯示的回報群組。'));
      return;
    }
    clusters.forEach((cluster) => {
      const card = el('article', 'swsi-cluster-card');
      const head = el('div', 'swsi-cluster-head');
      const left = document.createElement('div');
      const title = cluster.summary || cluster.context_title || cluster.cluster_key || '未命名問題群組';
      left.appendChild(el('div', 'swsi-cluster-title', title));
      const pending = Number(cluster?.status_counts?.pending || 0);
      const metaBits = [`${Number(cluster.count || 0)} 筆回報`];
      if (pending) metaBits.push(`${pending} 筆待處理`);
      if (cluster.subject) metaBits.push(cluster.subject);
      if (cluster.context_title && cluster.context_title !== title) metaBits.push(cluster.context_title);
      if (Array.isArray(cluster.report_nos) && cluster.report_nos.length) metaBits.push('回報 #' + cluster.report_nos.slice(0, 8).join(', #'));
      left.appendChild(el('div', 'swsi-cluster-meta', metaBits.join('｜')));
      head.appendChild(left);
      const risk = String(cluster.risk_level || 'untriaged');
      head.appendChild(el('span', `swsi-cluster-risk ${risk}`, riskLabel[risk] || riskLabel.untriaged));
      card.appendChild(head);
      if (cluster.cluster_key) card.appendChild(el('div', 'swsi-cluster-meta', 'Cluster: ' + cluster.cluster_key));
      const actions = el('div', 'swsi-cluster-actions');
      const issue = safeGitHubLink(cluster.github_issue, '查看 GitHub Issue');
      const pr = safeGitHubLink(cluster.github_pr, '查看 Draft PR');
      if (issue) actions.appendChild(issue);
      if (pr) actions.appendChild(pr);
      if (actions.childNodes.length) card.appendChild(actions);
      list.appendChild(card);
    });
  }

  function renderError(message) {
    const list = document.getElementById('swsiClusterList');
    if (!list) return;
    list.replaceChildren(el('div', 'swsi-cluster-empty', message));
  }

  async function loadClusters() {
    const list = document.getElementById('swsiClusterList');
    if (list) list.replaceChildren(el('div', 'swsi-cluster-empty', '正在讀取問題群組…'));
    let token = tokenFromStorage();
    for (let i = 0; !token && i < 20; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      token = tokenFromStorage();
    }
    if (!token) {
      renderError('尚未取得管理者登入狀態。請先登入管理中心。');
      return;
    }
    try {
      const res = await fetch(ADMIN_ENDPOINT, {
        headers: {
          apikey: SUPABASE_PUBLISHABLE_KEY,
          Authorization: 'Bearer ' + token,
        },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`);
      renderClusters(data);
    } catch (error) {
      renderError('問題群組暫時讀取失敗：' + (error?.message || '未知錯誤'));
    }
  }

  function init() {
    addStyles();
    const ui = ensureUi();
    if (!ui) return;
    ui.tab.addEventListener('click', showClusterTab);
    document.getElementById('swsiClusterRefresh')?.addEventListener('click', loadClusters);
    document.querySelectorAll('.tabs .tab:not(#swsiClusterTab)').forEach((tab) => tab.addEventListener('click', hideClusterTab));
    window.swsiLoadFeedbackClusters = loadClusters;
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
