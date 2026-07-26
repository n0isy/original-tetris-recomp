#!/usr/bin/env python3
"""
Собрать библиотеку из модулей нескольких библиотек.

Ни одна уцелевшая библиотека не совпадает с той, которой собран тетрис,
целиком. Но совпадение помодульное: часть модулей точна в одной библиотеке,
часть -- в другой. Компоновщику всё равно, из какого файла пришёл модуль,
поэтому библиотеку можно пересобрать, беря каждый модуль оттуда, где он верен.

Объектный файл -- цепочка форматных записей, и модуль занимает в ней непрерывный
кусок от своего GSD до ENDMOD включительно. Значит замена модуля -- это замена
куска байт, разбирать и собирать формат заново не нужно.

  objmix.py <основная.obj> <выход.obj> имя=<донор.obj> [имя=<донор.obj> ...]
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from objdump import unrad50                                    # noqa: E402


def spans(data):
    """{имя модуля: (начало, конец)} -- границы модуля в байтах файла."""
    out, i, start, name = {}, 0, None, None
    while i < len(data) - 4:
        if data[i] != 1 or data[i + 1] != 0:
            i += 1
            continue
        ln = data[i + 2] | (data[i + 3] << 8)
        if not (6 <= ln <= len(data) - i):
            i += 1
            continue
        blk = data[i + 4:i + ln]
        typ = blk[0] | (blk[1] << 8) if len(blk) >= 2 else -1
        if typ == 1 and start is None:                          # GSD -- модуль начался
            start = i
            for o in range(2, len(blk) - 7, 8):
                if blk[o + 5] == 0:
                    name = (unrad50(blk[o] | (blk[o + 1] << 8))
                            + unrad50(blk[o + 2] | (blk[o + 3] << 8))).strip()
                    break
        i += ln + 1
        if typ == 6 and start is not None:                      # ENDMOD -- кончился
            out[name] = (start, i)
            start, name = None, None
    return out


def mix(base_path, repl):
    base = open(base_path, "rb").read()
    sp = spans(base)
    out, cut = bytearray(), []
    for nm, donor_path in repl.items():
        if nm not in sp:
            raise SystemExit(f"в основной библиотеке нет модуля {nm}")
        d = open(donor_path, "rb").read()
        ds = spans(d)
        if nm not in ds:
            raise SystemExit(f"в {donor_path} нет модуля {nm}")
        a, b = ds[nm]
        cut.append((sp[nm], d[a:b]))
    cut.sort()
    pos = 0
    for (a, b), blob in cut:
        out += base[pos:a]
        out += blob
        pos = b
    out += base[pos:]
    return bytes(out), sp, cut


def main():
    if len(sys.argv) < 4:
        print(__doc__); return
    base, dst = sys.argv[1], sys.argv[2]
    repl = dict(a.split("=", 1) for a in sys.argv[3:])
    data, sp, cut = mix(base, repl)
    open(dst, "wb").write(data)
    print(f"{dst}: {len(data)} б, заменено модулей {len(cut)}")
    for nm, p in repl.items():
        a, b = sp[nm]
        print(f"   {nm:<8} было {b - a:>6} б  ->  взят из {os.path.basename(p)}")


if __name__ == "__main__":
    main()
