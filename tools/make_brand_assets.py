#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the two brand assets used by the control panel.

1. ``app-icon.ico`` -- the Sound Connect launcher icon. The sharpest source in
   the APK is the *adaptive* icon: a 432x432 foreground (``icon_fg.png``) over
   a 432x432 background (``icon_bg.png``). Compositing them, applying the
   launcher's 72/108 visible-area crop and a round mask yields a 288x288
   master -- 1.5x the 192px legacy ``icon.png`` -- so the multi-size .ico
   (up to 256px) stays sharp in Explorer, the taskbar and the tray.
2. ``sony-logo.svg`` -- the official SONY wordmark vector from Wikimedia
   Commons, stripped of all editor metadata: one <path>, no bitmaps.

Sources:
  E:/Downloads/sound_connect_v13.3.0.apk
  https://commons.wikimedia.org/wiki/File:Sony_logo.svg

Run: python make_brand_assets.py
"""
import os
import re
import struct
import urllib.request
import zipfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app")
ASSETS = os.path.join(APP, "assets")
CACHE = os.path.join(HERE, "apk_assets")
CLOUD = os.path.join(HERE, "cloudimg")

APK = os.environ.get(
    "SOUND_CONNECT_APK", r"E:/Downloads/sound_connect_v13.3.0.apk")
APK_FG = "res/mipmap-xxxhdpi-v4/icon_fg.png"
APK_BG = "res/mipmap-xxxhdpi-v4/icon_bg.png"
SONY_SVG_URL = "https://upload.wikimedia.org/wikipedia/commons/c/ca/Sony_logo.svg"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def apk_png(name):
    os.makedirs(CACHE, exist_ok=True)
    dst = os.path.join(CACHE, name.replace("/", "_"))
    if not os.path.isfile(dst):
        with zipfile.ZipFile(APK) as z:
            open(dst, "wb").write(z.read(name))
    return dst


def master_icon():
    """432px adaptive foreground over background -> 288px round master."""
    fg = Image.open(apk_png(APK_FG)).convert("RGBA")
    bg = Image.open(apk_png(APK_BG)).convert("RGBA")
    comp = bg.copy()
    comp.alpha_composite(fg)
    w, h = comp.size
    side = int(w * 72 / 108)                    # adaptive-icon visible area
    box = ((w - side) // 2, (h - side) // 2,
           (w + side) // 2, (h + side) // 2)
    comp = comp.crop(box)
    ss = 4                                      # supersampled round mask
    mask = Image.new("L", (side * ss, side * ss), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, side * ss - 1, side * ss - 1), fill=255)
    comp.putalpha(mask.resize((side, side), Image.LANCZOS))
    return comp


def dib_from_image(im):
    """BITMAPINFOHEADER + bottom-up BGRA XOR + 1bpp AND, as an .ico entry."""
    im = im.convert("RGBA")
    w, h = im.size
    px = np.asarray(im)
    hdr = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    row_bytes = ((w + 31) // 32) * 4
    xor = bytearray()
    and_mask = bytearray()
    for y in range(h - 1, -1, -1):
        maskrow = bytearray(row_bytes)
        for x in range(w):
            r, g, b, a = px[y, x]
            xor += bytes((int(b), int(g), int(r), int(a)))   # DIB is BGRA
            if a < 128:
                maskrow[x // 8] |= 0x80 >> (x % 8)           # 1 = transparent
        and_mask += maskrow
    return hdr + bytes(xor) + bytes(and_mask)


def make_icon():
    src = master_icon()
    # keep a high-res preview outside the packaged assets
    src.resize((512, 512), Image.LANCZOS).save(
        os.path.join(CACHE, "app-icon-512.png"))
    images = [(s, dib_from_image(src.resize((s, s), Image.LANCZOS)))
              for s in ICO_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    for s, bits in images:
        w = 0 if s >= 256 else s
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32,
                               len(bits), offset)
        offset += len(bits)
    data = header + entries + b"".join(b for _, b in images)
    os.makedirs(ASSETS, exist_ok=True)
    outs = [os.path.join(ASSETS, "app-icon.ico"),
            os.path.join(APP, "icon.ico")]
    for p in outs:
        with open(p, "wb") as f:
            f.write(data)
    print("app icon  %dx%d master -> %s (%d bytes, %d sizes: %s)" % (
        src.width, src.height, ", ".join(os.path.basename(p) for p in outs),
        len(data), len(ICO_SIZES), "/".join(map(str, ICO_SIZES))))


def make_sony_svg():
    os.makedirs(CLOUD, exist_ok=True)
    src = os.path.join(CLOUD, "sony_logo_src.svg")
    if not os.path.isfile(src):
        req = urllib.request.Request(SONY_SVG_URL,
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            open(src, "wb").write(r.read())
    text = open(src, encoding="utf-8").read()
    m = re.search(r"<path\b[^>]*?/>", text, re.S)
    if not m:
        raise RuntimeError("no <path> found in the SONY wordmark SVG")
    tag = re.sub(r'\sfill="[^"]*"', '', m.group(0))
    tag = re.sub(r'\sid="[^"]*"', '', tag)
    tag = tag.replace("<path", '<path fill="#000000"', 1)
    out = ('<svg xmlns="http://www.w3.org/2000/svg" '
           'viewBox="0 0 1280 225.28" role="img" aria-label="SONY">\n'
           '  ' + tag.strip() + '\n</svg>\n')
    dst = os.path.join(ASSETS, "sony-logo.svg")
    open(dst, "w", encoding="utf-8").write(out)
    print("sony logo %s -> sony-logo.svg (%d bytes, 1 vector path)" % (
        os.path.basename(src), len(out.encode("utf-8"))))


if __name__ == "__main__":
    make_icon()
    make_sony_svg()
