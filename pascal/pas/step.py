#!/usr/bin/env python3
"""
Один шаг восстановления GAME.PAS: собрать, найти первое расхождение, показать
оригинал в этом месте.

Модуль игры кладётся по 001000 и там же собирается наш, поэтому смещения
совпадают и сравнивать можно прямо. Перемещаемые слова исключены: в объектнике
они ещё нулевые.

Когда байты разошлись, самое полезное -- увидеть, что в этом месте делает
оригинал. Листинг уже есть (`tetris/dis/TETRISB-GAME.ASM`), нужные строки
берутся из него по адресу.

  step.py [исходник.pas]        по умолчанию pascal/pas/GAME.PAS
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
from objlib import modules                                     # noqa: E402
from pasbuild import build                                     # noqa: E402

LST = os.path.join(ROOT, "tetris", "dis", "TETRISB-GAME.ASM")
SAV = os.path.join(ROOT, "tetris", "dis", "TETRISB.SAV")


def main():
    pas = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "GAME.PAS")
    res, errs, log = build(pas, "GAME", keep=HERE)
    if errs:
        print(f"ошибок компиляции: {errs}\n")
        for q, d in sorted(res.items()):
            if q.endswith(".LST"):
                t = d.replace(b"\r\n", b"\n").decode("latin-1")
                keep = False
                for ln in t.splitlines():
                    if re.match(r"^\s*\*+\s*(ERROR|WARNING)", ln) or "***" in ln:
                        keep = True
                    if keep and ln.strip():
                        print(" ", ln.rstrip()[:100])
                    if keep and not ln.strip():
                        keep = False
        return 1
    obj = os.path.join(HERE, "GAME.OBJ")
    m = [x for x in modules(open(obj, "rb").read())][0]
    img = bytes(m["image"])
    ref = open(SAV, "rb").read()[0o1000:]
    skip = {o + k for o in m["rld"] for k in (0, 1)}
    # Байты, которых объектный файл не задаёт вовсе (пропуски), сравнивать не с
    # чем: в .SAV на их месте лежит то, что осталось в буфере компоновщика.
    skip |= {i for i in range(len(img)) if i not in m["set"]}

    n = -1
    for i in range(min(len(img), len(ref))):
        if i in skip:
            continue
        if img[i] != ref[i]:
            break
        n = i
    done = n + 1
    print(f"совпадает {done} байт из 7338 ({100*done//7338}%), "
          f"расхождение по адресу {0o1000+done:06o}")
    if done >= 7338:
        return 0

    # что делает оригинал вокруг этого места
    addr = 0o1000 + (done & ~1)
    lines = open(LST).read().splitlines()
    k = None
    for j, ln in enumerate(lines):
        mm = re.match(r"^([0-7]{6})\s", ln)
        if mm and int(mm.group(1), 8) >= addr:
            k = j
            break
    if k is not None:
        print("\n--- оригинал ---")
        for ln in lines[max(0, k - 3):k + 16]:
            print(" ", ln.rstrip())

    # и что выдал компилятор
    mac = open(os.path.join(HERE, "GAME.MAC"), "rb").read()
    mac = mac.replace(b"\r\n", b"\n").rstrip(b"\x1a\x00").decode("latin-1")
    print("\n--- наш .MAC, хвост ---")
    body = [x for x in mac.splitlines() if x.strip()]
    for ln in body[-18:]:
        print(" ", ln)
    return 1


if __name__ == "__main__":
    sys.exit(main())
