#!/usr/bin/env python3
"""
Ассемблировать исходник на макроассемблере настоящим MACRO в эмуляторе.

Писать объектный файл самому оказалось тупиком: формат приходится угадывать, а
на границе секций один и тот же адрес кодируется двояко. Ассемблер это делает
сам и правильно -- он для того и есть.

  macasm.py <файл.mac> [имя] [-o каталог]
"""
import os, re, sys, argparse, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from rt11 import RT11                                          # noqa: E402
from interleave import to_physical, to_logical                 # noqa: E402

PDP11 = os.environ.get("PDP11") or os.path.join(HERE, "pdp11")
SYS = os.path.join(HERE, "..", "pascal", "sys-macro-link.rx01")
BLANK = os.path.join(HERE, "..", "disks", "blank.dsk")


def assemble(mac_path, name=None, keep=None, listing=False):
    import pexpect
    name = (name or os.path.basename(mac_path).split(".")[0])[:6].upper()
    src = open(mac_path, "rb").read()
    if not src.endswith(b"\x1a"):
        src = src.replace(b"\n", b"\r\n").replace(b"\r\r", b"\r") + b"\x1a"
    v = RT11(BLANK)
    for n, *_ in list(v.files()):
        v.rm(n)
    v.put(name + ".MAC", src)
    rx = tempfile.NamedTemporaryFile(suffix=".rx01", delete=False).name
    open(rx, "wb").write(to_physical(bytes(v.img)))

    ini = tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False)
    ini.write(f"set cpu 11/23\nset cpu 256k\nset tto 8b\n"
              f"attach rx0 {os.path.abspath(SYS)}\nattach rx1 {rx}\nboot rx0\n")
    ini.close()
    c = pexpect.spawn(f"{PDP11} {ini.name}", timeout=180, encoding="latin-1",
                      dimensions=(24, 132))
    c.expect(r"w02\.00")
    c.expect(r"\r\n\.")
    c.sendline("R MACRO")
    c.expect(r"\*")
    out = f"DX1:{name}" + (f",DX1:{name}" if listing else "")
    c.sendline(f"{out}=DX1:{name}")
    c.expect(r"ERRORS DETECTED:\s*\d+")
    log = c.before + c.after
    c.send("\x03")
    c.expect(r"\r\n\.")
    c.send("\x05")
    c.expect(r"sim>")
    c.sendline("detach all")
    c.expect(r"sim>")
    c.sendline("quit")
    c.close(force=True)

    dsk = rx.replace(".rx01", ".dsk")
    open(dsk, "wb").write(to_logical(open(rx, "rb").read()))
    v = RT11(dsk)
    res = {n: v.read(n) for n, *_ in v.files() if n.startswith(name + ".")}
    if keep:
        for n, d in res.items():
            open(os.path.join(keep, n), "wb").write(d)
    os.unlink(ini.name)
    m = re.search(r"ERRORS DETECTED:\s*(\d+)", log)
    return res, (int(m.group(1)) if m else -1), log


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mac"); ap.add_argument("name", nargs="?")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("-l", "--listing", action="store_true")
    a = ap.parse_args()
    res, errs, log = assemble(a.mac, a.name, a.outdir, a.listing)
    print(f"ошибок ассемблирования: {errs}")
    for n, d in sorted(res.items()):
        print(f"  {n:<12} {len(d):>6} б")
    if errs:
        print(log[-2000:])
