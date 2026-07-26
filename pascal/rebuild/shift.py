#!/usr/bin/env python3
"""
Проверить разметку перемещений в модуле игры, сдвинув её по памяти.

Побайтовое совпадение с `TETRIS.SAV` этого не проверяет: `.SAV` всегда грузится
по 001000, база модуля игры тоже 001000, и потому `MOV #2770,-(SP)` (константа)
и `MOV #CELL,-(SP)` (адрес) дают одни и те же байты. Ошибись я в том, что
считать адресом, -- сверка не заметит.

Заметит запуск по другому адресу. Перед игрой ставится пустой модуль, всё
съезжает, и тогда:

  * пропущенное перемещение -- код лезет по старому адресу и печатает мусор;
  * лишнее перемещение -- константа уезжает вместе с базой и портит счёт.

Обе сборки запускаются одинаково, экраны сравниваются. Эталон -- сборка по
001000: она побайтово равна оригиналу, значит ведёт себя как оригинал.

  shift.py [сдвиг8]           по умолчанию 2000
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
from macasm import assemble                                    # noqa: E402
from maclink import link                                       # noqa: E402
from runsim import run                                         # noqa: E402
from rt11 import RT11                                          # noqa: E402
from interleave import to_physical, to_logical                 # noqa: E402

WORK = os.path.join(HERE, "work")
SYS = os.path.join(ROOT, "pascal", "sys-macro-link.rx01")


def bootable(sav, name):
    """Записать .SAV на копию системного диска и вернуть путь к образу RX01."""
    dsk = os.path.join(WORK, name + ".dsk")
    open(dsk, "wb").write(to_logical(open(SYS, "rb").read()))
    v = RT11(dsk)
    v.put("TET.SAV", sav)
    rx = os.path.join(WORK, name + ".rx01")
    open(rx, "wb").write(to_physical(bytes(v.img)))
    return rx


def main():
    shift = int(sys.argv[1], 8) if len(sys.argv) > 1 else 0o2000
    src = os.path.join(WORK, "PAD.MAC")
    open(src, "w").write("\t.TITLE\tPAD\n\t.PSECT\n\t.BLKB\t%o\n\t.END\n" % shift)
    _, errs, log = assemble(src, "PAD", WORK)
    if errs:
        print("PAD.MAC:", errs, "ошибок"); print(log[-600:]); return 1

    objs = [os.path.join(WORK, n) for n in ("PAD.OBJ", "GAME.OBJ", "RT.OBJ")]
    for p in objs[1:]:
        if not os.path.exists(p):
            print(f"нет {p} -- сначала ./pascal/rebuild/rebuild.py"); return 1
    sav, log = link(objs, "TETPAD")
    if sav is None:
        print("компоновка не удалась:", log[-300:]); return 1
    open(os.path.join(WORK, "TETPAD.SAV"), "wb").write(sav)

    base = open(os.path.join(WORK, "TETNEW.SAV"), "rb").read()
    w = lambda b, a: b[a] | (b[a + 1] << 8)                     # noqa: E731
    print(f"  сдвиг {shift:o}")
    print(f"  точка входа: было {w(base,0o40):06o}, стало {w(sav,0o40):06o}")
    print(f"  верх:        было {w(base,0o50):06o}, стало {w(sav,0o50):06o}")
    if w(sav, 0o40) - w(base, 0o40) != shift:
        print("  <> точка входа не съехала на сдвиг"); return 1

    scr = {}
    for nm, data in (("001000", base), ("%06o" % (0o1000 + shift), sav)):
        scr[nm] = run(bootable(data, "b" + nm), "TET", keys="", wait=4.0)
        print(f"\n=== игра по {nm} ===")
        print(scr[nm])

    # Нутро стакана и счёт сравнивать нельзя: фигуры выпадают случайно, а зерно
    # генератора -- время до нажатия клавиши, оно от запуска к запуску разное.
    # Сравнивается всё остальное: надписи, рамка, панель подсказки. Именно там
    # и стоят адреса строк, по которым проверяется разметка перемещений.
    def mask(s):
        out = []
        for ln in s.splitlines():
            ln = ln[:27] + " " * len(ln[27:47]) + ln[47:]
            out.append("".join(" " if c.isdigit() else c for c in ln).rstrip())
        return out

    a, b = [mask(scr[k]) for k in scr]
    same = [x == y for x, y in zip(a, b)]
    print(f"\nстатический текст: совпало строк {sum(same)} из {len(same)}")
    for x, y in zip(a, b):
        if x != y:
            print(f"   по 001000: {x!r}\n   со сдвигом: {y!r}")
    return 0 if all(same) and len(a) == len(b) else 1


if __name__ == "__main__":
    sys.exit(main())
