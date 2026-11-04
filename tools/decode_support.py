#!/usr/bin/env python3
"""把 MDR v2 的 CONNECT_RET_SUPPORT_FUNCTION 载荷解成 libmdr 里的功能名。

用法:
    python decode_support.py <hex> [--table 1|2]

枚举从仓库里的 ProtocolV2.hpp 现读，名字和 libmdr 完全一致，方便直接贴进 issue。
"""
import re, sys, os

REPO = os.path.join(os.path.dirname(__file__), "..", "upstream", "shc")
HPP = os.path.join(REPO, "libmdr", "include", "mdr", "ProtocolV2.hpp")


def load_enums(path=HPP):
    """解析 t1/t2 两个 FunctionType 枚举块。"""
    src = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for ns in ("t1", "t2"):
        m = re.search(r"namespace %s\s*\{(?:[^{}]|\{[^{}]*\})*?enum class FunctionType[^{]*\{(.*?)\};" % ns,
                      src, re.S)
        if not m:
            continue
        out[ns] = {int(v, 16): n for n, v in re.findall(r"(\w+)\s*=\s*0x([0-9A-Fa-f]+)", m.group(1))}
    return out


def decode(payload: bytes, enums, ns="t1"):
    if len(payload) < 3:
        return []
    count = payload[2]
    body = payload[3:]
    names = enums.get(ns, {})
    rows = []
    for i in range(count):
        fn = body[i * 2]
        val = body[i * 2 + 1] if i * 2 + 1 < len(body) else None
        rows.append((fn, names.get(fn, f"0x{fn:02X}"), val))
    return rows


def main():
    hexs = sys.argv[1].replace(" ", "")
    ns = "t1"
    if "--table" in sys.argv:
        ns = "t" + sys.argv[sys.argv.index("--table") + 1]
    data = bytes.fromhex(hexs)
    enums = load_enums()
    print(f"payload {len(data)} bytes, entries={data[2] if len(data) > 2 else '?'}  (table {ns})")
    for fn, name, val in decode(data, enums, ns):
        print(f"  {val if val is not None else 0:02X}  {name}")


if __name__ == "__main__":
    main()
