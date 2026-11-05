# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the single-file, tray-enabled Windows build."""
import os

HERE = os.path.abspath(globals().get("SPECPATH", os.getcwd()))
TOOLS = os.path.normpath(os.path.join(HERE, "..", "tools"))

# Static assets are read from sys._MEIPASS by server.py at runtime.
DATAS = [(os.path.join(HERE, f), ".") for f in
         ("index.html", "style.css", "app.js", "manifest.json", "sw.js")]
ASSETS_DIR = os.path.join(HERE, "assets")

# SHC_CLEAN=1 produces the redistributable package. It leaves out the official
# Sony store renders and the Sound Connect app icon, neither of which can be
# redistributed; the panel then falls back to the traced line art and the
# programmatic tray icon. A user who owns the artwork can drop the renders into
# an `assets` folder next to the exe (server.asset_path prefers that folder).
CLEAN = os.environ.get("SHC_CLEAN") == "1"
if os.path.isdir(ASSETS_DIR):
    # The traced line art (xm4.svg / ls900n.svg) is only a fallback for a
    # checkout without product renders. When the WebP render is present the SVG
    # is unreachable, so bundling it would just add ~35 KB to the exe.
    rendered = {os.path.splitext(n)[0] for n in os.listdir(ASSETS_DIR)
                if n.endswith(".webp")}
    for name in sorted(os.listdir(ASSETS_DIR)):
        stem, ext = os.path.splitext(name)
        if CLEAN:
            if ext == ".webp" or name == "app-icon.ico":
                continue
        elif ext == ".svg" and stem in rendered:
            continue
        DATAS.append((os.path.join(ASSETS_DIR, name), "assets"))

# Verified against the runtime import set of appmain + server + tray.
# `email`, `http.client`, `ssl`, `ipaddress`, `datetime` MUST stay (http.server).
EXCLUDES = [
    # GUI / scientific stacks that PyInstaller hooks like to drag in
    "tkinter", "_tkinter", "turtle", "turtledemo", "idlelib",
    "PIL", "numpy", "PyQt5", "PySide2", "PySide6", "matplotlib", "pandas",
    "scipy", "IPython", "jupyter", "pytest",
    # dev / test / packaging stdlib
    "unittest", "doctest", "pydoc", "pydoc_data", "test", "lib2to3",
    "ensurepip", "venv", "distutils", "setuptools", "pkg_resources", "pip",
    "curses", "readline", "rlcompleter", "this", "antigravity",
    # concurrency / data / net stacks this app never touches
    "asyncio", "multiprocessing", "concurrent", "xml", "xmlrpc",
    "sqlite3", "logging",
    # TLS: http.client only does `try: import ssl / except ImportError: pass`.
    # This server is plain HTTP on 127.0.0.1, so dropping ssl also drops
    # libcrypto-3-x64.dll (1.4 MiB) and libssl-3-x64.dll (0.3 MiB).
    "ssl", "_ssl", "_hashlib", "hashlib",
    # never used by the app or by http.server's import path
    "decimal", "_decimal", "unicodedata", "bz2", "lzma", "gzip", "tarfile",
    "ftplib", "imaplib", "smtplib", "poplib", "telnetlib",
    "urllib.request", "urllib.error", "urllib.robotparser",
    "email.mime", "http.cookies", "http.cookiejar",
    # frozen boot helpers that are not used
    "pdb", "profile", "cProfile", "timeit", "trace",
    # Pulled in by hooks but never imported at runtime (verified by comparing
    # sys.modules before/after importing appmain + server + tray).
    "typing", "inspect", "zipfile", "argparse", "ast", "statistics",
    "dataclasses", "dis", "pickle", "subprocess", "importlib.metadata",
    "email._header_value_parser", "email.headerregistry", "getopt",
]
# NOTE: shutil / subprocess / socketserver / ssl / bz2 / lzma are imported by
# http.server at module level - never exclude them.

a = Analysis(
    [os.path.join(HERE, "appmain.py")],
    pathex=[HERE, TOOLS],
    binaries=[],
    datas=DATAS,
    hiddenimports=["tandem_client", "xm4_control", "linkbuds"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=2,
)
# Windows 10/11 provide the UCRT and the api-ms-win-* API-set forwarders in
# System32. PyInstaller had picked up private copies from a JDK on PATH; they
# are redundant (and version-skewed), so let the OS resolve them instead.
def _system_provided(name):
    n = name.lower()
    return n == "ucrtbase.dll" or n.startswith("api-ms-win-")


a.binaries = [b for b in a.binaries if not _system_provided(b[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SonyHeadphonesControl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=["vcruntime140.dll", "vcruntime140_1.dll", "qwindows.dll"],
    runtime_tmpdir=None,
    console=(os.environ.get("SHC_CONSOLE") == "1"),
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(HERE, "icon.ico"),
    # Explorer's Details tab and the UAC prompt read this. Without it the file
    # has no product name, which looks worse than it is.
    version=os.path.join(HERE, "version_info.txt"),
)
