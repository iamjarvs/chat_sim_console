let TENANT = { name: "Loading…", initials: "…", environment: "…", host: "…" };
let GPU_COUNT = 8;
let GPU_MODEL = "GPU";

const THINKING_FRAGMENTS = [
  "Parsing the request…",
  "Pulling in relevant recent context…",
  "Weighing a couple of ways to frame this…",
  "Checking this stays consistent with earlier turns…",
  "Drafting a first pass…",
  "Trimming for length and tone…",
  "Double-checking the specifics before answering…",
  "Considering what you'll actually do with this…",
  "Looking for the most useful framing…",
  "Reviewing for clarity…",
  "Making sure nothing here is stale…",
  "Settling on a final phrasing…",
];

const QUESTION_BANK = [
  {
    q: "Summarize this quarter's sales pipeline",
    a: [
      "Pipeline's tracking about 12% ahead of target for the quarter, with most of that upside sitting in mid-market renewals rather than new logos.",
      "Two larger opportunities are still flagged at risk due to procurement delays — worth a check-in with those account owners before the forecast call."
    ]
  },
  {
    q: "Draft a follow-up email to a prospective client",
    a: [
      "Sure — here's a short draft: \"Hi [Name], great speaking with you earlier this week. Following up with the materials we discussed, and happy to set up a deeper session whenever suits your team.\"",
      "Want me to make the tone more formal, or add a specific call-to-action like booking a demo slot?"
    ]
  },
  {
    q: "What are our top churn risks this month?",
    a: [
      "Three accounts are showing reduced usage over the last 30 days, which is usually the earliest signal before a renewal conversation gets difficult.",
      "Support sentiment on two of those has also dipped — worth looping in customer success before the next billing cycle."
    ]
  },
  {
    q: "Give me a recap of yesterday's leadership sync",
    a: [
      "Main themes were headcount planning for next quarter and a proposed change to the new-hire onboarding process.",
      "No firm decisions were made — a follow-up session is expected once finance shares updated budget numbers."
    ]
  },
  {
    q: "Help me outline a project status update for stakeholders",
    a: [
      "Here's a simple structure: what shipped this period, what's slipping and why, key risks, and what you need from stakeholders to keep things moving.",
      "Want me to draft actual bullet points under each section, or leave it as a skeleton to fill in yourself?"
    ]
  }
];

function genericAnswers(){
  return [
    ["I don't have enough context to answer that precisely — try rephrasing, or give me a bit more detail."],
    [
      "Good question, but I don't have a confident answer for that one right now.",
      "Try one of the suggested prompts below — those are the kinds of things I've got solid context for."
    ],
    ["I can help most with day-to-day business questions for **" + TENANT.name + "** — pipeline, email drafts, meeting recaps, that kind of thing. Ask me something along those lines and I'll do better."]
  ];
}

const SEED_CHATS = [
  {
    title: "Q3 pipeline summary",
    meta: "2h ago",
    transcript: [
      { role: "user", text: "Summarize this quarter's sales pipeline" },
      { role: "assistant", answer: QUESTION_BANK[0].a, gpu: 3, thinking: ["Pulling in relevant recent context…", "Weighing a couple of ways to frame this…", "Drafting a first pass…"] }
    ]
  },
  {
    title: "Client follow-up draft",
    meta: "Yesterday",
    transcript: [
      { role: "user", text: "Draft a follow-up email to a prospective client" },
      { role: "assistant", answer: QUESTION_BANK[1].a, gpu: 5, thinking: ["Parsing the request…", "Drafting a first pass…", "Trimming for length and tone…"] }
    ]
  },
  {
    title: "Churn risk check",
    meta: "2 days ago",
    transcript: [
      { role: "user", text: "What are our top churn risks this month?" },
      { role: "assistant", answer: QUESTION_BANK[2].a, gpu: 1, thinking: ["Pulling in relevant recent context…", "Double-checking the specifics before answering…", "Settling on a final phrasing…"] }
    ]
  },
  {
    title: "Leadership sync recap",
    meta: "3 days ago",
    transcript: [
      { role: "user", text: "Give me a recap of yesterday's leadership sync" },
      { role: "assistant", answer: QUESTION_BANK[3].a, gpu: 6, thinking: ["Parsing the request…", "Checking this stays consistent with earlier turns…", "Reviewing for clarity…"] }
    ]
  }
];

let activeChatIndex = null;
let busy = false;

const chatListEl = document.getElementById('chatList');
const chatInnerEl = document.getElementById('chatInner');
const chipRowEl = document.getElementById('chipRow');
const gpuRailEl = document.getElementById('gpuRail');
const gpuStatusLine = document.getElementById('gpuStatusLine');
const gpuStatusSub = document.getElementById('gpuStatusSub');
const composerInput = document.getElementById('composerInput');
const sendBtn = document.getElementById('sendBtn');
const topbarTitle = document.getElementById('topbarTitle');
const topbarHost = document.getElementById('topbarHost');

function initialsFor(name){
  return (name || '').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join('') || '?';
}

async function fetchContext(){
  try{
    const res = await fetch('/api/context');
    if(!res.ok) throw new Error('context request failed: ' + res.status);
    const data = await res.json();
    TENANT = {
      name: data.tenant_name || 'Unknown tenant',
      initials: initialsFor(data.tenant_name),
      environment: data.environment_name || 'Unknown',
      host: data.host_label || 'unknown-host',
    };
    if(data.gpu_count) GPU_COUNT = data.gpu_count;
    if(data.gpu_model) GPU_MODEL = data.gpu_model;
    applyContextToDOM();
  }catch(err){
    console.warn('Could not load /api/context', err);
  }
}

function applyContextToDOM(){
  document.getElementById('tenantAvatar').textContent = TENANT.initials;
  document.getElementById('tenantName').textContent = TENANT.name;
  document.getElementById('tenantHost').textContent = 'Env: ' + TENANT.environment;
  document.getElementById('tenantFootTag').textContent = 'Tenant: ' + TENANT.name + ' · Env: ' + TENANT.environment;
  topbarHost.textContent = TENANT.host;
  gpuStatusSub.textContent = GPU_MODEL + ' · ' + GPU_COUNT + '× GPUs';

  if(gpuRailEl.children.length !== GPU_COUNT){
    buildGPURail();
  }
  const emptyHeading = document.getElementById('emptyHeading');
  if(emptyHeading){
    emptyHeading.textContent = 'Hi ' + TENANT.name + ' — what can I help with?';
  }
}

function buildGPURail(){
  gpuRailEl.innerHTML = '';
  for(let i = 0; i < GPU_COUNT; i++){
    const tile = document.createElement('div');
    tile.className = 'gpu-tile idle';
    tile.title = 'GPU ' + i + ' · ' + GPU_MODEL;
    tile.dataset.index = i;
    gpuRailEl.appendChild(tile);
  }
}
function setActiveGPU(index){
  [...gpuRailEl.children].forEach((t, i) => t.classList.toggle('active', i === index));
  gpuStatusLine.innerHTML = 'Serving inference on <b>GPU ' + index + '</b>';
}
function clearActiveGPU(){
  [...gpuRailEl.children].forEach(t => t.classList.remove('active'));
  gpuStatusLine.textContent = 'Idle';
}
buildGPURail();

function renderChatList(){
  chatListEl.innerHTML = '';
  SEED_CHATS.forEach((c, i) => {
    const btn = document.createElement('button');
    btn.className = 'chat-item' + (i === activeChatIndex ? ' active' : '');
    btn.innerHTML = '<span class="chat-item-title">' + c.title + '</span><span class="chat-item-meta">' + c.meta + '</span>';
    btn.onclick = () => loadSeedChat(i);
    chatListEl.appendChild(btn);
  });
}

function loadSeedChat(i){
  activeChatIndex = i;
  const chat = SEED_CHATS[i];
  topbarTitle.textContent = chat.title;
  chatInnerEl.innerHTML = '';
  renderChatList();
  chat.transcript.forEach(turn => {
    if(turn.role === 'user'){
      appendUserBubble(turn.text);
    }else{
      appendAssistantStatic(turn.answer, turn.thinking);
      setActiveGPU(turn.gpu);
    }
  });
  renderChips();
  scrollToBottom();
}

function startNewChat(){
  activeChatIndex = null;
  topbarTitle.textContent = 'New chat';
  clearActiveGPU();
  renderChatList();
  renderEmptyState();
}

function renderEmptyState(){
  chatInnerEl.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.className = 'empty-state';
  wrap.innerHTML = `
    <svg class="empty-mark" viewBox="0 0 32 32" fill="none">
      <circle cx="16" cy="16" r="12" stroke="#FF3B69" stroke-width="1.6"/>
      <path d="M16 4 C 25 4 25 28 16 28" stroke="#FF3B69" stroke-width="1.6" fill="none"/>
      <circle cx="16" cy="16" r="2.6" fill="#FF3B69"/>
    </svg>
    <h1 id="emptyHeading">Hi ${TENANT.name} — what can I help with?</h1>
    <p>Ask me anything, or try one of the prompts below. Responses are simulated for demo purposes.</p>
    <div class="empty-chip-grid" id="emptyChipGrid"></div>
  `;
  chatInnerEl.appendChild(wrap);
  const grid = wrap.querySelector('#emptyChipGrid');
  QUESTION_BANK.forEach(item => {
    const chip = document.createElement('button');
    chip.className = 'chip';
    chip.textContent = item.q;
    chip.onclick = () => submitMessage(item.q);
    grid.appendChild(chip);
  });
}

function renderChips(){
  chipRowEl.innerHTML = '';
  QUESTION_BANK.forEach(item => {
    const chip = document.createElement('button');
    chip.className = 'chip';
    chip.textContent = item.q;
    chip.onclick = () => submitMessage(item.q);
    chipRowEl.appendChild(chip);
  });
}

function mdToHtml(line){
  return line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function appendUserBubble(text){
  const row = document.createElement('div');
  row.className = 'msg msg-user';
  row.innerHTML = `<div class="msg-body"><div class="msg-bubble">${mdToHtml(text)}</div></div>`;
  chatInnerEl.appendChild(row);
}

function assistantAvatarSVG(){
  return `<svg width="14" height="14" viewBox="0 0 32 32" fill="none">
    <circle cx="16" cy="16" r="12" stroke="#FF3B69" stroke-width="2.4"/>
    <path d="M16 4 C 25 4 25 28 16 28" stroke="#FF3B69" stroke-width="2.4" fill="none"/>
    <circle cx="16" cy="16" r="3" fill="#FF3B69"/>
  </svg>`;
}

function appendAssistantStatic(paragraphs, thinking){
  const row = document.createElement('div');
  row.className = 'msg msg-assistant';
  const p = paragraphs.map(t => '<p>' + mdToHtml(t) + '</p>').join('');
  const lines = (thinking || []).map(t => '<div class="thinking-line" style="opacity:1"><span class="b">›</span><span>' + t + '</span></div>').join('');
  row.innerHTML = `
    <div class="msg-avatar">${assistantAvatarSVG()}</div>
    <div class="msg-body">
      <button class="thinking-toggle"><span class="chev">›</span> Thought for 2s</button>
      <div class="thinking-block" style="display:none">${lines}</div>
      <div class="msg-bubble">${p}</div>
    </div>`;
  chatInnerEl.appendChild(row);

  const toggle = row.querySelector('.thinking-toggle');
  const thinkEl = row.querySelector('.thinking-block');
  toggle.onclick = () => {
    const opening = thinkEl.style.display === 'none';
    thinkEl.style.display = opening ? 'flex' : 'none';
    toggle.classList.toggle('open');
  };
}

function scrollToBottom(){
  const scroller = document.getElementById('chatScroll');
  scroller.scrollTop = scroller.scrollHeight;
}

function pickAnswer(text){
  const hit = QUESTION_BANK.find(item => item.q.toLowerCase() === text.trim().toLowerCase());
  if(hit) return hit.a;
  const lower = text.toLowerCase();
  const kw = QUESTION_BANK.find(item => item.q.toLowerCase().split(' ').some(w => w.length > 4 && lower.includes(w)));
  if(kw) return kw.a;
  const generic = genericAnswers();
  return generic[Math.floor(Math.random() * generic.length)];
}

function sample(arr, n){
  const copy = [...arr];
  const out = [];
  while(out.length < n && copy.length){
    out.push(copy.splice(Math.floor(Math.random() * copy.length), 1)[0]);
  }
  return out;
}

function wait(ms){ return new Promise(r => setTimeout(r, ms)); }

async function submitMessage(text){
  if(busy || !text.trim()) return;
  busy = true;
  sendBtn.disabled = true;
  composerInput.value = '';
  composerInput.style.height = 'auto';

  if(activeChatIndex === null && chatInnerEl.querySelector('.empty-state')){
    chatInnerEl.innerHTML = '';
  }
  activeChatIndex = null;
  renderChatList();
  topbarTitle.textContent = text.length > 42 ? text.slice(0, 42) + '…' : text;

  appendUserBubble(text);
  scrollToBottom();

  const row = document.createElement('div');
  row.className = 'msg msg-assistant';
  row.innerHTML = `
    <div class="msg-avatar">${assistantAvatarSVG()}</div>
    <div class="msg-body">
      <div class="thinking-block" id="think-live"></div>
      <div class="msg-bubble" id="answer-live"></div>
    </div>`;
  chatInnerEl.appendChild(row);
  scrollToBottom();

  const thinkEl = row.querySelector('#think-live');
  const frags = sample(THINKING_FRAGMENTS, 3 + Math.floor(Math.random() * 2));
  const startTime = Date.now();

  for(const frag of frags){
    await wait(420 + Math.random() * 420);
    const line = document.createElement('div');
    line.className = 'thinking-line';
    line.innerHTML = '<span class="b">›</span><span>' + frag + '</span>';
    thinkEl.appendChild(line);
    scrollToBottom();
  }
  await wait(350);

  const gpuIndex = Math.floor(Math.random() * GPU_COUNT);
  setActiveGPU(gpuIndex);
  const routeLine = document.createElement('div');
  routeLine.className = 'thinking-line';
  routeLine.innerHTML = '<span class="b">→</span><span>Routed to <b style="color:var(--good)">GPU ' + gpuIndex + '</b> · ' + GPU_MODEL + '</span>';
  routeLine.style.animationDelay = '0s';
  thinkEl.appendChild(routeLine);
  scrollToBottom();
  await wait(300);

  const elapsedSec = Math.max(1, Math.round((Date.now() - startTime) / 1000));
  const toggle = document.createElement('button');
  toggle.className = 'thinking-toggle';
  toggle.innerHTML = '<span class="chev">›</span> Thought for ' + elapsedSec + 's';
  toggle.onclick = () => {
    const opening = thinkEl.style.display === 'none';
    thinkEl.style.display = opening ? 'flex' : 'none';
    if(opening){
      [...thinkEl.children].forEach(line => {
        line.style.opacity = '1';
        line.style.transform = 'none';
      });
    }
    toggle.classList.toggle('open');
  };
  thinkEl.replaceWith(toggle);
  toggle.insertAdjacentElement('afterend', thinkEl);
  thinkEl.style.display = 'none';

  const answerEl = row.querySelector('#answer-live');
  const paragraphs = pickAnswer(text);
  for(const para of paragraphs){
    const pEl = document.createElement('p');
    answerEl.appendChild(pEl);
    const words = mdToHtml(para).split(' ');
    const cursor = document.createElement('span');
    cursor.className = 'msg-cursor';
    for(let i = 0; i < words.length; i++){
      pEl.innerHTML = words.slice(0, i + 1).join(' ');
      pEl.appendChild(cursor);
      scrollToBottom();
      await wait(28 + Math.random() * 35);
    }
    cursor.remove();
  }

  busy = false;
  updateSendState();
  scrollToBottom();
}

function updateSendState(){
  sendBtn.disabled = busy || !composerInput.value.trim();
}

composerInput.addEventListener('input', () => {
  composerInput.style.height = 'auto';
  composerInput.style.height = Math.min(140, composerInput.scrollHeight) + 'px';
  updateSendState();
});
composerInput.addEventListener('keydown', (e) => {
  if(e.key === 'Enter' && !e.shiftKey){
    e.preventDefault();
    if(!sendBtn.disabled) submitMessage(composerInput.value);
  }
});
sendBtn.addEventListener('click', () => submitMessage(composerInput.value));
document.getElementById('newChatBtn').addEventListener('click', startNewChat);

renderChatList();
renderChips();
renderEmptyState();
fetchContext();
setInterval(fetchContext, 60000);
