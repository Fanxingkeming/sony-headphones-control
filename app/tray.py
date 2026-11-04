#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows tray icon + small OS helpers, implemented entirely with ctypes.

Deliberately dependency-free: no pystray, no Pillow, no pywin32, no subprocess.
The tray HICON is loaded from the bundled Sound Connect ``app-icon.ico``
via LoadImageW(LR_LOADFROMFILE); the in-memory 32bpp DIB is only a fallback
for a bare source checkout that has not generated the brand assets yet.

Public helpers
--------------
    ensure_single_instance() -> bool
    open_panel(url, app_mode=True)
    autostart_enabled() / set_autostart(bool)
    Tray(callbacks).run()  -> blocking message loop
"""
import ctypes
import os
import struct
import sys
import winreg
from ctypes import wintypes

# ---------------------------------------------------------------------------
# Win32 bindings
# ---------------------------------------------------------------------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
WM_NULL = 0x0000
WM_APP = 0x8000
WM_QUIT = 0x0012
CB_MESSAGE = WM_APP + 1

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
NIIF_INFO, NIIF_NOSOUND = 0x01, 0x10

MF_STRING, MF_GRAYED, MF_CHECKED, MF_POPUP, MF_SEPARATOR = 0x0000, 0x0001, 0x0008, 0x0010, 0x0800
MF_OWNERDRAW = 0x0100
TPM_RETURNCMD, TPM_RIGHTBUTTON, TPM_NONOTIFY = 0x0100, 0x0002, 0x0080

# Owner-drawn menu. The shell's default 9 pt menu font cannot be replaced, and
# on a high-resolution panel it looks small and hazy. Drawing the items
# ourselves lets us use a ClearType font sized from the window DPI, which is
# the only way to make the tray menu genuinely crisp.
WM_MEASUREITEM, WM_DRAWITEM = 0x002C, 0x002B
ODS_SELECTED, ODS_GRAYED, ODS_DISABLED = 0x0001, 0x0002, 0x0004
DT_SINGLELINE, DT_VCENTER, DT_LEFT, DT_NOPREFIX = 0x0020, 0x0004, 0x0000, 0x0800
COLOR_MENU, COLOR_MENUTEXT, COLOR_HIGHLIGHT, COLOR_HIGHLIGHTTEXT, COLOR_GRAYTEXT = 4, 7, 13, 14, 17
CLEARTYPE_QUALITY, DEFAULT_CHARSET = 5, 1
ID_SEP = 1000
SW_SHOWNORMAL = 1
ERROR_ALREADY_EXISTS = 183

ID_OPEN, ID_CURRENT, ID_SWITCH = 1001, 1010, 1011
ID_AUTOSTART, ID_DISCONNECT, ID_ABOUT, ID_QUIT = 1030, 1040, 1050, 1099
ID_FONT = 1060

# Menu text sizes offered by the 菜单字号 item. 13 px matches Microsoft YaHei UI
# at 100 %% scaling; 11 and 15 are the usual "denser" and "bigger" wishes.
FONT_STEPS = (11, 13, 15)


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("message", wintypes.UINT),
                ("wParam", WPARAM), ("lParam", LPARAM),
                ("time", wintypes.DWORD), ("pt", POINT),
                ("lPrivate", wintypes.DWORD)]


class MEASUREITEMSTRUCT(ctypes.Structure):
    _fields_ = [("CtlType", wintypes.UINT), ("CtlID", wintypes.UINT),
                ("itemID", wintypes.UINT), ("itemWidth", wintypes.UINT),
                ("itemHeight", wintypes.UINT), ("itemData", ctypes.c_size_t)]


class DRAWITEMSTRUCT(ctypes.Structure):
    _fields_ = [("CtlType", wintypes.UINT), ("CtlID", wintypes.UINT),
                ("itemID", wintypes.UINT), ("itemAction", wintypes.UINT),
                ("itemState", wintypes.UINT), ("hWndItem", wintypes.HWND),
                ("hDC", wintypes.HDC), ("rcItem", wintypes.RECT),
                ("itemData", ctypes.c_size_t)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID),
                ("hBalloonIcon", wintypes.HICON)]


def _bind(dll, name, argtypes, restype):
    fn = getattr(dll, name)
    fn.argtypes, fn.restype = argtypes, restype
    return fn


_CreateIcon = _bind(user32, "CreateIconFromResourceEx",
                    [ctypes.c_void_p, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
                     ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.HICON)
_RegisterClass = _bind(user32, "RegisterClassExW",
                       [ctypes.POINTER(WNDCLASSEXW)], wintypes.ATOM)
_CreateWindow = _bind(user32, "CreateWindowExW",
                      [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                       wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                       ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                       wintypes.HINSTANCE, ctypes.c_void_p], wintypes.HWND)
_NotifyIcon = _bind(shell32, "Shell_NotifyIconW",
                    [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)], wintypes.BOOL)
_CreatePopupMenu = _bind(user32, "CreatePopupMenu", [], wintypes.HMENU)
_AppendMenu = _bind(user32, "AppendMenuW",
                    [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR],
                    wintypes.BOOL)
_TrackPopupMenu = _bind(user32, "TrackPopupMenu",
                        [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, wintypes.HWND, ctypes.c_void_p], ctypes.c_int)
_GetCursorPos = _bind(user32, "GetCursorPos", [ctypes.POINTER(POINT)], wintypes.BOOL)
_GetSystemMetrics = _bind(user32, "GetSystemMetrics", [ctypes.c_int], ctypes.c_int)
SM_CXSMICON = 49
_GetDC = _bind(user32, "GetDC", [wintypes.HWND], wintypes.HDC)
_ReleaseDC = _bind(user32, "ReleaseDC", [wintypes.HWND, wintypes.HDC], ctypes.c_int)
_CreateFontW = _bind(gdi32, "CreateFontW",
                     [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR],
                     wintypes.HFONT)
_CreateSolidBrush = _bind(gdi32, "CreateSolidBrush", [wintypes.DWORD], wintypes.HBRUSH)
_FillRect = _bind(user32, "FillRect",
                  [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH],
                  ctypes.c_int)
_SelectObject = _bind(gdi32, "SelectObject",
                      [wintypes.HDC, wintypes.HGDIOBJ], wintypes.HGDIOBJ)
_DeleteObject = _bind(gdi32, "DeleteObject", [wintypes.HGDIOBJ], wintypes.BOOL)
_SetTextColor = _bind(gdi32, "SetTextColor",
                      [wintypes.HDC, wintypes.DWORD], wintypes.DWORD)
_SetBkMode = _bind(gdi32, "SetBkMode", [wintypes.HDC, ctypes.c_int], ctypes.c_int)
_DrawTextW = _bind(user32, "DrawTextW",
                   [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int,
                    ctypes.POINTER(wintypes.RECT), wintypes.UINT], ctypes.c_int)
_GetTextExtentPoint32W = _bind(gdi32, "GetTextExtentPoint32W",
                               [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int,
                                ctypes.POINTER(wintypes.SIZE)], wintypes.BOOL)
_GetSysColor = _bind(user32, "GetSysColor", [ctypes.c_int], wintypes.DWORD)
_GetDpiForWindow = _bind(user32, "GetDpiForWindow", [wintypes.HWND], wintypes.UINT)
_SetForegroundWindow = _bind(user32, "SetForegroundWindow", [wintypes.HWND], wintypes.BOOL)
_PostMessage = _bind(user32, "PostMessageW",
                     [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM], wintypes.BOOL)
_DestroyMenu = _bind(user32, "DestroyMenu", [wintypes.HMENU], wintypes.BOOL)
_DestroyWindow = _bind(user32, "DestroyWindow", [wintypes.HWND], wintypes.BOOL)
_DestroyIcon = _bind(user32, "DestroyIcon", [wintypes.HICON], wintypes.BOOL)
_GetMessage = _bind(user32, "GetMessageW",
                    [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT],
                    wintypes.BOOL)
_TranslateMessage = _bind(user32, "TranslateMessage", [ctypes.POINTER(MSG)], wintypes.BOOL)
_DispatchMessage = _bind(user32, "DispatchMessageW", [ctypes.POINTER(MSG)], LRESULT)
_DefWindowProc = _bind(user32, "DefWindowProcW",
                       [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM], LRESULT)
_PostQuitMessage = _bind(user32, "PostQuitMessage", [ctypes.c_int], None)
_LoadIcon = _bind(user32, "LoadIconW",
                  [wintypes.HINSTANCE, wintypes.LPCWSTR], wintypes.HICON)
_LoadImage = _bind(user32, "LoadImageW",
                   [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                    ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.HICON)

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010


def asset_path(name):
    """Static asset location, both from source and from a onefile exe."""
    base = (sys._MEIPASS if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", name)
_RegisterWindowMessage = _bind(user32, "RegisterWindowMessageW",
                               [wintypes.LPCWSTR], wintypes.UINT)
_ShellExecute = _bind(shell32, "ShellExecuteW",
                      [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                       wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int],
                      wintypes.HINSTANCE)
_CreateMutex = _bind(kernel32, "CreateMutexW",
                     [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE)
_GetModuleHandle = _bind(kernel32, "GetModuleHandleW", [wintypes.LPCWSTR],
                         wintypes.HINSTANCE)

_mutex_handle = None
_wndproc_ref = None
_taskbar_msg = _RegisterWindowMessage("TaskbarCreated")


# ---------------------------------------------------------------------------
# OS helpers
# ---------------------------------------------------------------------------

def ensure_single_instance(name="Local\\SonyHeadphonesControlPanel"):
    """Return True if this is the first instance. Keep the mutex alive globally."""
    global _mutex_handle
    _mutex_handle = _CreateMutex(None, False, name)
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "SonyHeadphonesControl")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.path.expanduser("~")
    return d


def autostart_command():
    """Command stored in HKCU\\...\\Run. Frozen -> the exe; source -> python + script."""
    if getattr(sys, "frozen", False):
        return '"%s" --minimized' % os.path.abspath(sys.executable)
    return '"%s" "%s" --minimized' % (os.path.abspath(sys.executable),
                                      os.path.abspath(sys.argv[0]))


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "SonyHeadphonesControl"


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            v, _ = winreg.QueryValueEx(k, RUN_NAME)
        return bool(v)
    except OSError:
        return False


def set_autostart(enabled):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE) as k:
        if enabled:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


def find_browser():
    """Prefer Edge, then Chrome. Returns an absolute exe path or None."""
    roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
             os.environ.get("LOCALAPPDATA")]
    rels = [(r"Microsoft\Edge\Application\msedge.exe",),
            (r"Google\Chrome\Application\chrome.exe",)]
    for base in roots:
        if not base:
            continue
        for rel in rels:
            p = os.path.join(base, rel[0])
            if os.path.isfile(p):
                return p
    return None


def open_panel(url, app_mode=True):
    """Launch a chromeless Edge/Chrome window, or the default browser."""
    exe = find_browser() if app_mode else None
    if exe:
        args = '--app=%s --window-size=1320,940 --no-first-run' % url
        r = _ShellExecute(None, "open", exe, args, None, SW_SHOWNORMAL)
        if r and int(r) > 32:
            return True
    r = _ShellExecute(None, "open", url, None, None, SW_SHOWNORMAL)
    return bool(r and int(r) > 32)


# ---------------------------------------------------------------------------
# Icon: generated as a 32x32 32bpp DIB, 4x supersampled for smooth edges
# ---------------------------------------------------------------------------

def _rounded(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _glyph(x, y, size=32):
    """Returns (kind, shade) where kind: 0=transparent 1=background 2=headphone.

    Geometry is authored in a 32x32 space and scaled, so the same design can be
    emitted at 16 / 32 / 48 px for the .ico and the tray HICON.
    """
    k = size / 32.0
    X, Y = x / k, y / k
    if (X - 16.0) ** 2 + (Y - 16.0) ** 2 > 15.2 ** 2:
        return 0, 0.0
    cx, cy = 16.0, 17.0
    d2 = (X - cx) ** 2 + (Y - cy) ** 2
    headband = 9.0 ** 2 <= d2 <= 11.4 ** 2 and Y <= cy + 0.6
    cup_l = _rounded(X, Y, 4.0, 15.5, 9.2, 26.0, 2.2)
    cup_r = _rounded(X, Y, 22.8, 15.5, 28.0, 26.0, 2.2)
    if headband or cup_l or cup_r:
        return 2, 0.0
    return 1, (Y - 1.0) / 30.0


def icon_dib(size=32, ss=4):
    """Raw icon resource bits (BITMAPINFOHEADER + XOR + AND), reusable as .ico data."""
    px = []
    for y in range(size):
        row = []
        for x in range(size):
            bg = fg = n = 0
            for sy in range(ss):
                for sx in range(ss):
                    kind, shade = _glyph(x + (sx + 0.5) / ss,
                                         y + (sy + 0.5) / ss, size)
                    n += 1
                    if kind == 1:
                        bg += 1
                    elif kind == 2:
                        fg += 1
            total = ss * ss
            a = round(255 * (bg + fg) / total)
            if bg + fg == 0:
                row.append((0, 0, 0, 0))
                continue
            # blue vertical gradient background, white headphone
            t = (y / (size / 32.0) - 1.0) / 30.0
            br = (int(46 - 26 * t), int(102 - 56 * t), int(235 - 92 * t))
            fgcol = (255, 255, 255)
            w = fg / (bg + fg)
            col = tuple(int(br[i] * (1 - w) + fgcol[i] * w) for i in range(3))
            row.append((col[0], col[1], col[2], a))
        px.append(row)

    hdr = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    row_bytes = ((size + 31) // 32) * 4      # 1bpp AND rows are DWORD-aligned
    xor = bytearray()
    and_mask = bytearray()
    for y in range(size - 1, -1, -1):          # DIB rows are bottom-up
        maskrow = bytearray(row_bytes)
        for x in range(size):
            r, g, b, a = px[y][x]
            xor += bytes((b, g, r, a))         # 32bpp DIB is BGRA
            if a < 128:
                maskrow[x // 8] |= 0x80 >> (x % 8)   # 1 = transparent
        and_mask += maskrow
    return hdr + bytes(xor) + bytes(and_mask)


def make_icon(size=None):
    """The Sound Connect app logo, identical to the PE icon in icon.ico.

    `size` defaults to the shell's small-icon metric: at 125-200 % display
    scaling this asks for 20/24/32 px and LoadImageW picks the matching .ico
    entry, instead of Windows resampling a 16 px bitmap.
    """
    if size is None:
        size = _GetSystemMetrics(SM_CXSMICON) or 16
    ico = asset_path("app-icon.ico")
    if os.path.isfile(ico):
        hicon = _LoadImage(None, ico, IMAGE_ICON, size, size, LR_LOADFROMFILE)
        if hicon:
            return hicon
    raw = icon_dib(size)                      # fallback: generated DIB
    buf = ctypes.create_string_buffer(raw)
    hicon = _CreateIcon(buf, len(raw), True, 0x00030000, size, size, 0)
    if not hicon:                             # last-resort stock icon
        hicon = _LoadIcon(None, ctypes.cast(ctypes.c_void_p(32512), wintypes.LPCWSTR))
    return hicon


# ---------------------------------------------------------------------------
# Tray
# ---------------------------------------------------------------------------

class Tray:
    """Blocking tray icon. callbacks is a dict of callables + get_state()."""

    def __init__(self, callbacks, tip="Sony Headphones Control"):
        self.cb = callbacks
        self.tip = tip
        self.hwnd = None
        self.hicon = None
        self.nid = None
        self._destroyed = False
        self._pending_balloon = None
        self._texts = []
        self._popup_menu = None

    # -- menu --------------------------------------------------------------
    def _dpi(self):
        try:
            return _GetDpiForWindow(self.hwnd) or 96
        except Exception:
            return 96

    def _font_height(self):
        # The size is a preference, so it can be changed from the menu itself
        # without rebuilding the exe.
        try:
            base = int(self.cb.get("get_state", lambda: {})().get("menu_px") or 13)
        except Exception:
            base = 13
        base = max(9, base)
        return max(10, int(round(base * self._dpi() / 96)))

    def _item_height(self):
        return self._font_height() + int(round(9 * self._dpi() / 96))

    def _menu_font(self):
        return _CreateFontW(-self._font_height(), 0, 0, 0, 400, 0, 0, 0,
                            DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0,
                            "Microsoft YaHei UI")

    def _menu(self):
        """Owner-drawn popup: every item carries its own label, so the text is
        drawn with a ClearType font at the window's real DPI."""
        st = self.cb.get("get_state", lambda: {})()
        m = _CreatePopupMenu()
        self._texts = []

        def item(cmd, label, flags=0):
            t = ctypes.c_wchar_p(label)
            self._texts.append(t)              # keep the pointer alive
            _AppendMenu(m, MF_OWNERDRAW | flags, cmd, t)

        def sep():
            _AppendMenu(m, MF_OWNERDRAW, ID_SEP, None)

        item(ID_OPEN, "打开控制面板")
        sep()
        # Only the headset the app is actually talking to is shown - no
        # two-device chooser here either.
        item(ID_CURRENT, "当前耳机：" + (st.get("device_label") or "检测中…"),
             MF_GRAYED)
        item(ID_SWITCH, "切换到另一副耳机")
        sep()
        item(ID_AUTOSTART, ("✓ " if st.get("autostart") else "     ") + "开机自动启动")
        item(ID_FONT, "菜单字号：" + str(st.get("menu_px") or 13) + " px")
        sep()
        item(ID_DISCONNECT, "重新连接设备")
        item(ID_ABOUT, "关于 / 状态")
        sep()
        item(ID_QUIT, "退出")
        self._popup_menu = m
        return m

    def _measure_item(self, lp):
        mis = ctypes.cast(lp, ctypes.POINTER(MEASUREITEMSTRUCT)).contents
        if mis.itemID == ID_SEP:
            mis.itemWidth = 0
            mis.itemHeight = int(round(7 * self._dpi() / 96))
            return True
        text = ctypes.cast(mis.itemData, ctypes.c_wchar_p).value or ""
        hdc = _GetDC(self.hwnd)
        font = self._menu_font()
        old = _SelectObject(hdc, font)
        sz = wintypes.SIZE()
        _GetTextExtentPoint32W(hdc, text, len(text), ctypes.byref(sz))
        _SelectObject(hdc, old)
        _DeleteObject(font)
        _ReleaseDC(self.hwnd, hdc)
        mis.itemWidth = sz.cx + int(round(30 * self._dpi() / 96))
        mis.itemHeight = self._item_height()
        return True

    def _draw_item(self, lp):
        dis = ctypes.cast(lp, ctypes.POINTER(DRAWITEMSTRUCT)).contents
        hdc, rc = dis.hDC, dis.rcItem
        if dis.itemID == ID_SEP:
            brush = _CreateSolidBrush(_GetSysColor(COLOR_MENU))
            _FillRect(hdc, ctypes.byref(rc), brush)
            _DeleteObject(brush)
            y = (rc.top + rc.bottom) // 2
            line = wintypes.RECT(rc.left + 10, y, rc.right - 10, y + 1)
            brush = _CreateSolidBrush(_GetSysColor(COLOR_GRAYTEXT))
            _FillRect(hdc, ctypes.byref(line), brush)
            _DeleteObject(brush)
            return True
        text = ctypes.cast(dis.itemData, ctypes.c_wchar_p).value or ""
        selected = bool(dis.itemState & ODS_SELECTED)
        disabled = bool(dis.itemState & (ODS_GRAYED | ODS_DISABLED))
        bg = _GetSysColor(COLOR_HIGHLIGHT if selected else COLOR_MENU)
        brush = _CreateSolidBrush(bg)
        _FillRect(hdc, ctypes.byref(rc), brush)
        _DeleteObject(brush)
        if disabled:
            fg = _GetSysColor(COLOR_GRAYTEXT)
        else:
            fg = _GetSysColor(COLOR_HIGHLIGHTTEXT if selected else COLOR_MENUTEXT)
        old_tc = _SetTextColor(hdc, fg)
        old_bk = _SetBkMode(hdc, 1)            # TRANSPARENT
        font = self._menu_font()
        old_font = _SelectObject(hdc, font)
        pad = int(round(14 * self._dpi() / 96))
        trc = wintypes.RECT(rc.left + pad, rc.top, rc.right - pad, rc.bottom)
        _DrawTextW(hdc, text, -1, ctypes.byref(trc),
                   DT_SINGLELINE | DT_VCENTER | DT_LEFT | DT_NOPREFIX)
        _SelectObject(hdc, old_font)
        _DeleteObject(font)
        _SetBkMode(hdc, old_bk)
        _SetTextColor(hdc, old_tc)
        return True

    def _popup(self):
        m = self._menu()
        pos = POINT()
        _GetCursorPos(ctypes.byref(pos))
        _SetForegroundWindow(self.hwnd)       # required, or menu won't dismiss
        cmd = _TrackPopupMenu(m, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_NONOTIFY,
                              pos.x, pos.y, 0, self.hwnd, None)
        _PostMessage(self.hwnd, WM_NULL, 0, 0)
        _DestroyMenu(m)
        return cmd

    def _dispatch(self, cmd):
        c = self.cb
        st = c.get("get_state", lambda: {})()
        if cmd == ID_OPEN:
            c.get("on_open", lambda: None)()
        elif cmd == ID_SWITCH:
            c.get("on_switch", lambda: None)()
        elif cmd == ID_AUTOSTART:
            c.get("on_autostart", lambda v: None)(not st.get("autostart"))
        elif cmd == ID_DISCONNECT:
            c.get("on_disconnect", lambda: None)()
        elif cmd == ID_ABOUT:
            c.get("on_about", lambda: None)()
        elif cmd == ID_FONT:
            cur = int(st.get("menu_px") or 13)
            nxt = FONT_STEPS[(FONT_STEPS.index(cur) + 1) % len(FONT_STEPS)] \
                if cur in FONT_STEPS else FONT_STEPS[1]
            c.get("on_menu_font", lambda v: None)(nxt)
        elif cmd == ID_QUIT:
            c.get("on_quit", lambda: None)()
            self.stop()

    # -- shell_notify helpers ---------------------------------------------
    def _add_icon(self):
        n = NOTIFYICONDATAW()
        n.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        n.hWnd, n.uID = self.hwnd, 1
        n.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        n.uCallbackMessage = CB_MESSAGE
        n.hIcon = self.hicon
        n.szTip = self.tip[:127]
        self.nid = n
        return bool(_NotifyIcon(NIM_ADD, ctypes.byref(n)))

    def set_tip(self, text):
        self.tip = text
        if self.nid is not None:
            n = self.nid
            n.uFlags, n.szTip = NIF_TIP, text[:127]
            _NotifyIcon(NIM_MODIFY, ctypes.byref(n))

    def balloon(self, title, text):
        if self.nid is None:                  # called before run(): defer it
            self._pending_balloon = (title, text)
            return
        n = NOTIFYICONDATAW()
        n.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        n.hWnd, n.uID = self.hwnd, 1
        n.uFlags = NIF_INFO
        n.szInfo, n.szInfoTitle = text[:255], title[:63]
        n.dwInfoFlags = NIIF_INFO | NIIF_NOSOUND
        _NotifyIcon(NIM_MODIFY, ctypes.byref(n))

    def stop(self):
        if self._destroyed:
            return
        self._destroyed = True
        if self.nid is not None:
            n = NOTIFYICONDATAW()
            n.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            n.hWnd, n.uID = self.hwnd, 1
            _NotifyIcon(NIM_DELETE, ctypes.byref(n))
        if self.hicon:
            _DestroyIcon(self.hicon)
        if self.hwnd:
            _DestroyWindow(self.hwnd)
        _PostQuitMessage(0)

    # -- message loop ------------------------------------------------------
    def run(self):
        global _wndproc_ref
        hinst = _GetModuleHandle(None)

        def wndproc(hwnd, msg, wp, lp):
            try:
                if msg == WM_MEASUREITEM:
                    return 1 if self._measure_item(lp) else 0
                if msg == WM_DRAWITEM:
                    return 1 if self._draw_item(lp) else 0
                if msg == CB_MESSAGE:
                    ev = lp & 0xFFFFFFFF
                    if ev in (WM_RBUTTONUP, WM_CONTEXTMENU):
                        cmd = self._popup()
                        if cmd:
                            self._dispatch(cmd)
                    elif ev == WM_LBUTTONDBLCLK:
                        self.cb.get("on_open", lambda: None)()
                    return 0
                if msg == _taskbar_msg:            # Explorer restarted
                    self._add_icon()
                    return 0
                if msg == WM_CLOSE:
                    # A tray icon has no close affordance: quitting is the
                    # menu's 退出 item, which calls on_quit() and then stop().
                    # Ignoring a stray WM_CLOSE keeps the background app alive
                    # when another tool pokes the hidden window. A real log-off
                    # still ends the process through WM_ENDSESSION/WM_DESTROY.
                    return 0
                if msg == WM_DESTROY:
                    _PostQuitMessage(0)
                    return 0
            except Exception:
                # A raising WNDPROC corrupts the native stack - never let it.
                try:
                    import traceback
                    with open(os.path.join(data_dir(), "tray-error.log"), "a",
                              encoding="utf-8") as f:
                        f.write(traceback.format_exc() + "\n")
                except Exception:
                    pass
                return 0
            return _DefWindowProc(hwnd, msg, wp, lp)

        _wndproc_ref = WNDPROC(wndproc)           # keep GC away
        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
        cls.lpfnWndProc = _wndproc_ref
        cls.hInstance = hinst
        cls.lpszClassName = "SonyHeadphonesTrayWnd"
        if not _RegisterClass(ctypes.byref(cls)) and ctypes.get_last_error() != 1410:
            raise OSError("RegisterClassExW failed: %d" % ctypes.get_last_error())

        self.hwnd = _CreateWindow(0, "SonyHeadphonesTrayWnd", "SonyHeadphonesTray",
                                  0, 0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            raise OSError("CreateWindowExW failed: %d" % ctypes.get_last_error())
        self.hicon = make_icon()
        if not self._add_icon():
            raise OSError("Shell_NotifyIconW(NIM_ADD) failed")
        if self._pending_balloon:
            title, text = self._pending_balloon
            self._pending_balloon = None
            self.balloon(title, text)

        msg = MSG()
        while True:
            r = _GetMessage(ctypes.byref(msg), None, 0, 0)
            if r == 0 or r == -1:
                break
            _TranslateMessage(ctypes.byref(msg))
            _DispatchMessage(ctypes.byref(msg))
