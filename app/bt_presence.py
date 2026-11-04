#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which Sony headphones are *actually connected* to this Windows PC?

Pure ctypes against BluetoothAPIs.dll - no third-party packages, no pairing
changes, no RFCOMM sockets opened (the device only tolerates one client).
Two complementary Win32 calls:

  BluetoothFindFirstDevice / Next  cached device list, names, fConnected
  BluetoothGetDeviceInfo           fresh fConnected for one known MAC

The control panel uses this to render only the headset that is online. If the
Bluetooth stack is unavailable (non-Windows, no adapter, API failure) the
caller falls back to listing every configured device.

    python bt_presence.py     -> diagnostic dump of all known BT devices
"""
import ctypes
import threading
import time
from ctypes import wintypes as wt

MAX_NAME = 248
CACHE_TTL = 2.0                 # seconds; the UI polls every few seconds
ERROR_SUCCESS = 0


class _SystemTime(ctypes.Structure):
    _fields_ = [(n, wt.WORD) for n in
                ("wYear", "wMonth", "wDayOfWeek", "wDay", "wHour",
                 "wMinute", "wSecond", "wMilliseconds")]


class _BtAddress(ctypes.Union):
    # rgBytes is really [6] in the SDK; the union is 8 bytes because of ullLong.
    _fields_ = [("ullLong", ctypes.c_ulonglong), ("rgBytes", ctypes.c_ubyte * 8)]


class DeviceInfo(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("Address", _BtAddress),
        ("ulClassofDevice", wt.ULONG),
        ("fConnected", wt.BOOL),
        ("fRemembered", wt.BOOL),
        ("fAuthenticated", wt.BOOL),
        ("stLastSeen", _SystemTime),
        ("stLastUsed", _SystemTime),
        ("szName", wt.WCHAR * MAX_NAME),
    ]


class SearchParams(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("fReturnAuthenticated", wt.BOOL),
        ("fReturnRemembered", wt.BOOL),
        ("fReturnUnknown", wt.BOOL),
        ("fReturnConnected", wt.BOOL),
        ("fIssueInquiry", wt.BOOL),
        ("cTimeoutMultiplier", ctypes.c_ubyte),
        ("hRadio", wt.HANDLE),
    ]


class RadioParams(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD)]


_api = None
_api_error = ""
_lock = threading.Lock()
_cache = {"at": 0.0, "result": None}


def _load():
    global _api, _api_error
    if _api is not None or _api_error:
        return _api
    try:
        a = ctypes.WinDLL("BluetoothAPIs.dll", use_last_error=True)
        a.BluetoothFindFirstDevice.argtypes = [ctypes.POINTER(SearchParams),
                                               ctypes.POINTER(DeviceInfo)]
        a.BluetoothFindFirstDevice.restype = wt.HANDLE
        a.BluetoothFindNextDevice.argtypes = [wt.HANDLE, ctypes.POINTER(DeviceInfo)]
        a.BluetoothFindNextDevice.restype = wt.BOOL
        a.BluetoothFindDeviceClose.argtypes = [wt.HANDLE]
        a.BluetoothFindDeviceClose.restype = wt.BOOL
        a.BluetoothFindFirstRadio.argtypes = [ctypes.POINTER(RadioParams),
                                              ctypes.POINTER(wt.HANDLE)]
        a.BluetoothFindFirstRadio.restype = wt.HANDLE
        a.BluetoothFindRadioClose.argtypes = [wt.HANDLE]
        a.BluetoothFindRadioClose.restype = wt.BOOL
        a.BluetoothGetDeviceInfo.argtypes = [wt.HANDLE, ctypes.POINTER(DeviceInfo)]
        a.BluetoothGetDeviceInfo.restype = wt.DWORD
        _api = a
    except Exception as e:                     # pragma: no cover - Windows only
        _api_error = str(e)
    return _api


def _mac(ull):
    h = "%012X" % (ull & 0xFFFFFFFFFFFF)
    return ":".join(h[i:i + 2] for i in range(0, 12, 2))


def _row(info):
    return {
        "mac": _mac(info.Address.ullLong),
        "name": info.szName.strip(),
        "connected": bool(info.fConnected),
        "remembered": bool(info.fRemembered),
        "authenticated": bool(info.fAuthenticated),
        "cod": int(info.ulClassofDevice),
    }


def _enumerate(a):
    p = SearchParams()
    p.dwSize = ctypes.sizeof(p)
    p.fReturnAuthenticated = 1
    p.fReturnRemembered = 1
    p.fReturnUnknown = 0
    p.fReturnConnected = 1
    p.fIssueInquiry = 0                       # cached devices only: no 1.28 s inquiry
    p.cTimeoutMultiplier = 1
    p.hRadio = None                           # all local radios

    info = DeviceInfo()
    info.dwSize = ctypes.sizeof(info)
    rows = []
    h = a.BluetoothFindFirstDevice(ctypes.byref(p), ctypes.byref(info))
    if not h:
        return rows, ctypes.get_last_error()
    try:
        while True:
            rows.append(_row(info))
            if len(rows) >= 512:
                break
            ctypes.memset(ctypes.byref(info), 0, ctypes.sizeof(info))
            info.dwSize = ctypes.sizeof(info)
            if not a.BluetoothFindNextDevice(h, ctypes.byref(info)):
                break
    finally:
        a.BluetoothFindDeviceClose(h)
    return rows, ERROR_SUCCESS


def _local_radio(a):
    p = RadioParams()
    p.dwSize = ctypes.sizeof(p)
    h = wt.HANDLE()
    find = a.BluetoothFindFirstRadio(ctypes.byref(p), ctypes.byref(h))
    if find:
        a.BluetoothFindRadioClose(find)
    return h.value


def _refresh(a, radio, mac):
    """Ask the stack directly for one address. Returns (connected, name) or None."""
    info = DeviceInfo()
    info.dwSize = ctypes.sizeof(info)
    try:
        info.Address.ullLong = int(mac.replace(":", ""), 16)
    except ValueError:
        return None
    rc = a.BluetoothGetDeviceInfo(radio, ctypes.byref(info))
    if rc != ERROR_SUCCESS:
        return None
    return bool(info.fConnected), info.szName.strip()


def scan(force=False):
    """Return ``{'available', 'probe', 'devices', 'error'}``.

    ``devices`` is a list of dicts with mac/name/connected/... for every known
    Bluetooth device. Results are cached for CACHE_TTL seconds so the UI can
    poll without hammering the Bluetooth stack.
    """
    with _lock:
        now = time.monotonic()
        if not force and _cache["result"] is not None and now - _cache["at"] < CACHE_TTL:
            return _cache["result"]

        a = _load()
        if a is None:
            result = {"available": False, "probe": "unavailable",
                      "devices": [], "error": _api_error or "BluetoothAPIs.dll 不可用"}
        else:
            try:
                rows, err = _enumerate(a)
                radio = _local_radio(a)
                # A fresh per-address query repairs stale fConnected cache entries.
                # Only upgrade False -> True, never downgrade (avoid flicker).
                for r in rows:
                    fresh = _refresh(a, radio, r["mac"])
                    if fresh is not None:
                        if fresh[0]:
                            r["connected"] = True
                        if fresh[1] and not r["name"]:
                            r["name"] = fresh[1]
                        r["verified"] = True
                result = {"available": True,
                          "probe": "connected" if any(r["connected"] for r in rows) else "idle",
                          "devices": rows, "error": "" if not rows else "",
                          "enumerate_error": err, "radio": bool(radio)}
                if not rows and err not in (0, 259, 1168):
                    result["error"] = "BluetoothFindFirstDevice 错误 %d" % err
            except Exception as e:             # pragma: no cover
                result = {"available": False, "probe": "error",
                          "devices": [], "error": str(e)}

        result["at"] = time.strftime("%H:%M:%S")
        _cache["result"], _cache["at"] = result, now
        return result


def connected_map(force=False):
    """``{MAC: device-row}`` for currently connected devices only."""
    s = scan(force=force)
    return {r["mac"]: r for r in s["devices"] if r["connected"]}


if __name__ == "__main__":
    import json
    print(json.dumps(scan(force=True), ensure_ascii=False, indent=2))
