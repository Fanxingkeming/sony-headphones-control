#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sony Headphones Control Panel - local web UI for the reverse-engineered MDR protocol.

Zero third-party dependencies: Python standard library HTTP server + a single-page UI.
Reuses the already verified protocol layer in ../tools (tandem_client / xm4_control / linkbuds).

    python server.py            -> http://127.0.0.1:8765
    python server.py --port 9000

Windows AF_BTH RFCOMM only. The device accepts exactly one tandem client at a time,
so every operation is serialized under one lock and one persistent connection.
"""
import copy
import json
import os
import socketserver
import sys
import threading
import time
import traceback
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN = getattr(sys, "frozen", False)
# In a PyInstaller onefile build the HTML/CSS/JS live in the extraction dir.
ROOT = sys._MEIPASS if FROZEN else HERE
TOOLS = os.path.normpath(os.path.join(HERE, "..", "tools"))
sys.path.insert(0, TOOLS)

import tandem_client as tc          # noqa: E402
import xm4_control as xm4           # noqa: E402
import linkbuds as lb               # noqa: E402
import bt_presence as bt            # noqa: E402

UUID_V1 = (0x96CC203E, 0x5068, 0x46AD, (0xB3, 0x2D, 0xE3, 0x16, 0xF5, 0xE0, 0x69, 0xBA))
UUID_V2 = (0x956C7B26, 0xD49A, 0x4BA8, (0xB0, 0x3F, 0xB1, 0x7D, 0x39, 0x3C, 0xB6, 0xE2))

# When frozen, never write next to the exe (it may sit in Program Files).
if FROZEN:
    DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                            "SonyHeadphonesControl")
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except OSError:
        DATA_DIR = os.path.expanduser("~")
else:
    DATA_DIR = HERE
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEVICES = {
    "xm4": {
        "id": "xm4", "name": "WH-1000XM4", "short": "XM4", "protocol": "v1",
        "mac": "", "uuid": UUID_V1,
        "caps": ["anc", "level", "focus", "wind", "eq", "eqbands", "dsee", "quality",
                 "voice_write", "stc", "apo_full", "pause", "multipoint", "touch"],
    },
    "ls900n": {
        "id": "ls900n", "name": "LinkBuds S (WF-LS900N)", "short": "LS900N", "protocol": "v2",
        "mac": "", "uuid": UUID_V2,
        "caps": ["anc", "level", "focus", "eq", "eqbands", "dsee", "quality", "voice",
                 "stc", "stc_ext", "apo_two", "keys", "multipoint_ro", "battery_detail"],
    },
}


LAST_DEVICE = None                  # last headset that answered a real MDR handshake
# key -> colour dict. Persisted so a disconnected headset still shows the right
# official product render instead of falling back to another colourway.
CACHED_COLOR = {}


def load_config():
    global LAST_DEVICE
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    for key, dev in DEVICES.items():
        mac = cfg.get(key, {}).get("mac")
        if isinstance(mac, str) and len(mac.replace(":", "")) == 12:
            dev["mac"] = mac.upper()
        col = cfg.get(key, {}).get("color")
        if isinstance(col, dict) and isinstance(col.get("code"), int):
            CACHED_COLOR[key] = col
    if cfg.get("last_device") in DEVICES:
        LAST_DEVICE = cfg["last_device"]
    return cfg


def save_config():
    data = {}
    for k, d in DEVICES.items():
        entry = {"mac": d["mac"]}
        if CACHED_COLOR.get(k):
            entry["color"] = CACHED_COLOR[k]
        data[k] = entry
    if LAST_DEVICE:
        data["last_device"] = LAST_DEVICE
    # Write to a sibling temp file and rename: a crash mid-write must never
    # leave a truncated config.json, which would silently lose the MAC and the
    # cached colour on the next start.
    tmp = CONFIG_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONFIG_PATH)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def remember_color(key, color):
    if color and CACHED_COLOR.get(key) != color:
        CACHED_COLOR[key] = color
        save_config()


def remember_device(key):
    global LAST_DEVICE
    if key not in DEVICES or key == LAST_DEVICE:
        return
    LAST_DEVICE = key
    save_config()


load_config()

# ---------------------------------------------------------------------------
# Frame log: wrap the verified transfer helpers so the UI can show raw bytes.
# ---------------------------------------------------------------------------


class FrameLog:
    def __init__(self, limit=240):
        self.items = deque(maxlen=limit)
        self.lock = threading.Lock()

    def add(self, tx, rx, tag=""):
        name = tc.CMDS.get(tx[0], "0x%02x" % tx[0]) if tx else ""
        with self.lock:
            self.items.append({
                "t": time.strftime("%H:%M:%S"),
                "table": tag,
                "cmd": name,
                "tx": tx.hex(" ") if tx else "",
                "rx": rx.hex(" ") if rx else "(无响应)",
            })

    def dump(self):
        with self.lock:
            return list(self.items)


LOG = FrameLog()


def log_exception():
    """Windowed builds have no console; keep exceptions in the data dir."""
    try:
        with open(os.path.join(DATA_DIR, "error.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + traceback.format_exc() + "\n")
    except Exception:
        pass


_orig_request = tc.Client.request


def _logged_request(self, payload, dtype=tc.T1, wait=2.0, retries=1):
    r = _orig_request(self, payload, dtype=dtype, wait=wait, retries=retries)
    LOG.add(bytes(payload), r, "T2" if dtype == tc.T2 else "T1")
    return r


tc.Client.request = _logged_request

_orig_xfer = lb.xfer


def _logged_xfer(c, payload, want=None, wait=2.5):
    r = _orig_xfer(c, payload, want, wait)
    LOG.add(bytes(payload), r, "T1")
    return r


lb.xfer = _logged_xfer

_orig_t2 = lb.t2_cmd


def _logged_t2(c, payload, want=None, wait=2.2):
    r = _orig_t2(c, payload, want, wait)
    LOG.add(bytes(payload), r, "T2")
    return r


lb.t2_cmd = _logged_t2

# ---------------------------------------------------------------------------
# Connection: one persistent client, serialized. V2 uses the V2 service UUID
# with SDP (verified); channel 9 is only a fallback.
# ---------------------------------------------------------------------------


class Session:
    def __init__(self):
        self.lock = threading.RLock()
        self.key = None
        self.client = None
        self.error = None

    def dispose(self):
        c, self.client = self.client, None
        self.key = None
        if c is not None:
            try:
                tc.ws2.closesocket(c.sock)
            except Exception:
                pass

    def get(self, key, force=False):
        with self.lock:
            if not force and self.key == key and self.client is not None:
                return self.client
            self.dispose()
            c = do_connect(DEVICES[key])
            self.client, self.key, self.error = c, key, None
            return c

    def fail(self, exc):
        self.error = str(exc)
        self.dispose()


SESSION = Session()

# A status snapshot costs a dozen round trips on a single RFCOMM link, so a
# short window is shared by the UI poll, a manual refresh and the read-back
# after a write. Any state-changing POST invalidates it.
STATUS_CACHE = {"key": None, "at": 0.0, "state": None}
STATUS_TTL = 2.0

# When the headset is off, every status read costs a full connect attempt.
# A short cool-down keeps the UI from re-paying that on every poll; an explicit
# refresh (?fresh=1) bypasses it.
STATUS_FAIL = {"until": 0.0}
STATUS_FAIL_COOLDOWN = 3.0


def same_origin(host, origin, site, port):
    """True only for requests issued by the local panel itself.

    The service is unauthenticated and listens on loopback, so without this any
    page open in the same browser could POST to 127.0.0.1 and toggle the
    headset. A DNS-rebinding page would additionally arrive with a foreign Host
    header, which the host check rejects.
    """
    hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}
    if host and host.lower() not in hosts:
        return False
    if origin:
        return origin in ("http://127.0.0.1:%d" % port,
                          "http://localhost:%d" % port)
    return site in (None, "same-origin", "none")


def do_connect(dev, quick=False):
    """Open the MDR link. `quick` is used by device discovery: short socket
    timeouts and fewer INIT retries, so a headset that is off/occupied fails
    in ~1-2 s instead of ~10 s. Established links are unaffected.
    """
    tc.SONY_UUID = dev["uuid"]
    last = None
    c = None
    # LinkBuds S never resolves through the SDP path in practice (verified:
    # SDP fails, the fixed channel answers), and an SDP connect can block for
    # tens of seconds inside Winsock before our own timeout applies. So the v2
    # device is pinned to channel 9 and never falls back to SDP. The XM4 needs
    # SDP, with channel 9 as a fallback.
    if dev["protocol"] == "v2":
        channels = (9,)
    elif quick:
        channels = (0,)
    else:
        channels = (0, 9)
    for channel in channels:
        try:
            c = tc.Client(dev["mac"], channel, timeout=1.2 if quick else 5.0)
            break
        except Exception as e:
            last = e
            try:
                tc.SONY_UUID = dev["uuid"]
            except Exception:
                pass
    if c is None:
        raise OSError(
            "%s：%s。确认耳机已开机、已从充电盒取出，且手机上的 Sound Connect 已完全退出。"
            % (dev["name"], last))

    if dev["protocol"] == "v2":
        init = None
        for _ in range(2 if quick else 5):
            init = c.request(b"\x00\x00", wait=1.0 if quick else 2.5, retries=0)
            if init:
                break
            time.sleep(0.2 if quick else 0.7)
        if not init:
            tc.ws2.closesocket(c.sock)
            raise OSError("INIT 无响应：设备可能被手机 App 占用，或已进入休眠。")
        if len(init) != 8:
            tc.ws2.closesocket(c.sock)
            raise OSError("INIT 返回 %d 字节，不是预期的 v2 设备（应为 8 字节）" % len(init))
        c.request(b"\x02\x00", wait=2.0, retries=0)
        time.sleep(0.2)
        c.request(b"\x06\x00", wait=2.0, retries=0)
        time.sleep(0.2)
        c.request(b"\x06\x00", dtype=tc.T2, wait=1.5, retries=0)
    return c


# ---------------------------------------------------------------------------
# "Which headset is this?" - decided by a real MDR handshake, not by the
# Windows pairing list. Both headsets can be paired/connected at the same
# time, but only the one that answers CONNECT_GET_PROTOCOL_INFO is the one the
# panel controls, so only that one is ever shown in the UI.
# ---------------------------------------------------------------------------

NAME_HINTS = {
    "xm4": ("wh-1000xm4", "wh1000xm4", "1000xm4", "xm4"),
    "ls900n": ("linkbuds s", "wf-ls900n", "wfls900n", "linkbuds"),
}
PROBE_TTL = 20.0                    # seconds between automatic re-probes
CURRENT_LOCK = threading.RLock()
CURRENT = {"key": None, "at": 0.0, "status": "offline", "probe": "",
           "online": [], "alternatives": 0, "color": None}

# Colour instruction demo fallback. The real value comes from the headset via
# CONNECT_GET_DEVICE_INFO / SERIES_AND_COLOR_INFO (04 03) after each handshake.
# 05 03 60 02 = LINK_BUDS (0x60) + ModelColor.WHITE (0x02).
DEMO_COLOR = {
    "ls900n": lb.parse_series_color(bytes([0x05, 0x03, 0x60, 0x02])),
}


def public_device(key):
    d = DEVICES[key]
    return {"id": d["id"], "name": d["name"], "short": d["short"],
            "protocol": d["protocol"], "mac": d["mac"], "caps": d["caps"]}


def read_device_color(key, c):
    """CONNECT_GET_DEVICE_INFO / SERIES_AND_COLOR_INFO: 04 03 -> 05 03 ...

    v2 replies with <series> <color>; v1 omits the series byte. A headset that
    does not implement this device-info type returns None and the UI simply
    hides the colour rows instead of guessing.
    """
    proto = DEVICES[key]["protocol"]
    # v1 also defines SERIES_AND_COLOR_INFO (0x03), but the reply shape has
    # not been verified on our XM4. Skip it so the fast v1 handshake stays
    # fast; parse_series_color() already understands the 3-byte v1 form when
    # a capture becomes available.
    if proto != "v2":
        return None
    try:
        raw = lb.xfer(c, bytes([0x04, 0x03]), wait=0.8)
    except Exception:
        return None
    return lb.parse_series_color(raw, proto)


def _bt_rows():
    try:
        s = bt.scan()
        return s.get("devices", []) if s.get("available") else []
    except Exception:
        return []


def _online_keys(rows):
    """Known Bluetooth devices that map onto our two supported models.

    Also repairs a stale configured MAC when the same headset shows up under a
    different address (Windows can renumber a re-paired device).
    """
    found = []
    for key, dev in DEVICES.items():
        hit = None
        for r in rows:
            if r.get("mac", "").upper() == dev["mac"].upper():
                hit = r
                break
        if hit is None:
            hints = NAME_HINTS[key]
            connected = [r for r in rows
                         if any(h in (r.get("name") or "").lower() for h in hints)
                         and (r.get("connected") or r.get("remembered"))]
            if len(connected) == 1:
                hit = connected[0]
        if hit is None:
            continue
        found.append(key)
        new_mac = hit.get("mac", "").upper()
        if new_mac and new_mac != dev["mac"]:
            dev["mac"] = new_mac
            save_config()
    return found


def _set_current(key, status, probe, online):
    CURRENT.update({
        "key": key, "at": time.monotonic(), "status": status,
        "probe": probe, "online": list(online),
        "alternatives": len([k for k in online if k != key]),
    })
    return key


def probe_device(prefer=None, force=False, quiet=False, single=False):
    """Return the key of the headset that actually answered an MDR handshake.

    A successful probe keeps the live socket in SESSION, so the following
    /api/status request is instant. Failed candidates leave the existing
    session untouched.
    """
    global LAST_DEVICE
    with CURRENT_LOCK:
        now = time.monotonic()
        if not force and SESSION.client is not None and SESSION.key in DEVICES:
            return _set_current(SESSION.key, "connected", "会话已建立",
                                CURRENT["online"] or list(DEVICES))
        if quiet and not force and CURRENT["key"] and now - CURRENT["at"] < PROBE_TTL:
            return CURRENT["key"]
        if not force and CURRENT["key"] and now - CURRENT["at"] < PROBE_TTL:
            return CURRENT["key"]

        rows = _bt_rows()
        online = _online_keys(rows) or list(DEVICES)
        order = []
        for k in (prefer, SESSION.key, LAST_DEVICE, CURRENT["key"]):
            if k in DEVICES and k not in order:
                order.append(k)
        for k in online + list(DEVICES):
            if k not in order:
                order.append(k)
        if single and prefer in DEVICES:
            order = [prefer]

        errors = []
        CURRENT["color"] = None
        # A forced re-probe must drop the old link first, otherwise Windows
        # returns WSAEADDRINUSE (10048) for the same RFCOMM address.
        if force:
            with SESSION.lock:
                SESSION.dispose()
        with SESSION.lock:
            for key in order:
                try:
                    c = do_connect(DEVICES[key], quick=True)
                except Exception as e:
                    errors.append("%s: %s" % (DEVICES[key]["short"], str(e)[:70]))
                    continue
                old, skey = SESSION.client, key
                SESSION.client, SESSION.key, SESSION.error = c, skey, None
                if old is not None and old is not c:
                    try:
                        tc.ws2.closesocket(old.sock)
                    except Exception:
                        pass
                remember_device(skey)
                # Colour is part of device identity. Read it once per
                # handshake and cache it, so /api/context can select the
                # matching official product render without another round trip.
                try:
                    CURRENT["color"] = read_device_color(skey, c)
                except Exception:
                    CURRENT["color"] = None
                if CURRENT["color"]:
                    remember_color(skey, CURRENT["color"])
                return _set_current(skey, "connected", "%s 握手成功" % DEVICES[skey]["short"],
                                    online)

        # Nothing answered: keep the last known headset so the panel is still
        # usable (it will fall back to demo data with a clear explanation).
        fallback = CURRENT["key"] or LAST_DEVICE or (online[0] if online else "xm4")
        return _set_current(fallback, "offline", "未建立连接；" + " / ".join(errors), online)


def current_context(demo=False, want=None, force=False, quiet=False):
    if demo:
        key = want if want in DEVICES else (LAST_DEVICE or "xm4")
        return {"ok": True, "device": public_device(key), "status": "demo",
                "alternatives": len(DEVICES) - 1, "probe": "演示模式",
                "color": DEMO_COLOR.get(key) or CACHED_COLOR.get(key),
                "online": [public_device(k)["short"] for k in DEVICES]}
    key = probe_device(prefer=want if force else None, force=force, quiet=quiet)
    return {"ok": True, "device": public_device(key), "status": CURRENT["status"],
            "alternatives": CURRENT["alternatives"], "probe": CURRENT["probe"],
            "color": CURRENT.get("color") or CACHED_COLOR.get(key),
            "online": [DEVICES[k]["short"] for k in CURRENT["online"]]}


def switch_device(demo=False):
    """Move to the other headset. Never shows a two-item chooser in the UI."""
    cur = CURRENT["key"] or LAST_DEVICE or "xm4"
    keys = list(DEVICES)
    nxt = keys[(keys.index(cur) + 1) % len(keys)]
    if demo:
        return current_context(demo=True, want=nxt)
    with SESSION.lock:
        SESSION.dispose()             # only one tandem client may exist at a time
    key = probe_device(prefer=nxt, force=True, single=True)
    if key != nxt or CURRENT["status"] != "connected":
        err = "无法连接 %s：%s" % (DEVICES[nxt]["name"], CURRENT["probe"])
        # Restore the original headset so a failed switch never leaves the
        # panel without a live session.
        with SESSION.lock:
            SESSION.dispose()
        try:
            probe_device(prefer=cur, force=True, single=True)
        except Exception:
            pass
        return {"ok": False, "error": err, "context": current_context(quiet=True)}
    return current_context(quiet=True)


# ---------------------------------------------------------------------------
# State reading. Both devices are normalized into one shape for the UI.
# ---------------------------------------------------------------------------


def empty_state(key):
    dev = DEVICES[key]
    return {
        "device": key, "name": dev["name"], "protocol": dev["protocol"],
        "mac": dev["mac"], "caps": dev["caps"], "connected": False, "demo": False,
        "info": {"model": dev["short"], "firmware": "?", "codec": "?",
                 "series": "", "color": None},
        "battery": {"main": None, "left": None, "right": None, "case": None},
        "anc": {"mode": "?", "level": 0, "focus": False},
        "eq": {"preset": "?", "bands": [0, 0, 0, 0, 0, 0]},
        "sound": {"dsee": None, "quality": "?", "voice": None},
        "system": {"stc": None, "apo": "?", "pause": None, "wind": None,
                   "touch": None, "multipoint": None, "multipoint_ro": False,
                   "keys": {"left": None, "right": None},
                   "stc_ext": {"sensitivity": "?", "off_time": "?"}},
    }


EQ_NAME_V1 = {v: k for k, v in xm4.EQ_PRESETS.items()}
EQ_NAME_V2 = {v: k for k, v in lb.EQ_PRESETS.items()}
APO_NAME_V1 = {v: k for k, v in xm4.AUTO_POWER_OFF.items()}


def read_status_v1(c):
    s = empty_state("xm4")
    r = c.request(b"\x10\x00")
    if r and len(r) >= 3:
        s["battery"]["main"] = r[2]
    s["info"]["firmware"] = xm4._version(c) or "?"
    s["info"]["codec"] = xm4._codec(c) or "?"

    def flag(hexstr):
        v = c.request(bytes.fromhex(hexstr))
        return (v[-1] if v and len(v) >= 2 else None)

    r = c.request(bytes.fromhex("6602"))
    if r and len(r) >= 8:
        if r[2] == 0x00:
            s["anc"]["mode"] = "off"
        else:
            s["anc"]["mode"] = {0x00: "ambient", 0x01: "wind", 0x02: "nc"}.get(r[4], "?")
        s["anc"]["focus"] = bool(r[6])
        s["anc"]["level"] = r[7]

    r = c.request(bytes.fromhex("5601"))
    if r and len(r) >= 10:
        s["eq"]["preset"] = EQ_NAME_V1.get(r[2], "0x%02x" % r[2])
        s["eq"]["bands"] = [b - 10 for b in r[4:10]]

    d = flag("e602")
    s["sound"]["dsee"] = None if d is None else bool(d)
    q = flag("e601")
    s["sound"]["quality"] = "stable" if q == 1 else ("hifi" if q == 0 else "?")
    s["sound"]["voice"] = None                      # v1: write-only, no known read-back

    s["system"]["stc"] = _b(flag("f605"))
    s["system"]["pause"] = _b(flag("f603"))
    s["system"]["touch"] = _b(flag("d6d1"))
    s["system"]["multipoint"] = _b(flag("d6d2"))
    r = c.request(bytes.fromhex("f604"))
    if r and len(r) >= 5:
        s["system"]["apo"] = APO_NAME_V1.get((r[3], r[4]), "?")
    return s


def _b(v):
    return None if v is None else bool(v)


def read_status_v2(c):
    s = empty_state("ls900n")
    s["info"]["model"] = lb.read_model(c) or "LinkBuds S"
    s["info"]["firmware"] = lb.read_fw(c) or "?"
    s["info"]["codec"] = lb.read_codec(c) or "?"
    s["info"]["series"] = lb.read_series(c) or ""

    b = lb.read_battery(c)
    s["battery"] = {"main": b.get("整体"), "left": b.get("左"),
                    "right": b.get("右"), "case": b.get("充电盒")}

    a = lb.read_anc(c)
    if a:
        s["anc"]["mode"] = ("off" if a["effect"] == 0
                            else {0: "nc", 1: "ambient"}.get(a["mode"], "?"))
        s["anc"]["focus"] = bool(a["focus"])
        s["anc"]["level"] = a["level"]

    preset, bands = lb.read_eq(c)
    if preset is not None:
        s["eq"]["preset"] = EQ_NAME_V2.get(preset, "0x%02x" % preset)
    if bands is not None:
        s["eq"]["bands"] = bands

    d = lb.read_dsee(c)
    s["sound"]["dsee"] = None if d is None else bool(d)
    q = lb.read_quality(c)
    s["sound"]["quality"] = "stable" if q == 1 else ("hifi" if q == 0 else "?")
    # T2 voice guidance status: 42 01 00 -> 43 01 00 <00=ON|01=OFF>
    v = lb.t2_cmd(c, bytes([0x42, 0x01, 0x00]), want=0x43, wait=1.8)
    s["sound"]["voice"] = (v[3] == 0x00) if v and len(v) >= 4 else None

    s["system"]["stc"] = lb.read_stc(c)
    a = lb.read_apo(c)
    s["system"]["apo"] = {0x10: "takenoff", 0x11: "off"}.get(a, "?")
    m = lb.read_multi(c)
    s["system"]["multipoint"] = None if m is None else bool(m)
    s["system"]["multipoint_ro"] = True
    lk, rk = lb.read_keys(c)
    s["system"]["keys"] = {"left": lk, "right": rk}
    ext = lb.read_stc_ext(c)
    if ext:
        s["system"]["stc_ext"] = {
            "sensitivity": lb.SENS_NAME.get(ext["sensitivity"], str(ext["sensitivity"])),
            "off_time": lb.OFFTIME_NAME.get(ext["off_time"], str(ext["off_time"])),
        }
    return s


def read_status(key, c):
    s = read_status_v1(c) if DEVICES[key]["protocol"] == "v1" else read_status_v2(c)
    s["connected"] = True
    s["info"]["color"] = CURRENT.get("color") or CACHED_COLOR.get(key)
    return s


# ---------------------------------------------------------------------------
# Demo data: fully interactive UI without a live device.
# ---------------------------------------------------------------------------

DEMO = {
    "xm4": {
        "info": {"model": "WH-1000XM4", "firmware": "2.5.0", "codec": "LDAC",
                 "series": "", "color": None},
        "battery": {"main": 68, "left": None, "right": None, "case": None},
        "anc": {"mode": "nc", "level": 12, "focus": False},
        "eq": {"preset": "bass", "bands": [4, 2, 0, -1, -2, 0]},
        "sound": {"dsee": True, "quality": "hifi", "voice": None},
        "system": {"stc": False, "apo": "30min", "pause": True, "wind": False,
                   "touch": True, "multipoint": True, "multipoint_ro": False,
                   "keys": {"left": None, "right": None},
                   "stc_ext": {"sensitivity": "?", "off_time": "?"}},
    },
    "ls900n": {
        "info": {"model": "LinkBuds S", "firmware": "2.0.2", "codec": "AAC",
                 "series": "series=0x60 color=0x02",
                 "color": DEMO_COLOR["ls900n"]},
        "battery": {"main": 90, "left": 92, "right": 88, "case": 74},
        "anc": {"mode": "ambient", "level": 8, "focus": True},
        "eq": {"preset": "off", "bands": [0, 0, 0, 0, 0, 0]},
        "sound": {"dsee": False, "quality": "stable", "voice": True},
        "system": {"stc": True, "apo": "takenoff", "pause": None, "wind": None,
                   "touch": None, "multipoint": True, "multipoint_ro": True,
                   "keys": {"left": 0x20, "right": 0x35},
                   "stc_ext": {"sensitivity": "auto", "off_time": "mid"}},
    },
}


def demo_state(key):
    s = empty_state(key)
    src = copy.deepcopy(DEMO[key])
    for k, v in src.items():
        s[k] = v
    s["connected"] = False
    s["demo"] = True
    return s


def demo_action(key, action, value):
    """Mutate the in-memory demo state so every control is demonstrable."""
    d = DEMO[key]
    a, e, snd, sysd = d["anc"], d["eq"], d["sound"], d["system"]
    if action == "anc_mode":
        a["mode"] = value
    elif action == "anc_level":
        a["level"] = int(value)
    elif action == "focus":
        a["focus"] = bool(value)
    elif action == "eq_preset":
        e["preset"] = value
    elif action == "eq_bands":
        e["bands"] = [int(x) for x in value]
        e["preset"] = "custom"
    elif action == "dsee":
        snd["dsee"] = bool(value)
    elif action == "quality":
        snd["quality"] = value
    elif action == "voice":
        snd["voice"] = bool(value)
    elif action == "stc":
        sysd["stc"] = bool(value)
    elif action == "apo":
        sysd["apo"] = value
    elif action == "pause":
        sysd["pause"] = bool(value)
    elif action == "touch":
        sysd["touch"] = bool(value)
    elif action == "multipoint":
        sysd["multipoint"] = bool(value)
    elif action == "wind":
        a["mode"] = "wind"
    elif action == "keys":
        sysd["keys"] = {"left": lb.KEY_PRESETS[value["left"]],
                        "right": lb.KEY_PRESETS[value["right"]]}
    elif action == "stc_ext":
        sysd["stc_ext"].update(value)
    return "演示模式：已更新界面（未向设备发送任何数据）"


# ---------------------------------------------------------------------------
# Actions. Everything is read back after a write; no "success" is reported
# from an echo alone.
# ---------------------------------------------------------------------------

KEY_NAME = {v: k for k, v in lb.KEY_PRESETS.items()}


def apply_action(key, c, action, value):
    v1 = DEVICES[key]["protocol"] == "v1"
    msg = "已执行"
    reconnect = False

    if action == "anc_mode":
        if v1:
            if value == "off":
                p = bytes.fromhex("6802000202010000")
            elif value == "nc":
                p = bytes.fromhex("6802110202010000")
            else:
                lv = c.request(bytes.fromhex("6602"))
                level = lv[7] if lv and len(lv) >= 8 else 20
                p = bytes([0x68, 0x02, 0x11, 0x02, 0x00, 0x01, 0x00, level])
            c.request(p)
        else:
            if value == "off":
                lb.set_off(c)
            else:
                lb.set_anc(c, mode=0x00 if value == "nc" else 0x01)
        msg = {"nc": "已切换到降噪", "ambient": "已切换到环境声",
               "off": "已关闭降噪处理"}.get(value, "已切换")

    elif action == "anc_level":
        lv = max(0, min(20, int(value)))
        if v1:
            r = c.request(bytes.fromhex("6602"))
            if r and len(r) >= 8:
                p = bytearray(r)
                p[0], p[7] = 0x68, lv
                c.request(bytes(p))
        else:
            lb.set_anc(c, level=lv)
        msg = "环境声等级 → %d" % lv

    elif action == "focus":
        on = bool(value)
        if v1:
            r = c.request(bytes.fromhex("6602"))
            if r and len(r) >= 8:
                p = bytearray(r)
                p[0], p[6] = 0x68, (1 if on else 0)
                c.request(bytes(p))
        else:
            lb.set_anc(c, focus=1 if on else 0)
        msg = "关注语音 → %s" % ("开" if on else "关")

    elif action == "wind":
        r = c.request(bytes.fromhex("6602"))
        if r and len(r) >= 8:
            p = bytearray(r)
            p[0], p[2], p[4] = 0x68, 0x11, 0x01
            c.request(bytes(p))
        msg = "已启用风噪降低"

    elif action == "eq_preset":
        if v1:
            c.request(bytes([0x58, 0x01, xm4.EQ_PRESETS[value], 0x00]))
        else:
            lb.xfer(c, bytes([0x58, 0x00, lb.EQ_PRESETS[value], 0x00]))
        time.sleep(0.5)
        msg = "EQ 预设 → %s" % value

    elif action == "eq_bands":
        vals = [max(-10, min(10, int(x))) for x in value][:6]
        if v1:
            c.request(bytes([0x58, 0x01, 0xFF, 0x06] + [v + 10 for v in vals]))
        else:
            lb.set_eqbands(c, vals)
        time.sleep(0.5)
        msg = "自定义 EQ 已写入并读回"

    elif action == "dsee":
        on = bool(value)
        if v1:
            c.request(bytes([0xE8, 0x02, 0x00, 1 if on else 0]))
        else:
            lb.set_dsee(c, on)
        msg = "DSEE Extreme → %s" % ("自动" if on else "关")

    elif action == "quality":
        stable = value == "stable"
        if v1:
            c.request(bytes([0xE8, 0x01, 0x00, 1 if stable else 0]))
        else:
            lb.set_quality(c, stable)
        msg = "连接模式 → %s" % ("稳定优先" if stable else "音质优先")

    elif action == "voice":
        on = bool(value)
        if v1:
            c.request(bytes([0x48, 0x01, 0x01, 1 if on else 0]), dtype=tc.T2)
            msg = "语音向导写入（v1 无读回，请用 App 确认）"
        else:
            lb.set_voice(c, on)
            msg = "通知和语音向导 → %s" % ("开" if on else "关")

    elif action == "stc":
        on = bool(value)
        if v1:
            c.request(bytes([0xF8, 0x05, 0x01, 1 if on else 0]))
        else:
            lb.set_stc(c, on)
        msg = "智能免摘 / 智能对话 → %s" % ("开" if on else "关")

    elif action == "apo":
        if v1:
            c0, c1 = xm4.AUTO_POWER_OFF[value]
            c.request(bytes([0xF8, 0x04, 0x01, c0, c1]))
        else:
            lb.set_apo(c, 0x10 if value == "takenoff" else 0x11)
        msg = "自动断电 → %s" % value

    elif action == "pause":
        c.request(bytes([0xF8, 0x03, 0x01, 1 if bool(value) else 0]))
        msg = "取下暂停 → %s" % ("开" if value else "关")

    elif action == "touch":
        c.request(bytes([0xD8, 0xD1, 0x01, 1 if bool(value) else 0]))
        msg = "触摸面板 → %s" % ("开" if value else "关")

    elif action == "multipoint":
        if v1:
            # 94 01 00 gates the write; 99/98 handshake must be answered.
            xm4._enable_alerts(c)
            alerts = xm4._write_with_alert(c, bytes([0xD8, 0xD2, 0x01, 1 if bool(value) else 0]))
            reconnect = True
            msg = "多点连接写入完成（设备将断开重连）。收到 %d 条告警并已应答。" % len(alerts)
        else:
            return None, "LinkBuds S 的多点连接是只读的，设备不接受写入", False

    elif action == "keys":
        l = lb.KEY_PRESETS[value["left"]]
        r = lb.KEY_PRESETS[value["right"]]
        lb.set_key(c, left=l, right=r)
        msg = "按键分配 → 左 %s / 右 %s" % (value["left"], value["right"])

    elif action == "stc_ext":
        sens = value.get("sensitivity")
        oft = value.get("off_time")
        lb.set_stc_ext(c, sens if sens in lb.SENS else None,
                       oft if oft in lb.OFFTIME else None)
        msg = "智能对话扩展参数已写入"

    else:
        return None, "未知操作：%s" % action, False

    return True, msg, reconnect


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

STATIC = {"": "index.html", "/": "index.html", "/index.html": "index.html",
          "/style.css": "style.css", "/app.js": "app.js",
          "/favicon.ico": "assets/placeholder.svg"}
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp",
        ".ico": "image/x-icon"}
ASSET_OK = {"xm4.svg", "ls900n.svg", "xm4.png", "ls900n.png",
            "ls900n_w.png", "sony-logo.svg", "app-icon.ico",
            "placeholder.svg"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _file(self, name):
        if name.startswith("assets/") and name.split("/")[-1] not in ASSET_OK:
            self.send_error(404)
            return
        path = os.path.join(ROOT, name)
        if not os.path.isfile(path):
            self.send_error(404)
            return
        ext = os.path.splitext(name)[1]
        data = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        if p in STATIC:
            f = STATIC[p]
            if f is None:
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self._file(f)
            return
        if p.startswith("/assets/") and p.rsplit("/", 1)[-1] in ASSET_OK:
            self._file("assets/" + p.rsplit("/", 1)[-1])
            return
        if p == "/api/context":
            ctx = current_context(
                demo=q.get("demo", ["0"])[0] == "1",
                want=q.get("device", [None])[0],
                force=q.get("force", ["0"])[0] == "1",
                quiet=q.get("quiet", ["0"])[0] == "1")
            self._json(ctx)
            return
        if p == "/api/devices":
            # Legacy/debug endpoint: the panel itself only ever uses /api/context.
            online = _online_keys(_bt_rows())
            self._json({"ok": True, "devices": [
                dict(public_device(k), online=(k in online),
                     current=(k == CURRENT["key"])) for k in DEVICES],
                "current": CURRENT["key"]})
            return
        if p == "/api/log":
            self._json({"ok": True, "items": LOG.dump()})
            return
        if p == "/api/status":
            key = q.get("device", [CURRENT["key"] or LAST_DEVICE or "xm4"])[0]
            if key not in DEVICES:
                self._json({"ok": False, "error": "未知设备"}, 400)
                return
            if q.get("demo", ["0"])[0] == "1":
                self._json({"ok": True, "state": demo_state(key)})
                return
            fresh = q.get("fresh", ["0"])[0] == "1"
            if not fresh and time.monotonic() < STATUS_FAIL["until"]:
                self._json({"ok": False, "error": "设备暂时不可达",
                            "hint": "耳机开机并连上后点「↻ 刷新」重试。"})
                return
            now = time.monotonic()
            if (not fresh and STATUS_CACHE["key"] == key
                    and STATUS_CACHE["state"] is not None
                    and now - STATUS_CACHE["at"] < STATUS_TTL):
                self._json({"ok": True, "state": STATUS_CACHE["state"]})
                return
            try:
                with SESSION.lock:
                    c = SESSION.get(key)
                    try:
                        st = read_status(key, c)
                    except Exception:
                        # Retry only when a live link existed and broke mid-read.
                        # If the connect itself failed there is nothing to
                        # retry, and a second attempt would just double the
                        # offline wait (observed 5 s -> 10 s).
                        if SESSION.client is None:
                            raise
                        c = SESSION.get(key, force=True)
                        st = read_status(key, c)
                STATUS_CACHE.update({"key": key, "at": time.monotonic(),
                                     "state": st})
                self._json({"ok": True, "state": st})
            except Exception as e:
                STATUS_CACHE["state"] = None
                STATUS_FAIL["until"] = time.monotonic() + STATUS_FAIL_COOLDOWN
                SESSION.fail(e)
                self._json({"ok": False, "error": str(e),
                            "hint": "耳机开机、从盒中取出，并在手机上完全退出 Sound Connect 后重试；"
                                    "也可以切到演示模式查看完整界面。"})
            return
        self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)
        p = u.path
        if not same_origin(self.headers.get("Host"), self.headers.get("Origin"),
                           self.headers.get("Sec-Fetch-Site"),
                           self.server.server_port):
            self._json({"ok": False, "error": "已拒绝跨站请求"}, 403)
            return
        STATUS_CACHE["state"] = None          # a write invalidates the snapshot
        n = int(self.headers.get("Content-Length", "0") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            self._json({"ok": False, "error": "请求体不是合法 JSON"}, 400)
            return

        if p == "/api/config":
            key, mac = body.get("device"), str(body.get("mac", "")).strip().upper()
            if key not in DEVICES or len(mac.replace(":", "")) != 12:
                self._json({"ok": False, "error": "设备或 MAC 格式不正确"}, 400)
                return
            try:
                int(mac.replace(":", ""), 16)
            except ValueError:
                self._json({"ok": False, "error": "MAC 含非法字符"}, 400)
                return
            DEVICES[key]["mac"] = mac
            save_config()
            SESSION.dispose()
            self._json({"ok": True, "mac": mac})
            return

        if p == "/api/disconnect":
            SESSION.dispose()
            self._json({"ok": True})
            return

        if p == "/api/switch":
            result = switch_device(demo=bool(body.get("demo")))
            self._json(result, 200 if result.get("ok", True) else 409)
            return

        if p == "/api/action":
            key = body.get("device") or CURRENT["key"] or LAST_DEVICE or "xm4"
            action, value = body.get("action"), body.get("value")
            if key not in DEVICES:
                self._json({"ok": False, "error": "未知设备"}, 400)
                return
            if body.get("demo"):
                msg = demo_action(key, action, value)
                self._json({"ok": True, "message": msg, "state": demo_state(key)})
                return
            try:
                with SESSION.lock:
                    c = SESSION.get(key)
                    ok, msg, reconnect = apply_action(key, c, action, value)
                    if not ok:
                        self._json({"ok": False, "error": msg})
                        return
                    if reconnect:
                        SESSION.dispose()
                        self._json({"ok": True, "message": msg, "state": None,
                                    "reconnect": True})
                        return
                    st = read_status(key, c)
                self._json({"ok": True, "message": msg, "state": st})
            except Exception as e:
                SESSION.fail(e)
                log_exception()
                self._json({"ok": False, "error": "操作失败：%s" % e,
                            "hint": "连接可能已断开。点「重新连接」或切到演示模式。"})
            return

        self.send_error(404)


class LocalHTTPServer(ThreadingHTTPServer):
    """Loopback-only server.

    HTTPServer.server_bind normally calls socket.getfqdn(), which encodes the
    hostname with the `idna` codec (and drags in unicodedata + libcrypto via
    ssl). We never need a FQDN here, so set it from the bound address instead.
    Disabling SO_REUSEADDR also stops a second copy from silently hijacking
    the port on Windows.
    """

    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name, self.server_port = host, port


def create_server(port=8765, tries=12):
    """Bind 127.0.0.1 on the first free port. Returns (server, port)."""
    for p in range(port, port + tries):
        try:
            return LocalHTTPServer(("127.0.0.1", p), Handler), p
        except OSError:
            continue
    return None, None


def warmup():
    """Resolve the connected headset in the background as soon as the app
    starts, so the first browser request to /api/context is a cache hit.
    """
    def run():
        try:
            probe_device(force=True)
        except Exception:
            pass
    threading.Thread(target=run, name="mdr-warmup", daemon=True).start()


def start_server(port=8765, tries=12):
    """Start the HTTP server on a daemon thread (used by the tray entry point)."""
    srv, bound = create_server(port, tries)
    if srv is None:
        raise OSError("无法绑定端口（%d-%d 都被占用）" % (port, port + tries - 1))
    srv.daemon_threads = True
    t = threading.Thread(target=srv.serve_forever,
                         kwargs={"poll_interval": 0.2}, name="mdr-http", daemon=True)
    t.start()
    warmup()
    return srv, bound


def stop_server(srv):
    if srv is None:
        return
    with SESSION.lock:
        SESSION.dispose()
    try:
        srv.shutdown()
        srv.server_close()
    except Exception:
        pass


def main():
    port = 8765
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (ValueError, IndexError):
            pass
    srv, port = create_server(port)
    if srv is None:
        print("无法绑定端口（%d-%d 都被占用）" % (port, port + 11))
        return
    srv.daemon_threads = True
    warmup()
    url = "http://127.0.0.1:%d" % port
    print("Sony Headphones Control Panel")
    print("  打开: " + url)
    print("  演示: " + url + "/?demo=1")
    print("  设备:")
    for d in DEVICES.values():
        print("    %-8s %-26s %-4s %s" % (d["short"], d["name"], d["protocol"], d["mac"]))
    print("  Ctrl+C 退出")
    if "--open" in sys.argv:
        import tray
        threading.Timer(1.2, lambda: tray.open_panel(url)).start()
    try:
        srv.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop_server(srv)


if __name__ == "__main__":
    main()
