/* Sony Headphones Control Panel - front end. No framework, no network calls
   outside 127.0.0.1. */
'use strict';

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const qs = new URLSearchParams(location.search);

/* ---------------- theme ---------------- */
/* A choice is "explicit" once the user names one (?theme= or the toggle).
   Until then the panel keeps following the OS, including live changes. */
const THEME_KEY = 'shcp.theme';
const mediaDark = window.matchMedia ? matchMedia('(prefers-color-scheme: dark)') : null;
let themeExplicit = false;

function systemTheme(){
  return (mediaDark && mediaDark.matches) ? 'dark' : 'light';
}

function applyTheme(t, remember){
  const theme = (t === 'dark') ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
  if (remember) {
    themeExplicit = true;
    try { localStorage.setItem(THEME_KEY, theme); } catch(e){}
  }
}

/* Picking the theme the system is already using drops the override, so the
   panel resumes following the OS after the user toggles back to it. */
function chooseTheme(t){
  const theme = (t === 'dark') ? 'dark' : 'light';
  if (theme === systemTheme()) {
    themeExplicit = false;
    try { localStorage.removeItem(THEME_KEY); } catch(e){}
    applyTheme(theme, false);
  } else {
    applyTheme(theme, true);
  }
}

(function initTheme(){
  let t = qs.get('theme');
  if (t) { applyTheme(t, true); return; }
  try { t = localStorage.getItem(THEME_KEY); } catch(e){}
  if (t) { applyTheme(t, true); return; }
  applyTheme(systemTheme(), false);
  if (mediaDark) {
    const onChange = (e) => { if (!themeExplicit) applyTheme(e.matches ? 'dark' : 'light', false); };
    if (mediaDark.addEventListener) mediaDark.addEventListener('change', onChange);
    else if (mediaDark.addListener) mediaDark.addListener(onChange);   // old Edge
  }
})();

// The panel shows exactly ONE headset: the one the app actually established an
// MDR session with. There is deliberately no two-device chooser. `device` is
// assigned by /api/context.
let device = 'xm4';
let context = null;
let state = null;
let uiVoice = false;          // v1 has no voice read-back; remember the last write locally

const EQ_V1 = ['off','bright','excited','mellow','relaxed','vocal','treble','bass','speech','custom1','custom2'];
const EQ_V2 = ['off','bright','excited','mellow','relaxed','vocal','treble','bass','speech'];
const EQ_LABEL = {off:'关闭',bright:'明亮',excited:'激昂',mellow:'柔和',relaxed:'轻松',
  vocal:'人声',treble:'高音增强',bass:'低音增强',speech:'语音',
  custom1:'自定义 1',custom2:'自定义 2',custom:'自定义'};
const APO_V1 = [['off','关闭'],['5min','5 分钟'],['30min','30 分钟'],['1h','1 小时'],
  ['3h','3 小时'],['takenoff','取下耳机时']];
const APO_V2 = [['off','关闭'],['takenoff','取下即关']];
const BAND_LABELS = ['低音','1k','2.5k','4k','6.3k','10k'];
const KEY_NAME = {0x10:'volume',0x20:'playback',0x35:'quick_ambient',0xff:'none'};
const KEY_LABEL = {volume:'音量控制',playback:'播放控制',quick_ambient:'快速环境声',none:'无'};

function esc(s){return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

function busy(on, text){
  $('#busyText').textContent = text || '正在与设备通信…';
  $('#busy').classList.toggle('hidden', !on);
}

/* Cheap loading state: a 2 px bar plus dimmed values, so the page is readable
   and scrollable while the radio is still answering. The full-screen overlay
   is reserved for writes, where a stray click would be harmful. */
function progress(on){
  const bar = $('#progress');
  if (bar) bar.classList.toggle('hidden', !on);
  const grid = $('#grid');
  if (grid) grid.classList.toggle('loading', !!on);
}

/* ModelColor suffix -> render file. Keys are the suffixes the headset reports
   in 04 03. No Sony artwork is redistributed with this repository: drop your
   own renders into app/assets/ under these names and colour detection starts
   working immediately. Anything missing falls back to <model>.svg and then to
   the neutral placeholder we do ship. */
const PHOTO_VARIANTS = {
  xm4:    { b: 'xm4', s: 'xm4_s', l: 'xm4_l', w: 'xm4_w' },
  ls900n: { l: 'ls900n', b: 'ls900n_b', w: 'ls900n_w', cream: 'ls900n_cream' },
};

/* Warm the browser cache for both headsets so switching does not flash. */
function preloadPhotos(){
  Object.keys(PHOTO_VARIANTS).forEach(id => {
    const names = [id].concat(Object.values(PHOTO_VARIANTS[id]));
    [...new Set(names)].forEach(n => {
      const im = new Image();
      im.src = '/assets/' + n + '.png';
    });
    const svg = new Image();
    svg.src = '/assets/' + id + '.svg';
  });
}
let toastTimer;
function toast(msg, bad){
  const t = $('#toast');
  t.textContent = msg;
  t.classList.toggle('bad', !!bad);
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(()=>t.classList.remove('show'), 3400);
}
function banner(html, err){
  const b = $('#banner');
  b.innerHTML = html;
  b.classList.toggle('err', !!err);
  b.classList.remove('hidden');
}
function clearBanner(){ $('#banner').classList.add('hidden'); }

async function api(path, body, timeout){
  // A stuck backend used to leave the busy overlay up forever: every request
  // now has a deadline, and the server's `hint` survives to the banner.
  const opt = body ? {method:'POST', headers:{'Content-Type':'application/json'},
                      body:JSON.stringify(body)} : {};
  const ac = new AbortController();
  opt.signal = ac.signal;
  const timer = setTimeout(() => ac.abort(), timeout || 8000);
  try {
    const r = await fetch(path, opt);
    const j = await r.json();
    if (j.ok === false) {
      const err = new Error(j.error || '请求失败');
      if (j.hint) err.hint = j.hint;
      throw err;
    }
    return j;
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('请求超时：后端无响应');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/* ---------------- single-device identity ---------------- */
function renderDevice(ctx){
  context = ctx;
  device = ctx.device.id;
  const d = ctx.device;
  const live = ctx.status === 'connected';
  $('#devbadge').innerHTML =
    `<span class="devbadge-dot ${ctx.status}"></span>` +
    `<div class="devbadge-text"><b>${esc(d.name)}</b>` +
    `<small>MDR ${esc(d.protocol.toUpperCase())} · ${esc(d.mac)}` +
    `${live ? ' · 已连接' : ' · 未连接'}</small></div>`;
  $('#btnSwitch').classList.toggle('hidden', !(ctx.alternatives > 0));
  $('#btnSwitch').title = ctx.alternatives > 0
    ? '切换到另一副已连接的耳机' : '当前只检测到这一副耳机';
  setPhoto(device, ctx.color);
}

function photoCandidates(id, color){
  // The headset reports its own ModelColor in 04 03; map it to the matching
  // render. A colourway we have no render for is probed as <id>_<suffix>.png,
  // then everything falls back to the default render, the traced SVG and
  // finally the neutral placeholder.
  const table = PHOTO_VARIANTS[id] || {};
  const sfx = color && color.suffix;
  const list = [];
  const variant = sfx ? (table[sfx] || (id + '_' + sfx)) : null;
  if (variant) list.push('/assets/' + variant + '.png');
  if (list.indexOf('/assets/' + id + '.png') < 0) list.push('/assets/' + id + '.png');
  list.push('/assets/' + id + '.svg', '/assets/placeholder.svg');
  return list;
}

function setPhoto(id, color){
  const img = $('#devPhoto');
  const cands = photoCandidates(id, color);
  let i = 0;
  img.classList.remove('hidden');
  img.onerror = () => {
    i += 1;
    if (i < cands.length) img.src = cands[i];
    else img.classList.add('hidden');
  };
  img.src = cands[0];
}

async function loadContext(force, quiet){
  const p = new URLSearchParams();
  if (force) p.set('force', '1');
  if (quiet) p.set('quiet', '1');
  const j = await api('/api/context?' + p.toString());
  const changed = device !== j.device.id;
  renderDevice(j);
  return changed;
}

/* ---------------- status ---------------- */
let statusInFlight = false;
async function loadStatus(fresh){
  // The 20 s poll and a manual refresh can collide on a single RFCOMM link;
  // queueing them only doubles the latency, so a second call is dropped.
  if (statusInFlight) return;
  statusInFlight = true;
  progress(true);
  try {
    const q = `device=${encodeURIComponent(device)}` + (fresh ? '&fresh=1' : '');
    const j = await api(`/api/status?${q}`, null, 25000);
    state = j.state;
    clearBanner();
    render();
  } catch (e) {
    const hint = e.hint ? ' ' + esc(e.hint) : '';
    banner(`<b>设备未连接。</b> ${esc(e.message)}${hint}` +
           ` <button class="btn small" id="bannerRetry">重试</button>`, true);
    const btn = $('#bannerRetry');
    if (btn) btn.onclick = () => loadStatus(true);
    toast(e.message, true);
  } finally {
    statusInFlight = false;
    progress(false);
    busy(false);
    loadLog();
  }
}

/* ---------------- render ---------------- */
function has(cap){ return state && state.caps.indexOf(cap) >= 0; }
function hasVal(v){ return v !== null && v !== undefined; }

function render(){
  if (!state) return;
  const s = state, v1 = s.protocol === 'v1';

  // connection badge
  const dot = $('#dot');
  dot.className = 'dot ' + (s.connected ? 'on' : 'off');
  $('#conntext').textContent = s.connected ? '已连接' : '未连接';

  // overview
  $('#ov-sub').textContent = s.name + ' · ' + s.mac;
  $('#ov-proto').textContent = 'MDR ' + s.protocol.toUpperCase();
  const bm = hasVal(s.battery.main) ? s.battery.main : null;
  $('#bat-main').textContent = bm === null ? '--' : bm;
  const bar = $('#bat-bar');
  bar.style.width = (bm === null ? 0 : bm) + '%';
  bar.classList.toggle('low', bm !== null && bm < 20);
  const bd = [];
  if (hasVal(s.battery.left)) bd.push('左 ' + s.battery.left + '%');
  if (hasVal(s.battery.right)) bd.push('右 ' + s.battery.right + '%');
  if (hasVal(s.battery.case)) bd.push('充电盒 ' + s.battery.case + '%');
  $('#bat-detail').textContent = bd.join(' · ') || (v1 ? '头戴式 · 单电池' : '');
  const kv = [['型号', s.info.model], ['固件版本', s.info.firmware],
              ['当前编解码', s.info.codec]];
  if (s.info.color) {
    kv.push(['机身颜色', s.info.color.label + ' · ' + s.info.color.enum]);
    kv.push(['颜色指令', s.info.color.instruction]);
    if (s.info.color.series_name) kv.push(['产品系列', s.info.color.series_name]);
  } else if (s.info.series) {
    kv.push(['系列 / 颜色', s.info.series]);
  }
  kv.push(['协议', 'MDR ' + s.protocol.toUpperCase()]);
  $('#ov-kv').innerHTML = kv.map(([k,v]) =>
    `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
  $('#macInput').value = s.mac;

  // ANC
  $$('#ancseg button').forEach(b =>
    b.classList.toggle('active', b.dataset.value === s.anc.mode));
  $('#levelRange').value = s.anc.level;
  $('#levelVal').textContent = s.anc.level;
  $('#focusSw').checked = !!s.anc.focus;
  $('.cap-wind').classList.toggle('hidden', !has('wind'));

  // EQ
  const eqList = v1 ? EQ_V1 : EQ_V2;
  const curPreset = eqList.indexOf(s.eq.preset) >= 0 ? s.eq.preset : 'custom';
  $('#eqPreset').innerHTML = eqList.map(k =>
    `<option value="${k}">${esc(EQ_LABEL[k]||k)}</option>`).join('') +
    (curPreset === 'custom' ? '<option value="custom">自定义</option>' : '');
  $('#eqPreset').value = curPreset;
  $('#eqPresetLabel').textContent = EQ_LABEL[curPreset] || curPreset;
  $('#eqbands').innerHTML = s.eq.bands.map((v,i) =>
    `<div class="eqband">
       <div class="vslider"><input type="range" min="-10" max="10" step="1" value="${v}" data-band="${i}"></div>
       <span class="vval" data-bandval="${i}">${v>0?'+':''}${v}</span>
       <span class="vlabel">${BAND_LABELS[i]}</span>
     </div>`).join('');
  $$('.vslider input').forEach(inp => inp.addEventListener('input', () => {
    const i = inp.dataset.band;
    const n = Number(inp.value);
    $(`[data-bandval="${i}"]`).textContent = (n>0?'+':'') + n;
  }));

  // sound
  $('#dseeSw').checked = !!s.sound.dsee;
  $('#qualitySel').value = s.sound.quality === 'stable' ? 'stable' : 'hifi';
  $('#voiceHint').textContent = v1 ? 'v1 无读回 · 仅写入，请用 App 确认' : 'Table#2 · 00 = 开';
  $('#voiceSw').checked = v1 ? uiVoice : !!s.sound.voice;

  // system
  $('#stcLabel').textContent = v1 ? '智能免摘' : '智能对话';
  $('#stcSw').checked = !!s.system.stc;
  $$('.cap-stcext').forEach(e=>e.classList.toggle('hidden', !has('stc_ext')));
  $('#sensSel').value = s.system.stc_ext.sensitivity || 'auto';
  $('#offSel').value = s.system.stc_ext.off_time || 'mid';
  const apoList = has('apo_full') ? APO_V1 : APO_V2;
  $('#apoSel').innerHTML = apoList.map(([k,n]) =>
    `<option value="${k}">${esc(n)}</option>`).join('');
  $('#apoSel').value = s.system.apo;
  $$('.cap-pause').forEach(e=>e.classList.toggle('hidden', !has('pause')));
  $$('.cap-touch').forEach(e=>e.classList.toggle('hidden', !has('touch')));
  $('#pauseSw').checked = !!s.system.pause;
  $('#touchSw').checked = !!s.system.touch;
  $('#multiSw').checked = !!s.system.multipoint;
  $('#multiSw').disabled = !!s.system.multipoint_ro;
  $('#multiRow').classList.toggle('readonly', !!s.system.multipoint_ro);
  $('#multiHint').textContent = s.system.multipoint_ro
    ? '只读 · 设备拒绝写入' : (v1 ? '写入后链路会断开重连' : '同时连接两台设备');
  $$('.cap-keys').forEach(e=>e.classList.toggle('hidden', !has('keys')));
  const keyOpts = Object.entries(KEY_LABEL).map(([k,n]) =>
    `<option value="${k}">${esc(n)}</option>`).join('');
  $('#keyLeft').innerHTML = keyOpts;
  $('#keyRight').innerHTML = keyOpts;
  const lk = KEY_NAME[s.system.keys.left] || 'none';
  const rk = KEY_NAME[s.system.keys.right] || 'none';
  $('#keyLeft').value = lk; $('#keyRight').value = rk;
}

/* ---------------- actions ---------------- */
let acting = false;
async function act(action, value, text){
  if (acting || !state) return;
  acting = true;
  busy(true, text || '正在写入并读回…');
  try {
    const j = await api('/api/action', {device, action, value});
    if (action === 'voice' && state.protocol === 'v1') uiVoice = !!value;
    if (j.state) state = j.state;
    if (j.reconnect) {
      banner('<b>设备正在断开重连。</b> 等待约 6 秒后点右上角「↻ 刷新」读取真实状态。', false);
    }
    toast(j.message || '完成');
    render();
  } catch (e) {
    toast(e.message, true);
    render();
  } finally {
    acting = false;
    busy(false);
    loadLog();
  }
}

/* ---------------- log ---------------- */
async function loadLog(){
  try {
    const j = await fetch('/api/log').then(r=>r.json());
    const items = (j.items || []).slice().reverse();
    $('#logbox').innerHTML = items.length ? items.map(i =>
      `<div class="logline"><span class="lt">${esc(i.t)}</span><span class="lg">${esc(i.table)}</span>` +
      `<span class="lc" title="${esc(i.cmd)}">${esc(i.cmd)}</span>` +
      `<span class="lb"><b>→</b> ${esc(i.tx)} &nbsp; <b>←</b> ${esc(i.rx)}</span></div>`
    ).join('') : '<div class="muted">暂无数据（尚未与耳机通信）</div>';
  } catch(e){ /* log is best-effort */ }
}

/* ---------------- bindings ---------------- */
async function doSwitch(){
  if (acting) return;
  busy(true, '正在切换到另一副耳机…');
  try {
    const j = await api('/api/switch', {});
    renderDevice(j.context || j);
    await loadStatus();
    toast('当前耳机：' + context.device.name);
  } catch(e) {
    toast(e.message, true);
    busy(false);
  }
}

function bind(){
  document.addEventListener('change', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el || !state) return;
    const a = el.dataset.action;
    let v;
    if (el.type === 'checkbox') v = el.checked;
    else if (el.type === 'range') v = Number(el.value);
    else if (el.dataset.value !== undefined) v = el.dataset.value;
    else v = el.value;
    act(a, v);
  });

  // buttons (mode segments, wind) fire click, not change
  document.addEventListener('click', (e) => {
    const el = e.target.closest('button[data-action]');
    if (!el || !state) return;
    const raw = el.dataset.value;
    act(el.dataset.action, raw === '1' ? true : raw);
  });

  $('#btnRefresh').onclick = async () => {
    progress(true);
    try {
      try { await api('/api/disconnect', {}); } catch(e){}
      clearBanner();
      await loadContext(true);
      await loadStatus(true);
      toast('状态已刷新');
    } catch(e) {
      toast(e.message, true);
    } finally {
      progress(false);
    }
  };

  $('#btnSwitch').onclick = doSwitch;
  $('#btnTheme').onclick = () => chooseTheme(
    document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

  $('#btnMac').onclick = async () => {
    const mac = $('#macInput').value.trim().toUpperCase();
    busy(true, '正在保存配置…');
    try {
      await api('/api/config', {device, mac});
      toast('MAC 已保存，正在重新连接');
      await loadStatus();
    } catch(e){ toast(e.message, true); busy(false); }
  };

  $('#btnEqApply').onclick = () => {
    const vals = $$('.vslider input').map(i => Number(i.value));
    act('eq_bands', vals, '正在写入 6 段 EQ…');
  };
  $('#btnEqReset').onclick = () => {
    $$('.vslider input').forEach(i => { i.value = 0; });
    $$('.vval').forEach(v => { v.textContent = '0'; });
    act('eq_bands', [0,0,0,0,0,0]);
  };
  $('#btnKeys').onclick = () =>
    act('keys', {left:$('#keyLeft').value, right:$('#keyRight').value});

  const stcExt = () => {
    if (!has('stc_ext')) return;
    act('stc_ext', {sensitivity:$('#sensSel').value, off_time:$('#offSel').value});
  };
  $('#sensSel').addEventListener('change', stcExt);
  $('#offSel').addEventListener('change', stcExt);

  $('#btnLog').onclick = loadLog;
  $('#levelRange').addEventListener('input', e => {
    $('#levelVal').textContent = e.target.value;
  });

}

(async function init(){
  bind();
  preloadPhotos();
  progress(true);
  try {
    await loadContext();
  } catch(e){
    banner('<b>后端未就绪。</b> ' + esc(e.message), true);
    progress(false);
    return;
  }
  await loadStatus();
  if (qs.get('switch') === '1') {
    history.replaceState(null, '', location.pathname +
      (location.search.replace(/[?&]switch=1/, '') || ''));
    setTimeout(doSwitch, 400);        // tray "switch headset" opens this URL
  }
  // If the headset is turned off and another one takes over, follow it.
  setInterval(async () => {
    if (document.hidden || acting) return;
    try {
      const p = new URLSearchParams({quiet: 1});
      const j = await api('/api/context?' + p.toString());
      if (j.device.id !== device) { renderDevice(j); await loadStatus(); }
    } catch(e){ /* best-effort */ }
  }, 20000);
})();
