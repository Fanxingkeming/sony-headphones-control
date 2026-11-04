"""Convert Android VectorDrawable XML (plain text, e.g. Compose Multiplatform
assets/composeResources drawables) into standalone SVG.

Usage: python vd2svg.py <input.xml> <output.svg>
Also importable: vd_to_svg(xml_string) -> svg_string
"""
import sys
import re
import xml.etree.ElementTree as ET

ANDROID = '{http://schemas.android.com/apk/res/android}'
AAPT = '{http://schemas.android.com/aapt}'

def _a(el, name, default=None):
    return el.get(ANDROID + name, default)

def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def _color(v, alpha_attr=None):
    """#RRGGBB / #AARRGGBB -> (css color, extra opacity multiplier)."""
    if not v:
        return None, 1.0
    v = v.strip()
    if v.startswith('#'):
        h = v[1:]
        if len(h) == 8:  # AARRGGBB
            a = int(h[0:2], 16) / 255.0
            return '#' + h[2:], a
        if len(h) == 6:
            return '#' + h, 1.0
        if len(h) == 3:
            return '#' + ''.join(c * 2 for c in h), 1.0
        if len(h) == 4:  # ARGB
            return '#' + ''.join(c * 2 for c in h[1:]), int(h[0], 16) / 15.0
    return v, 1.0

class Conv:
    def __init__(self):
        self.clips = []
        self.clip_id = 0
        self.defs = []
        self.grad_id = 0

    def gradient(self, g):
        """Handle <gradient> child of a path (aapt:attr style inline)."""
        self.grad_id += 1
        gid = 'grad%d' % self.grad_id
        start = _a(g, 'startX'); end = _a(g, 'endX')
        sy = _a(g, 'startY'); ey = _a(g, 'endY')
        typ = _a(g, 'type', 'linear')
        stops = []
        for item in g:
            if item.tag.endswith('item'):
                off = _a(item, 'offset')
                col, _ = _color(_a(item, 'color'))
                opa = _num(_a(item, 'alpha', '1'), 1.0)
                stops.append('    <stop offset="%s" stop-color="%s" stop-opacity="%s"/>'
                             % (off or '0', col or '#000', opa))
        if not stops:
            items = re.findall(r'android:(?:color|offset)="([^"]+)"', ET.tostring(g, encoding='unicode'))
        if typ == 'radial':
            cx = _a(g, 'centerX', '0'); cy = _a(g, 'centerY', '0'); r = _a(g, 'gradientRadius', '1')
            s = ('  <radialGradient id="%s" cx="%s" cy="%s" r="%s" gradientUnits="userSpaceOnUse">\n%s\n  </radialGradient>'
                 % (gid, cx, cy, r, '\n'.join(stops)))
        else:
            s = ('  <linearGradient id="%s" x1="%s" y1="%s" x2="%s" y2="%s" gradientUnits="userSpaceOnUse">\n%s\n  </linearGradient>'
                 % (gid, start or '0', sy or '0', end or '1', ey or '0', '\n'.join(stops)))
        self.defs.append(s)
        return 'url(#%s)' % gid

    def path(self, el, inherited_clip=None):
        d = _a(el, 'pathData', '')
        if not d:
            return ''
        attrs = []
        # fill: gradient child wins over solid fillColor
        fill = None
        for child in el:
            if child.tag.endswith('gradient') or 'gradient' in child.tag:
                fill = self.gradient(child)
                break
        if fill is None:
            c, ca = _color(_a(el, 'fillColor'))
            fa = _num(_a(el, 'fillAlpha', '1'), 1.0)
            if c:
                fill = c
                if ca * fa < 0.999:
                    attrs.append('fill-opacity="%.4f"' % (ca * fa))
            else:
                fill = 'none'
        attrs.append('fill="%s"' % fill)
        ft = _a(el, 'fillType')
        if ft == 'evenOdd':
            attrs.append('fill-rule="evenodd"')
        sc, sca = _color(_a(el, 'strokeColor'))
        if sc:
            sa = _num(_a(el, 'strokeAlpha', '1'), 1.0)
            attrs.append('stroke="%s"' % sc)
            attrs.append('stroke-width="%s"' % _a(el, 'strokeWidth', '1'))
            if sca * sa < 0.999:
                attrs.append('stroke-opacity="%.4f"' % (sca * sa))
            cap = _a(el, 'strokeLineCap')
            if cap: attrs.append('stroke-linecap="%s"' % cap)
            join = _a(el, 'strokeLineJoin')
            if join: attrs.append('stroke-linejoin="%s"' % join)
        clip = inherited_clip
        if clip:
            attrs.append('clip-path="url(#%s)"' % clip)
        return '  <path d="%s" %s/>' % (d, ' '.join(attrs))

    def children(self, el, clip=None):
        out = []
        local_clip = clip
        for child in el:
            tag = child.tag.split('}')[-1]
            if tag == 'clip-path':
                self.clip_id += 1
                cid = 'clip%d' % self.clip_id
                pd = _a(child, 'pathData', '')
                self.defs.append('  <clipPath id="%s"><path d="%s"/></clipPath>' % (cid, pd))
                local_clip = cid
            elif tag == 'group':
                out.append(self.group(child, local_clip))
            elif tag == 'path':
                out.append(self.path(child, local_clip))
        return '\n'.join(x for x in out if x)

    def group(self, el, clip=None):
        t = []
        tx = _num(_a(el, 'translateX', '0')); ty = _num(_a(el, 'translateY', '0'))
        sx = _num(_a(el, 'scaleX', '1')); sy = _num(_a(el, 'scaleY', '1'))
        rot = _num(_a(el, 'rotation', '0'))
        px = _num(_a(el, 'pivotX', '0')); py = _num(_a(el, 'pivotY', '0'))
        if tx or ty: t.append('translate(%g %g)' % (tx, ty))
        if rot: t.append('rotate(%g %g %g)' % (rot, px, py))
        if sx != 1 or sy != 1: t.append('scale(%g %g)' % (sx, sy))
        inner = self.children(el, clip)
        if t:
            return '  <g transform="%s">\n%s\n  </g>' % (' '.join(t), inner)
        return inner

def vd_to_svg(xml_text):
    root = ET.fromstring(xml_text)
    vw = _a(root, 'viewportWidth', '24')
    vh = _a(root, 'viewportHeight', '24')
    w = _a(root, 'width', vw).replace('dp', '')
    h = _a(root, 'height', vh).replace('dp', '')
    c = Conv()
    body = c.children(root)
    defs = ('  <defs>\n%s\n  </defs>\n' % '\n'.join(c.defs)) if c.defs else ''
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" '
            'viewBox="0 0 %s %s">\n%s%s\n</svg>\n' % (w, h, vw, vh, defs, body))

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding='utf-8') as f:
        svg = vd_to_svg(f.read())
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(svg)
    print('wrote', dst, len(svg))
