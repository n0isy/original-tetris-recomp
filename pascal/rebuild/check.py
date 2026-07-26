#!/usr/bin/env python3
"""
Сверить собранный модуль с оригиналом, не прибегая к компоновке.

Проверок две, и они дополняют друг друга:

  1. Байты. В объектнике перемещаемые слова ещё нулевые, поэтому сравниваются
     только неперемещаемые -- зато с образом из готовой программы, где всё
     настоящее.
  2. Перемещения. Их список берётся из библиотеки, где лежит тот же модуль.
     Если хоть одно смещение не совпало, значит текст разъехался с оригиналом,
     и видно это сразу, без линковки и без гадания по процентам.

  check.py <модуль.obj> <имя> <база8> [<программа.sav>]
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from objlib import modules                                     # noqa: E402

DEF_SAV = os.path.join(ROOT, "tetris", "dis", "TETRISB.SAV")
LIB = os.path.join(ROOT, "pascal", "gold", "PASMIX.OBJ")


def one(path, name):
    for m in modules(open(path, "rb").read()):
        if m["name"] == name:
            return m
    return None


def check(obj_path, name, base, sav_path=DEF_SAV):
    m = one(obj_path, name)
    if m is None:
        print(f"в {obj_path} нет модуля {name}")
        return 1
    img = bytes(m["image"])
    ref = open(sav_path, "rb").read()[base:base + len(img)]
    gold = one(LIB, name)

    ok = True
    print(f"{name}: наш {len(img):o} б, оригинал {len(ref):o} б", end="")
    if gold and len(img) != gold["size"]:
        print(f"   <> РАЗМЕР (в библиотеке {gold['size']:o})"); ok = False
    else:
        print("   размер сходится")

    ours, theirs = set(m["rld"]), set(gold["rld"]) if gold else set()
    if gold:
        if ours == theirs:
            print(f"  перемещений {len(ours)} -- все на своих местах")
        else:
            ok = False
            print(f"  перемещений: наших {len(ours)}, в библиотеке {len(theirs)}")
            for a in sorted(ours - theirs):
                print(f"    лишнее  +{a:06o}")
            for a in sorted(theirs - ours):
                print(f"    нет     +{a:06o}")

    skip = {a + k for a in ours | theirs for k in (0, 1)}
    bad = [i for i in range(min(len(img), len(ref)))
           if i not in skip and img[i] != ref[i]]
    print(f"  неперемещаемых байт {min(len(img),len(ref))-len(skip)}, "
          f"расходится {len(bad)}")
    for i in bad[:40]:
        print(f"    +{i:06o}  наш {img[i]:03o}  оригинал {ref[i]:03o}")
    if len(bad) > 40:
        print(f"    ... ещё {len(bad)-40}")
    return 0 if ok and not bad else 1


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(1)
    a = sys.argv
    sys.exit(check(a[1], a[2], int(a[3], 8), a[4] if len(a) > 4 else DEF_SAV))
