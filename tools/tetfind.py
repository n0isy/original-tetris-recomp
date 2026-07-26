#!/usr/bin/env python3
"""
Найти все тетрисы по сигнатуре, устойчивой к сдвигу.

Сравнивать программы окнами байт бесполезно: компоновщик кладёт код по своему
адресу, и любой сдвиг ломает сравнение целиком. Нужна опора, которая от адресов
не зависит вовсе -- **текст**. Рамка стакана, подсказки и подпись автора лежат в
области данных, релокации их не касаются, и они одинаковы во всех сборках.

Сигнатуры вырезаны прямо из известных бинарей, а не набраны на глаз: русские
строки в КОИ-7 Н2 выглядят латиницей (`polnyh strok:`), и угадать их написание
нельзя. Хвост блока (паддинг) сигнатуры не задевают -- они внутри программы.

Ищет во всём подряд: в обычных файлах, в образах дисков RT-11 (тогда называет
файл внутри) и в образах лент.

  tetfind.py <каталог> [...]
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from rt11 import RT11                                          # noqa: E402

# Узкая сигнатура, снятая с двух известных бинарей, пропустит любую другую
# редакцию: иначе набранный перевод, другая ширина стакана, другие подсказки.
# Поэтому берутся короткие куски, которые обязаны быть в любом тетрисе.
#
# Приятная особенность КОИ-7 Н2: кириллица лежит в диапазоне латиницы, и слово
# «ТЕТРИС» записано теми же байтами, что латинское `tetris`. Один поиск без
# учёта регистра ловит сразу обе версии.
SIG = {
    "клин стакана": b"\\/\\/\\/",           # основание, 3 клина подряд
    "пустая строка": b". . . . .",         # ряд пустого стакана
    "дно":          b"=========",
    "ТЕТРИС/TETRIS": b"tetris",            # КОИ-7 «ТЕТРИС» = байты `tetris`
    "УРОВЕНЬ":      b"urowenx",
    "СЧЕТ":         b"s~et",
    "СТРОК":        b"strok",
    "ФИГУРА":       b"figura",
    "LEVEL":        b"LEVEL",
    "SCORE":        b"SCORE",
    "LINES":        b"LINES",
    "ПОДПИСЬ":      b"PAJITNOV",
}


def _ci(data, pat):
    """Поиск без учёта регистра -- в КОИ-7 регистр значит смену алфавита."""
    return pat.lower() in data.lower()
MAXSIZE = 200 << 20


def hits(data):
    return [k for k, v in SIG.items() if _ci(data, v)]


def scan_image(path, data):
    """Если это том RT-11 -- вернуть попадания пофайлово, иначе None."""
    try:
        v = RT11(path)
    except Exception:
        return None
    out = []
    for n, ln, blk, dt in v.files():
        try:
            d = v.blk(blk, ln)
        except Exception:
            continue
        h = hits(d)
        if h:
            out.append((n, ln, dt, h, d))
    return out


def walk(roots):
    seen = {}
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
                h = hits(data)
                if not h:
                    continue
                inner = scan_image(p, data)
                if inner:
                    for n, ln, dt, hh, d in inner:
                        yield f"{p}::{n}", ln * 512, dt, hh, d
                else:
                    yield p, len(data), "", h, data


def main():
    import hashlib
    roots = sys.argv[1:] or ["."]
    seen = {}
    for where, size, dt, h, d in walk(roots):
        m = hashlib.md5(d).hexdigest()[:8]
        seen.setdefault(m, []).append((where, size, dt, h))
    print(f"различных бинарей с попаданиями: {len(seen)}\n")
    for m, rows in sorted(seen.items(), key=lambda x: -len(x[1])):
        where, size, dt, h = rows[0]
        print(f"md5 {m}  {size:>8} б  {dt:<12} {', '.join(sorted(h))}")
        for w, _, dd, _ in rows:
            print(f"      {w}  {dd}")


if __name__ == "__main__":
    main()
