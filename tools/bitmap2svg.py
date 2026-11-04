"""Vectorize a dark-on-white bitmap (APK drawable PNG) into a standalone SVG.

Uses OpenCV contour tracing with a few tonal layers so soft gradients in the
original flat illustration survive as real vector paths instead of a bitmap.

Usage: python bitmap2svg.py
"""
import io
import os
import numpy as np
import cv2
from PIL import Image

# tonal bands: many thin bands approximate the soft gradient of the original
# flat illustration without embedding any raster data
def _band_color(b):
    g = max(0, b - 6)
    return '#%02X%02X%02X' % (g, g, g)


LAYERS = [(b, _band_color(b)) for b in range(248, 38, -12)]
MIN_AREA = 24


def contours_to_path(contours, hierarchy, eps=0.8):
    """Return an SVG path string with even-odd holes (RETR_CCOMP hierarchy)."""
    if hierarchy is None:
        hierarchy = []
    segs = []
    n = len(contours)
    for i, cnt in enumerate(contours):
        if len(cnt) < 3:
            continue
        area = abs(cv2.contourArea(cnt))
        if area < MIN_AREA:
            continue
        # skip hole contours (they are emitted together with their parent)
        h = hierarchy[i] if i < len(hierarchy) else None
        if h is not None and len(h) >= 4 and h[3] != -1:
            continue
        ap = cv2.approxPolyDP(cnt, eps, True).reshape(-1, 2)
        if len(ap) < 3:
            continue
        segs.append('M' + ' L'.join('%.2f,%.2f' % (x, y) for x, y in ap) + ' Z')
        # child holes
        child = h[2] if (h is not None and len(h) >= 4) else -1
        while child != -1 and child < n:
            ch = contours[child]
            if abs(cv2.contourArea(ch)) >= MIN_AREA and len(ch) >= 3:
                hp = cv2.approxPolyDP(ch, eps, True).reshape(-1, 2)
                segs.append('M' + ' L'.join('%.2f,%.2f' % (x, y) for x, y in hp) + ' Z')
            hh = hierarchy[child] if child < len(hierarchy) else None
            child = hh[0] if (hh is not None and len(hh) >= 4) else -1
    if not segs:
        return ''
    return ' '.join(segs)


def vectorize(png_bytes, crop, out_svg, out_png=None, size=512, padding=0.10):
    im = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    rgb = np.array(bg.convert('RGB'))
    x0, y0, x1, y1 = crop
    arr = rgb[y0:y1, x0:x1]
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    body = []
    for bound, color in LAYERS:
        mask = (gray < bound).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        h = hier[0].tolist() if hier is not None else None
        d = contours_to_path(list(cnts), h)
        if d:
            body.append('  <path d="%s" fill="%s" fill-rule="evenodd"/>' % (d, color))

    w, h = x1 - x0, y1 - y0
    # fit into a square canvas with padding
    scale = (size * (1 - 2 * padding)) / max(w, h)
    tw, th = w * scale, h * scale
    ox = (size - tw) / 2
    oy = (size - th) / 2
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d">\n'
           '  <g transform="translate(%.3f %.3f) scale(%.6f)">\n%s\n  </g>\n</svg>\n'
           % (size, size, size, size, ox, oy, scale, '\n'.join(body)))
    with open(out_svg, 'w', encoding='utf-8') as f:
        f.write(svg)

    if out_png:
        # transparent PNG fallback: crop then alpha-out white background
        crop_im = bg.crop(crop).convert('RGB')
        a = np.array(crop_im)
        # whiteness -> alpha, keep original dark colors
        lum = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
        alpha = np.clip((255 - lum.astype(np.int16)) * 2.6, 0, 255).astype(np.uint8)
        rgba = np.dstack([a, alpha])
        side = int(max(w, h) * (1 / (1 - 2 * padding)))
        src = Image.fromarray(rgba, 'RGBA')
        scale_png = (size * (1 - 2 * padding)) / max(w, h)
        nw, nh = int(w * scale_png), int(h * scale_png)
        src = src.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        canvas.alpha_composite(src, ((size - nw) // 2, (size - nh) // 2))
        canvas.save(out_png)
    return len(svg), len(body)
