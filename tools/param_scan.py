#!/usr/bin/env python3
"""
不依赖抓包的状态观测工具：枚举各命令族的 GET_PARAM / GET_STATUS。

原理：耳机对支持的参数编号会回 RET_PARAM (GET+1)，不支持的通常不回。
把 App 里切换设置前后的两次枚举结果做差，变化的那个编号就是该设置的参数位。

用法:
  python param_scan.py dump  audio system general opt play vpt sense
  python param_scan.py diff  before.json after.json
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tandem_client as tc

MAC = os.environ.get("SONY_MAC", "")

# 各命令族的 GET_PARAM 命令字节（Table#1）
FAMILIES = {
    "vpt":     0x46,
    "sense":   0x76,
    "opt":     0x86,
    "play":    0xA6,
    "general": 0xD6,
    "audio":   0xE6,
    "system":  0xF6,
}


def scan(client, cmd, ids=range(0x00, 0x20), wait=0.7):
    """枚举某族的参数编号，返回 {id: 响应hex}"""
    out = {}
    for pid in ids:
        payload = bytes([cmd, pid])
        r = client.request(payload, wait=wait)
        if r:
            out[pid] = r.hex()
    return out


def dump(families, ids, path):
    c = tc.Client(MAC)
    try:
        result = {}
        for fam in families:
            cmd = FAMILIES[fam]
            got = scan(c, cmd, ids)
            result[fam] = got
            print(f"{fam} (0x{cmd:02X}): {len(got)} 个响应")
            for pid, val in sorted(got.items()):
                print(f"    param 0x{pid:02X}  {val}")
        json.dump(result, open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"\n已保存 {path}")
    finally:
        tc.ws2.closesocket(c.sock)
        tc.ws2.WSACleanup()


def diff(before_path, after_path):
    b = json.load(open(before_path, encoding="utf-8"))
    a = json.load(open(after_path, encoding="utf-8"))
    changed = False
    for fam in sorted(set(a) | set(b)):
        fb, fa = b.get(fam, {}), a.get(fam, {})
        for pid in sorted(set(fa) | set(fb), key=lambda x: int(x)):
            vb, va = fb.get(str(pid)), fa.get(str(pid))
            if vb != va:
                changed = True
                print(f"[变化] {fam} param 0x{int(pid):02X}: {vb} -> {va}")
    if not changed:
        print("两次枚举完全相同，该操作没有改变任何可读参数")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    action = sys.argv[1]
    if action == "dump":
        fams = sys.argv[2:] or list(FAMILIES)
        fams = [f for f in fams if f in FAMILIES]
        rng = range(0x00, 0x20)
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "param_dump.json")
        dump(fams, rng, os.path.abspath(path))
    elif action == "diff" and len(sys.argv) >= 4:
        diff(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
