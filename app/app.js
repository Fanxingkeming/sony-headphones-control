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

/* ---- dynamic colour: the panel tints itself after the headset ----
   A tiny M3-style tonal palette generator. The headset reports its ModelColor
   enum (04 03); we map it to a seed hue and repaint the primary/secondary
   roles. Neutral roles (surfaces, outlines) stay untouched. */
const SEED_DEFAULT = '#4159b4';
let lastSeed = SEED_DEFAULT;

function hexToHsl(hex){
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16 & 255) / 255, g = (n >> 8 & 255) / 255, b = (n & 255) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
  let h = 0, s = 0;
  if (mx !== mn) {
    const d = mx - mn;
    s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
    if (mx === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (mx === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }
  return [h, s * 100];
}

function seedForStatus(s, device){
  const en = ((s.info && s.info.color && s.info.color.enum) || '').toUpperCase();
  if (en.includes('WHITE')) return '#a39a86';
  if (en.includes('CREAM') || en.includes('BEIGE') || en.includes('GOLD')) return '#a08a5e';
  if (en.includes('SILVER') || en.includes('PLATINUM')) return '#64708a';
  if (en.includes('BLUE')) return '#4a6da7';
  if (en.includes('BLACK') || en.includes('GRAPHITE')) return '#565f75';
  return device === 'ls900n' ? '#4a6da7' : '#565f75';
}

function applyPalette(){
  const dark = document.documentElement.dataset.theme === 'dark';
  const [h, s0] = hexToHsl(lastSeed);
  const s = Math.round(Math.min(64, Math.max(16, s0)));
  const L  = (x) => 'hsl(' + h.toFixed(1) + ' ' + s + '% ' + x + '%)';
  const Ls = (x) => 'hsl(' + h.toFixed(1) + ' ' + Math.round(s * 0.4) + '% ' + x + '%)';
  const r = document.documentElement.style;
  const set = (k, v) => r.setProperty(k, v);
  if (dark) {
    set('--primary', L(80));               set('--on-primary', L(18));
    set('--primary-container', L(32));     set('--on-primary-container', L(90));
    set('--secondary-container', Ls(30));  set('--on-secondary-container', Ls(88));
  } else {
    set('--primary', L(42));               set('--on-primary', '#ffffff');
    set('--primary-container', L(90));     set('--on-primary-container', L(14));
    set('--secondary-container', Ls(90));  set('--on-secondary-container', Ls(22));
  }
}

function systemTheme(){
  return (mediaDark && mediaDark.matches) ? 'dark' : 'light';
}

function applyTheme(t, remember){
  const theme = (t === 'dark') ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
  applyPalette();
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


/* ---------------- language ---------------- */
/* Chinese source text doubles as the lookup key: a miss simply stays Chinese,
   so an untranslated string degrades instead of showing a raw key. Server-side
   messages (connect errors, action results) are still Chinese — they are built
   in Python and would need the language passed down. */
const LANG_KEY = 'shcp.lang';
const LANG = (function(){
  const q = qs.get('lang');
  if (q === 'zh' || q === 'en') { try { localStorage.setItem(LANG_KEY, q); } catch(e){} return q; }
  try { const v = localStorage.getItem(LANG_KEY); if (v === 'zh' || v === 'en') return v; } catch(e){}
  return (navigator.language || 'zh').toLowerCase().indexOf('zh') === 0 ? 'zh' : 'en';
})();

const EN = {
  "Control Panel · MDR Protocol · 非官方工具": "Control Panel · MDR Protocol · unofficial tool",
  "未连接": "Disconnected",
  "↻ 刷新": "↻ Refresh",
  "切换明暗主题": "Toggle light/dark theme",
  "重新读取所有状态": "Re-read every value",
  "设备概览": "Overview",
  "电量": "Battery",
  "型号": "Model",
  "固件版本": "Firmware",
  "当前编解码": "Codec",
  "LDAC 输出": "LDAC output",
  "LDAC 已生效": "LDAC active",
  "未生效": "Not active",
  "说明": "Info",
  "收起": "Hide",
  "已检测到 A2DP Windows Bridge": "A2DP Windows Bridge detected",
  "未检测到 A2DP Windows Bridge": "No A2DP Windows Bridge detected",
  "Windows 只带 SBC 和 AAC，没有 LDAC 编码器，也不开放第三方编码器接口。":
    "Windows ships SBC and AAC only. There is no LDAC encoder and no plug-in point for a third-party one.",
  "改注册表或装普通驱动都不会让系统输出 LDAC。":
    "Registry tweaks or an ordinary driver will not make Windows output LDAC.",
  "「音质优先（LDAC）」只影响耳机侧偏好；源端不给 LDAC 时仍协商为 AAC。":
    "\u201cSound quality first (LDAC)\u201d only sets the headset's preference; without an LDAC source it still negotiates AAC.",
  "开源方案 A2DP Windows Bridge 需要一支专用 USB 蓝牙适配器，内置蓝牙不能这样接管。":
    "The open-source A2DP Windows Bridge needs a dedicated USB Bluetooth adapter; the built-in radio cannot be taken over this way.",
  "商业方案 Alternative A2DP Driver 可替换 A2DP 驱动，支持内置蓝牙。":
    "The commercial Alternative A2DP Driver replaces the A2DP driver and works with the built-in radio.",
  "本应用不下载驱动，也不修改系统蓝牙栈。":
    "This app never downloads a driver or modifies the Bluetooth stack.",
  "协议": "Protocol",
  "机身颜色": "Colour",
  "颜色指令": "Colour command",
  "产品系列": "Series",
  "系列 / 颜色": "Series / colour",
  "头戴式 · 单电池": "Over-ear · single battery",
  "充电盒 ": "Case ",
  "左 ": "Left ",
  "右 ": "Right ",
  "当前耳机": "Current headset",
  "当前耳机：": "Current headset: ",
  "切换": "Switch",
  "⇄ 切换": "⇄ Switch",
  "切换到另一副已连接的耳机": "Switch to the other connected headset",
  "当前只检测到这一副耳机": "Only this headset is detected",
  "蓝牙设备": "Bluetooth device",
  "扫描": "Scan",
  "手动": "Manual",
  "断开": "Disconnect",
  "蓝牙 MAC": "Bluetooth address",
  "保存并重连": "Save & reconnect",
  "选择要控制的耳机（自动从已配对的蓝牙设备中识别）": "Pick the headset to control (detected from paired devices)",
  "重新扫描已配对的蓝牙设备": "Rescan paired Bluetooth devices",
  "释放设备，把耳机让回给手机": "Release the headset so the phone can take over",
  "设备改名或未识别时，手动填写 MAC": "Enter the address by hand if the device was renamed",
  "未发现已配对的蓝牙设备": "No paired Bluetooth devices found",
  "没有发现已配对的蓝牙设备": "No paired Bluetooth devices found",
  "已连接": "Connected",
  "已配对": "Paired",
  "未配对": "Not paired",
  "· 已连接": "· Connected",
  "· 未连接": "· Disconnected",
  "已保存（当前不在附近）": "saved (not nearby)",
  "降噪 / 环境声": "Noise cancelling / ambient",
  "降噪": "Noise cancelling",
  "环境声": "Ambient sound",
  "关闭": "Off",
  "环境声等级": "Ambient level",
  "环境声下聚焦人声": "Focus on voice in ambient sound",
  "关注语音": "Focus on voice",
  "风噪降低": "Wind noise reduction",
  "自动": "Auto",
  "高": "High",
  "低": "Low",
  "声音": "Sound",
  "均衡器": "Equalizer",
  "预设": "Preset",
  "自定义": "Custom",
  "自定义 1": "Custom 1",
  "自定义 2": "Custom 2",
  "低音": "Bass",
  "人声": "Vocal",
  "明亮": "Bright",
  "激昂": "Excited",
  "柔和": "Mellow",
  "轻松": "Relaxed",
  "语音": "Speech",
  "低音增强": "Bass boost",
  "高音增强": "Treble boost",
  "压缩音源升频": "Upscale compressed audio",
  "连接质量": "Connection quality",
  "音质优先（LDAC）": "Sound quality first (LDAC)",
  "稳定连接优先": "Stable connection first",
  "EQ · 6 段自定义": "EQ · 6-band custom",
  "归零": "Reset",
  "写入自定义 EQ": "Apply custom EQ",
  "仅支持预设，动作不可单独改": "Presets only; the action itself is fixed",
  "系统设置": "System",
  "智能免摘 / 智能对话": "Speak-to-Chat",
  "智能免摘": "Speak-to-Chat",
  "智能对话": "Speak-to-Chat",
  "开启后说话会自动暂停播放": "Playback pauses while you speak",
  "自动断电": "Auto power off",
  "退出时间": "Off timer",
  "取下耳机时": "When taken off",
  "取下即关": "When taken off",
  "5 分钟": "5 minutes",
  "30 分钟": "30 minutes",
  "1 小时": "1 hour",
  "3 小时": "3 hours",
  "触摸式传感器面板": "Touch sensor panel",
  "取下耳机时暂停": "Pause when taken off",
  "多点连接": "Multipoint",
  "同时连接两台设备": "Connect two devices at once",
  "只读 · 设备拒绝写入": "Read-only · the device refuses writes",
  "按键 / 触摸功能分配": "Button / touch assignment",
  "左耳": "Left",
  "右耳": "Right",
  "音量控制": "Volume",
  "播放控制": "Playback",
  "快速环境声": "Quick ambient",
  "无": "None",
  "写入分配": "Apply assignment",
  "对话灵敏度": "Speak-to-Chat sensitivity",
  "快": "Fast",
  "中": "Medium",
  "慢": "Slow",
  "通知和语音向导": "Notifications and voice guidance",
  "启用": "Enabled",
  "Table#2 · 00 = 开": "Table#2 · 00 = on",
  "v1 无读回 · 仅写入，请用 App 确认": "v1 has no read-back; confirm in the App",
  "写入后请用 App 确认模式": "Confirm the mode in the App after writing",
  "写入后链路会断开重连": "The link drops and reconnects after writing",
  "原始帧日志": "Raw frame log",
  "最近收发的 MDR 帧（十六进制）": "Recent MDR frames (hex)",
  "暂无数据": "No data yet",
  "暂无数据（尚未与耳机通信）": "No data yet (nothing exchanged with the headset yet)",
  "正在读取设备…": "Reading the device…",
  "正在与设备通信…": "Talking to the device…",
  "正在保存配置…": "Saving…",
  "正在写入并读回…": "Writing and reading back…",
  "正在写入 6 段 EQ…": "Writing the 6-band EQ…",
  "正在切换到另一副耳机…": "Switching to the other headset…",
  "完成": "Done",
  "状态已刷新": "Status refreshed",
  "刷新": "Refresh",
  "重试": "Retry",
  "已断开，下次操作会重新连接": "Disconnected; the next action reconnects",
  "MAC 已保存，正在重新连接": "Address saved, reconnecting",
  "已切换到 ": "Switched to ",
  "已自动识别 ": "Detected ",
  "蓝牙扫描不可用：": "Bluetooth scan unavailable: ",
  "后端未就绪。": "Backend not ready.",
  "设备未连接。": "Headset not connected.",
  "已保存": "saved",
  "发现 ": "Found ",
  " 台音频设备": " audio devices",
  "请求失败": "Request failed",
  "请求超时：后端无响应": "Timed out: the backend did not answer",
  "本地运行 · 不上传任何数据 · 同一时刻只允许一个 tandem 客户端（请先退出手机上的 Sound Connect）": "Runs locally · uploads nothing · only one tandem client at a time (quit Sound Connect on the phone first)"
};

function t(s){ return (LANG === 'en' && EN[s]) ? EN[s] : s; }

/* Backend messages are formatted in Python, so an exact-match table cannot work.
   These patterns cover everything the panel can surface: connection failures,
   the generic hints and the result text of every /api/action call. Anything
   unmatched stays Chinese rather than guessing. */
const _onoff = (v) => (v === '开' ? 'on' : 'off');
const _cap = (v) => (v ? v.charAt(0).toUpperCase() + v.slice(1) : v);
const _apo = (v) => ({ off: 'off', '5min': '5 min', '30min': '30 min',
                       '1h': '1 hour', '3h': '3 hours', takenoff: 'when taken off' })[v] || v;
const _key = (v) => ({ volume: 'volume', playback: 'playback',
                       quick_ambient: 'ambient control', none: 'none' })[v] || v;

const MSG_EN = [
  /* --- connection --- */
  [/^(.+)：connect 超时。确认耳机已开机、已从充电盒取出，且手机上的 Sound Connect 已完全退出。$/,
   '$1: connect timed out. Make sure the headset is on, out of the charging case, and that Sound Connect is closed on the phone.'],
  [/^(.+)：connect 失败, SO_ERROR=(\d+)。.*$/,
   '$1: connect failed (SO_ERROR=$2). The headset is probably still held by the phone.'],
  [/^设备暂时不可达$/, 'Headset unreachable'],
  [/^耳机开机、从盒中取出，并在手机上完全退出 Sound Connect 后重试。$/,
   'Turn the headset on, take it out of the case and quit Sound Connect on the phone, then retry.'],
  [/^耳机开机并连上后点「↻ 刷新」重试。$/,
   'Turn the headset on and connect it, then click \u21bb Refresh.'],
  [/^请求失败$/, 'Request failed'],
  [/^未知设备$/, 'Unknown device'],
  [/^已拒绝跨站请求$/, 'Cross-site request rejected'],
  [/^请求体不是合法 JSON$/, 'Request body is not valid JSON'],
  [/^设备或 MAC 格式不正确$/, 'Invalid device or MAC address'],
  [/^MAC 含非法字符$/, 'MAC address contains invalid characters'],
  [/^连接可能已断开。点右上角「↻ 刷新」重新连接。$/,
   'The link may have dropped. Click \u21bb Refresh at the top right to reconnect.'],
  [/^操作失败：(.+)$/, 'Action failed: $1'],

  /* --- noise cancelling --- */
  [/^已执行$/, 'Done'],
  [/^已切换到降噪$/, 'Noise cancelling on'],
  [/^已切换到环境声$/, 'Ambient sound on'],
  [/^已关闭降噪处理$/, 'Noise cancelling off'],
  [/^已切换$/, 'Switched'],
  [/^环境声等级 → (\d+)$/, 'Ambient level → $1'],
  [/^关注语音 → (开|关)$/, (m, v) => 'Focus on voice → ' + _onoff(v)],
  [/^已启用风噪降低$/, 'Wind noise reduction on'],

  /* --- sound --- */
  [/^EQ 预设 → (\S+)$/, (m, v) => 'EQ preset → ' + _cap(v)],
  [/^自定义 EQ 已写入并读回$/, 'Custom EQ written and read back'],
  [/^DSEE Extreme → (自动|关)$/, (m, v) => 'DSEE Extreme → ' + (v === '自动' ? 'auto' : 'off')],
  [/^连接模式 → (稳定优先|音质优先)$/,
   (m, v) => 'Connection mode → ' + (v === '稳定优先' ? 'stable first' : 'sound quality first')],
  [/^语音向导写入（v1 无读回，请用 App 确认）$/,
   'Voice guidance written (v1 has no read-back; confirm in the phone app)'],
  [/^通知和语音向导 → (开|关)$/, (m, v) => 'Notifications & voice guide → ' + _onoff(v)],

  /* --- system --- */
  [/^智能免摘 \/ 智能对话 → (开|关)$/, (m, v) => 'Speak-to-Chat → ' + _onoff(v)],
  [/^智能对话扩展参数已写入$/, 'Speak-to-Chat parameters written'],
  [/^自动断电 → (\S+)$/, (m, v) => 'Auto power off → ' + _apo(v)],
  [/^取下暂停 → (开|关)$/, (m, v) => 'Pause when removed → ' + _onoff(v)],
  [/^触摸面板 → (开|关)$/, (m, v) => 'Touch sensor → ' + _onoff(v)],
  [/^多点连接写入完成（设备将断开重连）。收到 (\d+) 条告警并已应答。$/,
   'Multipoint written (the headset will reconnect). $1 alert(s) received and acknowledged.'],
  [/^LinkBuds S 的多点连接是只读的，设备不接受写入$/,
   'Multipoint is read-only on LinkBuds S; the headset rejects writes'],
  [/^按键分配 → 左 (\S+) \/ 右 (\S+)$/,
   (m, l, r) => 'Button assignment → L ' + _key(l) + ' / R ' + _key(r)],
  [/^未知操作：(.+)$/, 'Unknown action: $1'],
];

function tmsg(s){
  if (LANG !== 'en' || !s) return s;
  for (const [re, rep] of MSG_EN) if (re.test(s)) return s.replace(re, rep);
  return s;
}

/* Translate in place. Idempotent: English text is never a key, so a second
   pass over the same subtree changes nothing. */
let _localizing = false;
function localize(root){
  if (LANG !== 'en' || _localizing || !root) return;
  _localizing = true;
  try {
    if (root.nodeType === 3) {
      const v = root.nodeValue, key = (v || '').trim();
      if (key && EN[key]) root.nodeValue = v.replace(key, EN[key]);
    } else {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        // [data-raw] marks text that must survive translation verbatim, such
        // as the 中/EN toggle label.
        acceptNode(n) {
          const el = n.parentNode;
          if (el && el.closest && el.closest('[data-raw]')) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        }
      });
      const pending = [];
      while (walker.nextNode()) pending.push(walker.currentNode);
      pending.forEach(n => {
        const v = n.nodeValue, key = (v || '').trim();
        if (key && EN[key]) n.nodeValue = v.replace(key, EN[key]);
      });
      if (root.querySelectorAll) {
        root.querySelectorAll('[placeholder],[title],[aria-label]').forEach(el => {
          ['placeholder', 'title', 'aria-label'].forEach(a => {
            const v = el.getAttribute(a);
            if (v && EN[v.trim()]) el.setAttribute(a, EN[v.trim()]);
          });
        });
      }
    }
  } finally {
    _localizing = false;
  }
}

/* Every screen in this panel is built by re-writing innerHTML, so one observer
   covers all of them (and toasts) without touching each render function. */
function watchLanguage(){
  if (LANG !== 'en') return;
  localize(document.body);
  const mo = new MutationObserver(() => {
    if (_localizing) return;
    requestAnimationFrame(() => localize(document.body));
  });
  mo.observe(document.body, { childList: true, subtree: true, characterData: true });
}

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
   in 04 03; values are what actually ships in app/assets. The bare model name
   is used for the colourway it was rendered in, so no byte-identical copy is
   shipped twice (xm4.png is the black one, ls900n.png the earth-blue one).
   Keep in sync with make_cloud_assets.py. */
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
      im.src = '/assets/' + n + '.webp';
    });
    const svg = new Image();
    svg.src = '/assets/' + id + '.svg';
  });
}
let toastTimer;
function toast(msg, bad){
  const t = $('#toast');
  t.textContent = tmsg(msg);
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
/* The Bluetooth address is an identifier the user may not want on screen
   (screenshots, shoulder surfing). Shown abbreviated everywhere it is
   display-only; the manual-entry input keeps the full value. */
function maskMac(m){
  if (!m) return m || '';
  const p = String(m).split(':');
  if (p.length !== 6) return m;
  return p[0] + ':' + p[1] + ':…:' + p[4] + ':' + p[5];
}

function renderDevice(ctx){
  context = ctx;
  device = ctx.device.id;
  const d = ctx.device;
  const live = ctx.status === 'connected';
  $('#devbadge').innerHTML =
    `<span class="devbadge-dot ${ctx.status}"></span>` +
    `<div class="devbadge-text"><b>${esc(d.name)}</b>` +
    `<small>MDR ${esc(d.protocol.toUpperCase())} · ${esc(maskMac(d.mac))}` +
    `${live ? ' ' + t('· 已连接') : ' ' + t('· 未连接')}</small></div>`;
  $('#btnSwitch').classList.toggle('hidden', !(ctx.alternatives > 0));
  $('#btnSwitch').title = ctx.alternatives > 0
    ? '切换到另一副已连接的耳机' : '当前只检测到这一副耳机';
  setPhoto(device, ctx.color);
}

/* ---------------- Bluetooth device picker ---------------- */
/* The address itself is an implementation detail: Windows already knows which
   headsets are paired, so the panel lists them and the user clicks one. */
const BT_MODEL = { xm4: 'WH-1000XM4', ls900n: 'LinkBuds S' };
let btScan = { devices: [] };

function btOptionLabel(d){
  const name = d.name || maskMac(d.mac);
  const model = BT_MODEL[d.guess || d.owner] || '';
  const state = t(d.connected ? '已连接' : (d.remembered ? '已配对' : '未配对'));
  const parts = [name];
  if (model && model.toLowerCase() !== name.toLowerCase()) parts.push(model);
  parts.push(state);
  return parts.join(' · ');
}

function renderBt(j){
  btScan = j || { devices: [] };
  const sel = $('#btPick');
  if (!sel) return;
  const cur = (context && context.device && context.device.mac) || '';
  const list = (btScan.devices || []).filter(d => d.audio || d.guess || d.owner);
  const html = list.map(d =>
    `<option value="${esc(d.mac)}">${esc(btOptionLabel(d))}</option>`);
  // Keep the saved address selectable even when the headset is switched off,
  // otherwise the picker would look empty exactly when nothing is nearby.
  if (cur && !list.some(d => d.mac === cur)) {
    html.unshift(`<option value="${esc(cur)}">${esc(maskMac(cur))} · 已保存（当前不在附近）</option>`);
  }
  if (!html.length) {
    html.push('<option value="">未发现已配对的蓝牙设备</option>');
  }
  sel.innerHTML = html.join('');
  if (cur) sel.value = cur;
  if (!btScan.available && btScan.error) {
    sel.title = t('蓝牙扫描不可用：') + btScan.error;
  }
}

async function loadBt(force){
  try {
    const j = await api('/api/bt' + (force ? '?scan=1' : ''), null, 8000);
    renderBt(j);
    return j;
  } catch (e) {
    return null;
  }
}

/* Save the address for a model and immediately probe that model. */
async function bindDevice(key, mac){
  await api('/api/config', {device: key, mac});
  const j = await api('/api/context?force=1&device=' + encodeURIComponent(key),
                      null, 30000);
  renderDevice(j);
  $('#macInput').value = mac;
  return j;
}

/* First run: a saved address exists for nobody, but Windows knows the headset.
   Adopt it only when exactly one scanned device matches the model we are
   showing, so a renamed or ambiguous device never gets auto-assigned. */
async function autoBind(){
  if (!context || !context.device || context.device.mac) return false;
  const same = (btScan.devices || []).filter(d => d.guess === device);
  if (same.length !== 1) return false;
  try {
    await bindDevice(device, same[0].mac);
    toast(t('已自动识别 ') + (same[0].name || maskMac(same[0].mac)));
    return true;
  } catch (e) {
    return false;
  }
}

function photoCandidates(id, color){
  // The headset reports its own ModelColor in 04 03; map it to the matching
  // render. A colourway we have no render for is probed as <id>_<suffix>,
  // then everything falls back to the default render, the traced SVG and
  // finally the neutral placeholder.
  // Shipped renders are WebP (82% smaller inside the exe); PNG is still tried
  // so a hand-dropped render in app/assets/ works without conversion.
  const table = PHOTO_VARIANTS[id] || {};
  const sfx = color && color.suffix;
  const list = [];
  const add = (base) => {
    list.push('/assets/' + base + '.webp', '/assets/' + base + '.png');
  };
  const variant = sfx ? (table[sfx] || (id + '_' + sfx)) : null;
  if (variant) add(variant);
  if (variant !== id) add(id);
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
/* `silent` skips the progress bar and the error banner: used by the idle
   refresh below, where a once-a-minute flash would be worse than the stale
   value it is replacing. */
async function loadStatus(fresh, silent){
  // The 20 s poll and a manual refresh can collide on a single RFCOMM link;
  // queueing them only doubles the latency, so a second call is dropped.
  if (statusInFlight) return;
  statusInFlight = true;
  if (!silent) progress(true);
  try {
    const q = `device=${encodeURIComponent(device)}` + (fresh ? '&fresh=1' : '');
    const j = await api(`/api/status?${q}`, null, 25000);
    state = j.state;
    clearBanner();
    render();
  } catch (e) {
    if (!silent) {
      const hint = e.hint ? ' ' + esc(tmsg(e.hint)) : '';
      banner(`<b>${t('设备未连接。')}</b> ${esc(tmsg(e.message))}${hint}` +
             ` <button class="btn small" id="bannerRetry">重试</button>`, true);
      const btn = $('#bannerRetry');
      if (btn) btn.onclick = () => loadStatus(true);
      toast(e.message, true);
    }
  } finally {
    statusInFlight = false;
    if (!silent) progress(false);
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
  $('#ov-sub').textContent = s.name + ' · ' + maskMac(s.mac);
  $('#ov-proto').textContent = 'MDR ' + s.protocol.toUpperCase();
  // repaint the accent colours once the headset's own colour is known
  lastSeed = seedForStatus(s, device);
  applyPalette();
  const bm = hasVal(s.battery.main) ? s.battery.main : null;
  $('#bat-main').textContent = bm === null ? '--' : bm;
  const bar = $('#bat-bar');
  bar.style.width = (bm === null ? 0 : bm) + '%';
  bar.parentElement.style.setProperty('--pct', bm === null ? 0 : bm);
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

  // EQ - presets as a chip row (the generic [data-action] click handler
  // dispatches them, so no extra wiring is needed).
  const eqList = v1 ? EQ_V1 : EQ_V2;
  const curPreset = eqList.indexOf(s.eq.preset) >= 0 ? s.eq.preset : 'custom';
  const eqChips = (curPreset === 'custom' ? eqList.concat(['custom']) : eqList);
  $('#eqPreset').innerHTML = eqChips.map(k =>
    `<button type="button" class="eqchip${k === curPreset ? ' active' : ''}"` +
    ` data-action="eq_preset" data-value="${k}">${esc(EQ_LABEL[k]||k)}</button>`).join('');
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

  renderLdac();
}

/* ---------------- LDAC ----------------
   "Sound quality first (LDAC)" is a headset-side preference. The codec itself
   is negotiated by the Windows Bluetooth stack, which ships SBC/AAC only and
   exposes no plug-in point for a third-party encoder. So this row reports what
   was actually negotiated and explains the rest; it never installs anything. */
let ldacBridge = null;

function renderLdac(){
  const el = $('#ldacState');
  if (!el || !state) return;
  const codec = (state.info && state.info.codec) || '?';
  const on = codec === 'LDAC';
  el.textContent = on ? t('LDAC 已生效') : t('未生效') + ' · ' + codec;
  el.classList.toggle('ok', on);
}

async function loadLdac(){
  try {
    const j = await api('/api/ldac', null, 5000);
    ldacBridge = j.bridge || null;
  } catch(e){ ldacBridge = null; }
  const el = $('#ldacBridge');
  if (!el) return;
  if (ldacBridge && ldacBridge.installed) {
    el.textContent = t('已检测到 A2DP Windows Bridge') +
      (ldacBridge.version ? ' ' + ldacBridge.version : '');
    el.classList.add('on');
  } else {
    el.textContent = t('未检测到 A2DP Windows Bridge');
    el.classList.remove('on');
  }
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
    loadBt();                          // the picker follows the active headset
    await loadStatus();
    toast(t('当前耳机：') + context.device.name);
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
  $('#btnLang').textContent = LANG === 'en' ? '中' : 'EN';
  $('#btnLang').onclick = () => {
    try { localStorage.setItem(LANG_KEY, LANG === 'en' ? 'zh' : 'en'); } catch(e){}
    location.reload();          // every string is regenerated on load
  };

  $('#btnTheme').onclick = () => chooseTheme(
    document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

  $('#btnLdacInfo').onclick = () => {
    const note = $('#ldacNote'), btn = $('#btnLdacInfo');
    const willOpen = note.classList.contains('hidden');
    note.classList.toggle('hidden', !willOpen);
    btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    btn.textContent = willOpen ? t('收起') : t('说明');
  };

  $('#btPick').onchange = async () => {
    const mac = $('#btPick').value;
    if (!mac) return;
    const hit = (btScan.devices || []).find(d => d.mac === mac);
    // Clicking a device that looks like the other model means "control that
    // one", which is exactly what the single-device view is for.
    const target = (hit && hit.guess) || device;
    progress(true);
    try {
      await bindDevice(target, mac);
      await loadStatus(true);
      toast(t('已切换到 ') + (target === 'xm4' ? 'WH-1000XM4' : 'LinkBuds S'));
    } catch (e) {
      toast(e.message, true);
    } finally {
      progress(false);
    }
  };

  $('#btnBtScan').onclick = async () => {
    progress(true);
    try {
      const j = await loadBt(true);
      const n = j ? j.devices.filter(d => d.audio || d.guess).length : 0;
      toast(j && n ? `${t('发现 ')}${n}${t(' 台音频设备')}` : t('没有发现已配对的蓝牙设备'));
    } finally {
      progress(false);
    }
  };

  $('#btnDisconnect').onclick = async () => {
    // The headset accepts one tandem client; releasing it here is what lets
    // the phone take over again without touching the tray menu.
    try {
      await api('/api/disconnect', {});
    } catch (e) {
      toast(e.message, true);
      return;
    }
    if (context) {
      context.status = 'offline';
      renderDevice(context);
    }
    toast('已断开，下次操作会重新连接');
  };

  $('#btnBtManual').onclick = () => {
    const row = $('#macRow');
    row.classList.toggle('hidden');
    if (!row.classList.contains('hidden')) $('#macInput').focus();
  };

  $('#btnMac').onclick = async () => {
    const mac = $('#macInput').value.trim().toUpperCase();
    busy(true, '正在保存配置…');
    try {
      await api('/api/config', {device, mac});
      $('#macRow').classList.add('hidden');
      toast('MAC 已保存，正在重新连接');
      await loadStatus();
      await loadBt();
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
  watchLanguage();
  preloadPhotos();
  loadLdac();                          // capability probe, not on the RFCOMM path
  progress(true);
  try {
    await loadContext();
  } catch(e){
    banner('<b>后端未就绪。</b> ' + esc(e.message), true);
    progress(false);
    return;
  }
  if (!context || !context.device.mac) {
    // Nothing saved yet: ask Windows what is paired and adopt it when the
    // answer is unambiguous, so a first run needs no typing at all.
    await loadBt();
    if (await autoBind()) await loadStatus(true);
  } else {
    loadBt();                          // populate the picker in the background
  }
  await loadStatus();
  if (qs.get('switch') === '1') {
    history.replaceState(null, '', location.pathname +
      (location.search.replace(/[?&]switch=1/, '') || ''));
    setTimeout(doSwitch, 400);        // tray "switch headset" opens this URL
  }
  // Nothing re-reads the values after the first load, so a panel left open
  // shows a frozen battery/ANC state. Refresh slowly in the background, and
  // immediately when the tab regains focus.
  const idleRefresh = () => {
    if (document.hidden || acting || statusInFlight) return;
    loadStatus(false, true);
  };
  setInterval(idleRefresh, 60000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) idleRefresh();
  });
  window.addEventListener('focus', idleRefresh);

  // M3 ripple on pressable controls (skipped when the OS wants less motion).
  document.addEventListener('pointerdown', (e) => {
    const t = e.target.closest('.btn, .segmented button, .eqchip');
    if (!t || t.disabled) return;
    if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const r = t.getBoundingClientRect();
    const d = Math.max(r.width, r.height) * 2.2;
    const sp = document.createElement('span');
    sp.className = 'ripple';
    sp.style.width = sp.style.height = d + 'px';
    sp.style.left = (e.clientX - r.left - d / 2) + 'px';
    sp.style.top = (e.clientY - r.top - d / 2) + 'px';
    t.appendChild(sp);
    sp.addEventListener('animationend', () => sp.remove());
  });

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
