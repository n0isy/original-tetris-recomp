#!/usr/bin/env python3
"""
Перебрать директивы компилятора пачками.

Загрузка эмулятора стоит секунд двадцать, а сама трансляция -- две. Поэтому
машина поднимается один раз на пачку: после каждой трансляции ПАСКАЛЬ снова
печатает свой `*` и готов принять следующую команду.

  probe.py 'T-' 'A-' 'C-' ...        напечатает, во что превратился образец

Образец подобран так, чтобы за один прогон было видно все три целочисленные
операции: умножение, деление и остаток. В игре они идут через $B116/$B118/$B120
(без контроля переполнения), а по умолчанию компилятор зовёт $B78/$B80/$B82.
"""
import os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
from rt11 import RT11                                          # noqa: E402
from interleave import to_physical, to_logical                 # noqa: E402

PDP11 = os.environ.get("PDP11") or os.path.join(ROOT, "tools", "pdp11")
SYS = os.path.join(ROOT, "pascal", "sys-macro-link.rx01")
GOLD = os.path.join(ROOT, "pascal", "gold")
BLANK = os.path.join(ROOT, "disks", "blank.dsk")

BODY = """(*$T-,A-%s*)
program %s;
var a, b : integer;
begin
  a := b * 13077 + 6925;
  a := b div 3;
  a := b mod 3
end.
"""


def batch(items):
    """items -- [(имя, текст директивы)]. Вернуть {имя: текст .MAC}."""
    import pexpect
    v = RT11(BLANK)
    for n, *_ in list(v.files()):
        v.rm(n)
    v.put("PASCAL.SAV", open(os.path.join(GOLD, "PASSIM.SAV"), "rb").read())
    for name, d in items:
        src = BODY % (d, name.lower())
        src = src.replace("\n", "\r\n").encode("latin-1") + b"\x1a"
        v.put(name + ".PAS", src)
    rx = tempfile.NamedTemporaryFile(suffix=".rx01", delete=False).name
    open(rx, "wb").write(to_physical(bytes(v.img)))

    ini = tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False)
    ini.write(f"set cpu 11/23\nset cpu 256k\nset tto 8b\n"
              f"attach rx0 {os.path.abspath(SYS)}\nattach rx1 {rx}\nboot rx0\n")
    ini.close()
    c = pexpect.spawn(f"{PDP11} {ini.name}", timeout=120, encoding="latin-1",
                      dimensions=(24, 80))
    c.expect(r"w02\.00")
    c.expect(r"\r\n\.")
    def start():
        c.sendline("RUN DX1:PASCAL")
        c.expect(r"\*")

    start()
    bad = set()
    for name, _ in items:
        c.sendline(f"DX1:{name}=DX1:{name}")
        i = c.expect([r"ERRORS DETECTED:\s*(\d+)", r"\?\w+-F-[^\r\n]*"],
                     timeout=120)
        if i == 1 or int(c.match.group(1)):
            bad.add(name)
        # дальше либо звёздочка -- транслятор готов к следующему файлу,
        # либо точка -- он вышел в монитор, и его надо запустить снова
        if c.expect([r"\*", r"\r\n\."], timeout=60) == 1:
            start()
    c.send("\x03")
    c.expect([r"\r\n\.", r"\*"])
    c.send("\x05"); c.expect(r"sim>")
    c.sendline("detach all"); c.expect(r"sim>")
    c.sendline("quit")
    c.close(force=True)

    dsk = rx.replace(".rx01", ".dsk")
    open(dsk, "wb").write(to_logical(open(rx, "rb").read()))
    v = RT11(dsk)
    out = {}
    for n, *_ in v.files():
        if n.endswith(".MAC"):
            d = v.read(n).replace(b"\r\n", b"\n").rstrip(b"\x1a\x00")
            out[n[:-4]] = d.decode("latin-1")
    os.unlink(ini.name)
    return out, bad


def calls(mac):
    return sorted(set(re.findall(r"\$B\d+", mac)))


def main():
    ds = sys.argv[1:]
    if not ds:
        print(__doc__); return 1
    items = [("P%02d" % i, "," + d if d else "") for i, d in enumerate(ds)]
    res, bad = batch(items)
    print("%-6s %-8s %s" % ("ключ", "статус", "вызовы рантайма"))
    for (name, _), d in zip(items, ds):
        if name in bad:
            print("%-6s %s" % (d, "ОТВЕРГНУТ компилятором"))
        elif name in res:
            print("%-6s %-8s %s" % (d, "ок", " ".join(calls(res[name]))))
        else:
            print("%-6s %s" % (d, "нет .MAC"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
