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
   roles. Neutral roles (surfaces, outlines) stay untouched. An explicit
   "signature" accent (Sony black & gold) overrides the device colour. */
const SEED_DEFAULT = '#4159b4';
const SEED_SIGNATURE = '#c9a227';
const ACCENT_KEY = 'shcp.accent';
let lastSeed = SEED_DEFAULT;

function accentMode(){
  try { return localStorage.getItem(ACCENT_KEY) || 'auto'; } catch(e){ return 'auto'; }
}

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
  const seed = (accentMode() === 'signature') ? SEED_SIGNATURE : lastSeed;
  const [h, s0] = hexToHsl(seed);
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
  "关于": "About",
  "版本与信息": "Version & info",
  "版本": "Version",
  "更新检查": "Update check",
  "检查更新": "Check for updates",
  "检查中…": "Checking…",
  "已是最新": "Up to date",
  "未检查": "Not checked",
  "点「检查更新」联网查询": "click Check for updates (uses GitHub)",
  "一键场景": "Scenes",
  "一次切换降噪、环境声与音质": "Switch noise mode, ambient and sound together",
  "可撤销": "Undoable",
  "保存当前为场景": "Save current as scene",
  "撤销上一次": "Undo last change",
  "导出配置": "Export config",
  "导入配置": "Import config",
  "场景会连续写入多项设置，约 2–4 秒，期间请勿操作耳机。当前设置可导出为 JSON 备份。":
    "A scene writes several settings in a row (~2-4 s). Do not touch the headset meanwhile. Export the current setup as a JSON backup.",
  "通勤": "Commute", "办公室": "Office", "飞机": "Flight", "居家": "Home",
  "耳机未连接 · 设置已锁定": "Headset offline - controls locked",
  "不再提示": "Don't show again",
  "在 Windows 蓝牙设置里让耳机处于「已连接」":
    "Connect the headset in Windows Bluetooth settings",
  "完全退出手机上的 Sound Connect（同一时刻只允许一个客户端）":
    "Quit Sound Connect on your phone completely (only one client at a time)",
  "点右上角「↻ 刷新」重新读取状态": "Click Refresh at the top right to re-read",
  "设备详情（协议信息）": "Device details (protocol info)",
  "展开原始帧（诊断用）": "Show raw frames (diagnostics)",
  "快捷键与帮助": "Shortcuts & help",
  "最小": "Min", "最大": "Max",
  "电量偏低，建议充电": "Low battery - charge soon",
  "风噪": "Wind",
  "配置已导出为 JSON": "Config exported as JSON",
  "已导入为场景，点场景名即可应用（不会自动写入耳机）":
    "Imported as a scene; click its name to apply (nothing is written yet)",

  "NC · Ambient Sound · 改动即时写入耳机": "NC · Ambient Sound · applies immediately",
  "System · General · 改动即时写入耳机": "System · General · applies immediately",
  "Audio · Connection · 改动即时写入耳机": "Audio · Connection · applies immediately",
  "EQ · 6 段自定义 · 需点「写入自定义 EQ」": "EQ · 6-band custom · press Apply custom EQ",
  "About · 版本与信息": "About · Version & info",
  "本地运行 · 默认不联网，仅手动「检查更新」时访问 GitHub · 非官方工具，与 Sony 无关联。":
    "Runs locally - no network except a manual update check on GitHub. Unofficial, not affiliated with Sony.",
  "本地运行 · 默认不联网（仅点「检查更新」时访问 GitHub）· 同一时刻只允许一个 tandem 客户端（请先退出手机上的 Sound Connect）":
    "Runs locally - no network except a manual update check on GitHub. One tandem client at a time (quit Sound Connect on the phone).",
  "风噪降低是一种降噪模式；点其它胶囊即可退出":
    "Wind reduction is one noise mode; pick another pill to exit",
  "Speak-to-Chat｜检测到你说话时自动暂停播放并放大环境声，说完恢复。":
    "Speak-to-Chat pauses playback and opens ambient sound when you speak, then resumes.",
  "DSEE Extreme｜把压缩音源实时升频，接近无损听感；对本地无损文件没有作用。":
    "DSEE Extreme upscales compressed audio in real time; it does nothing for lossless files.",
  "LDAC｜索尼的高码率蓝牙编码。Windows 只自带 SBC/AAC，需要额外发射端才可能输出 LDAC；这里显示的只是耳机侧偏好与实际协商结果。":
    "LDAC is Sony's high-bitrate Bluetooth codec. Windows only ships SBC/AAC, so LDAC needs a separate transmitter; this row shows the headset's preference and the codec actually negotiated.",
  "关注语音｜环境声模式下压低背景噪音、突出人声频段。仅环境声模式生效。":
    "Focus on voice lowers background noise and lifts voices in Ambient Sound mode only.",
  "多点连接｜耳机同时保持两台设备的连接。XM4 写入后链路会断开重连，LinkBuds S 为只读。":
    "Multipoint keeps two devices connected at once. On XM4 a write reconnects the link; on LinkBuds S it is read-only.",
  "发现新版本": "New version available",
  "前往下载": "Download",
  "检查失败": "Check failed",
  "日志": "Log",
  "导出日志": "Export log",
  "日志已导出": "Log exported",
  "导出失败": "Export failed",
  "开源": "Source",
  "强调色：Sony 签名金": "Accent: Sony signature gold",
  "强调色：跟随耳机颜色": "Accent: follow the headset colour",
  "自动化": "Automation",
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
  "写入后自动读回确认": "read back automatically after writing",
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
  [/^(.+)：connect 失败, (?:SO_ERROR|WSAError)=10048.*$/,
   '$1: connect failed (SO_ERROR=10048) - the headset is held by another program: another instance on this PC, or Sound Connect on your phone. Close it and retry.'],
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
  [/^已切换到风噪降低（点其它模式退出）$/,
   'Wind noise reduction on (pick another mode to exit)'],
  [/^场景已应用（(\d+) 项）$/, 'Scene applied ($1 settings)'],
  [/^场景步骤为空或过多（最多 12 项）$/, 'Scene has no steps or too many (max 12)'],
  [/^场景步骤格式错误$/, 'Malformed scene step'],
  [/^场景在「(.+)」处失败：(.+)$/, 'Scene failed at $1: $2'],
  [/^该机型不支持风噪降低$/, 'This model does not support wind noise reduction'],

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
  if (EN[s]) return EN[s];
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

/* Live curve for the custom EQ: one smooth path through the six band gains,
   redrawn on every slider input (and after a preset/reset re-render). */
function drawEqCurve(){
  const svg = $('#eqcurve');
  if (!svg) return;
  const inputs = $$('.vslider input');
  if (!inputs.length) { svg.classList.add('hidden'); return; }
  svg.classList.remove('hidden');
  const W = 300, H = 64, PAD = 10;
  const pts = inputs.map((inp, i) => ({
    x: PAD + i * (W - 2 * PAD) / (inputs.length - 1),
    y: H / 2 - Number(inp.value) / 10 * (H / 2 - 4),
  }));
  // Catmull-Rom through the points, emitted as cubic beziers.
  let d = `M ${pts[0].x.toFixed(1)} ${pts[0].y.toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i], p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const c1x = p1.x + (p2.x - p0.x) / 6, c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6, c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  svg.innerHTML =
    `<line class="eqc-zero" x1="${PAD}" y1="${H/2}" x2="${W-PAD}" y2="${H/2}"/>` +
    `<path class="eqc-line" d="${d}"/>`;
}

/* Drag on the curve itself: the nearest band follows the pointer's height.
   The SVG stretches with preserveAspectRatio="none", so band i sits at a
   fixed fraction of the element width - mirror the PAD/spacing maths. */
(function eqCurveDrag(){
  const svg = $('#eqcurve');
  if (!svg) return;
  const W = 300, PAD = 10;
  let dragging = false;
  const apply = (clientX, clientY) => {
    const inputs = $$('.vslider input');
    if (!inputs.length) return;
    const rect = svg.getBoundingClientRect();
    const vx = (clientX - rect.left) / rect.width * W;
    const step = (W - 2 * PAD) / (inputs.length - 1);
    const i = Math.max(0, Math.min(inputs.length - 1,
                                   Math.round((vx - PAD) / step)));
    const t = 1 - (clientY - rect.top) / rect.height;        // 0..1, up = +10
    const n = Math.max(-10, Math.min(10, Math.round((t - 0.5) * 2 * 10)));
    const inp = inputs[i];
    inp.value = n;
    lastEqTouch = Date.now();
    const v = $(`[data-bandval="${inp.dataset.band}"]`);
    if (v) v.textContent = (n > 0 ? '+' : '') + n;
    drawEqCurve();
  };
  svg.addEventListener('pointerdown', (e) => {
    if (!$$('.vslider input').length) return;
    dragging = true;
    try { svg.setPointerCapture(e.pointerId); } catch(err){}
    apply(e.clientX, e.clientY);
    e.preventDefault();
  });
  svg.addEventListener('pointermove', (e) => { if (dragging) apply(e.clientX, e.clientY); });
  svg.addEventListener('pointerup', () => { dragging = false; });
  svg.addEventListener('pointercancel', () => { dragging = false; });
})();
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
  setPhoto(device, ctx.color);
  // Showcase tile brightness follows the body colour: light bodies
  // (white/cream/silver) pop on the dark tile, dark bodies need the light
  // one to stay visible. In light mode the tile is always light anyway.
  const lightBody = ['w', 's', 'cream', 'gold', 'beige']
    .includes(String(ctx.color || '').toLowerCase());
  const wrap = document.querySelector('.dev-photo-wrap');
  if (wrap) wrap.classList.toggle('tile-keep-light', !lightBody);
  const verEl = $('#aboutVer');
  if (verEl) verEl.textContent = 'v' + (ctx.version || '?');
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
let lastRenderState = null;   // JSON of the last rendered status snapshot
let lastEqTouch = 0;          // a band slider was just dragged - don't fight it
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
    }
  } finally {
    statusInFlight = false;
    if (!silent) progress(false);
    busy(false);
    loadLog();
  }
}

/* ---------------- offline gating ----------------
   Nothing may look writable while the headset is gone: the old panel let
   every switch fire and only answered with an error toast afterwards. */
function applyOfflineState(connected){
  const ro = !!(state && state.system && state.system.multipoint_ro);
  $$('[data-action]').forEach(el => {
    el.disabled = !connected || (el.id === 'multiSw' && ro);
  });
  ['btnEqApply', 'btnEqReset', 'btnKeys', 'btnSceneSave'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !connected;
  });
  const tip = $('#offlineTip');
  if (tip) tip.classList.toggle('hidden', connected || guideDismissed());
  setUndoButton();
}

/* ---------------- render ---------------- */
function has(cap){ return state && state.caps.indexOf(cap) >= 0; }
function hasVal(v){ return v !== null && v !== undefined; }

function render(){
  if (!state) return;
  const s = state, v1 = s.protocol === 'v1';

  // The live-sync poll re-renders every few seconds; skip identical snapshots
  // so nothing flickers, and yield for a moment after the user drags an EQ
  // band (the DOM is rebuilt wholesale and would swallow the in-flight drag).
  const j = JSON.stringify(s);
  if (j === lastRenderState && Date.now() - lastEqTouch > 4000) return;
  lastRenderState = j;

  // connection badge
  const dot = $('#dot');
  dot.className = 'dot ' + (s.connected ? 'on' : 'off');
  $('#conntext').textContent = s.connected ? '已连接' : '未连接';

  // overview - the badge in the top bar already carries the (masked) MAC,
  // so the card shows just the friendly name.
  $('#ov-sub').textContent = s.name;
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
  if (bm !== null && bm < 20) bd.unshift('电量偏低，建议充电');
  $('#bat-detail').textContent = bd.join(' · ') || (v1 ? '头戴式 · 单电池' : '');
  const kv = [['型号', s.info.model], ['固件版本', s.info.firmware],
              ['当前编解码', s.info.codec]];
  if (s.info.color) {
    kv.push(['机身颜色', s.info.color.label + ' · ' + s.info.color.enum]);
    if (s.info.color.series_name) kv.push(['产品系列', s.info.color.series_name]);
  } else if (s.info.series) {
    kv.push(['系列 / 颜色', s.info.series]);
  }
  kv.push(['协议', 'MDR ' + s.protocol.toUpperCase()]);
  const rowHtml = (pairs) => pairs.map(([k,v]) =>
    `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
  $('#ov-kv').innerHTML = rowHtml(kv.slice(0, 3));
  const kvMore = $('#ov-kv-more');
  if (kvMore) kvMore.innerHTML = rowHtml(kv.slice(3));
  const ovMore = $('#ovMore');
  if (ovMore) ovMore.classList.toggle('hidden', kv.length <= 3);
  $('#macInput').value = s.mac;

  // ANC
  $$('#ancseg button').forEach(b => {
    const on = b.dataset.value === s.anc.mode;
    b.classList.toggle('active', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  $('#levelRange').value = s.anc.level;
  $('#levelRange').setAttribute('aria-valuetext', s.anc.level + ' / 20');
  $('#levelVal').textContent = s.anc.level;
  $('#focusSw').checked = !!s.anc.focus;
  // Wind-noise reduction only makes sense in ambient mode, so the row lives
  // with the mode instead of being a stand-alone button.
  const windSeg = $('.wind-seg');
  if (windSeg) windSeg.classList.toggle('hidden', !has('wind'));

  // EQ - presets as a chip row (the generic [data-action] click handler
  // dispatches them, so no extra wiring is needed).
  const eqList = v1 ? EQ_V1 : EQ_V2;
  const curPreset = eqList.indexOf(s.eq.preset) >= 0 ? s.eq.preset : 'custom';
  const eqChips = (curPreset === 'custom' ? eqList.concat(['custom']) : eqList);
  $('#eqPreset').innerHTML = eqChips.map(k =>
    `<button type="button" class="eqchip${k === curPreset ? ' active' : ''}"` +
    ` aria-pressed="${k === curPreset}"` +
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
    lastEqTouch = Date.now();
    drawEqCurve();
  }));
  drawEqCurve();

  // sound
  $('#dseeSw').checked = !!s.sound.dsee;
  $('#qualitySel').value = s.sound.quality === 'stable' ? 'stable' : 'hifi';
  // Both models support LDAC (LinkBuds S is Sony's first Hi-Res TWS) - the
  // LDAC row stays for everyone; only the wording differs per protocol.
  $('#voiceHint').textContent = v1 ? t('v1 无读回 · 仅写入，请用 App 确认') : t('写入后自动读回确认');
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
  $('#multiRow').classList.toggle('hidden',
                                 !(has('multipoint') || has('multipoint_ro')));
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
  applyOfflineState(!!s.connected);
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

/* ---------------- scenes ----------------
   A scene is a batch of ordinary writes executed on one RFCOMM link, so four
   or five related settings change together instead of one by one. Scenes are
   plain data: built-ins live here, user scenes live in localStorage and can
   be exported/imported as JSON. Nothing is sent to any server. */
const SCENES_KEY = 'shcp.scenes';
const GUIDE_KEY = 'shcp.guide';
const BUILTIN_SCENES = [
  {id:'commute', name:'通勤', steps:[
    {action:'anc_mode', value:'nc'}, {action:'eq_preset', value:'bass'},
    {action:'dsee', value:true}]},
  {id:'office', name:'办公室', steps:[
    {action:'anc_mode', value:'ambient'}, {action:'anc_level', value:8},
    {action:'focus', value:true}, {action:'dsee', value:false}]},
  {id:'flight', name:'飞机', steps:[
    {action:'anc_mode', value:'nc'}, {action:'eq_preset', value:'vocal'},
    {action:'dsee', value:true}, {action:'stc', value:false}]},
  {id:'home', name:'居家', steps:[
    {action:'anc_mode', value:'off'}, {action:'eq_preset', value:'off'},
    {action:'dsee', value:true}]},
];

function savedScenes(){
  try {
    const v = JSON.parse(localStorage.getItem(SCENES_KEY) || '[]');
    return Array.isArray(v)
      ? v.filter(x => x && x.name && Array.isArray(x.steps)).slice(-12) : [];
  } catch(e){ return []; }
}
function writeSavedScenes(list){
  try { localStorage.setItem(SCENES_KEY, JSON.stringify(list.slice(-12))); } catch(e){}
}
function allScenes(){
  return BUILTIN_SCENES.concat(savedScenes().map((x, i) =>
    ({id:'saved' + i, name:x.name, steps:x.steps, custom:true})));
}
function renderScenes(){
  const box = $('#sceneChips');
  if (!box) return;
  box.innerHTML = allScenes().map(sc =>
    `<button type="button" class="eqchip scenechip" data-scene="${esc(sc.id)}" ` +
    `aria-pressed="false">${esc(t(sc.name))}</button>`).join('');
}
async function applyScene(id){
  const sc = allScenes().find(x => x.id === id);
  if (sc) await act('scene', {name:sc.name, steps:sc.steps},
                    '正在应用场景「' + sc.name + '」…');
}

/* Turn a status snapshot back into writes. Used by undo, "save current as
   scene" and the config export - one representation for all three. */
function stepsFromState(s){
  const steps = [
    {action:'anc_mode', value:s.anc.mode},
    {action:'anc_level', value:s.anc.level},
    {action:'focus', value:!!s.anc.focus},
  ];
  if (s.eq.preset === 'custom')
    steps.push({action:'eq_bands', value:(s.eq.bands || []).slice(0, 6)});
  else
    steps.push({action:'eq_preset', value:s.eq.preset});
  steps.push({action:'dsee', value:!!s.sound.dsee});
  steps.push({action:'quality', value:s.sound.quality});
  steps.push({action:'stc', value:!!s.system.stc});
  steps.push({action:'apo', value:s.system.apo});
  if (has('pause')) steps.push({action:'pause', value:!!s.system.pause});
  if (has('touch')) steps.push({action:'touch', value:!!s.system.touch});
  return steps.slice(0, 12);
}

let undoSnapshot = null;
function setUndoButton(){
  const b = $('#btnUndo');
  if (b) b.disabled = !undoSnapshot || !(state && state.connected);
}
function guideDismissed(){
  try { return localStorage.getItem(GUIDE_KEY) === 'off'; } catch(e){ return false; }
}
function syncAccentLabel(){
  const b = $('#btnAccent');
  if (!b) return;
  const gold = accentMode() === 'signature';
  b.textContent = LANG === 'en'
    ? (gold ? 'Accent: gold' : 'Accent: auto')
    : (gold ? '强调色：金' : '强调色：跟随');
}
function downloadJson(name, obj){
  const blob = new Blob([JSON.stringify(obj, null, 2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

/* ---------------- actions ---------------- */
let acting = false;
async function act(action, value, text){
  if (acting || !state) return;
  acting = true;
  const before = JSON.parse(JSON.stringify(state));
  busy(true, text || '正在写入并读回…');
  try {
    const j = await api('/api/action', {device, action, value});
    if (action === 'voice' && state.protocol === 'v1') uiVoice = !!value;
    if (j.state) state = j.state;
    if (j.reconnect) {
      banner('<b>设备正在断开重连。</b> 等待约 6 秒后点右上角「↻ 刷新」读取真实状态。', false);
    }
    undoSnapshot = before;
    setUndoButton();
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
  // Switch inputs are visually hidden; give screen readers the row label.
  $$('.switch input').forEach(inp => {
    const row = inp.closest('.row');
    const lbl = row && row.querySelector('.lbl');
    if (lbl && !inp.hasAttribute('aria-label'))
      inp.setAttribute('aria-label', lbl.textContent.trim());
  });
  renderScenes();
  syncAccentLabel();
  setUndoButton();

  $('#sceneChips').addEventListener('click', (e) => {
    const b = e.target.closest('[data-scene]');
    if (b && !b.disabled && state && state.connected) applyScene(b.dataset.scene);
  });
  $('#btnSceneSave').onclick = () => {
    if (!state || !state.connected) return;
    const name = (window.prompt('给当前设置起个场景名称',
                  '我的场景 ' + (savedScenes().length + 1)) || '').trim();
    if (!name) return;
    const list = savedScenes();
    list.push({name, steps:stepsFromState(state)});
    writeSavedScenes(list);
    renderScenes();
    toast('场景「' + name + '」已保存到本机');
  };
  $('#btnUndo').onclick = () => {
    if (!undoSnapshot) return;
    const steps = stepsFromState(undoSnapshot);
    undoSnapshot = null;
    setUndoButton();
    act('scene', {name:'撤销', steps}, '正在撤销上一次修改…');
  };
  $('#btnCfgExport').onclick = () => {
    if (!state) return;
    downloadJson('shcp-config-' + device + '.json', {
      app:'sony-headphones-control',
      version:(context && context.version) || '',
      device, savedAt:new Date().toISOString(),
      steps:stepsFromState(state), scenes:savedScenes(),
    });
    toast('配置已导出为 JSON');
  };
  $('#btnCfgImport').onclick = () => $('#cfgFile').click();
  $('#cfgFile').onchange = async (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    try {
      const j = JSON.parse(await f.text());
      const list = savedScenes();
      if (Array.isArray(j.scenes)) j.scenes.forEach(x => {
        if (x && x.name && Array.isArray(x.steps)) list.push(x);
      });
      if (Array.isArray(j.steps) && j.steps.length)
        list.push({name:'导入的配置', steps:j.steps});
      writeSavedScenes(list);
      renderScenes();
      toast('已导入为场景，点场景名即可应用（不会自动写入耳机）');
    } catch (err) {
      toast('配置文件无法解析：' + err.message, true);
    }
    e.target.value = '';
  };
  $('#btnGuideClose').onclick = () => {
    try { localStorage.setItem(GUIDE_KEY, 'off'); } catch(e){}
    const tip = $('#offlineTip');
    if (tip) tip.classList.add('hidden');
  };
  $('#btnHelp').onclick = () => {
    const port = location.port || '80';
    const drift = port !== '8765';
    toast(LANG === 'en'
      ? ('Shortcuts: 1/2/3 noise cancelling / ambient / off, D toggles DSEE, R re-reads | ' +
         'Switches and dropdowns write immediately; EQ and button assignment need Apply | ' +
         'Port ' + port + (drift ? ' (non-default; reinstall the PWA)' : ''))
      : ('快捷键：1 / 2 / 3 切换降噪·环境声·关闭，D 切换 DSEE，R 重新读取 ｜ ' +
         '开关与下拉即时写入，EQ 与按键分配需点「写入」 ｜ 当前端口 ' + port +
         (drift ? '（非默认，已安装的 PWA 需重新安装）' : '')));
  };
  document.addEventListener('click', (e) => {
    const h = e.target.closest('[data-help]');
    if (h) toast(tmsg(h.dataset.help));
  });

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

  $('#btnLang').textContent = LANG === 'en' ? '中' : 'EN';
  $('#btnLang').onclick = () => {
    try { localStorage.setItem(LANG_KEY, LANG === 'en' ? 'zh' : 'en'); } catch(e){}
    location.reload();          // every string is regenerated on load
  };

  $('#btnTheme').onclick = () => chooseTheme(
    document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

  // Accent mode: follow the headset's colour, or lock a fixed "Sony
  // signature" black & gold. The choice persists and survives theme flips.
  $('#btnAccent').onclick = () => {
    const next = accentMode() === 'signature' ? 'auto' : 'signature';
    try { localStorage.setItem(ACCENT_KEY, next); } catch(e){}
    applyPalette();
    syncAccentLabel();
    toast(next === 'signature'
      ? t('强调色：Sony 签名金')
      : t('强调色：跟随耳机颜色'));
  };

  // Keyboard shortcuts (ignored while typing in a field): 1/2/3 switch the
  // noise modes, D toggles DSEE, R forces a re-read.
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.altKey || e.metaKey || e.isComposing) return;
    const tag = (e.target && e.target.tagName) || '';
    if (/INPUT|SELECT|TEXTAREA/.test(tag) || !state || acting) return;
    const mode = {'1': 'nc', '2': 'ambient', '3': 'off'}[e.key];
    if (mode && has('anc')) { act('anc_mode', mode); return; }
    if ((e.key === 'd' || e.key === 'D') && has('dsee')) { act('dsee', !state.sound.dsee); return; }
    if (e.key === 'r' || e.key === 'R') { loadStatus(true); }
  });

  // Update check straight from the browser: api.github.com sends CORS
  // headers, so the panel can ask it without the server growing an HTTPS
  // stack. Silent at start-up, loud only when a newer release exists.
  const REPO = 'Fanxingkeming/sony-headphones-control';
  function compareVer(a, b){
    const pa = String(a).split('.').map(Number), pb = String(b).split('.').map(Number);
    for (let i = 0; i < 3; i++) {
      const d = (pa[i] || 0) - (pb[i] || 0);
      if (d) return d;
    }
    return 0;
  }
  async function checkUpdate(){
    const el = $('#aboutUpdate');
    if (!el) return;
    el.textContent = t('检查中…');
    try {
      const r = await fetch('https://api.github.com/repos/' + REPO + '/releases/latest',
                            {headers: {Accept: 'application/vnd.github+json'}});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const j = await r.json();
      const remote = String(j.tag_name || '').replace(/^v/, '');
      const cur = (context && context.version) || '';
      if (remote && cur && compareVer(remote, cur) > 0) {
        el.innerHTML = '<b class="upd-new">' + esc(t('发现新版本 v' + remote)) +
          '</b> · <a target="_blank" rel="noopener" href="https://github.com/' + REPO +
          '/releases/latest">' + esc(t('前往下载')) + '</a>';
      } else {
        el.textContent = t('已是最新') + (remote ? '（远端 v' + remote + '）' : '');
      }
    } catch (e) {
      el.textContent = t('检查失败') + ' (' + e.message + ')';
    }
  }
  $('#btnCheckUpdate').onclick = checkUpdate;
  // Privacy: start-up makes no external request. The user asks for a check.
  const updEl = $('#aboutUpdate');
  if (updEl) updEl.textContent = t('未检查') + ' · ' + t('点「检查更新」联网查询');

  // Export the raw-frame log as a JSON file download.
  $('#btnLogExport').onclick = async () => {
    try {
      const j = await api('/api/log');
      const blob = new Blob([JSON.stringify(j.items, null, 2)],
                            {type: 'application/json'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'shcp-log-' +
        new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-') + '.json';
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      toast(t('日志已导出'));
    } catch (e) {
      toast(t('导出失败'), true);
    }
  };

  $('#btnLdacInfo').onclick = () => {    const note = $('#ldacNote'), btn = $('#btnLdacInfo');
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
    drawEqCurve();
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
  document.documentElement.lang = LANG === 'en' ? 'en' : 'zh-CN';
  bind();
  watchLanguage();
  preloadPhotos();
  if (location.port && location.port !== '8765') {
    const hint = document.createElement('p');
    hint.className = 'hint portwarn';
    hint.textContent = '当前端口 ' + location.port +
      '（非默认）。已安装的 PWA 快捷方式指向旧端口，请重新安装。';
    const about = document.querySelector('#card-about .aboutbody');
    if (about) about.appendChild(hint);
  }
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
  // shows a frozen battery/ANC state - and a change made on the headset
  // itself (buttons, phone app) would take a minute to show up. While the
  // headset answers, mirror it every 8 s; offline, back off to 30 s so a
  // powered-off headset is not hammered with connect attempts. render()
  // skips identical snapshots, so nothing flickers.
  let lastPoll = 0;
  const idleRefresh = (force) => {
    if (document.hidden || acting || statusInFlight) return;
    const wait = (state && state.connected) ? 8000 : 30000;
    if (!force && Date.now() - lastPoll < wait) return;
    lastPoll = Date.now();
    loadStatus(false, true);
  };
  setInterval(idleRefresh, 2000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) idleRefresh(true);
  });
  window.addEventListener('focus', () => idleRefresh(true));

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

  // PWA installability: a no-op service worker is enough for Edge/Chrome to
  // offer "Install app", which gives the panel a chrome-less window.
  if ('serviceWorker' in navigator && /^https?:\/\/(127\.0\.0\.1|localhost)/.test(location.origin)) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
})();
