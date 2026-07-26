#!/usr/bin/env python3
"""
Найти в архиве библиотеки рантайма Паскаля и определить их поколение.

В архиве уживаются два несовместимых рантайма, и оба зовутся `PASCAL.OBJ`,
поэтому искать надо по содержимому, а не по имени:

  * **OMSI**        -- `ARRAY BOUNDS ERROR`, `DEVIDE BY ZERO`, `BAD SUPPORT PACKAGE`
  * **ПАСКАЛЬ/РАФОС** -- `SUBSCRIPT OUT OF BOUNDS`, `STACK EXCEEDED MEMORY`,
    `DOUBLE DEALLOCATION OF DYNAMIC MEMORY`; этим собран тетрис

Строки берутся через `objdump.py`, то есть из блоков TXT по адресам загрузки.
Простой grep по `.OBJ` даёт ложные отрицания: строки рвутся границами записей.

  pasfind.py scan               обойти образы дискет и распакованное
  pasfind.py file <путь> [...]  проверить конкретные файлы
"""
import os, sys, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from objdump import obj_strings, is_obj, strings as raw_strings   # noqa: E402
from rt11 import RT11                                             # noqa: E402

RAFOS = ["SUBSCRIPT OUT OF BOUNDS", "STACK EXCEEDED MEMORY", "DIVISION BY ZERO",
         "DOUBLE DEALLOCATION OF DYNAMIC MEMORY", "PUT NOT ALLOWED",
         "WRITE PAST EOF", "FILE NOT OPEN", "PROGRAM COUNTER:"]
OMSI = ["ARRAY BOUNDS ERROR", "DEVIDE BY ZERO", "BAD SUPPORT PACKAGE",
        "I/O CHANNEL NOT OPEN", "END OF FILE ON DEVICE", "MISSING SPECIAL FEATURE",
        "NOT A VALID DEVICE"]
INTEREST = (".OBJ", ".LIB", ".SAV", ".SYS")


def classify(data):
    """(попаданий РАФОС, попаданий OMSI, это_объектник)."""
    obj = is_obj(data)
    if obj:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data); tmp = f.name
        try: ss = set(obj_strings(tmp, 6))
        finally: os.unlink(tmp)
    else:
        ss = set(raw_strings(data, 6))
    blob = "\n".join(ss)
    return sum(m in blob for m in RAFOS), sum(m in blob for m in OMSI), obj


def walk_images(paths):
    for img in paths:
        try: v = RT11(img)
        except Exception: continue
        for name, ln, blk, _ in v.files():
            if not name.upper().endswith(INTEREST): continue
            try: yield f"{img}::{name}", v.blk(blk, ln)
            except Exception: continue


def walk_files(root):
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.upper().endswith(INTEREST): continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) > 20_000_000: continue
                yield p, open(p, "rb").read()
            except Exception: continue


def scan(sources):
    hits = []
    for where, data in sources:
        r, o, obj = classify(data)
        if r or o:
            hits.append((r, o, obj, where))
    hits.sort(key=lambda h: (-h[0], -h[1]))
    print(f"{'РАФОС':>6}{'OMSI':>6}  {'тип':<7} файл")
    for r, o, obj, where in hits:
        print(f"{r:>4}/{len(RAFOS)}{o:>4}/{len(OMSI)}  {'OBJ' if obj else 'образ':<7} {where}")
    rafos_libs = [h for h in hits if h[0] >= 4 and h[2]]
    print(f"\nвсего просмотрено с попаданиями: {len(hits)}")
    print(f"ОБЪЕКТНЫХ файлов с рантаймом РАФОС: {len(rafos_libs)}")
    for h in rafos_libs: print("   ", h[3])
    return rafos_libs


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    if sys.argv[1] == "scan":
        imgs = [l.strip() for l in open(os.path.join(base, "images.txt")) if l.strip()]
        imgs = [i if os.path.isabs(i) else os.path.join(base, i) for i in imgs]
        src = list(walk_images(imgs)) + list(walk_files(os.path.join(base, "extracted")))
        scan(src)
    elif sys.argv[1] == "file":
        scan((p, open(p, "rb").read()) for p in sys.argv[2:])
