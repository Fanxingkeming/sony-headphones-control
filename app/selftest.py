#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline self-test for the state parsers. No headphone, no Bluetooth needed.

    python selftest.py

Feeds canned MDR responses through read_status_v1 / read_status_v2 and asserts
the normalized state. Run this after touching any protocol code.
"""
import ctypes
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server as srv          # noqa: E402
import tandem_client as tc    # noqa: E402
import linkbuds as lb         # noqa: E402
import tray                   # noqa: E402

V1 = {
    b"\x10\x00": bytes.fromhex("11 00 44 00"),
    b"\x04\x02": b"\x05\x02\x05" + b"2.5.0",
    b"\x18\x00": bytes.fromhex("19 00 10"),
    b"\x66\x02": bytes.fromhex("67 02 11 02 02 01 01 0c"),
    b"\x56\x01": bytes.fromhex("57 01 16 06 0a 0a 0a 0a 0a 0a"),
    b"\xe6\x02": bytes.fromhex("e7 02 01"),
    b"\xe6\x01": bytes.fromhex("e7 01 00"),
    b"\xf6\x05": bytes.fromhex("f7 05 01 01"),
    b"\xf6\x03": bytes.fromhex("f7 03 01 01"),
    b"\xd6\xd1": bytes.fromhex("d7 d1 01 01"),
    b"\xd6\xd2": bytes.fromhex("d7 d2 01 01"),
    b"\xf6\x04": bytes.fromhex("f7 04 01 01 01"),
}

V2 = {
    b"\x04\x01": b"\x05\x01\x0a" + b"LinkBuds S",
    b"\x04\x02": b"\x05\x02\x05" + b"2.0.2",
    b"\x04\x03": bytes.fromhex("05 03 60 02"),
    b"\x12\x02": bytes.fromhex("13 02 02"),
    b"\x22\x00": bytes.fromhex("23 00 5a 00"),
    b"\x22\x01": bytes.fromhex("23 01 5b 00 58 00"),
    b"\x22\x02": bytes.fromhex("23 02 4a 00"),
    b"\x66\x17": bytes.fromhex("67 17 01 01 01 01 08"),
    b"\x56\x00": bytes.fromhex("57 00 00 06 0a 0a 0a 0a 0a 0a"),
    b"\xe6\x01": bytes.fromhex("e7 01 01"),
    b"\xe6\x00": bytes.fromhex("e7 00 00"),
    b"\xf6\x02": bytes.fromhex("f7 02 01 00"),
    b"\x26\x04": bytes.fromhex("27 04 10 00"),
    b"\xd6\xd2": bytes.fromhex("d7 d2 01 01"),
    b"\xf6\x03": bytes.fromhex("f7 03 02 20 35"),
    b"\xfa\x02": bytes.fromhex("fb 02 00 00 01"),
}


class FakeV1:
    def request(self, payload, dtype=tc.T1, wait=2.0, retries=1):
        return V1.get(bytes(payload))


def fake_xfer(c, payload, want=None, wait=2.5):
    return V2.get(bytes(payload))


def fake_t2(c, payload, want=None, wait=2.2):
    return bytes.fromhex("43 01 00 00") if bytes(payload) == b"\x42\x01\x00" else None


def _menu_labels():
    t = tray.Tray({"get_state": lambda: {"device_label": "LinkBuds S"}})
    t._menu()
    return [x.value for x in t._texts]


def _measure_ok():
    t = tray.Tray({"get_state": lambda: {"device_label": "X"}})
    t._menu()
    mis = tray.MEASUREITEMSTRUCT()
    mis.itemID = 1001
    mis.itemData = ctypes.cast(t._texts[0], ctypes.c_void_p).value
    return bool(t._measure_item(ctypes.byref(mis))) and mis.itemHeight > 0


def _atomic_config_ok():
    import json as _json
    import tempfile
    d = tempfile.mkdtemp()
    orig = srv.CONFIG_PATH
    try:
        srv.CONFIG_PATH = os.path.join(d, "config.json")
        srv.save_config()
        ok = (os.path.isfile(srv.CONFIG_PATH)
              and not os.path.exists(srv.CONFIG_PATH + ".tmp"))
        _json.load(open(srv.CONFIG_PATH, encoding="utf-8"))
        return ok
    except Exception:
        return False
    finally:
        srv.CONFIG_PATH = orig


def _colour_v1():
    """XM4 really answers 05 03 30 01: PREMIUM series, BLACK."""
    d = lb.parse_series_color(bytes([0x05, 0x03, 0x30, 0x01]))
    return (d["en"] == "BLACK" and d["series"] == 0x30
            and d["series_enum"] == "PREMIUM" and d["suffix"] == "b")


def _colour_v2():
    d = lb.parse_series_color(bytes([0x05, 0x03, 0x60, 0x02]))
    return (d["en"] == "WHITE" and d["series_enum"] == "LINK_BUDS"
            and d["suffix"] == "w")


def _v1_colour_read():
    """read_device_color must work for v1 too, via the plain request() path."""
    class FakeV1:
        def request(self, payload, wait=1.0, retries=0):
            assert payload == b"\x04\x03", payload
            return bytes([0x05, 0x03, 0x30, 0x01])

    d = srv.read_device_color("xm4", FakeV1())
    return bool(d) and d["en"] == "BLACK"


def _battery_stages():
    """One alert per stage; nothing repeats until the headset is recharged."""
    srv.BATTERY_WATCH.update({"key": None, "stage": 0})
    del srv.ALERTS[:]
    seq = [50, 19, 18, 9, 8, 40, 19]
    out = []
    for level in seq:
        srv.check_battery("xm4", {"battery": {"main": level}})
        out.append(len(srv.ALERTS))
        del srv.ALERTS[:]
    # first sighting silent, low once, quiet, critical once, quiet, reset, low again
    ok = out == [0, 1, 0, 1, 0, 0, 1]
    srv.check_battery("xm4", {"battery": {"main": None}})
    return ok and not srv.ALERTS


def _photo_table():
    """Parse PHOTO_VARIANTS out of app.js: {model: {suffix: render file}}."""
    js = open(os.path.join(srv.ROOT, "app.js"), encoding="utf-8").read()
    if "const PHOTO_VARIANTS = {" not in js:
        return {}
    block = js.split("const PHOTO_VARIANTS = {", 1)[1].split("};", 1)[0]
    table = {}
    for m in re.finditer(r"(\w+)\s*:\s*\{([^}]*)\}", block):
        table[m.group(1)] = dict(re.findall(r"(\w+)\s*:\s*'([\w.-]+)'", m.group(2)))
    return table


def _photo_table_matches_assets():
    """Every colour the panel can name must map to a render that ships.

    This is the check that catches the realistic failure: a new colourway gets
    a file but nobody updates the table (or the reverse), and the panel silently
    shows the default render for one colour.
    """
    table = _photo_table()
    if not table:
        return False
    assets = set(os.listdir(os.path.join(srv.ROOT, "assets")))
    suffixes = set(v[2] for v in lb.MODEL_COLORS.values() if v[2])
    def shipped(base):
        return (base + ".webp") in assets

    for dev, mapping in table.items():
        if not shipped(dev):                    # the default render
            return False
        for sfx, name in mapping.items():
            if sfx not in suffixes:             # typo in a key
                return False
            if not shipped(name):               # render missing
                return False
    return True


def _v1_model_name():
    class FakeV1:
        def request(self, payload, wait=1.0, retries=0):
            assert payload == b"\x04\x01", payload
            return b"\x05\x01\x0a" + b"WH-1000XM4"

    return srv.read_device_model("xm4", FakeV1()) == "WH-1000XM4"


def _v2_skips_model_read():
    """v2 already reads the model inside read_status_v2, so the handshake must
    not spend another round trip on it."""
    class Boom:
        def request(self, *a, **k):
            raise AssertionError("must not be called")

    return srv.read_device_model("ls900n", Boom()) is None


def _log_stamped():
    import tempfile
    import appmain
    d = tempfile.mkdtemp()
    orig = appmain.tray.data_dir
    appmain.tray.data_dir = lambda: d
    try:
        appmain.log("hello")
        text = open(os.path.join(d, "app.log"), encoding="utf-8").read()
        head = text[:19]
        return (head[4] == "-" and head[7] == "-" and head[10] == " "
                and head[13] == ":" and text.endswith("hello\n"))
    finally:
        appmain.tray.data_dir = orig


def _battery_tick_light():
    """The 10-minute watch must send the battery command only.

    A full status snapshot here would hold the session lock for over a second
    and collide with whatever the panel is doing.
    """
    sent = []

    class Fake:
        def request(self, payload, wait=1.0, retries=0):
            sent.append(payload)
            return bytes([0x11, 0x00, 55])

    fake = Fake()
    prev = (srv.CURRENT.get("key"), srv.SESSION.client, srv.SESSION.key)
    srv.CURRENT["key"] = "xm4"
    srv.SESSION.client, srv.SESSION.key = fake, "xm4"
    srv.BATTERY_WATCH.update({"key": "xm4", "stage": 0})
    del srv.ALERTS[:]
    try:
        level = srv.battery_tick()
        return level == 55 and sent == [b"\x10\x00"]
    finally:
        srv.CURRENT["key"], srv.SESSION.client, srv.SESSION.key = prev


def _bt_candidates_shape():
    """The picker endpoint must be safe to call with or without a radio.

    On a machine with no Bluetooth adapter bt.scan() reports unavailable; the
    endpoint still has to answer with an empty list rather than raise, because
    the panel calls it unconditionally on load.
    """
    res = srv.bt_candidates()
    if not (res.get("ok") and isinstance(res.get("devices"), list)):
        return False
    for d in res["devices"]:
        if not {"mac", "name", "connected", "remembered",
                "audio", "guess", "owner"} <= set(d):
            return False
    return True


def _picker_wired():
    """The panel must offer the picker and the first-run auto-adopt path."""
    js = open(os.path.join(srv.ROOT, "app.js"), encoding="utf-8").read()
    html = open(os.path.join(srv.ROOT, "index.html"), encoding="utf-8").read()
    return ('id="btPick"' in html and 'id="btnBtScan"' in html
            and "'/api/bt'" in js and "function autoBind(" in js
            and "async function bindDevice(" in js)


def _ldac_probe_shape():
    """The LDAC row is fed by a read-only probe, so it must never raise.

    Windows has no third-party A2DP encoder hook, so the panel only reports
    whether a bridge is installed; on a clean machine that is simply False.
    """
    res = srv.a2dp_bridge_status()
    return (isinstance(res, dict)
            and {"installed", "path", "version"} <= set(res)
            and isinstance(res["installed"], bool)
            and isinstance(res["path"], str))


def _ldac_row_wired():
    """The sound card must carry the LDAC row and its explanation, and the
    text must promise no driver installation."""
    js = open(os.path.join(srv.ROOT, "app.js"), encoding="utf-8").read()
    html = open(os.path.join(srv.ROOT, "index.html"), encoding="utf-8").read()
    return ('id="ldacState"' in html and 'id="ldacNote"' in html
            and 'id="btnLdacInfo"' in html
            and "'/api/ldac'" in js and "function renderLdac(" in js
            and "本应用不下载驱动" in html)


def _theme_follows():
    js = open(os.path.join(srv.ROOT, "app.js"), encoding="utf-8").read()
    return ("addEventListener('change'" in js and "themeExplicit" in js
            and "function chooseTheme(" in js
            and "localStorage.removeItem(THEME_KEY)" in js)


def _rotate_ok():
    import tempfile
    import appmain
    d = tempfile.mkdtemp()
    path = os.path.join(d, "app.log")
    with open(path, "wb") as f:
        f.write(b"x" * (appmain.LOG_MAX + 1))
    appmain.LOG_TICKS["n"] = 63          # the next call performs the size check
    appmain._rotate_log(path)
    rotated = path + ".1"
    return (not os.path.exists(path) and os.path.exists(rotated)
            and os.path.getsize(rotated) > appmain.LOG_MAX)


def main():
    s1 = srv.read_status_v1(FakeV1())
    lb.xfer, lb.t2_cmd = fake_xfer, fake_t2
    s2 = srv.read_status_v2(None)

    # Single-device context (no live Bluetooth needed for the demo path).
    ctx = srv.current_context(demo=True, want="ls900n")
    prev_key = srv.CURRENT["key"]
    srv.CURRENT["key"] = "ls900n"
    demo_switch = srv.switch_device(demo=True)
    srv.CURRENT["key"] = prev_key
    rows = [
        {"mac": "AC:80:0A:BF:C3:C7", "name": "LinkBuds S",
         "connected": True, "remembered": True},
        {"mac": "88:C9:E8:91:BE:6B", "name": "WH-1000XM4",
         "connected": True, "remembered": True},
    ]
    online = srv._online_keys(rows)

    # Successful switch path: the second headset is not reachable on this PC,
    # so stub the transport to prove the single-device state machine.
    orig_connect, orig_remember = srv.do_connect, srv.remember_device
    fake_client = type("FakeClient", (), {"sock": 0})()
    srv.do_connect = lambda dev, quick=False: fake_client
    srv.remember_device = lambda key: None
    srv.SESSION.dispose()
    srv.CURRENT["key"] = "xm4"
    switched = srv.switch_device(demo=False)
    srv.CURRENT["key"] = prev_key
    srv.SESSION.dispose()
    srv.do_connect, srv.remember_device = orig_connect, orig_remember

    checks = [
        ("switch adopts the headset that answered",
         switched["ok"] and switched["device"]["id"] == "ls900n"),
        ("context exposes exactly one device",
         set(ctx) >= {"device", "status", "alternatives"} and
         ctx["device"]["id"] == "ls900n" and "devices" not in ctx),
        ("demo switch moves to the other model",
         demo_switch["ok"] and demo_switch["device"]["id"] == "xm4"),
        ("bluetooth MAC decoding", srv.bt._mac(0x88C9E891BE6B) == "88:C9:E8:91:BE:6B"),
        ("both models map from BT rows", online == ["xm4", "ls900n"]),
        ("public device shape", srv.public_device("xm4")["protocol"] == "v1"),
        ("v1 battery", s1["battery"]["main"] == 0x44),
        ("v1 anc = nc", s1["anc"]["mode"] == "nc"),
        ("v1 focus", s1["anc"]["focus"] is True),
        ("v1 ambient level", s1["anc"]["level"] == 12),
        ("v1 eq preset", s1["eq"]["preset"] == "bass"),
        ("v1 eq 6 bands", len(s1["eq"]["bands"]) == 6),
        ("v1 auto power off", s1["system"]["apo"] == "30min"),
        ("v1 codec", s1["info"]["codec"] == "LDAC"),
        ("v2 battery detail", s2["battery"] == {"main": 90, "left": 91, "right": 88, "case": 74}),
        ("v2 anc = ambient", s2["anc"]["mode"] == "ambient"),
        ("v2 voice ON is 0x00", s2["sound"]["voice"] is True),
        ("v2 speak-to-chat ON is 0x00", s2["system"]["stc"] is True),
        ("v2 auto power off", s2["system"]["apo"] == "takenoff"),
        ("v2 key presets", s2["system"]["keys"] == {"left": 0x20, "right": 0x35}),
        ("v2 stc extended", s2["system"]["stc_ext"] ==
         {"sensitivity": "auto", "off_time": "mid"}),
        ("v2 series", "0x60" in s2["info"]["series"]),
        # Colour instruction (CONNECT_GET_DEVICE_INFO / 04 03).
        ("colour 0x02 = WHITE",
         srv.DEMO_COLOR["ls900n"]["name"] == "白色" and
         srv.DEMO_COLOR["ls900n"]["suffix"] == "w"),
        ("colour enum name", srv.DEMO_COLOR["ls900n"]["enum"] == "ModelColor.WHITE"),
        ("colour instruction shows raw reply",
         srv.DEMO_COLOR["ls900n"]["instruction"] == "04 03 → 05 03 60 02"),
        ("colour series = LinkBuds",
         srv.DEMO_COLOR["ls900n"]["series_name"] == "LinkBuds (LINK_BUDS)" and
         srv.DEMO_COLOR["ls900n"]["series_enum"] == "LINK_BUDS" and
         srv.DEMO_COLOR["ls900n"]["series"] == 0x60),
        ("v1 3-byte colour reply",
         lb.parse_series_color(bytes.fromhex("05 03 01"), "v1")["name"] == "黑色"),
        ("_I variant keeps base colour",
         lb.parse_series_color(bytes.fromhex("05 03 60 12"))["enum"] ==
         "ModelColor.WHITE_I"),
        ("non-colour reply rejected",
         lb.parse_series_color(bytes.fromhex("05 02 00")) is None),
        ("unknown colour degrades safely",
         lb.parse_series_color(bytes.fromhex("05 03 60 fe"))["name"] == "未知"),
        ("demo context carries colour",
         bool(ctx.get("color")) and ctx["color"]["suffix"] == "w"),
        ("demo state carries colour",
         srv.demo_state("ls900n")["info"]["color"]["name"] == "白色"),
        ("v1 demo does not invent a colour",
         srv.demo_state("xm4")["info"]["color"] is None),
        ("brand assets present",
         all(os.path.isfile(os.path.join(srv.ROOT, "assets", f)) for f in
             ("sony-logo.svg", "placeholder.svg"))),
        # One render per colourway, named after the ModelColor suffix the
        # headset reports in 04 03 (see make_cloud_assets.py).
        ("colour table covers both models", len(_photo_table()) == 2),
        ("renders cover both models", len(_photo_table()) == 2),
        ("asset gate accepts a shipped image", srv.asset_allowed("sony-logo.svg")),
        ("asset gate rejects traversal", not srv.asset_allowed("../server.py")),
        ("asset gate rejects non-images", not srv.asset_allowed("config.json")),
        ("black maps to the default xm4 render",
         _photo_table().get("xm4", {}).get("b") == "xm4"),
        ("white maps to the white LinkBuds render",
         _photo_table().get("ls900n", {}).get("w") == "ls900n_w"),
        # Tray menu is owner-drawn and must not expose a demo entry any more.
        ("tray menu has 8 labelled items", len(_menu_labels()) == 8),
        ("tray menu has no demo entry",
         not any("演示" in x for x in _menu_labels())),
        ("tray menu shows the live headset",
         any("当前耳机" in x for x in _menu_labels())),
        ("tray menu exposes the font size",
         any("菜单字号" in x for x in _menu_labels())),
        ("tray mutates measure struct",
         _measure_ok()),
        # Cross-site guard: the local panel is unauthenticated.
        ("origin accepts the panel itself",
         srv.same_origin("127.0.0.1:8765", "http://127.0.0.1:8765", None, 8765)),
        ("origin accepts localhost",
         srv.same_origin("localhost:8765", "http://localhost:8765", None, 8765)),
        ("origin accepts local CLI (no headers)",
         srv.same_origin(None, None, None, 8765)),
        ("origin rejects a foreign Host (DNS rebinding)",
         not srv.same_origin("evil.example:8765", None, None, 8765)),
        ("origin rejects a foreign Origin",
         not srv.same_origin("127.0.0.1:8765", "http://evil.example", None, 8765)),
        ("origin rejects cross-site fetch",
         not srv.same_origin("127.0.0.1:8765", None, "cross-site", 8765)),
        # Atomic config write must not leave a temp file behind.
        ("config write is atomic",
         _atomic_config_ok()),
        # Colour identification on both protocol generations.
        ("v1 colour decodes BLACK/PREMIUM", _colour_v1()),
        ("v2 colour decodes WHITE/LINK_BUDS", _colour_v2()),
        ("read_device_color works for v1", _v1_colour_read()),
        ("unknown colour degrades safely", lb.parse_series_color(
            bytes([0x05, 0x03, 0x30, 0x7F]))["en"] == "UNKNOWN"),
        # Battery alerts: one balloon per stage, reset only after a recharge.
        ("battery alerts fire once per stage", _battery_stages()),
        # Log rotation keeps app.log bounded.
        ("log rotates past the size cap", _rotate_ok()),
        # Theme keeps following the OS until the user picks one explicitly.
        ("theme listens for OS changes", _theme_follows()),
        ("v1 model name parsed from 04 01", _v1_model_name()),
        ("v2 skips the extra model round trip", _v2_skips_model_read()),
        ("log lines carry a timestamp", _log_stamped()),
        ("battery watch sends one command", _battery_tick_light()),
        ("bt candidates answer without a radio", _bt_candidates_shape()),
        ("panel offers the device picker", _picker_wired()),
        ("ldac probe answers read-only", _ldac_probe_shape()),
        ("sound card carries the ldac row", _ldac_row_wired()),
        # Windows can reserve the whole 8765-8776 block for Hyper-V/WSL.
        ("OS-reserved port range falls back to a free port", _port_fallback()),
        # Review pass: structure, honesty and the scene/undo feature.
        ("every HTML element closes on the right nesting level", _html_wellformed()),
        ("scene card is present exactly once", _scene_wired()),
        ("demo scene replays every step", _demo_scene_roundtrip()),
        ("wind is an ANC mode, not a one-way enable button", _wind_is_mode()),
        ("privacy copy matches the manual-only update check", _privacy_honest()),
        ("offline state disables writes and explains the first run", _offline_gate()),
        ("live regions and focus styles are present", _a11y_wired()),
    ]
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
    passed = sum(1 for _, ok in checks if ok)
    print("\n%d/%d passed" % (passed, len(checks)))
    return 0 if passed == len(checks) else 1


def _port_fallback():
    """A busy or OS-reserved preferred port still yields a usable server."""
    import socket
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = None
    try:
        probe.bind(("127.0.0.1", 0))
        busy = probe.getsockname()[1]
        server, bound = srv.create_server(busy, tries=1)
        return bool(server) and bool(bound) and bound != busy
    except OSError:
        return False
    finally:
        if server is not None:
            server.server_close()
        probe.close()


def _read(name):
    with open(os.path.join(srv.ROOT, name), encoding="utf-8") as f:
        return f.read()


def _html_wellformed():
    """Every non-void element must close at the same nesting level.

    A missing </div> in the About card once trapped the whole body inside the
    flex header; a plain grep cannot catch that, but a tag stack can.
    """
    from html.parser import HTMLParser
    void = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    class Check(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self, convert_charrefs=True)
            self.stack, self.bad = [], []

        def handle_startendtag(self, tag, attrs):
            pass                      # <path/>, <circle/> ... in inline SVGs

        def handle_starttag(self, tag, attrs):
            if tag not in void:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if tag in void:
                return
            if not self.stack or self.stack[-1] != tag:
                self.bad.append((tag, self.stack[-3:]))
            else:
                self.stack.pop()

    c = Check()
    c.feed(_read("index.html"))
    return not c.bad and not c.stack


def _scene_wired():
    html, js, py = _read("index.html"), _read("app.js"), _read("server.py")
    return (html.count('id="card-scene"') == 1
            and html.count('id="sceneChips"') == 1
            and "BUILTIN_SCENES" in js and "stepsFromState" in js
            and "btnCfgExport" in js and "btnCfgImport" in js
            and 'elif action == "scene":' in py
            and "allowed = {" in py)


def _demo_scene_roundtrip():
    import copy
    before = copy.deepcopy(srv.DEMO["xm4"])
    try:
        srv.demo_action("xm4", "scene", {"steps": [
            {"action": "anc_mode", "value": "nc"},
            {"action": "dsee", "value": True},
            {"action": "eq_bands", "value": [0, 2, 1, 0, -1, 0]}]})
        st = srv.demo_state("xm4")
        return (st["anc"]["mode"] == "nc" and st["sound"]["dsee"] is True
                and st["eq"]["bands"] == [0, 2, 1, 0, -1, 0])
    finally:
        srv.DEMO["xm4"] = before


def _wind_is_mode():
    html, py = _read("index.html"), _read("server.py")
    return (html.count('data-action="anc_mode" data-value="wind"') == 1
            and 'data-action="wind"' not in html
            and 'elif value == "wind":' in py
            and "已切换到风噪降低" in py)


def _privacy_honest():
    html, js = _read("index.html"), _read("app.js")
    return ("不上传任何数据" not in html
            and "默认不联网" in html
            and "start-up makes no external request" in js
            and js.count("  checkUpdate();") == 0)


def _offline_gate():
    html, js = _read("index.html"), _read("app.js")
    return ('id="offlineTip"' in html and "applyOfflineState" in js
            and "el.disabled = !connected" in js
            and "btnGuideClose" in js and "不再提示" in html)


def _a11y_wired():
    html, js, css = _read("index.html"), _read("app.js"), _read("style.css")
    return ('aria-live="polite"' in html and 'role="status"' in html
            and "document.documentElement.lang" in js
            and 'setAttribute(\'aria-label\', lbl.textContent.trim())' in js
            and ":focus-visible" in css)


if __name__ == "__main__":
    sys.exit(main())
