#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point for the single-file Windows build.

Starts the local HTTP server on a daemon thread, then owns a system-tray icon.
Run from source with `python appmain.py`; the frozen exe uses the same path.
"""
import ctypes
import json
import os
import sys
import threading
import time

import server as srv
import tray

VERSION = "1.0"
PREFS_NAME = "prefs.json"
PORT_NAME = "port.json"


def _set_dpi_awareness():
    """Become DPI-aware *before* any window or menu exists.

    The tray popup menu and message boxes are drawn by the shell. In a
    DPI-unaware process Windows bitmap-scales them at 125-200 % display
    scaling, which is exactly why the menu looked blurry.
    """
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4 (Win10 1703+)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except Exception:
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return "per-monitor"
    except Exception:
        pass
    try:
        if ctypes.windll.user32.SetProcessDPIAware():
            return "system"
    except Exception:
        pass
    return "none"


DPI_MODE = _set_dpi_awareness()


LOG_MAX = 512 * 1024          # one generation is plenty for a tray app
LOG_TICKS = {"n": 0}


def _rotate_log(path):
    """Keep app.log bounded: rename to .1 and start over.

    An always-on tray app logs on every start and every failure, so without
    this the file grows forever. The size is checked every 64 writes instead of
    on each one, which keeps the common path at a single append.
    """
    LOG_TICKS["n"] += 1
    if LOG_TICKS["n"] % 64:
        return
    try:
        if os.path.getsize(path) < LOG_MAX:
            return
    except OSError:
        return
    try:
        os.replace(path, path + ".1")
    except OSError:
        pass


def log(text):
    try:
        path = os.path.join(tray.data_dir(), "app.log")
        with open(path, "a", encoding="utf-8") as f:
            # Timestamped: a bare line tells you what happened but not when,
            # which made correlating a failure with a user action impossible.
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
        _rotate_log(path)
    except Exception:
        pass


def fatal(text):
    log("FATAL: " + text)
    if not getattr(sys, "frozen", False):
        sys.stderr.write(text + "\n")     # console/source mode: never block
        return
    # A plain MessageBoxW would hang an autostart / --minimized launch forever.
    try:
        ctypes.windll.user32.MessageBoxTimeoutW(
            0, text[:1500], "Sony Headphones Control", 0x10, 0, 15000)
    except Exception:
        pass                              # the traceback is already in app.log


class App:
    def __init__(self, argv):
        self.argv = argv
        self.port = self._opt_int("--port", 8765)
        self.minimized = "--minimized" in argv or "--no-browser" in argv
        self.data = tray.data_dir()
        self.prefs_path = os.path.join(self.data, PREFS_NAME)
        self.port_path = os.path.join(self.data, PORT_NAME)
        self.prefs = {"device": "xm4", "menu_px": 13}
        try:
            with open(self.prefs_path, encoding="utf-8") as f:
                self.prefs.update(json.load(f))
        except Exception:
            pass
        dev = self._opt_str("--device")
        if dev in srv.DEVICES:
            self.prefs["device"] = dev
        self.device_override = dev if dev in srv.DEVICES else None
        if self.prefs.get("device") not in srv.DEVICES:
            self.prefs["device"] = "xm4"
        self.server = None
        self.tray = None
        self._stopped = False

    def _opt_int(self, flag, default):
        try:
            return int(self.argv[self.argv.index(flag) + 1])
        except (ValueError, IndexError):
            return default

    def _opt_str(self, flag):
        try:
            return self.argv[self.argv.index(flag) + 1]
        except (ValueError, IndexError):
            return None

    def save_prefs(self):
        try:
            with open(self.prefs_path, "w", encoding="utf-8") as f:
                json.dump(self.prefs, f)
        except OSError:
            pass

    def url(self, switch=False):
        # The browser asks /api/context which headset is connected; the URL
        # never pins one (except an explicit --device, for testing).
        parts = []
        if self.device_override:
            parts.append("device=" + self.device_override)
        if switch:
            parts.append("switch=1")
        return "http://127.0.0.1:%d/" % self.port + (
            "?" + "&".join(parts) if parts else "")

    def open_panel(self):
        tray.open_panel(self.url())

    def switch_panel(self):
        tray.open_panel(self.url(switch=True))

    def current_key(self):
        key = srv.CURRENT.get("key") or srv.LAST_DEVICE or "xm4"
        return key if key in srv.DEVICES else "xm4"

    # -- tray callbacks ----------------------------------------------------
    def state(self):
        key = self.current_key()
        return {"device": key, "device_label": srv.DEVICES[key]["short"],
                "autostart": tray.autostart_enabled(),
                "menu_px": int(self.prefs.get("menu_px") or 13)}

    def set_menu_font(self, px):
        self.prefs["menu_px"] = int(px)
        self.save_prefs()
        log("tray menu font -> %d px" % self.prefs["menu_px"])

    def set_autostart(self, on):
        try:
            tray.set_autostart(on)
            self.tray.balloon("开机自动启动", "已%s" % ("开启" if on else "关闭"))
        except Exception as e:
            self.tray.balloon("设置失败", str(e))

    def disconnect(self):
        with srv.SESSION.lock:
            srv.SESSION.dispose()
        self.tray.balloon("已断开", "下次操作会重新连接耳机")

    def about(self):
        d = srv.DEVICES[self.current_key()]
        self.tray.balloon(
            "Sony Headphones Control v%s" % VERSION,
            "%s (%s) · 端口 %d · DPI %s" % (
                d["name"], d["protocol"], self.port, DPI_MODE))

    def quit(self):
        if self._stopped:
            return
        self._stopped = True
        srv.stop_server(self.server)
        try:
            os.remove(self.port_path)
        except OSError:
            pass
        log("stopped")

    def _battery_watch(self):
        """Drain queued battery alerts and refresh the level now and then.

        Alerts are produced inside read_status(), i.e. whenever the panel is
        open. The periodic tick additionally re-reads the level over the link
        that is already established, so a headset left connected overnight
        still warns even if no browser is open. It never opens a new link.
        """
        first_tick = time.monotonic() + 90        # let the start-up probe settle
        next_tick = first_tick
        while not self._stopped:
            try:
                item = srv.pop_alert()
            except Exception:
                item = None
            if item:
                try:
                    log("battery alert: %s" % item[1])
                    self.tray.balloon(item[0], item[1])
                except Exception:
                    pass
            if time.monotonic() >= next_tick:
                next_tick = time.monotonic() + 600
                try:
                    srv.battery_tick()
                except Exception:
                    pass
            time.sleep(2)

    def _sync_tip(self):
        if self.tray:
            d = srv.DEVICES[self.current_key()]
            self.tray.set_tip("Sony 耳机 · %s · :%d" % (d["short"], self.port))

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        if not tray.ensure_single_instance():
            # A second launch just brings up the already-running panel.
            try:
                with open(self.port_path, encoding="utf-8") as f:
                    self.port = int(json.load(f)["port"])
            except Exception:
                pass
            if not self.minimized:
                tray.open_panel(self.url())
            return 0

        self.server, self.port = srv.start_server(self.port)
        try:
            with open(self.port_path, "w", encoding="utf-8") as f:
                json.dump({"port": self.port}, f)
        except OSError:
            pass
        log("started on port %d (frozen=%s dpi=%s)" % (
            self.port, getattr(sys, "frozen", False), DPI_MODE))

        self.tray = tray.Tray({
            "on_open": self.open_panel,
            "on_switch": self.switch_panel,
            "on_autostart": self.set_autostart,
            "on_menu_font": self.set_menu_font,
            "on_disconnect": self.disconnect,
            "on_about": self.about,
            "on_quit": self.quit,
            "get_state": self.state,
        })
        self._sync_tip()
        self.tray.balloon("Sony 耳机控制面板", "已启动，双击图标打开面板；右键显示菜单")
        threading.Thread(target=self._battery_watch, name="battery-watch",
                         daemon=True).start()
        if not self.minimized:
            threading.Timer(0.9, self.open_panel).start()
        self.tray.run()                       # blocks until 退出
        self.quit()
        return 0


def main():
    try:
        return App(sys.argv[1:]).start()
    except Exception:
        import traceback
        fatal(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
