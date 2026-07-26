#!/usr/bin/env python3
"""
Вырезать программу из «сырых» данных вокруг найденной сигнатуры.

Половина попаданий приходится не на файлы каталога, а на свободные блоки
томов и на остатки прошлых записей в образах HX1: -- то есть на удалённое.
Каталога там уже нет, поэтому границы файла надо восстанавливать по самому
образу.

Опора -- заголовок `.SAV` (область связи RT-11): файл грузится с адреса 0, и
по фиксированным смещениям лежат точка входа (0o40), начальный стек (0o42,
почти всегда 0o1000) и верхняя граница (0o50). Значит начало файла ищется
назад по границам блоков, а длина берётся из самой верхней границы.

  tetcarve.py <файл> [<файл> ...]   -- вырезать всё найденное в ./carved/
"""
import os, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tetfind import SIG                                        # noqa: E402

OUT = "carved"


def w(d, a):
    return d[a] | (d[a + 1] << 8)


def looks_like_sav(d, base):
    """Заголовок .SAV на месте и правдоподобен?

    Одной проверки «в 0o42 лежит 0o1000» мало: такое слово попадается в любых
    данных, и поиск назад цеплял первый же ложный заголовок в двух шагах от
    сигнатуры -- все вырезки выходили одинаково короткими. Настоящий признак
    строже: **первые 32 байта области связи нулевые**, а дальше идут точка
    входа, стек и верхняя граница.
    """
    if base + 0o60 > len(d):
        return None
    if any(d[base:base + 0o40]):              # область связи начинается нулями
        return None
    stack = w(d, base + 0o42)
    entry = w(d, base + 0o40)
    top = w(d, base + 0o50)
    if stack != 0o1000:
        return None
    if not (0o1000 <= entry < 0o200000) or not (0o20000 <= top < 0o200000):
        return None
    if base + top > len(d):
        return None
    return top


def carve(path):
    d = open(path, "rb").read()
    found = {}
    for name, sig in SIG.items():
        o = d.find(sig)
        while o >= 0:
            # Назад от сигнатуры. По границам блоков искать нельзя: в образах
            # лент данные обёрнуты записями с заголовками, и выравнивание
            # файла относительно начала образа произвольное. Поэтому шаг --
            # слово, а отсев делает проверка заголовка.
            for b in range(o - o % 2, max(-1, o - 65536), -2):
                if b < 0:
                    break
                top = looks_like_sav(d, b)
                if top and b + top > o:       # сигнатура попала внутрь
                    blocks = (top + 511) // 512
                    img = d[b:b + blocks * 512]
                    found.setdefault(hashlib.md5(img).hexdigest()[:8],
                                     (b, img, set()))[2].add(name)
                    break
            o = d.find(sig, o + 1)
    return found


def main():
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for p in sys.argv[1:]:
        try:
            f = carve(p)
        except Exception as e:
            print(f"  {p}: {e}"); continue
        for m, (base, img, names) in f.items():
            name = f"{OUT}/{m}.SAV"
            if not os.path.exists(name):
                open(name, "wb").write(img)
            print(f"  {p}  смещение {base} -> {name}  {len(img)} б  "
                  f"({', '.join(sorted(names))})")
            total += 1
    print(f"вырезано образов: {total}")


if __name__ == "__main__":
    main()
