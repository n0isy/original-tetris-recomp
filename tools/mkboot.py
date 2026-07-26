#!/usr/bin/env python3
"""
Собрать загрузочный образ RX01 для SIMH из логического образа ФОДОС/RT-11,
дописав в него нужные программы.

    mkboot.py <fodos.dsk> <out.rx01> ИМЯ.SAV=путь [ИМЯ.SAV=путь ...]

Пример -- залить все четыре версии тетриса на дистрибутивную 8" дискету:

    ./mkboot.py ../extracted/.../4800001.DSK /tmp/t.rx01 \\
        TETRA.SAV=.../g3_dsk.rar_unpacked/g3_dsk/TETRIS.SAV \\
        TETRB.SAV=.../g1_dsk.rar_unpacked/g1_dsk/TETRIS.SAV

Свободного места на дистрибутиве почти нет, поэтому по мере надобности
удаляются файлы из EXPENDABLE -- компилятор, компоновщик, редактор и прочее,
без чего система грузится. Трогать монитор (DXMNSJ.SYS), DX.SYS, TT.SYS,
SWAP.SYS и утилиты PIP/DUP/DIR нельзя.

На выходе -- физический образ RX01, уже пригодный для `attach rx0`.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rt11 import RT11                                          # noqa: E402
from interleave import to_physical                             # noqa: E402

EXPENDABLE = ["MACRO.SAV", "MDUP.MT", "DXMNFB.SYS", "SYSMAC.SML",
              "LINK.SAV", "EDIT.SAV", "CREF.SAV", "DXMNSJ.BL"]


def build(src, out, items):
    v = RT11(src)
    need = sum((len(d) + 511) // 512 for _, d in items)
    free = lambda: max((w[4] for w in v._seg()[2] if w[0] & v.E_MPTY), default=0)
    for junk in EXPENDABLE:
        if free() >= need:
            break
        try:
            v.rm(junk)
            print(f"  освобождено: {junk}")
        except KeyError:
            pass
    if free() < need:
        raise SystemExit(f"не хватает места: нужно {need} блоков, свободно {free()}")
    for name, data in items:
        print(f"  записан: {name} -> блок {v.put(name, data)}")
    open(out, "wb").write(to_physical(bytes(v.img)))
    print(f"{out}: физический RX01, {os.path.getsize(out)} байт")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    pairs = []
    for arg in sys.argv[3:]:
        name, _, path = arg.partition("=")
        pairs.append((name.upper(), open(path, "rb").read()))
    build(sys.argv[1], sys.argv[2], pairs)
