#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the per-model product images for the control panel.

Source: Sony's own online store CDN (model-specific product renders), one per
colourway. The suffix of each file is the ModelColor suffix the headset itself
reports in `04 03 -> 05 03 <series> <color>`, so the panel can pick the right
render from the colour it decoded:

  WH-1000XM4-B (黑)  WH-1000XM4-S (铂金银)  WH-1000XM4-L (深夜蓝)  WH-1000XM4-W (白)
  WF-LS900N-B (黑)   WF-LS900N-W (白)        WF-LS900N-L (地球蓝)   WF-LS900N-C (米色)

The App's own CloudModelInfo image service needs an authenticated GraphQL
call, so these official per-model renders are used instead. These are photo
renders (not line art), so they stay bitmaps; the traced SVG line art in
app/assets/*.svg remains as an offline fallback.

Run: python make_cloud_assets.py
"""
import os
import urllib.request

import cv2
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "..", "cloudimg")
ASSETS = os.path.join(HERE, "..", "app", "assets")

BASE = "https://store.sony.com.tw/resource/product_files/%s/%s_pi.jpg"

# (output key, Sony SKU, cut-out style)
#   key   -> luminance keying, for the dark bodies
#   light -> border flood-fill, for white/silver/cream bodies that luminance
#            keying would erase
#
# The bare model name (xm4, ls900n) is the colour-agnostic default used when a
# headset reports a colour we have no render for.
# The bare name doubles as the default for that model, so only the colourways
# that differ from it get their own file (app.js maps BLACK -> xm4.png and
# earth blue -> ls900n.png instead of shipping byte-identical copies).
VARIANTS = [
    ("xm4",          "WH-1000XM4-B", "key"),      # 黑，也是默认图
    ("xm4_s",        "WH-1000XM4-S", "light"),    # 铂金银
    ("xm4_l",        "WH-1000XM4-L", "key"),      # 深夜蓝
    ("xm4_w",        "WH-1000XM4-W", "light"),    # 白
    ("ls900n",       "WF-LS900N-L",  "key"),      # 地球蓝，也是默认图
    ("ls900n_b",     "WF-LS900N-B",  "key"),      # 黑
    ("ls900n_w",     "WF-LS900N-W",  "light"),    # 白
    ("ls900n_cream", "WF-LS900N-C",  "light"),    # 米色
]


def fetch(url, path):
    if os.path.isfile(path):
        return
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r, open(path, "wb") as f:
        f.write(r.read())


def _save(im, dst):
    """WebP for the shipped renders: identical at panel size, ~82% smaller.

    PNG alpha was 589 KB for eight colourways; WebP q88 comes out at 105 KB,
    which matters because every byte ends up inside the single-file exe.
    """
    if dst.lower().endswith(".webp"):
        im.save(dst, "WEBP", quality=88, method=6)
    else:
        im.save(dst)
    return os.path.getsize(dst)


def _sharpen(rgba):
    """Unsharp-mask the RGB channels only, so the alpha edge stays clean.

    The store renders are only 270-336 px wide; after the small upscale an
    unsharp pass restores the edge definition that the panel's 118 px photo
    would otherwise lose.
    """
    rgb = rgba.convert("RGB").filter(
        ImageFilter.UnsharpMask(radius=1.1, percent=55, threshold=2))
    out = rgb.convert("RGBA")
    out.putalpha(rgba.getchannel("A"))
    return out


def to_transparent(src, dst, size=384, pad=0.07):
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    lum = a.mean(axis=2)
    mn, mx = a.min(axis=2), a.max(axis=2)
    # White studio background -> alpha ramp; kill flat bright pixels entirely
    # so JPEG noise does not leave a white halo.
    alpha = np.clip((250 - lum) * 3.4, 0, 255).astype(np.uint8)
    alpha[(mn > 230) & ((mx - mn) < 20)] = 0
    rgba = np.dstack([a.astype(np.uint8), alpha])
    out = Image.fromarray(rgba, "RGBA")
    box = out.getchannel("A").getbbox()
    if box:
        out = out.crop(box)
    w, h = out.size
    scale = size * (1 - 2 * pad) / max(w, h)
    out = out.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    out = _sharpen(out)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(out, ((size - out.width) // 2, (size - out.height) // 2))
    return _save(canvas, dst)


def to_transparent_light(src, dst, size=384, pad=0.06, feather=1.1,
                         thresh_bg=244):
    """White / silver / cream bodies on the white studio background.

    Two earlier attempts failed here. Luminance keying erases the body along
    with the background, and feathering only the edges leaves a white
    rectangle that is plainly visible on the panel's plinth. So the background
    is instead identified structurally: flood-fill the near-white area from the
    four borders. Studio white touching an edge disappears, while white
    highlights *enclosed* by the product outline (ear-pad rims, the inside of
    the headband) stay opaque, which is what keeps a white headset looking like
    a headset.
    """
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    mn, mx = a.min(axis=2), a.max(axis=2)
    bgish = ((mn > thresh_bg) & ((mx - mn) < 14)).astype(np.uint8)

    work = bgish.copy()
    h, w = work.shape
    scratch = np.zeros((h + 2, w + 2), np.uint8)   # cv2 requires the halo
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if work[seed[1], seed[0]] == 1:
            cv2.floodFill(work, scratch, seed, 2, loDiff=0, upDiff=0,
                          flags=4 | cv2.FLOODFILL_FIXED_RANGE)

    alpha = np.where(work == 2, 0, 255).astype(np.uint8)
    alpha = np.asarray(Image.fromarray(alpha, "L").filter(
        ImageFilter.GaussianBlur(feather)))
    out = Image.fromarray(np.dstack([np.asarray(im), alpha]), "RGBA")

    solid = Image.fromarray(alpha, "L").point(lambda v: 255 if v > 8 else 0)
    box = solid.getbbox()
    if box:
        out = out.crop(box)
    w, h = out.size
    scale = size * (1 - 2 * pad) / max(w, h)
    out = out.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                     Image.LANCZOS)
    out = _sharpen(out)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(out, ((size - out.width) // 2,
                                 (size - out.height) // 2))
    return _save(canvas, dst)


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(ASSETS, exist_ok=True)
    total = 0
    for key, sku, style in VARIANTS:
        url = BASE % (sku, sku)
        src = os.path.join(CACHE, key + "_src.jpg")
        fetch(url, src)
        dst = os.path.join(ASSETS, key + ".webp")
        stale = os.path.join(ASSETS, key + ".png")
        if os.path.isfile(stale):
            os.remove(stale)          # never ship both formats
        convert = to_transparent_light if style == "light" else to_transparent
        n = convert(src, dst)
        total += n
        print("%-13s %-5s <- %-14s -> %s.webp (%6d B)" % (
            key, style, sku, key, n))
    print("%d files, %.0f KB total" % (len(VARIANTS), total / 1024))


if __name__ == "__main__":
    main()
