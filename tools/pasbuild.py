#!/usr/bin/env python3
"""
Быстро собрать программу на ПАСКАЛЬ/РАФОС в эмуляторе и забрать результат.

    pasbuild.py <файл.pas> [имя] [-o вывод.sav] [--lib PASSIM] [--sw /ключи]

Ждёт приглашений монитора и утилит, а не фиксированных пауз -- сборка занимает
секунды вместо минут. Цепочка: PASCAL -> MACRO -> LINK с библиотекой рантайма.

Тома: DX0: -- система с MACRO и LINK, DX1: -- компилятор, библиотеки, исходник.
"""
import os, re, sys, argparse, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from rt11 import RT11                                          # noqa: E402
from interleave import to_physical, to_logical                 # noqa: E402

PDP11 = os.environ.get("PDP11") or os.path.join(HERE, "pdp11")
SYS = os.path.join(HERE, "..", "pascal", "sys-macro-link.rx01")
GOLD = os.path.join(HERE, "..", "pascal", "gold")
BLANK = os.path.join(HERE, "..", "disks", "blank.dsk")


def make_disk(src, name, libs, out, extra=()):
    v = RT11(BLANK)
    for n, *_ in list(v.files()):
        v.rm(n)
    v.put("PASCAL.SAV", open(os.path.join(GOLD, "PASSIM.SAV"), "rb").read())
    for lib in libs:
        v.put(lib + ".OBJ", open(os.path.join(GOLD, lib + ".OBJ"), "rb").read())
    for p in extra:
        v.put(os.path.basename(p).upper(), open(p, "rb").read())
    v.put(name + ".PAS", src)
    open(out, "wb").write(to_physical(bytes(v.img)))


def build(pas_path, name=None, lib="PASSIM", switches="", keep=None, extra=()):
    """extra -- объектные файлы, подаваемые компоновщику ОТДЕЛЬНО от библиотеки.

    Вклеивать модуль в библиотеку нельзя: у неё в начале каталог, и смена длины
    модуля его рушит (`?LINK-F-ILLEGAL RECORD TYPE`). А отдельный .OBJ
    компоновщик берёт целиком, и библиотечную копию того же модуля уже не
    ищет -- символ определён.
    """
    import pexpect
    name = (name or os.path.basename(pas_path).split(".")[0])[:6].upper()
    src = open(pas_path, "rb").read()
    if not src.endswith(b"\x1a"):
        src = src.replace(b"\n", b"\r\n").replace(b"\r\r", b"\r") + b"\x1a"
    rx = tempfile.NamedTemporaryFile(suffix=".rx01", delete=False).name
    make_disk(src, name, [lib], rx, extra)

    ini = tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False)
    ini.write(f"set cpu 11/23\nset cpu 256k\nset tto 8b\n"
              f"attach rx0 {os.path.abspath(SYS)}\nattach rx1 {rx}\nboot rx0\n")
    ini.close()
    c = pexpect.spawn(f"{PDP11} {ini.name}", timeout=180, encoding="latin-1",
                      dimensions=(24, 80))
    log = []

    def wait(pat, tag):
        i = c.expect([pat, r"\?\w+-F-[^\r\n]*", pexpect.TIMEOUT], timeout=180)
        log.append(c.before + (c.after if isinstance(c.after, str) else ""))
        if i == 1:
            raise RuntimeError(f"{tag}: {c.after}")
        if i == 2:
            raise RuntimeError(f"{tag}: таймаут")

    c.expect(r"w02\.00")
    wait(r"\r\n\.", "загрузка")
    c.sendline("RUN DX1:PASCAL");            wait(r"\*", "запуск компилятора")
    c.sendline(f"DX1:{name}{switches}=DX1:{name}")
    wait(r"ERRORS DETECTED:\s*\d+", "компиляция")
    errs = re.search(r"ERRORS DETECTED:\s*(\d+)", log[-1])
    wait(r"[.*]", "после компиляции"); c.send("\x03")
    c.expect(r"\r\n\.")
    c.sendline("R MACRO");                   wait(r"\*", "запуск MACRO")
    c.sendline(f"DX1:{name}=DX1:{name}");    wait(r"ERRORS DETECTED:\s*\d+", "ассемблирование")
    c.send("\x03"); c.expect(r"\r\n\.")
    c.sendline("R LINK");                    wait(r"\*", "запуск LINK")
    ex = "".join(f",DX1:{os.path.basename(p).split('.')[0].upper()}" for p in extra)
    c.sendline(f"DX1:{name}=DX1:{name}{ex},DX1:{lib}")
    wait(r"\*", "компоновка")
    c.send("\x03"); c.expect(r"\r\n\.")
    c.send("\x05"); c.expect(r"sim>")        # выйти в SIMH и сбросить образ
    c.sendline("detach all"); c.expect(r"sim>")
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
    return res, (int(errs.group(1)) if errs else -1), "".join(log)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pas"); ap.add_argument("name", nargs="?")
    ap.add_argument("--lib", default="PASSIM"); ap.add_argument("--sw", default="")
    ap.add_argument("-o", "--outdir", default=".")
    a = ap.parse_args()
    res, errs, _ = build(a.pas, a.name, a.lib, a.sw, a.outdir)
    print(f"ошибок компиляции: {errs}")
    for n, d in sorted(res.items()):
        print(f"  {n:<12} {len(d):>6} б")
