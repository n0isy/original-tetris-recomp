#!/usr/bin/env python3
"""
Найти библиотеки рантайма ПАСКАЛЬ/РАФОС где угодно, по именам модулей.

Искать библиотеку по имени файла бесполезно (она называется и `PASCAL.OBJ`, и
`PASSIM.OBJ`, и как угодно), по строкам -- ненадёжно: в объектном файле записи
рвут текст на куски. Надёжный признак -- **имена модулей в блоках GSD**: они
записаны в RADIX-50, лежат в служебной структуре, и никакой сдвиг на них не
влияет, потому что объектный формат разбирается, а не сканируется.

Библиотекой рантайма считается объектный файл, где есть характерные модули
`$IO`, `$INIT`, `$ALLOC`, `$FPSIM`, `ERROR`.

Заодно проверяется, проставлены ли **номера ошибок** в дескрипторах `$IO`, --
именно этим отличается сборка, которой собраны все уцелевшие программы, от
тех пяти библиотек, что есть в наличии.

  libfind.py <каталог> [...]
"""
import os, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from objdump import is_obj                                     # noqa: E402
from objlib import modules                                     # noqa: E402
from rt11 import RT11                                          # noqa: E402

CORE = {"$IO", "$INIT", "$ALLOC", "$FPSIM", "ERROR", "$WRITC", "$READC"}
MAXSIZE = 60 << 20


def errnums(mods):
    """Номера ошибок из дескрипторов $IO: [(номер, текст), ...]."""
    m = next((x for x in mods if x["name"] == "$IO"), None)
    if not m:
        return []
    img = m["image"]
    w = lambda a: img[a] | (img[a + 1] << 8)                    # noqa: E731
    out, a = [], 0
    while a < len(img) - 8:
        if w(a) == 0o004067:                                   # JSR R0,$ERROR
            num, ln = img[a + 5], w(a + 6)
            if 0 < ln < 40 and all(32 <= c < 127 for c in img[a + 8:a + 8 + ln]):
                out.append((num, img[a + 8:a + 8 + ln].decode()))
                a += (8 + ln + 1) & ~1
                continue
        a += 2
    return out


def check(data, where):
    if not is_obj(data):
        return None
    try:
        mods = modules(data)
    except Exception:
        return None
    names = {m["name"] for m in mods}
    if len(names & CORE) < 4:
        return None
    nums = errnums(mods)
    return dict(where=where, md5=hashlib.md5(data).hexdigest()[:8], size=len(data),
                nmod=len(mods), nums=nums)


def each(roots):
    for root in roots:
        for dp, _, fs in os.walk(root):
            for fn in sorted(fs):
                p = os.path.join(dp, fn)
                try:
                    if os.path.getsize(p) > MAXSIZE:
                        continue
                    data = open(p, "rb").read()
                except Exception:
                    continue
                yield p, data
                for sub in _volumes(p, data, 0):
                    yield sub


def _volumes(path, data, depth):
    """Файлы тома RT-11; тома внутри томов (.VIR, .SYS) тоже разбираются."""
    if depth > 2:
        return
    try:
        v = RT11(path)
    except Exception:
        return
    import tempfile
    for n, ln, blk, dt in v.files():
        try:
            d = v.blk(blk, ln)
        except Exception:
            continue
        yield f"{path}::{n}  {dt}", d
        if ln >= 100:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".vol") as f:
                f.write(d)
                q = f.name
            for sub in _volumes(q, d, depth + 1):
                yield sub
            os.unlink(q)


def main():
    seen = {}
    for where, data in each(sys.argv[1:] or ["."]):
        r = check(data, where)
        if r:
            seen.setdefault(r["md5"], r).setdefault("copies", []).append(where)
    print(f"библиотек рантайма найдено: {len(seen)}\n")
    for md5, r in sorted(seen.items(), key=lambda x: -sum(n for n, _ in x[1]["nums"])):
        filled = sum(1 for n, _ in r["nums"] if n)
        print(f"md5 {md5}  {r['size']:>7} б  модулей {r['nmod']}  "
              f"номера ошибок: {filled} из {len(r['nums'])}")
        for c in r["copies"][:4]:
            print(f"      {c}")
        if filled:
            print("      " + ", ".join(f"{t}={n}" for n, t in r["nums"]))


if __name__ == "__main__":
    main()
