// Configuration
const API_BASE = 'http://localhost:3000';

//global state tracking
let currentGoal = 'caption';
let businessName = '';
let businessId = '';

//saved results to show in history table
const savedRecs = {};

//result currently shown on screen 
let currentPayload = null;

// Navigation
function switchTab(tabId) {
  const panels = document.querySelectorAll('.view-panel');
  panels.forEach(p => p.classList.remove('active'));

  const menuItems = document.querySelectorAll('.menu-item');
  menuItems.forEach(item => item.classList.remove('active'));

  const targetPanel = document.getElementById(`view-${tabId}`);
  if (targetPanel) {
    targetPanel.classList.add('active');
  }

  //breadcrumb update
  const breadcrumb = document.getElementById('headerBreadcrumb');
  if (breadcrumb) {
    let titleMap = {
      'dashboard': 'Dashboard',
      'new-request': 'New request',
      'history': 'History',
      'profile': 'Business profile'
    };
    breadcrumb.innerHTML = `Workspace / <span>${titleMap[tabId] || tabId}</span>`;
  }

  //to highlight active menu
  const menuMap = {
    'dashboard': 0,
    'new-request': 1,
    'history': 2,
    'profile': 3
  };
  if (menuMap[tabId] !== undefined && menuItems[menuMap[tabId]]) {
    menuItems[menuMap[tabId]].classList.add('active');
  }
}

//new request from goal
function startNewRequest(goalType) {
  selectGoalCard(goalType);
  switchTab('new-request');
  hideAllStates();
  document.getElementById('requestResultSection').classList.add('hidden');
}

//goal card for new request
function selectGoalCard(goalType) {
  const previousGoal = currentGoal;
  currentGoal = goalType;

  const cards = document.querySelectorAll('.goal-card');
  cards.forEach(c => { c.classList.remove('active'); c.setAttribute('aria-pressed', 'false'); });

  const selectedCard = document.getElementById(`goal-${goalType}`);
  if (selectedCard) {
  selectedCard.classList.add('active');
  selectedCard.setAttribute('aria-pressed', 'true');
  }

 //prompt change based on goal type
  const promptInput = document.getElementById('userPrompt');
  if (promptInput) {
  
    if (goalType !== previousGoal) {
      promptInput.value = '';
      renderSuggestedPrompts([]);
    }

    const who = businessName || 'your business';
    if (goalType === 'caption') {
      promptInput.placeholder = `e.g. Create an Instagram caption for ${who} autumn collection.`;
    } else if (goalType === 'promo') {
      promptInput.placeholder = `e.g. Create a promotional campaign for ${who} 20% off weekend special.`;
    } else if (goalType === 'stock') {
      promptInput.placeholder = `e.g. Generate a stock update post for ${who} freshly restocked bestsellers.`;
    }

    updateCharCount(promptInput);
  }
}

//to update char count
function updateCharCount(textarea) {
  const countSpan = document.getElementById('charNum');
  if (countSpan && textarea) {
    countSpan.innerText = textarea.value.length;
  }
}


// Backend calls

async function checkBackend() {
  const pill = document.querySelector('.status-pill');
  if (!pill) return;
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(4000) });
    if (!res.ok) throw new Error('bad status');
    pill.textContent = 'Backend connected';
    pill.classList.add('status-connected');
    pill.style.background = '';
    pill.style.color = '';
  } catch (e) {
    pill.textContent = 'Backend offline';
    pill.classList.remove('status-connected');
    pill.style.background = '#FFEBEE';
    pill.style.color = '#E5484D';
  }
}

async function fetchBusiness(id) {
  let res;
  try {
    res = await fetch(`${API_BASE}/api/business/${encodeURIComponent(id)}`, { signal: AbortSignal.timeout(6000) });
  } catch (e) {
    throw new Error('Backend unreachable');
  }
  let data = null;
  try { data = await res.json(); } catch (e) {}
  if (res.status === 404) {
    const err = new Error(errorText(data) || 'Business not found.');
    err.notFound = true;
    throw err;
  }
  if (!res.ok) throw new Error(errorText(data) || `The backend returned status ${res.status}.`);
  return data;
}

function updateBusinessNotice() {
  const box = document.getElementById('noBusinessNotice');
  if (box) box.classList.toggle('hidden', !!businessId);
}

//readable error text from a backend error body
function errorText(data) {
  if (!data) return '';
  if (typeof data.message === 'string' && data.message) return data.message;
  if (typeof data.detail === 'string' && data.detail) return data.detail;
  return '';
}

// POST 
async function callAgent(request) {
  let response;
  try {
    response = await fetch(`${API_BASE}/api/agent/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ businessId, request }),
      signal: AbortSignal.timeout(210000) // backend allows the AI service 200s
    });
  } catch (e) {
    throw new Error(`Could not reach the backend at ${API_BASE}. Is it running (node index.js)?`);
  }

  let data = null;
  try {
    data = await response.json();
  } catch (e) {
    // body wasn't JSON so, handled below
  }

  if (!response.ok) {
    throw new Error(errorText(data) || `The backend returned status ${response.status}.`);
  }
  const status = data ? String(data.status || '').toLowerCase() : '';
  if (data && (data.success === false || ['error', 'failed', 'failure'].includes(status))) {
    throw new Error(errorText(data) || 'The backend returned an error.');
  }
  return data || {};
}

//turn value from the backend into readable text
function valueToText(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v.map(valueToText).filter(Boolean).join(', ');
  if (typeof v === 'object') {
    const named = v.message || v.warning || v.reason || v.question || v.name || v.field || v.title || v.detail || v.text || v.description;
    return valueToText(named) || JSON.stringify(v);
  }
  return String(v);
}

function mergeWarnings(...lists) {
  const seen = new Set();
  return lists
    .flatMap(l => (l || []).map(valueToText).filter(Boolean))
    .filter(w => !seen.has(w) && seen.add(w));
}

//backend contract istype and content
//warnings, data_gaps, questions_for_owner, limitations
function normalizeResult(data) {
  data = data || {};
  const typeMap = { caption: 'GENERATED CAPTION', promo: 'PROMO CAMPAIGN', stock: 'STOCK UPDATE' };
  const subheadMap = { caption: 'Social caption', promo: 'Promo campaign', stock: 'Stock update' };
  const asList = v => Array.isArray(v) ? v : (v ? [v] : []);


  const recommendations = asList(data.recommendations)
    .map(r => {
      const rec = (typeof r === 'string') ? { content: r } : (r || {});
      return {
        type: typeMap[rec.type] || typeMap[currentGoal] || 'RECOMMENDATION',
        content: typeof rec.content === 'string'
         ? rec.content.trim()
         : typeof rec.draft === 'string'
         ? rec.draft.trim()
          : '',
        warnings: asList(rec.warnings),
        evidence: rec.evidence !== undefined ? rec.evidence : null,
        confidence: rec.confidence !== undefined ? rec.confidence : null
      };
    })
    .filter(r => r.content);

  return {
    status: typeof data.status === 'string' ? data.status : '',
    createdAt: Date.now(),
    recommendations,
    active: 0,
    //cause no title in the contract
    historyTitle: `${subheadMap[currentGoal] || 'Recommendation'} · ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`,
    goalLabel: subheadMap[currentGoal] || 'Recommendation',
    subhead: `A draft for ${businessName || 'your business'} • ${subheadMap[currentGoal] || 'Recommendation'}`,
    mock: !!data.mock,
    warnings: asList(data.warnings),
    allWarnings: mergeWarnings(asList(data.warnings), ...recommendations.map(r => r.warnings)),
    dataGaps: asList(data.data_gaps),
    questions: asList(data.questions_for_owner),
    limitations: asList(data.limitations),
    hashtags: asList(data.hashtags)
      .map(h => valueToText(h).trim().replace(/^#+/, '').replace(/\s+/g, ''))
      .filter(Boolean)
      .map(h => '#' + h),
    suggestedPrompts: asList(data.suggested_prompts).map(s => valueToText(s).trim()).filter(Boolean),
    tips: asList(data.tips)
      .map(t => (typeof t === 'string')
        ? { title: '', content: t.trim() }
        : { title: valueToText(t && t.title).trim(), content: valueToText(t && t.content).trim() })
      .filter(t => t.title || t.content),
    evidence: data.evidence !== undefined ? data.evidence : null,
    confidence: data.confidence !== undefined ? data.confidence : null
  };
}


// Request execution

async function submitRecommendationRequest() {
  const btn = document.getElementById('generateBtn');
  if (btn && btn.disabled) return; 
  if (!businessId) {
    showState('error', 'No business is selected. Open Business profile, enter a Business ID and click Save profile.', true);
    return;
  }

  const userPrompt = document.getElementById('userPrompt').value;
  const targetAudience = document.getElementById('targetAudience').value.trim();

  if (!userPrompt.trim()) {
    alert('Please enter a prompt request before generating.');
    return;
  }

  hideAllStates();
  document.getElementById('requestResultSection').classList.add('hidden');

  const loader = document.getElementById('inContextLoader');
  loader.classList.remove('hidden');
  resetLoadingStages();
  const btnLabel = btn ? btn.textContent : '';
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Generating…';
  }

  try {
    const requestText = targetAudience
      ? `${userPrompt} (Audience: ${targetAudience})`
      : userPrompt;

    //start request and display stages
    const requestPromise = callAgent(requestText);
    requestPromise.catch(() => {});

    setLoadingProgress(25, 'stage-step-1');
    await sleep(600);
    setLoadingProgress(50, 'stage-step-2');
    await sleep(800);
    setLoadingProgress(75, 'stage-step-3');

    //wait for backend
    const data = await requestPromise;

    setLoadingProgress(100, 'stage-step-4');
    await sleep(400);

    const payload = normalizeResult(data);

    loader.classList.add('hidden');
    showResult(payload);
  } catch (error) {
    console.error('Error in request execution:', error);
    loader.classList.add('hidden');
    showState('error', error.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = btnLabel;
    }
  }
}

//decide what to show for a finished request
function showResult(payload) {
  hideAllStates();
  renderSuggestedPrompts(payload.suggestedPrompts);
  renderTips(payload.tips);
  renderLatestNotes(payload);

  
  if (payload.recommendations.length === 0) {
    showEmptyState(payload);
    return;
  }

 
  const hasGaps = payload.dataGaps.length > 0;
  renderInContextResult(payload, !hasGaps);
  logToHistory(payload);
  if (hasGaps) showDataGapWarning(payload.dataGaps);
}

function showEmptyState(payload) {
  document.getElementById('requestResultSection').classList.add('hidden');

  const notes = [
    ...payload.dataGaps.map(g => `Missing data: ${valueToText(g)}`),
    ...payload.limitations.map(valueToText),
    ...payload.questions.map(q => `Question for you: ${valueToText(q)}`)
  ].filter(Boolean);
  fillList('emptyStateList', notes);

  const box = document.getElementById('emptyRecsState');
  if (box) {
    box.classList.remove('hidden');
    box.scrollIntoView({ behavior: 'smooth' });
  } else {
    showState('error', 'No recommendations are available for this request.');
  }
}

//listing the data gaps
function showDataGapWarning(gaps) {
  fillList('missingDataList', gaps.map(valueToText).filter(Boolean));
  const box = document.getElementById('missingDataState');
  if (box) {
    box.classList.remove('hidden');
    box.scrollIntoView({ behavior: 'smooth' });
  }
}

function fillList(id, items) {
  const ul = document.getElementById(id);
  if (!ul) return;
  ul.innerHTML = '';
  items.forEach(text => {
    const li = document.createElement('li');
    li.textContent = text;
    ul.appendChild(li);
  });
  ul.classList.toggle('hidden', items.length === 0);
}

//to go back without clearing 
function editPrompt() {
  hideAllStates();
  const prompt = document.getElementById('userPrompt');
  if (prompt) {
    prompt.scrollIntoView({ behavior: 'smooth', block: 'center' });
    prompt.focus();
  }
}

function renderRecWarnings(warnings) {
  const box = document.getElementById('resRecWarnings');
  if (!box) return;
  box.innerHTML = '';
  const items = mergeWarnings(warnings);
  box.classList.toggle('hidden', items.length === 0);
  items.forEach(w => {
    const p = document.createElement('p');
    p.className = 'rec-warning';
    p.textContent = '⚠ ' + w;
    box.appendChild(p);
  });
}

//result which belongs to one recommendation
function paintRecommendation(data) {
  const rec = (data.recommendations && data.recommendations[data.active || 0]) || { type: '', content: '' };
  document.getElementById('resTypeLabel').innerText = rec.type;
  document.getElementById('resContent').innerText = rec.content;

  renderOptions(data);
  renderWarnings(mergeWarnings(data.warnings, rec.warnings));
  renderRecWarnings(rec.warnings);
  renderEvidence(rec.evidence != null ? rec.evidence : data.evidence);
  renderConfidence(rec.confidence != null ? rec.confidence : data.confidence, data.mock);
}

//for when the backend returns several recommendations
function renderOptions(data) {
  const box = document.getElementById('resOptions');
  if (!box) return;
  box.innerHTML = '';

  const recs = data.recommendations || [];
  box.classList.toggle('hidden', recs.length < 2);
  if (recs.length < 2) return;

  recs.forEach((r, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'option-pill' + (i === (data.active || 0) ? ' active' : '');
    b.textContent = `Option ${i + 1}`;
    b.addEventListener('click', () => {
      data.active = i;
      stopEditing();
      paintRecommendation(data);
    });
    box.appendChild(b);
  });
}

function evidenceEntries(evidence) {
  if (Array.isArray(evidence)) {
    return evidence.map((e, i) => {
      if (e && typeof e === 'object' && !Array.isArray(e)) {
        const label = valueToText(e.title || e.name || e.source || e.field) || `Evidence ${i + 1}`;
        const detail = valueToText(e.detail ?? e.description ?? e.text ?? e.message ?? e.value) || JSON.stringify(e);
        return [label, detail];
      }
      return [`Evidence ${i + 1}`, valueToText(e)];
    });
  }
  if (evidence && typeof evidence === 'object') {
    return Object.entries(evidence).map(([key, value]) => [key.replace(/_/g, ' '), valueToText(value)]);
  }
  if (typeof evidence === 'string' && evidence.trim()) return [['Evidence', evidence.trim()]];
  return [];
}

function renderEvidence(evidence) {
  const list = document.getElementById('resEvidenceList');
  if (!list) return;
  list.innerHTML = '';

  const entries = evidenceEntries(evidence).filter(([label, detail]) => label || detail);
  if (entries.length === 0) {
    const p = document.createElement('p');
    p.className = 'subtext';
    p.textContent = 'No evidence was returned for this recommendation.';
    list.appendChild(p);
    return;
  }

  entries.forEach(([label, detail]) => {
    const row = document.createElement('div');
    row.className = 'evidence-row';

    const check = document.createElement('div');
    check.className = 'check-circle';
    check.textContent = '✓';

    const body = document.createElement('div');
    const strong = document.createElement('strong');
    strong.textContent = label;
    const p = document.createElement('p');
    p.className = 'evidence-detail';
    p.textContent = detail;
    body.append(strong, p);

    row.append(check, body);
    list.appendChild(row);
  });
}

//limitations and mock data note
function renderNote(data) {
  const note = document.getElementById('resEvidenceNote');
  if (!note) return;
  const parts = [];
  if (data.mock) parts.push('Sample response: no real business data was used.');
  const limits = (data.limitations || []).map(valueToText).filter(Boolean);
  if (limits.length) parts.push(`Limitations: ${limits.join(' · ')}`);
  note.textContent = parts.join(' ');
}

function renderWarnings(warnings) {
  const box = document.getElementById('resWarningsList');
  if (!box) return;
  box.innerHTML = '';

  const items = (warnings || []).map(valueToText).filter(Boolean);

  const add = (title, detail, withDivider) => {
    if (withDivider) {
      const d = document.createElement('div');
      d.className = 'divider-line';
      box.appendChild(d);
    }
    const item = document.createElement('div');
    item.className = 'warning-item';
    const strong = document.createElement('strong');
    strong.textContent = title;
    item.appendChild(strong);
    if (detail) {
      const p = document.createElement('p');
      p.textContent = detail;
      item.appendChild(p);
    }
    box.appendChild(item);
  };

  if (items.length === 0) {
    add('No warnings returned', 'Still review pricing, hours and offer terms before posting.', false);
  } else {
    items.forEach((w, i) => add('! ' + w, '', i > 0));
  }
}

function renderGaps(gaps) {
  const pills = document.getElementById('resGapPills');
  const sub = document.getElementById('resGapsSubtext');
  if (!pills) return;
  pills.innerHTML = '';

  const items = (gaps || []).map(valueToText).filter(Boolean);
  if (items.length === 0) {
    if (sub) sub.textContent = 'No data gaps reported.';
    return;
  }
  if (sub) sub.textContent = "Data the assistant couldn't use:";
  items.forEach(g => {
    const span = document.createElement('span');
    span.className = 'gap-pill';
    span.textContent = g;
    pills.appendChild(span);
  });
}

function renderQuestions(questions) {
  const card = document.getElementById('resQuestionsCard');
  const list = document.getElementById('resQuestionsList');
  if (!card || !list) return;
  list.innerHTML = '';

  const items = (questions || []).map(valueToText).filter(Boolean);
  card.classList.toggle('hidden', items.length === 0);
  items.forEach(q => {
    const p = document.createElement('p');
    p.className = 'question-item';
    p.textContent = q;
    list.appendChild(p);
  });
}

function renderConfidence(confidence, mock) {
  const text = document.getElementById('resConfidenceText');
  const bar = document.getElementById('resConfidenceBar');
  const fill = document.getElementById('resConfidenceFill');
  if (!text) return;

  let c = confidence;
  if (typeof c === 'string' && c.trim() !== '' && !isNaN(Number(c))) c = Number(c);

  if (typeof c === 'string' && c.trim() && !mock) {
    text.textContent = c.trim();
    if (bar) bar.classList.add('hidden');
    return;
  }
  if (typeof c !== 'number' || mock) {
    text.textContent = 'Not provided';
    if (bar) bar.classList.add('hidden');
    return;
  }
  //accepts 0-1 or 0-100
  const pct = Math.max(0, Math.min(100, c <= 1 ? c * 100 : c));
  text.textContent = `${Math.round(pct)}%`;
  if (fill) fill.style.width = `${pct}%`;
  if (bar) bar.classList.remove('hidden');
}

//to shows the backend status
function renderStatus(data) {
  const badge = document.getElementById('resStatusBadge');
  if (badge) {
    const raw = (data.status || '').trim();
    const ok = !raw || ['success', 'ok', 'complete', 'completed', 'ready'].includes(raw.toLowerCase());
    badge.textContent = ok ? 'Draft ready' : raw.replace(/[_-]+/g, ' ').replace(/^./, ch => ch.toUpperCase());
    badge.classList.toggle('badge-ready-lg', ok);
    badge.classList.toggle('badge-review-lg', !ok);
  }
  const mockBadge = document.getElementById('mockBadge');
  if (mockBadge) mockBadge.classList.toggle('hidden', !data.mock);
}

function renderInContextResult(data, scroll = true) {
  currentPayload = data;
  stopEditing();

  //to keep title and hashtags empty and hidden when absent
  const titleEl = document.getElementById('resTitle');
  titleEl.innerText = data.title || '';
  titleEl.classList.toggle('hidden', !data.title);

  const tagsEl = document.getElementById('resHashtags');
  const tagsText = Array.isArray(data.hashtags) ? data.hashtags.join(' ') : (data.hashtags || '');
  tagsEl.innerText = tagsText;
  tagsEl.classList.toggle('hidden', !tagsText);

  paintRecommendation(data);
  renderNote(data);
  renderStatus(data);
  renderGaps(data.dataGaps);
  renderQuestions(data.questions);

  document.getElementById('recommendationSubhead').innerText = data.subhead || `A draft for ${businessName || 'your business'}`;

  const resultSection = document.getElementById('requestResultSection');
  resultSection.classList.remove('hidden');
  if (scroll) resultSection.scrollIntoView({ behavior: 'smooth' });
}

function renderSuggestedPrompts(prompts) {
  const block = document.getElementById('promptSuggestionsBlock');
  const box = document.getElementById('promptSuggestions');
  if (!block || !box) return;
  box.innerHTML = '';

  const items = (prompts || []).slice(0, 5);
  block.classList.toggle('hidden', items.length === 0);

  items.forEach(text => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'option-pill';
    b.textContent = text;
    b.addEventListener('click', () => {
      const input = document.getElementById('userPrompt');
      input.value = text.slice(0, 500);
      updateCharCount(input);
      input.focus();
    });
    box.appendChild(b);
  });
}

let defaultTipsHtml = null;

function renderTips(tips) {
  const list = document.getElementById('tipsList');
  if (!list) return;
  if (defaultTipsHtml === null) defaultTipsHtml = list.innerHTML;

  if (!tips || tips.length === 0) {
    list.innerHTML = defaultTipsHtml;
    return;
  }

  list.innerHTML = '';
  tips.slice(0, 5).forEach((t, i) => {
    const item = document.createElement('div');
    item.className = 'tip-item';

    const num = document.createElement('span');
    num.className = 'tip-num';
    num.textContent = String(i + 1).padStart(2, '0');

    const body = document.createElement('div');
    if (t.title) {
      const strong = document.createElement('strong');
      strong.textContent = t.title;
      body.appendChild(strong);
    }
    if (t.content) {
      const p = document.createElement('p');
      p.textContent = t.content;
      body.appendChild(p);
    }

    item.append(num, body);
    list.appendChild(item);
  });
}

let defaultPreNote = null;

function renderLatestNotes(payload) {
  const pre = document.getElementById('preGenNote');
  if (!pre) return;
  if (defaultPreNote === null) defaultPreNote = pre.textContent;

  const items = [
  ...payload.allWarnings,
  ...payload.dataGaps.map(g => `Missing data: ${valueToText(g)}`)
  ].filter(Boolean).slice(0, 3);

  pre.textContent = items.length
    ? `From your last request: ${items.join(' • ')}`
    : defaultPreNote;
}

// History

function historyStatus(payload) {
  if (payload.mock) return { label: 'Demo data', cls: 'badge-demo' };
  const raw = (payload.status || '').toLowerCase();
  const ok = !raw || ['success', 'ok', 'complete', 'completed', 'ready'].includes(raw);
  if (!ok || payload.dataGaps.length > 0 || payload.allWarnings.length > 0) return { label: 'Review', cls: 'badge-review' };
  return { label: 'Ready', cls: 'badge-ready' };
}

function buildHistoryRow(payload, withAction) {
  const title = payload.historyTitle;
  const type = payload.goalLabel;
  const tr = document.createElement('tr');
  const open = () => viewSavedRecommendation(title, type);

  const tdTitle = document.createElement('td');
  const strong = document.createElement('strong');
  strong.textContent = title;
  tdTitle.appendChild(strong);

  const tdType = document.createElement('td');
  tdType.textContent = type;

  const tdWhen = document.createElement('td');
  tdWhen.textContent = new Date(payload.createdAt).toLocaleString([], {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  });

  const status = historyStatus(payload);
  const tdStatus = document.createElement('td');
  const badge = document.createElement('span');
  badge.className = `badge ${status.cls}`;
  badge.textContent = status.label;
  tdStatus.appendChild(badge);

  tr.append(tdTitle, tdType, tdWhen, tdStatus);

  if (withAction) {
    const tdAction = document.createElement('td');
    const btn = document.createElement('button');
    btn.className = 'table-link-btn';
    btn.innerHTML = 'Open &rarr;';
    btn.addEventListener('click', open);
    tdAction.appendChild(btn);
    tr.appendChild(tdAction);
  } else {
    tr.addEventListener('click', open);
    tr.tabIndex = 0;
  }
  return tr;
}

//log new generation into both history tables
function logToHistory(payload) {
  const type = payload.goalLabel;
  savedRecs[`${payload.historyTitle}|${type}`] = payload;

  const dashBody = document.getElementById('dashboardHistoryBody');
  const fullBody = document.getElementById('fullHistoryTableBody');

  if (dashBody) dashBody.prepend(buildHistoryRow(payload, false));
  if (fullBody) fullBody.prepend(buildHistoryRow(payload, true));

  filterHistory();
}

//to open a saved recommendation
function viewSavedRecommendation(title, type) {
  switchTab('new-request');
  hideAllStates();
  document.getElementById('inContextLoader').classList.add('hidden');

  const saved = savedRecs[`${title}|${type}`];
  if (saved) {
    renderInContextResult(saved);
    return;
  }

  //(shoulnt be happening)
  renderInContextResult({
    status: '',
    recommendations: [{
      type: type.toUpperCase(),
      content: `Check out our latest ${title.toLowerCase()} offer at ${businessName || 'our shop'}. Hand-crafted with care and community love!`,
      evidence: null,
      confidence: null
    }],
    active: 0,
    title: title,
    hashtags: '',
    subhead: `A draft for ${businessName || 'your business'} • ${type}`,
    mock: true,
    warnings: [],
    dataGaps: [],
    questions: [],
    limitations: [],
    evidence: null,
    confidence: null
  });
}


// States and loader

function showState(stateType, message, plain = false) {
  hideAllStates();
  document.getElementById('inContextLoader').classList.add('hidden');
  document.getElementById('requestResultSection').classList.add('hidden');

  if (stateType === 'missingData') {
    document.getElementById('missingDataState').classList.remove('hidden');
  } else if (stateType === 'error') {
    const box = document.getElementById('errorRetryState');
    const text = box.querySelector('.state-body-text');
    if (text) {
      text.textContent = plain
        ? message
        : (message
          ? `${message} Your original prompt is saved, so you can try again.`
          : 'Something went wrong while connecting to the AI service. Your original prompt is saved, so you can try again.');
    }
    box.classList.remove('hidden');
  }
}

//clears all states and loader
function hideAllStates() {
  ['missingDataState', 'errorRetryState', 'emptyRecsState'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
  });
}

//progress bar and stage animation
function setLoadingProgress(percent, stageId) {
  const fill = document.getElementById('loadingProgressFill');
  if (fill) fill.style.width = `${percent}%`;

  const current = parseInt(stageId.split('-').pop(), 10);
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`stage-step-${i}`);
    if (!el) continue;
    const icon = el.querySelector('.stage-check-icon');
    if (i < current) {
      el.classList.remove('active');
      el.classList.add('done');
      icon.innerText = '✓';
    } else if (i === current) {
      el.classList.add('active');
      icon.innerText = '✓';
    }
  }
}

function resetLoadingStages() {
  const fill = document.getElementById('loadingProgressFill');
  if (fill) fill.style.width = '0%';

  ['stage-step-1', 'stage-step-2', 'stage-step-3', 'stage-step-4'].forEach((id, idx) => {
    const el = document.getElementById(id);
    if (el) {
      el.classList.remove('active', 'done');
      el.querySelector('.stage-check-icon').innerText = idx + 1;
    }
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function copyCaptionText() {
  const content = document.getElementById('resContent').innerText;
  const tags = document.getElementById('resHashtags').innerText;
  try {
    await navigator.clipboard.writeText(tags.trim() ? `${content}\n\n${tags}` : content);
    alert('Caption copied to clipboard!');
  } catch (e) {
    alert('Could not copy. Please select the text and copy it manually.');
  }
}


// Edit draft

function toggleEditDraft() {
  const body = document.getElementById('resContent');
  const btn = document.getElementById('editDraftBtn');

  //first click
  if (!body.isContentEditable) {
    body.contentEditable = 'true';
    body.classList.add('editing');
    body.focus();
    btn.textContent = 'Save changes';
    return;
  }

  //second click
  const text = body.innerText.trim();
  if (!text) {
    alert('The draft cannot be empty.');
    return;
  }
  body.innerText = text;
  if (currentPayload && currentPayload.recommendations) {
    
    const rec = currentPayload.recommendations[currentPayload.active || 0];
    if (rec) rec.content = text;
  }
  stopEditing();
}

function stopEditing() {
  const body = document.getElementById('resContent');
  const btn = document.getElementById('editDraftBtn');
  if (body) {
    body.contentEditable = 'false';
    body.classList.remove('editing');
  }
  if (btn) btn.textContent = 'Edit draft';
}


//business profile

const PROFILE_KEY = 'marketmateProfile';

function profileValue(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}

async function saveProfile() {
  const profile = {
    name: profileValue('profileName'),
    type: profileValue('profileType'),
    audience: profileValue('profileAudience'),
    voice: profileValue('profileVoice'),
    businessId: profileValue('profileBusinessId'),
  };

  const note = document.getElementById('profileSaveNote');
  let extra = '';

  if (profile.businessId) {
    try {
      const biz = await fetchBusiness(profile.businessId);
      if (biz && biz.name) {
        profile.name = biz.name;
        const nameInput = document.getElementById('profileName');
        if (nameInput) nameInput.value = biz.name;
        extra = ` Business name taken from the backend: ${biz.name}.`;
      }
    } catch (e) {
      if (e.notFound) {
        if (note) note.textContent = `Business ID "${profile.businessId}" was not found on the backend. Check the ID and try again.`;
        return;
      }
      extra = ' The backend could not be reached, so this ID was not checked.';
    }
  }

  try {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    applyProfile(profile);
    if (note) note.textContent = profile.businessId
      ? `Saved in this browser. The Business ID is sent with each request; other profile fields are not sent to the backend yet.${extra}`
      : 'Saved in this browser, but no Business ID is set, so recommendations cannot be generated yet.';
  } catch (e) {
    if (note) note.textContent = 'Could not save: browser storage is unavailable or blocked.';
  }
}


function getInitials(name) {
  const words = (name || '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '';
  if (words.length === 1) return words[0][0].toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function applyAvatar(name) {
  const shown = (name || '').trim();
  businessName = shown;
  selectGoalCard(currentGoal);

  const label = shown || 'User';

  const badge = document.querySelector('.business-badge span');
  if (badge) badge.textContent = label;

  const initials = getInitials(label);
  document.querySelectorAll('.avatar').forEach(el => {
    el.textContent = initials;
  });

  const userName = document.querySelector('.user-name');
  if (userName) userName.textContent = label;

  const greeting = document.getElementById('greetingTitle');
  if (greeting) greeting.textContent = `Hello, ${label}!`;
}

function applyProfile(profile) {
  if (!profile) return;
  businessId = (profile.businessId || '').trim();

  applyAvatar(profile.name);

  //default audience
  const audience = document.getElementById('targetAudience');
  if (audience && profile.audience) audience.value = profile.audience;

  updateBusinessNotice();
}

function loadProfile() {
  let profile = null;
  try {
    profile = JSON.parse(localStorage.getItem(PROFILE_KEY));
  } catch (e) {
    return;
  }
  if (!profile) return;

  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el && typeof value === 'string') el.value = value;
  };
  set('profileName', profile.name);
  set('profileType', profile.type);
  set('profileAudience', profile.audience);
  set('profileVoice', profile.voice);
  set('profileBusinessId', profile.businessId);

  applyProfile(profile);
}

// History filter
function filterHistory() {
  const searchEl = document.getElementById('historySearch');
  const typeEl = document.getElementById('historyTypeFilter');
  const query = (searchEl ? searchEl.value : '').trim().toLowerCase();
  const type = typeEl ? typeEl.value : 'all';

  document.querySelectorAll('#fullHistoryTableBody tr').forEach(row => {
    const cells = row.querySelectorAll('td');
    const title = cells[0] ? cells[0].textContent.toLowerCase() : '';
    const rowType = cells[1] ? cells[1].textContent.toLowerCase() : '';
    const matchesText = !query || title.includes(query) || rowType.includes(query);
    const matchesType = type === 'all' || rowType.includes(type);
    row.classList.toggle('hidden', !(matchesText && matchesType));
  });
}

//popup
function toggleAbout(e) {
  if (e) e.preventDefault();
  const pop = document.getElementById('aboutPopover');
  if (pop) pop.classList.toggle('hidden');
}

function closeAbout() {
  const pop = document.getElementById('aboutPopover');
  if (pop) pop.classList.add('hidden');
}

document.addEventListener('click', e => {
  const pop = document.getElementById('aboutPopover');
  if (!pop || pop.classList.contains('hidden')) return;
  if (!pop.contains(e.target) && !e.target.closest('.help-card')) closeAbout();
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeAbout();
});

//To make clickable cards and dashboard rows reachable
document.querySelectorAll('.action-card, .goal-card, #dashboardHistoryBody tr').forEach(el => {
  el.tabIndex = 0;
  if (!el.matches('tr')) el.setAttribute('role', 'button');
});

document.addEventListener('keydown', e => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const el = e.target.closest('.action-card, .goal-card, #dashboardHistoryBody tr');
  if (!el || e.target !== el) return; // ignore keys pressed on inner buttons/inputs
  e.preventDefault();
  el.click();
});

// Startup

checkBackend();
loadProfile();
updateBusinessNotice();
if (businessId) {
  fetchBusiness(businessId).then(biz => { if (biz && biz.name) applyAvatar(biz.name); }).catch(() => {});
}
selectGoalCard(currentGoal);
