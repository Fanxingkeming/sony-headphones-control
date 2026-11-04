#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sign the built exe with an Authenticode code-signing certificate.

    python sign.py [path\\to\\SonyHeadphonesControl.exe]

Certificate comes from the environment (never hard-code it):

    set SHC_PFX=C:\\path\\to\\cert.pfx
    set SHC_PFX_PASSWORD=...

What signing actually buys you, and what it does not
----------------------------------------------------
SmartScreen decides on *reputation*: a签名 only becomes trusted after enough
downloads, or immediately with an EV certificate (hardware token, yearly fee).
A self-signed certificate is worse than nothing for this purpose — Windows
shows "Unknown publisher" and the warning stays, while users are asked to
install a certificate they have no reason to trust.

So: this script signs when you have a real certificate, and otherwise tells you
plainly that the exe is unsigned. It also prints the version resource, which is
what makes the file look legitimate in Explorer and in the UAC prompt.
"""
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXE = os.path.join(HERE, "SonyHeadphonesControl.exe")


def find_signtool():
    exe = shutil.which("signtool")
    if exe:
        return exe
    roots = [os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                          "Windows Kits", "10", "bin"),
             os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                          "Windows Kits", "10", "bin")]
    found = []
    for root in roots:
        if os.path.isdir(root):
            found += glob.glob(os.path.join(root, "*", "x64", "signtool.exe"))
    if not found:
        return None
    # newest SDK wins; the directory name is the version
    return sorted(found)[-1]


def describe(exe):
    size = os.path.getsize(exe)
    print("exe : %s" % exe)
    print("size: %d bytes (%.2f MiB)" % (size, size / 1048576))
    print("unsigned" if not has_signature(exe) else "signed")


def has_signature(exe):
    """A signed PE carries a security directory in its optional header."""
    import struct
    with open(exe, "rb") as f:
        head = f.read(0x200)
    if head[:2] != b"MZ":
        return False
    pe = struct.unpack_from("<I", head, 0x3C)[0]
    with open(exe, "rb") as f:
        f.seek(pe)
        sig = f.read(4)
        if sig != b"PE\0\0":
            return False
        coff = f.read(20)
        opt_size = struct.unpack_from("<H", coff, 16)[0]
        opt = f.read(opt_size)
    magic = struct.unpack_from("<H", opt, 0)[0]
    if magic == 0x20B:            # PE32+
        dir_off = 112
    elif magic == 0x10B:          # PE32
        dir_off = 96
    else:
        return False
    # DataDirectory[4] = Certificate Table (file offset, size)
    if len(opt) < dir_off + 8:
        return False
    addr, length = struct.unpack_from("<II", opt, dir_off + 4 * 8)
    return addr != 0 and length != 0


def main(argv):
    exe = argv[0] if argv else DEFAULT_EXE
    if not os.path.isfile(exe):
        print("not found:", exe)
        return 2
    describe(exe)

    pfx = os.environ.get("SHC_PFX")
    if not pfx:
        print("\nNo certificate configured (SHC_PFX is empty) — the exe stays unsigned.")
        print("SmartScreen will keep warning until the file builds reputation;")
        print("a self-signed certificate does not help, only a CA-issued one does.")
        print("Windows SDK (for signtool) present:", bool(find_signtool()))
        return 0
    if not os.path.isfile(pfx):
        print("\nSHC_PFX points at a missing file:", pfx)
        return 2

    tool = find_signtool()
    if not tool:
        print("\nsigntool.exe not found. Install the Windows 10/11 SDK, or run")
        print("  signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256")
        print("  /f <cert.pfx> /p <password> \"%s\"" % exe)
        return 2

    cmd = [tool, "sign", "/fd", "sha256",
           "/tr", "http://timestamp.digicert.com", "/td", "sha256",
           "/f", pfx]
    pwd = os.environ.get("SHC_PFX_PASSWORD")
    if pwd:
        cmd += ["/p", pwd]
    cmd.append(exe)
    print("\n" + " ".join(c if " " not in c else '"%s"' % c for c in cmd))
    rc = subprocess.call(cmd)
    if rc == 0:
        print("\nsigned ok")
        describe(exe)
    else:
        print("\nsigntool failed with", rc)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
