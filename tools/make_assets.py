"""Build xm4.svg / ls900n.svg (+ transparent PNG fallbacks) from the
Sony Sound Connect 13.3.0 APK drawables.

The APK does not ship per-model product photos -- device images are fetched
from the cloud (see assets/model_info_list_for_debug.json).  The closest
in-APK artwork are the crisp dark-on-white headphone / true-wireless
illustrations used in the OOBE pairing guide.  We crop the device itself and
trace it into real vector paths (no embedded bitmap).

Run: python make_assets.py
"""
import os
import re
import zipfile
from bitmap2svg import vectorize

APK = r"E:\Downloads\sound_connect_v13.3.0.apk"
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'assets')
PREVIEW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_preview')

JOBS = [
    # name, apk entry, crop box (left, top, right, bottom) in source pixels
    ('xm4',
     'res/drawable-xhdpi-v4/a_mdr_oobe_img_pairing_manual.png',
     (100, 60, 330, 270)),
    ('ls900n',
     'res/drawable-xhdpi-v4/a_mdr_oobe_img_pairing_manual_tws01.png',
     (240, 60, 485, 340)),
]


def main():
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)
    z = zipfile.ZipFile(APK)
    cells = []
    for name, src, crop in JOBS:
        data = z.read(src)
        svg = os.path.join(ASSETS, name + '.svg')
        png = os.path.join(ASSETS, name + '.png')
        size, layers = vectorize(data, crop, svg, png, size=512, padding=0.08)
        open(os.path.join(PREVIEW, name + '_src.png'), 'wb').write(data)
        print('%-8s <- %s  crop=%s  svg=%d bytes (%d tonal layers)  png=%d bytes'
              % (name, src, crop, os.path.getsize(svg), layers, os.path.getsize(png)))
        svgtext = open(svg, encoding='utf-8').read()
        s = re.sub(r'(<svg[^>]*?)width="[^"]*"', r'\1width="100%"', svgtext, count=1)
        s = re.sub(r'(<svg[^>]*?)height="[^"]*"', r'\1height="100%"', s, count=1)
        cells.append((name, crop, s))

    parts = ['<html><head><meta charset="utf-8"><style>body{margin:0;background:#efefef;'
             'font-family:Arial}table{border-collapse:collapse}td{width:512px;height:560px;'
             'border:2px solid #999;text-align:center;vertical-align:middle;background:#fff}'
             '.box{width:512px;height:512px}.lbl{font-size:18px;font-weight:bold}'
             '</style></head><body><table>',
             '<tr><td>APK 原始 PNG（整张）</td><td>生成的 SVG（矢量）</td>'
             '<td>PNG 兜底（透明）</td></tr>']
    for name, crop, s in cells:
        parts.append('<tr>')
        parts.append('<td><div class="box"><img src="%s_src.png" style="width:100%%"></div>'
                     '<div class="lbl">%s crop=%s</div></td>' % (name, name, crop))
        parts.append('<td><div class="box">%s</div><div class="lbl">%s.svg</div></td>' % (s, name))
        parts.append('<td><div class="box"><img src="../app/assets/%s.png" '
                     'style="width:100%%"></div><div class="lbl">%s.png</div></td>' % (name, name))
        parts.append('</tr>')
    parts.append('</table></body></html>')
    open(os.path.join(PREVIEW, 'compare.html'), 'w', encoding='utf-8').write('\n'.join(parts))
    print('preview html written')


if __name__ == '__main__':
    main()
