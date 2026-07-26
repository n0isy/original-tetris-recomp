#!/usr/bin/env python3
"""
Вырезать объектные файлы из сырых данных: свободных блоков, остатков, лент.

Файл в каталоге можно прочитать штатно, а вот удалённый или недописанный --
только найдя его границы самому. У объектного файла границы видны: он состоит
из форматных двоичных записей `01 00 <длина 2б> <данные> <кс 1б>`, и записи
сцеплены встык. Значит начало -- позиция, с которой цепочка сходится несколько
раз подряд, а конец -- где сцепление рвётся.

Отбор по содержимому, а не по длине: годным считается только тот кусок, где
разбираются блоки GSD и находятся имена модулей рантайма.

  objcarve.py <файл> [...]     -- вырезает в ./carved-obj/
"""
import os, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from objlib import modules                                     # noqa: E402

OUT = "carved-obj"
CORE = {"$IO", "$INIT", "$ALLOC", "$FPSIM", "ERROR", "$WRITC", "$READC",
        "$ARITH", "$CNVRT", "$REG", "READS", "$ERROR", "$OPEN"}


def chain(d, p, limit=None):
    """Длина цепочки записей, начинающейся в p (0, если не цепочка)."""
    n = 0
    start = p
    while p + 4 < len(d):
        if d[p] != 1 or d[p + 1] != 0:
            break
        ln = d[p + 2] | (d[p + 3] << 8)
        if not (6 <= ln <= 1024) or p + ln + 1 > len(d):
            break
        p += ln + 1
        n += 1
        if limit and n >= limit:
            break
    return n, p - start


def carve(path):
    d = open(path, "rb").read()
    out, i = [], 0
    while True:
        i = d.find(b"\x01\x00", i)
        if i < 0:
            break
        n, ln = chain(d, i, limit=8)
        if n < 8:
            i += 1
            continue
        n, ln = chain(d, i)
        blob = d[i:i + ln]
        try:
            mods = modules(blob)
        except Exception:
            mods = []
        names = {m["name"] for m in mods}
        if len(names & CORE) >= 4:
            out.append((i, blob, sorted(names)))
        i += max(ln, 2)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    seen = {}
    for p in sys.argv[1:]:
        try:
            for off, blob, names in carve(p):
                m = hashlib.md5(blob).hexdigest()[:8]
                if m not in seen:
                    open(f"{OUT}/{m}.OBJ", "wb").write(blob)
                seen.setdefault(m, (len(blob), len(names), []))[2].append(f"{p}+{off}")
        except Exception as e:
            print(f"  {p}: {e}")
    print(f"вырезано объектных файлов: {len(seen)}")
    for m, (sz, nm, where) in sorted(seen.items(), key=lambda x: -x[1][0]):
        print(f"  md5 {m}  {sz:>7} б  модулей {nm}")
        for w in where[:3]:
            print(f"        {w}")


if __name__ == "__main__":
    main()
