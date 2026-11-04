#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline self-test for the state parsers. No headphone, no Bluetooth needed.

    python selftest.py

Feeds canned MDR responses through read_status_v1 / read_status_v2 and asserts
the normalized state. Run this after touching any protocol code.
"""
import ctypes
import os
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
        {"mac": "AA:BB:CC:DD:EE:02", "name": "LinkBuds S",
         "connected": True, "remembered": True},
        {"mac": "AA:BB:CC:DD:EE:01", "name": "WH-1000XM4",
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
        ("bluetooth MAC decoding", srv.bt._mac(0xAABBCCDDEE01) == "AA:BB:CC:DD:EE:01"),
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
         srv.DEMO_COLOR["ls900n"]["series_name"] == "LinkBuds" and
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
        ("placeholder artwork present",
         os.path.isfile(os.path.join(srv.ROOT, "assets", "placeholder.svg"))),
        ("asset whitelist covers shipped files",
         {"placeholder.svg", "sony-logo.svg"} <= srv.ASSET_OK),
        # Tray menu is owner-drawn and must not expose a demo entry any more.
        ("tray menu has 7 labelled items", len(_menu_labels()) == 7),
        ("tray menu has no demo entry",
         not any("演示" in x for x in _menu_labels())),
        ("tray menu shows the live headset",
         any("当前耳机" in x for x in _menu_labels())),
        ("tray mutates measure struct",
         _measure_ok()),
    ]
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
    passed = sum(1 for _, ok in checks if ok)
    print("\n%d/%d passed" % (passed, len(checks)))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
