(() => {
  'use strict';
  let items = window.BOARD_ITEMS;
  let meta = window.BOARD_META;
  let snapshot = new Date();
  const storageKey = 'ai-news-board-design-v1';
  const stages = ['待评估', '准备写', '已发布', '暂不做'];
  const categories = ['全部', '模型更新', '编程工具', '产品更新', '开源工具', '活动福利'];
  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const icons = {
    grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    box:'<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="M3 8v10l9 5 9-5V8M12 13v10M7.5 5.5l9 5"/>',
    calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18M8 15h2M14 15h2"/>',
    bookmark:'<path d="M6 4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v17l-6-4-6 4V4Z"/>',
    gift:'<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M5 12v9h14v-9M12 8v13M12 8H8a2.5 2.5 0 1 1 2.5-2.5L12 8Zm0 0h4a2.5 2.5 0 1 0-2.5-2.5L12 8Z"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    filter:'<path d="M3 5h18M6 12h12M9 19h6"/>',
    download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
    'arrow-right':'<path d="M4 12h16m-6-6 6 6-6 6"/>',
    'arrow-up-right':'<path d="M6 18 18 6M6 6h12v12"/>',
    globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
    x:'<path d="m6 6 12 12M6 18 18 6"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
    verified:'<path d="m12 3 3 2 3 .5.5 3 2 3-2 3-.5 3-3 .5-3 2-3-2-3-.5-.5-3-2-3 2-3 .5-3 3-.5 3-2Z"/><path d="m8 12 2.5 2.5L16 9"/>',
    edit:'<path d="m16 3 5 5-12 12-6 1 1-6L16 3ZM13 6l5 5"/>',
    alert:'<path d="m12 3 10 18H2L12 3ZM12 9v5M12 17h.01"/>',
    copy:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    user:'<circle cx="12" cy="8" r="3"/><path d="M5 21v-2a7 7 0 0 1 14 0v2H5Z"/>'
  };
  const icon = (name) => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (icons[name] || icons.grid) + '</svg>';
  const hydrateIcons = (root = document) => root.querySelectorAll('[data-icon]').forEach((node) => { node.outerHTML = icon(node.dataset.icon); });
  let validIds = new Set(items.map((item) => item.id));
  let stored = { selected: [], notes: {}, stages: {}, records: {} };
  let storageAvailable = true;
  try {
    const raw = JSON.parse(localStorage.getItem(storageKey) || 'null');
    if (raw && typeof raw === 'object') {
      stored.selected = Array.isArray(raw.selected) ? [...new Set(raw.selected.filter((id) => typeof id === 'string'))] : [];
      stored.records = raw.records && typeof raw.records === 'object' ? raw.records : {};
      for (const id of new Set([...stored.selected,...Object.keys(raw.notes || {}),...Object.keys(raw.stages || {})])) {
        if (typeof raw.notes?.[id] === 'string') stored.notes[id] = raw.notes[id].slice(0, 4000);
        if (stages.includes(raw.stages?.[id])) stored.stages[id] = raw.stages[id];
      }
    }
  } catch { storageAvailable = false; }
  restoreSaved();
  const state = { view: 'overview', type: 'all', category: '全部', query: '', range: 'all', sort: 'priority' };
  const views = {
    overview: { label:'消息总览', title:'AI 消息看板', subtitle:'产品更新与最新活动，放在一处看。', feed:'全部消息', icon:'grid' },
    release: { label:'产品发布', title:'产品发布', subtitle:'看看新变化，再决定值得为谁做一期。', feed:'产品更新', icon:'box' },
    event: { label:'活动福利', title:'活动与福利', subtitle:'先核对资格、权益和时间，再整理参与攻略。', feed:'活动消息', icon:'calendar' },
    heat: { label:'话题热度', title:'媒体话题热度', subtitle:'看看哪些话题被反复报道，找到值得跟进的切入点。', feed:'媒体话题', icon:'globe' },
    saved: { label:'选题清单', title:'我的选题清单', subtitle:'留住值得跟进的消息，把角度和进度记下来。', feed:'已加入的选题', icon:'bookmark' }
  };
  let toastTimer;
  function toast(message) {
    clearTimeout(toastTimer);
    $('#toast').textContent = message;
    $('#toast').classList.add('visible');
    toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 2800);
  }
  function persist() {
    try { localStorage.setItem(storageKey, JSON.stringify(stored)); return true; }
    catch {
      if (storageAvailable) toast('浏览器未允许保存；本次操作仅保留在当前页面');
      storageAvailable = false;
      return false;
    }
  }
  function isSaved(id) { return stored.selected.includes(id); }
  function eventStatus(item) {
    if (item.type !== 'event') return null;
    if (item.end && parseDate(item.end) < snapshot) return { label:'活动已结束', color:'gray' };
    if (item.periodStart && item.periodStart > new Date(snapshot.getTime()+8*3600000).toISOString().slice(0,10)) return { label:'即将开始 · 日期范围', color:'green' };
    if (item.start && parseDate(item.start) > snapshot) return { label:'即将开始', color:'green' };
    if (item.start && item.end) {
      const days = Math.ceil((parseDate(item.end) - snapshot) / 86400000);
      return { label: days <= 3 ? '活动约 ' + days + ' 天后结束' : '活动中', color: days <= 3 ? 'orange' : 'green' };
    }
    return { label:'活动时间待核对', color:'gray' };
  }
  function parseDate(value) { return new Date(value); }
  function archived(item) {
    if(item.savedArchive) return true;
    if(item.type==='event') return !!item.end && parseDate(item.end)<snapshot;
    return !!item.date && snapshot-parseDate(item.date)>30*86400000;
  }
  function currentItems() { return items.filter(item=>!archived(item)); }
  function restoreSaved() {
    for(const id of stored.selected) {
      if(items.some(item=>item.id===id)) continue;
      const old=stored.records[id];
      items.push(old ? {...old,savedArchive:true,checked:'已保存历史选题 · 本轮未更新'} : {
        id,title:'历史选题 · '+id,brand:'本机保存',summary:'此条来自此前版本，保留了你的笔记和进度。',
        type:'release',category:'历史记录',date:null,dateLabel:'历史记录',tags:['历史选题'],
        checked:'未作为最新消息展示',facts:[],conditions:['原文需重新核对。'],sources:[],
        angle:'',format:'待整理',audience:'待确定',priority:99,savedArchive:true
      });
    }
    validIds=new Set(items.map(item=>item.id));
  }
  function filterItems() {
    const query = state.query.trim().toLocaleLowerCase();
    const maxAge = state.range === 'week' ? 7 : state.range === 'month' ? 30 : Infinity;
    const result = items.filter((item) => {
      if(state.view!=='saved' && (state.range==='archive' ? !archived(item) : archived(item))) return false;
      if (state.view === 'saved' && !isSaved(item.id)) return false;
      if (state.type !== 'all' && item.type !== state.type) return false;
      if (state.category !== '全部' && item.category !== state.category) return false;
      if (maxAge !== Infinity) {
        if(!(item.type==='event' && !archived(item))) {
          if(!item.date) return false;
          const age=(snapshot-parseDate(item.date))/86400000;
          if(age<0 || age>=maxAge) return false;
        }
      }
      if (query && ![item.title,item.summary,item.brand,...item.tags].join(' ').toLocaleLowerCase().includes(query)) return false;
      return true;
    });
    return result.sort((a,b) => {
      if (state.sort === 'latest') {
        return (b.date ? parseDate(b.date).valueOf() : -Infinity) - (a.date ? parseDate(a.date).valueOf() : -Infinity) || a.priority - b.priority;
      }
      if (state.sort === 'deadline') {
        const deadlineA = a.end ? parseDate(a.end).valueOf() : Infinity;
        const deadlineB = b.end ? parseDate(b.end).valueOf() : Infinity;
        return deadlineA - deadlineB || a.priority - b.priority;
      }
      return a.priority - b.priority;
    });
  }
  function renderNavigation() {
    $('#navigation').innerHTML = Object.entries(views).map(([id,view]) => {
      const count = id === 'heat' ? (window.MEDIA_DATA?.sources || []).filter(s=>s.status==='ok').length : id === 'saved' ? stored.selected.length : id === 'overview' ? currentItems().length : currentItems().filter((item) => item.type === id).length;
      return (id === 'saved' ? '<div class="nav-divider"></div>' : '') + '<button class="nav-item' + (state.view === id ? ' active' : '') + '" data-view="' + id + '"' + (state.view === id ? ' aria-current="page"' : '') + '>' + icon(view.icon) + esc(view.label) + '<span class="nav-count">' + count + '</span></button>';
    }).join('');
  }
  function renderStatistics() {
    const closing = new Set(items.filter((item) => item.end && parseDate(item.end) >= snapshot && (parseDate(item.end) - snapshot) <= 3 * 86400000).map(item=>item.parentUrl || item.url)).size;
    const stats = [
      { label:'当前消息', value:currentItems().length, unit:'条', icon:'grid', kicker:'SOURCE INBOX', note:'已采集 · 等待选题筛选' },
      { label:'产品发布动态', value:currentItems().filter((item) => item.type === 'release').length, unit:'条', icon:'box', kicker:'PRODUCT LOGS', note:'产品更新与新功能' },
      { label:'活动与福利', value:currentItems().filter((item) => item.type === 'event').length, unit:'条', icon:'gift', kicker:'ACTIVITIES & GRANTS', note:'开放活动与后续预告' },
      { label:'3 天内活动结束', value:closing, unit:'项', icon:'clock', kicker:'EXPIRING IMMINENT', note:'按当前时间 · 不代表兑换期限' }
    ];
    $('#statistics').innerHTML = stats.map((stat) => '<article class="stat-card"><div class="stat-head"><div><div class="stat-kicker">' + esc(stat.kicker) + '</div><p class="stat-note">' + esc(stat.note) + '</p></div><span class="stat-icon">' + icon(stat.icon) + '</span></div><div class="stat-main"><h2 class="stat-label">' + esc(stat.label) + '</h2><div class="stat-value">' + stat.value + '<small>' + stat.unit + '</small></div></div></article>').join('');
  }
  function renderTabs() {
    $('#tabs').innerHTML = [{id:'all',label:'全部'},{id:'release',label:'产品发布'},{id:'event',label:'活动福利'}].map((tab) => {
      const count = items.filter((item) => (state.view==='saved' ? isSaved(item.id) : state.range==='archive' ? archived(item) : !archived(item)) && (tab.id === 'all' || item.type === tab.id)).length;
      return '<button class="tab' + (state.type === tab.id ? ' active' : '') + '" role="tab" aria-selected="' + (state.type === tab.id) + '" data-type="' + tab.id + '">' + tab.label + '<span class="tab-count">' + count + '</span></button>';
    }).join('');
    $('#categoryFilters').innerHTML = categories.filter((category) => category === '全部' || state.type === 'all' || (state.type === 'event' ? category === '活动福利' : category !== '活动福利')).map((category) => '<button class="filter-chip' + (state.category === category ? ' active' : '') + '" data-category="' + esc(category) + '" aria-pressed="' + (state.category === category) + '">' + esc(category) + '</button>').join('');
  }
  function renderSaveButton(item, detail = false) {
    const saved = isSaved(item.id);
    return '<button class="' + (detail ? 'button ' + (saved ? 'secondary' : 'primary') : 'save-button' + (saved ? ' saved' : '')) + '" data-save="' + item.id + '" aria-pressed="' + saved + '" aria-label="' + (saved ? '移出选题：' : '加入选题：') + esc(item.title) + '">' + icon(saved ? 'check' : 'bookmark') + (saved ? '已加入选题' : '加入选题') + '</button>';
  }
  function stageOptions(id) { return stages.map((stage) => '<option' + ((stored.stages[id] || '待评估') === stage ? ' selected' : '') + '>' + stage + '</option>').join(''); }
  function renderCard(item) {
    const status = eventStatus(item);
    return '<article class="news-card" data-item="' + item.id + '"><div class="news-content"><div class="news-header"><div class="news-meta"><span>' + esc(item.brand) + '</span><span class="meta-dot"></span><span class="type-text">' + (item.type === 'release' ? '产品发布' : '活动福利') + '</span><span class="meta-dot"></span><span>' + esc(item.periodStart ? item.periodStart+' — '+item.periodEnd+'（日期范围）' : item.dateLabel) + '</span></div>' + renderSaveButton(item) + '</div><h3><button class="news-title" data-open="' + item.id + '">' + esc(item.title) + '</button></h3><p class="news-summary">' + esc(item.summary) + '</p><div class="news-footer"><div class="tags">' + (status ? '<span class="tag ' + status.color + '">' + esc(status.label) + '</span>' : '') + item.tags.map((tag) => '<span class="tag">' + esc(tag) + '</span>').join('') + '</div><div class="checked-line">' + esc(item.checked) + '</div></div>' + (state.view === 'saved' ? '<div class="saved-stage"><label for="stage-' + item.id + '">选题进度</label><select id="stage-' + item.id + '" data-stage="' + item.id + '">' + stageOptions(item.id) + '</select><button class="remove-topic" data-save="' + item.id + '">移出清单</button></div>' + (stored.notes[item.id] ? '<p class="saved-note">' + esc(stored.notes[item.id]) + '</p>' : '') : '') + '</div></article>';
  }
  function renderList() {
    const filtered = filterItems();
    $('#resultCount').textContent = filtered.length;
    let caption = '官方事实与选题判断分开呈现 · 点击标题查看详情';
    if (state.range === 'archive') caption = '已结束活动、30 天前产品消息及历史收藏；记录保留供复查。';
    else if (state.range !== 'all') caption = '按发布时间筛选；进行中和时间待核对的活动保留展示。';
    else if (state.sort === 'latest') caption = '按官方发布时间排序；未记录发布时间的活动放在后面。';
    else if (state.sort === 'deadline') caption = '只对已核验精确截止时间的活动排序；日期区间与未公布时间的消息放在后面。';
    else if (state.view === 'saved') caption = '记录角度、核对条件、更新进度 · 清单仅保存在当前浏览器';
    $('#listCaption').textContent = caption;
    if (filtered.length) $('#newsList').innerHTML = filtered.map(renderCard).join('');
    else if (state.view === 'saved' && !stored.selected.length) $('#newsList').innerHTML = '<div class="empty-state">' + icon('bookmark') + '<h3>先留住一个值得做的选题</h3><p>在消息旁点击“加入选题”，就能在这里继续记录。</p><button class="button secondary" data-view="overview">去看消息' + icon('arrow-right') + '</button></div>';
    else $('#newsList').innerHTML = '<div class="empty-state">' + icon('search') + '<h3>这个条件下暂时没有消息</h3><p>试试其他关键词，或放宽筛选范围。</p><button class="button secondary" data-reset>清除筛选</button></div>';
  }
  function renderRail() {
    $('#savedCounter').textContent = stored.selected.length;
    const selected = stored.selected.map((id) => items.find((item) => item.id === id)).filter(Boolean);
    $('#topicPreview').innerHTML = selected.length ? selected.slice(0,3).map((item) => '<button class="topic-mini" data-open="' + item.id + '"><strong>' + esc(item.title) + '</strong><span>' + esc(stored.stages[item.id] || '待评估') + ' · ' + esc(item.format) + '</span></button>').join('') : '<div class="empty-topics">' + icon('bookmark') + '看到合适的消息，先加入选题。<br>角度和笔记可以慢慢补。</div>';
  }
  function render() {
    const view = views[state.view];
    $('#crumb').textContent = view.label;
    $('#pageTitle').innerHTML = esc(view.title) + '<span class="title-dot">.</span>';
    $('#pageSubtitle').textContent = view.subtitle;
    $('#feedTitle').firstChild.textContent = view.feed + ' ';
    $('#features').hidden = state.view !== 'overview';
    $('#statistics').hidden = state.view === 'saved' || state.view === 'heat';
    $('.desk-layout').hidden = state.view === 'heat';
    $('.sync-bar').hidden = state.view === 'heat';
    $('#heatPanel').hidden = state.view !== 'heat';
    if(state.view === 'heat') window.renderHeat?.();
    $('#sort').value = state.sort;
    $('#range').value = state.range;
    snapshot = new Date();
    renderNavigation(); renderStatistics(); renderTabs(); renderList(); renderRail(); renderLive();
  }
  function changeView(view, syncHash = true) {
    if (!views[view]) view = 'overview';
    state.view = view;
    state.type = view === 'release' || view === 'event' ? view : 'all';
    state.category = '全部';
    state.query = '';
    state.range = 'all';
    state.sort = view === 'release' ? 'latest' : view === 'event' ? 'deadline' : 'priority';
    $('#search').value = '';
    if (syncHash && location.hash !== '#' + view) history.replaceState(null,'','#' + view);
    render();
  }
  let currentDetail = null;
  window.saveHeatTopic = (entry) => {
    const previous=items.findIndex(item=>item.id===entry.id);
    if(previous>=0) items[previous]=entry; else items.push(entry);
    validIds.add(entry.id);stored.records[entry.id]=entry;
    if(!stored.selected.includes(entry.id))stored.selected.push(entry.id);
    persist();render();toast('话题已加入选题清单，保留本次媒体来源');
  };
  function openDetail(id) {
    const item = items.find((record) => record.id === id);
    if (!item) return;
    currentDetail = id;
    const status = eventStatus(item);
    $('#detailContent').innerHTML = '<div class="dialog-top"><div><div class="eyebrow">' + esc(item.brand) + ' · ' + esc(item.category) + '</div><h2 id="detailTitle">' + esc(item.title) + '</h2></div><button class="icon-button" data-close="detailDialog" aria-label="关闭消息详情">' + icon('x') + '</button></div><div class="dialog-meta"><span>' + esc(item.periodStart ? item.periodStart+' — '+item.periodEnd+'（日期范围）' : item.dateLabel) + '</span>' + (status ? '<span class="tag ' + status.color + '">' + esc(status.label) + '</span>' : '') + '<span class="tag">' + esc(item.format) + '</span></div><p class="dialog-summary">' + esc(item.summary) + '</p>' + (item.type==='event' ? '<section class="detail-section"><h3>活动时间</h3><p>开始：'+esc(humanTime(item.start))+'</p><p>结束：'+esc(humanTime(item.end))+'</p><p>兑换期限：'+esc(item.redeemEnd ? humanTime(item.redeemEnd) : '未公布，需核对邮件与结算页')+'</p><small>时间显示为新加坡时间（UTC+8）</small></section>' : '') + '<section class="detail-section"><h3>' + icon('verified') + '来源记录</h3><ul>' + item.facts.map((fact) => '<li>' + esc(fact) + '</li>').join('') + '</ul></section><section class="detail-section conditions-section"><h3>' + icon('alert') + '仍需核对</h3><ul>' + item.conditions.map((condition) => '<li>' + esc(condition) + '</li>').join('') + (item.dateBasis ? '<li>' + esc(item.dateBasis) + '</li>' : '') + '</ul></section><section class="detail-section"><h3>' + icon('edit') + '选题参考 · 编辑判断</h3><div class="angle-box">' + esc(item.angle) + '</div><p class="angle-format">建议形式：' + esc(item.format) + '　读者：' + esc(item.audience) + '</p></section><section class="detail-section"><h3>' + icon('globe') + '回到消息来源</h3><div class="source-links">' + item.sources.map((source) => '<a href="' + esc(source.url) + '" target="_blank" rel="noopener noreferrer">' + esc(source.label) + icon('arrow-up-right') + '</a>').join('') + '</div><div class="verified-at">采集时间：' + esc(item.lastChecked || '历史记录') + ' · 发稿前再次核对条件</div></section><section class="note-area"><div class="note-head"><label for="topicNote">我的切入角度</label><select id="detailStage" data-stage="' + item.id + '" aria-label="选题进度">' + stageOptions(item.id) + '</select></div><textarea id="topicNote" maxlength="4000" data-note="' + item.id + '" placeholder="比如：面向刚接触 Cursor 的读者，先说明能获得什么，再讲参与步骤。">' + esc(stored.notes[item.id] || '') + '</textarea><p class="note-tip">' + (storageAvailable ? '笔记随输入保存在当前浏览器；导出时包含已加入清单的选题。' : '当前浏览器未允许保存，笔记仅保留在本次页面中。') + '</p><div class="dialog-actions"><span id="detailSave">' + renderSaveButton(item, true) + '</span><button class="button secondary copy-button" data-copy="' + item.id + '">' + icon('copy') + '复制选题摘要</button></div></section>';
    $('#detailDialog').showModal();
    $('#detailDialog').scrollTop = 0;
  }
  function toggleSave(id) {
    if (!validIds.has(id)) return;
    const removing = isSaved(id);
    if(!removing) stored.records[id]=items.find(item=>item.id===id);
    stored.selected = removing ? stored.selected.filter((value) => value !== id) : [...stored.selected, id];
    persist(); render();
    if ($('#detailDialog').open && currentDetail === id) $('#detailSave').innerHTML = renderSaveButton(items.find((item) => item.id === id), true);
    toast(removing ? '已移出选题；笔记仍保留' : '已加入选题清单');
  }
  function itemMarkdown(item) {
    return '## ' + item.title + '\n\n' + '- 类型：' + (item.type === 'release' ? '产品发布' : '活动福利') + '\n- 时间：' + item.dateLabel + '\n- 进度：' + (stored.stages[item.id] || '待评估') + '\n- 最近采集：' + (item.lastChecked || '历史记录') + '\n\n来源记录：\n' + item.facts.map((fact) => '- ' + fact).join('\n') + '\n\n仍需核对：\n' + item.conditions.map((condition) => '- ' + condition).join('\n') + (item.dateBasis ? '\n- ' + item.dateBasis : '') + '\n\n选题参考（编辑判断）：\n' + item.angle + '\n\n我的笔记：\n' + (stored.notes[item.id] || '未填写') + '\n\n官方来源：\n' + item.sources.map((source) => '- [' + source.label + '](' + source.url + ')').join('\n') + '\n';
  }
  async function copyBrief(id) {
    const item = items.find((record) => record.id === id);
    if (!item) return;
    const value = itemMarkdown(item);
    let copied = false;
    try { await navigator.clipboard.writeText(value); copied = true; } catch {
      const input = document.createElement('textarea');
      input.value = value; input.style.position = 'fixed'; input.style.opacity = '0'; input.setAttribute('readonly','');
      ($('#detailDialog').open ? $('#detailDialog') : document.body).appendChild(input);
      input.select();
      try { copied = document.execCommand('copy'); } catch { copied = false; }
      input.remove();
    }
    toast(copied ? '选题摘要已复制，包含来源与待核对条件' : '未获剪贴板权限，可加入选题后导出清单');
  }
  function exportTopics() {
    if (!stored.selected.length) return toast('先加入一个选题，再导出清单');
    const records = stored.selected.map((id) => items.find((item) => item.id === id)).filter(Boolean);
    const output = '# AI 选题清单\n\n样本核验：' + meta.checkedDate + '\n此清单来自采集记录；抓取成功不代表权益核验完成。选题角度为编辑判断。\n\n' + records.map(itemMarkdown).join('\n---\n\n');
    const url = URL.createObjectURL(new Blob(['\uFEFF' + output], {type:'text/markdown;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url; link.download = 'AI选题清单-' + meta.checkedDate + '.md';
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast('已导出 ' + records.length + ' 个选题');
  }
  function openSources() {
    const sources=state.view==='heat' ? (window.MEDIA_DATA?.sources || []).map(s=>({...s,desc:s.error || '最近采集：'+humanTime(s.checkedAt),state:s.status==='ok'?'读取成功':s.status==='disabled'?'已停用':'读取失败'})) : window.BOARD_SOURCES;
    $('#sourceList').innerHTML = sources.map((source) => '<div class="source-row"><div><strong>' + esc(source.name) + '</strong><p>' + esc(source.desc) + '</p><span class="tag">' + esc(source.state) + '</span></div><a href="' + esc(source.url) + '" target="_blank" rel="noopener noreferrer">来源入口' + icon('arrow-up-right') + '</a></div>').join('');
    $('#sourcesDialog').showModal();
  }
  document.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.view) { changeView(button.dataset.view); window.scrollTo({top:0,behavior:'instant'}); }
    else if (button.dataset.type) {
      if (state.view !== 'saved') state.view = button.dataset.type === 'all' ? 'overview' : button.dataset.type;
      state.type = button.dataset.type; state.category = '全部';
      if (state.view !== 'saved') history.replaceState(null,'','#' + state.view);
      render();
    }
    else if (button.dataset.category) { state.category = button.dataset.category; renderTabs(); renderList(); }
    else if (button.dataset.open) openDetail(button.dataset.open);
    else if (button.dataset.save) toggleSave(button.dataset.save);
    else if (button.dataset.close) $('#' + button.dataset.close).close();
    else if (button.dataset.copy) copyBrief(button.dataset.copy);
    else if (button.hasAttribute('data-reset')) { state.query='';state.category='全部';state.range='all';$('#search').value='';render(); }
  });
  document.addEventListener('input', (event) => {
    if (event.target.id === 'search') { state.query = event.target.value; renderList(); }
    if (event.target.dataset.note) { stored.notes[event.target.dataset.note] = event.target.value; persist(); }
  });
  document.addEventListener('change', (event) => {
    if (event.target.id === 'sort') { state.sort = event.target.value; renderList(); }
    if (event.target.id === 'range') { state.range = event.target.value; renderTabs(); renderList(); }
    if (event.target.dataset.stage) { stored.stages[event.target.dataset.stage] = event.target.value; persist(); renderRail(); if (state.view === 'saved') renderList(); }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === '/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName) && !document.querySelector('dialog[open]')) { event.preventDefault(); $('#search').focus(); }
    if (['ArrowLeft','ArrowRight','Home','End'].includes(event.key) && document.activeElement.matches('[role="tab"]')) {
      const tabs = [...document.querySelectorAll('[role="tab"]')];
      const current = tabs.indexOf(document.activeElement);
      const index = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length-1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      event.preventDefault(); const type = tabs[index].dataset.type; tabs[index].click(); document.querySelector('[data-type="' + type + '"]').focus();
    }
  });
  for (const dialog of document.querySelectorAll('dialog')) dialog.addEventListener('click', (event) => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  $('#detailDialog').addEventListener('close', () => { currentDetail = null; renderList(); });
  $('#sourceButton').addEventListener('click', openSources);
  $('#exportButton').addEventListener('click', exportTopics);
  window.addEventListener('hashchange', () => changeView(location.hash.slice(1), false));

  let apiToken = null;
  let refreshing = false;
  const localMode = location.protocol==='http:' && ['127.0.0.1','localhost'].includes(location.hostname);
  // Published copy (GitHub Pages): data is rebuilt by the scheduled cloud job; there is no refresh endpoint.
  const hostedMode = location.protocol==='https:';
  if(hostedMode) $('.source-policy').textContent='相同链接更新原记录，保留历史版本。失败来源保留上次成功内容并标记；未知期限不猜测。GitHub Actions 每 4 小时自动采集，不依赖本机开机；运行结果和原始记录可在仓库 Actions 查看。';
  const humanTime = value => value ? new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Singapore',hour12:false}) : '未记录';
  // Scheduled-collection health: flag when no successful automatic run within staleAfterHours.
  function scheduleLine(sch) {
    // Older server process without health data: fall back to the plain flag.
    if(!sch) return {stale:false,text:(meta&&meta.scheduled)?'每 4 小时自动采集':'定时采集未开启'};
    if(!sch.enabled) return {stale:false,text:'定时采集未开启'};
    const last=sch.lastSuccess ? '上次自动采集成功：'+humanTime(sch.lastSuccess) : '尚无成功的自动采集';
    const failure=sch.lastRun && sch.lastRun.status==='failed' && sch.lastRun.error ? ' · 最近一次失败：'+sch.lastRun.error : '';
    // A static page must judge freshness against the viewer's clock, not the time it was built.
    const hours=sch.lastSuccess ? (Date.now()-new Date(sch.lastSuccess).getTime())/36e5 : null;
    const stale=hours==null || hours>sch.staleAfterHours;
    if(!stale) return {stale:false,text:(hostedMode?'云端':'')+'每 4 小时自动采集 · '+last+failure};
    const gap=hours==null ? '' : '已 '+Math.floor(hours)+' 小时没有成功，';
    const why=sch.lastRun && sch.lastRun.status==='failed' && sch.lastRun.error ? '最近一次失败：'+sch.lastRun.error : (hostedMode?'请到 GitHub 仓库的 Actions 页面查看运行记录':'可能是电脑睡眠、未登录，或 TUN/代理未就绪');
    return {stale:true,text:'自动采集'+gap+'超过 '+sch.staleAfterHours+' 小时未更新 · '+last+' · '+why};
  }
  function backupLine(sch) {
    const b=sch && sch.backup;
    return b ? '数据库备份：'+b.day.slice(4,6)+'/'+b.day.slice(6)+'（保留 '+b.kept+' 天）' : '数据库备份：暂无';
  }
  function sidebarHealth(sch) {
    return esc(scheduleLine(sch).text)+'<br>'+esc(backupLine(sch));
  }
  function renderLive() {
    const success=meta.sourceSuccess || 0, total=meta.sourceTotal || 0;
    $('#syncStatus').textContent=refreshing ? '正在读取官方来源…' : success+' / '+total+' 个来源采集成功';
    const sch=scheduleLine(meta.schedule);
    $('#syncTime').textContent='最近采集：'+humanTime(meta.snapshot)+'（新加坡时间） · '+((localMode||hostedMode)?sch.text:'本地快照');
    $('.sync-bar').classList.toggle('stale',(localMode||hostedMode)&&sch.stale);
    $('#refreshButton').hidden=hostedMode;
    $('#connectionNote').classList.toggle('stale',sch.stale);
    $('#connectionNote').innerHTML='<span class="small-dot"></span>'+(sch.stale?'自动采集需要检查':'采集已接入')+'<p>'+success+' 个成功 · '+(total-success)+' 个异常<br>'+sidebarHealth(meta.schedule)+'</p>';
    $('.snapshot-date').textContent='LAST SYNC / '+humanTime(meta.snapshot);
    $('.page-footer').lastElementChild.textContent='源文采集与编辑判断分开 · 原文、历史版本及失败记录均已留存';
    $('.rail-foot span').textContent='SOURCE ARCHIVE · '+meta.checkedDate;
    $('#refreshButton').disabled=refreshing;
    $('#refreshButton').textContent=refreshing?'正在刷新…':'刷新消息';
    const featured=currentItems().find(item=>item.type==='event'&&!item.stale) || currentItems()[0];
    $('#features').innerHTML=featured ? '<article class="featured"><div class="feature-content"><div class="feature-copy"><div class="featured-heading"><span class="label warm">优先查看</span><span class="feature-source">'+esc(featured.brand)+'</span></div><h2>'+esc(featured.title)+'</h2><p>'+esc(featured.summary)+'</p><div class="feature-bottom"><button class="button primary" data-open="'+featured.id+'">查看来源与条件'+icon('arrow-right')+'</button><span class="feature-note">选题建议 · 尚未实测</span></div></div><div class="feature-art" aria-hidden="true"><span class="dispatch-kicker">DISPATCH<br>BRIEF</span><strong>SOURCE</strong><span class="dispatch-note">保留原文</span><span class="dispatch-foot">EDITORIAL NOTE</span></div></div></article>' : '';
    const events=currentItems().filter(item=>item.type==='event'&&item.end).sort((a,b)=>parseDate(a.end)-parseDate(b.end));
    const deadlines=[...new Map(events.map(item=>[item.end,item])).values()].slice(0,3);
    $('.dates-card').innerHTML='<div class="section-top">'+icon('calendar')+'<h2>接下来，留意这些时间</h2></div>'+deadlines.map(item=>'<button class="date-item date-action" data-open="'+item.id+'"><span class="date-stamp"><b>'+new Date(item.end).toLocaleString('zh-CN',{day:'2-digit',timeZone:'Asia/Singapore'})+'</b>截止</span><span><strong>'+esc(item.title)+'</strong><p>'+humanTime(item.end)+'（新加坡）</p></span></button>').join('')+(!deadlines.length?'<p>暂无已确认的活动截止时间。</p>':'')+'<div class="dates-foot">活动结束与兑换期限分开核对</div>';
    if(state.view==='heat' && window.MEDIA_DATA){
      const media=window.MEDIA_DATA, good=media.sources.filter(s=>s.status==='ok').length;
      $('.snapshot-date').textContent='MEDIA SYNC / '+humanTime(media.snapshot);
      const msch=scheduleLine(media.schedule);
      $('#connectionNote').classList.toggle('stale',msch.stale);
      $('#connectionNote').innerHTML='<span class="small-dot"></span>'+(msch.stale?'自动采集需要检查':'媒体采集')+'<p>'+good+' 个成功 · '+(media.sources.length-good)+' 个未启用或异常<br>'+sidebarHealth(media.schedule)+'</p>';
    }

  }
  window.addEventListener('media-updated',()=>{renderNavigation();if(state.view==='heat')renderLive();});
  async function readServer() {
    const response=await fetch('/api/board',{cache:'no-store'});
    if(!response.ok) throw new Error('本地服务未响应');
    const data=await response.json();
    items=data.items;meta=data.meta;window.BOARD_SOURCES=data.sources;apiToken=data.token;
    restoreSaved();refreshing=!!data.refresh.running;render();return data;
  }
  async function waitRefresh() {
    while(refreshing) {
      await new Promise(resolve=>setTimeout(resolve,1500));
      const response=await fetch('/api/status',{cache:'no-store'});
      if(!response.ok) throw new Error('采集状态暂时无法读取');
      const job=await response.json();refreshing=job.running;
      if(!refreshing) {
        await readServer();
        toast(job.lastError || '采集完成：'+meta.sourceSuccess+'/'+meta.sourceTotal+' 个来源成功，异常见“信息来源”');
      }
    }
  }
  $('#refreshButton').addEventListener('click',async()=>{
    if(hostedMode) return toast('云端版本每 4 小时自动采集，也可以在 GitHub Actions 页面手动运行一次。');
    if(!localMode) return toast('当前为文件快照。请通过 http://127.0.0.1:8766/ 打开看板后刷新。');
    try {
      if(!apiToken) await readServer();
      const response=await fetch('/api/refresh',{method:'POST',headers:{'X-Board-Token':apiToken}});
      const result=await response.json();
      if(!response.ok) throw new Error(result.error || '刷新未启动');
      refreshing=true;renderLive();await waitRefresh();
    } catch(error) { refreshing=false;renderLive();toast(error.message); }
  });
  hydrateIcons();
  changeView(location.hash.slice(1) || 'overview', false);
  if(localMode) readServer().then(data=>{if(data.refresh.running) waitRefresh().catch(error=>toast(error.message));}).catch(()=>toast('本地服务不可用，正在显示上次保存的采集快照'));
  async function updateHealth() {
    if(hostedMode && !document.hidden) { renderLive(); return; }
    if(!localMode || document.hidden) return;
    try {
      const response=await fetch('/api/status',{cache:'no-store'});
      if(!response.ok) return;
      const data=await response.json();
      if(!data.schedule) return;
      meta.schedule=data.schedule;
      if(window.MEDIA_DATA) window.MEDIA_DATA.schedule=data.schedule;
      renderLive();
    } catch (_) { /* Keep the last recorded status if the local service is unavailable. */ }
  }
  if(localMode || hostedMode) {
    setInterval(updateHealth,60000);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden) updateHealth();});
  }
  if (!storageAvailable) toast('浏览器未允许本机保存，仍可筛选并导出选题');
})();
