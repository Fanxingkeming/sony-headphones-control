#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the per-model product images for the control panel.

Source: Sony's own online store CDN (model-specific product renders):

  https://store.sony.com.tw/resource/product_files/WH-1000XM4-B/WH-1000XM4-B_pi.jpg
  https://store.sony.com.tw/resource/product_files/WF-LS900N-L/WF-LS900N-L_pi.jpg
  https://store.sony.com.tw/resource/product_files/WF-LS900N-W/WF-LS900N-W_pi.jpg

The App's own CloudModelInfo image service needs an authenticated GraphQL
call, so these official per-model renders are used instead. These are photo
renders (not line art), so they stay bitmaps; the traced SVG line art in
app/assets/*.svg remains as an offline fallback.

Run: python make_cloud_assets.py
"""
import os
import urllib.request

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cloudimg")
ASSETS = os.path.join(HERE, "app", "assets")

SOURCES = {
    "xm4": ("https://store.sony.com.tw/resource/product_files/"
            "WH-1000XM4-B/WH-1000XM4-B_pi.jpg", "xm4_src.jpg"),
    "ls900n": ("https://store.sony.com.tw/resource/product_files/"
               "WF-LS900N-L/WF-LS900N-L_pi.jpg", "ls900n_src.jpg"),
    "ls900n_w": ("https://store.sony.com.tw/resource/product_files/"
                 "WF-LS900N-W/WF-LS900N-W_pi.jpg", "ls900n_w_src.jpg"),
}


def fetch(url, path):
    if os.path.isfile(path):
        return
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r, open(path, "wb") as f:
        f.write(r.read())


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
    canvas.save(dst)
    return os.path.getsize(dst)


def to_transparent_white(src, dst, size=384, pad=0.06, feather=0.13,
                         threshold=6):
    """White product on a white studio background.

    Luminance keying would erase the earbuds along with the background, so the
    render is kept intact: crop to the product's own bounding box (found from
    the soft grey outline, not from pure-white pixels), then feather only the
    four edges into alpha. The control panel puts products on a light plinth,
    so the remaining white studio background melts into it seamlessly.
    """
    im = Image.open(src).convert("RGB")
    lum = np.asarray(im).mean(axis=2)
    diff = Image.fromarray((255 - lum).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(1.2))
    mask = np.asarray(diff) > threshold
    ys, xs = np.where(mask)
    if len(xs):
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        mx, my = int((x1 - x0) * 0.08), int((y1 - y0) * 0.14)
        im = im.crop((max(0, x0 - mx), max(0, y0 - my),
                      min(im.width, x1 + mx), min(im.height, y1 + my)))
    im = im.convert("RGBA")
    w, h = im.size
    scale = size * (1 - 2 * pad) / max(w, h)
    im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                   Image.LANCZOS)
    im = _sharpen(im)
    W, H = im.size
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = np.minimum(xx, W - 1 - xx) / (W * feather)
    dy = np.minimum(yy, H - 1 - yy) / (H * feather)
    t = np.clip(np.minimum(dx, dy), 0, 1)
    alpha = (t * t * (3 - 2 * t) * 255).astype(np.uint8)   # smoothstep
    im.putalpha(Image.fromarray(alpha, "L"))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((size - W) // 2, (size - H) // 2))
    canvas.save(dst)
    return os.path.getsize(dst)


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(ASSETS, exist_ok=True)
    for key, (url, name) in SOURCES.items():
        src = os.path.join(CACHE, name)
        fetch(url, src)
        dst = os.path.join(ASSETS, key + ".png")
        convert = to_transparent_white if key.endswith("_w") else to_transparent
        n = convert(src, dst)
        print("%-9s <- %-30s -> %s.png (%d bytes)" % (
            key, url.rsplit("/", 1)[-1], key, n))


if __name__ == "__main__":
    main()
