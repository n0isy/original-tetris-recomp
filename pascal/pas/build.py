#!/usr/bin/env python3
"""
Собрать тетрис из GAME.PAS и сверить с оригиналом побайтово.

Цепочка та же, что была у автора: PASCAL -> MACRO -> LINK, всё настоящее, в
эмуляторе. Из паскалевской сборки берётся только объектный модуль игры;
рантайм подставляется наш, восстановленный (pascal/rebuild/work/RT.OBJ),
потому что библиотека нужной редакции не сохранилась.

  build.py            собрать и сверить; выход 0 только при полном совпадении
"""
import os, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
from pasbuild import build                                     # noqa: E402
from maclink import link                                       # noqa: E402

ORIG = os.path.join(ROOT, "tetris", "dis", "TETRISB.SAV")
RT = os.path.join(ROOT, "pascal", "rebuild", "work", "RT.OBJ")


def main():
    res, errs, log = build(os.path.join(HERE, "GAME.PAS"), "GAME", keep=HERE)
    if errs:
        print(f"ошибок компиляции: {errs}"); print(log[-1200:]); return 1
    print("  GAME.PAS -> GAME.OBJ, ошибок 0")
    if not os.path.exists(RT):
        print(f"нет {RT} -- сначала ./pascal/rebuild/rebuild.py"); return 1

    sav, log = link([os.path.join(HERE, "GAME.OBJ"), RT], "TET")
    if sav is None:
        print("компоновка не удалась:", log[-300:]); return 1
    dst = os.path.join(HERE, "TETPAS.SAV")
    open(dst, "wb").write(sav)
    print(f"  {dst}: {len(sav)} б")

    orig = open(ORIG, "rb").read()
    d = [i for i in range(min(len(sav), len(orig))) if sav[i] != orig[i]]
    ours, theirs = (hashlib.md5(sav).hexdigest(),
                    hashlib.md5(orig[:len(sav)]).hexdigest())
    print(f"  различий: {len(d)}")
    print(f"  md5 наш      {ours}")
    print(f"  md5 оригинал {theirs}   (первые {len(sav)} б; дальше на диске "
          f"мусор от удалённого файла)")
    return 0 if not d and ours == theirs else 1


if __name__ == "__main__":
    sys.exit(main())
