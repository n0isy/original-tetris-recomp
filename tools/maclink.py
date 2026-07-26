#!/usr/bin/env python3
"""
Слинковать объектные файлы настоящим LINK в эмуляторе.

Порядок аргументов задаёт порядок модулей в готовой программе, а он влияет на
адреса, поэтому для побайтового воспроизведения важен.

Отдельная тонкость: вклеивать модуль в библиотеку нельзя -- у неё в начале
каталог, и смена длины модуля его рушит (`?LINK-F-ILLEGAL RECORD TYPE`).
Поэтому модули подаются обычными объектными файлами: из них компоновщик берёт
всё подряд, в порядке файлов.

  maclink.py <выход.sav> <вход.obj> [<вход.obj> ...]
"""
import os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from rt11 import RT11                                          # noqa: E402
from interleave import to_physical, to_logical                 # noqa: E402

PDP11 = os.environ.get("PDP11") or os.path.join(HERE, "pdp11")
SYS = os.path.join(HERE, "..", "pascal", "sys-macro-link.rx01")
BLANK = os.path.join(HERE, "..", "disks", "blank.dsk")


def link(objs, name="OUT"):
    """Вернуть (байты .SAV, вывод компоновщика)."""
    import pexpect
    v = RT11(BLANK)
    for n, *_ in list(v.files()):
        v.rm(n)
    names = []
    for p in objs:
        n = os.path.basename(p).split(".")[0][:6].upper()
        names.append(n)
        v.put(n + ".OBJ", open(p, "rb").read())
    rx = tempfile.NamedTemporaryFile(suffix=".rx01", delete=False).name
    open(rx, "wb").write(to_physical(bytes(v.img)))

    ini = tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False)
    ini.write(f"set cpu 11/23\nset cpu 256k\nset tto 8b\n"
              f"attach rx0 {os.path.abspath(SYS)}\nattach rx1 {rx}\nboot rx0\n")
    ini.close()
    c = pexpect.spawn(f"{PDP11} {ini.name}", timeout=180, encoding="latin-1",
                      dimensions=(24, 80))
    c.expect(r"w02\.00")
    c.expect(r"\r\n\.")
    c.sendline("R LINK")
    c.expect(r"\*")
    c.sendline(f"DX1:{name}=" + ",".join("DX1:" + n for n in names))
    c.expect([r"\*", r"\?LINK-\w-[^\r\n]*"], timeout=150)
    log = c.before + (c.after if isinstance(c.after, str) else "")
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
    out = None
    for n, *_ in v.files():
        if n.startswith(name):
            out = v.read(n)
    os.unlink(ini.name)
    return out, log


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    dst, objs = sys.argv[1], sys.argv[2:]
    data, log = link(objs, os.path.basename(dst).split(".")[0][:6].upper())
    if data is None:
        print("компоновка не удалась:", log[-300:]); sys.exit(1)
    open(dst, "wb").write(data)
    print(f"{dst}: {len(data)} б")
