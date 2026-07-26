#!/usr/bin/env python3
"""
Сравнение двух двоичных файлов СО СДВИГОМ.

Сравнивать по одинаковым смещениям бесполезно: компоновщик кладёт рантайм по
своему адресу в каждой программе, и одинаковые библиотечные модули оказываются
на разных местах. Здесь строится гистограмма сдвигов -- сколько окон совпадает
при каждом смещении.

Разница видна сразу: у программ с общим рантаймом есть выраженный пик, у разных
-- ровный шум на всех сдвигах.

    tools/bincmp.py A.SAV B.SAV [ширина_окна]
"""
import sys
from collections import Counter


def informative(win, min_distinct=5):
    """Отбросить малоинформативные окна.

    Длинные прогоны нулей и прочего заполнения совпадают при любом сдвиге и
    дают ровное плато вместо пика -- на нём метрика становится бессмысленной.
    """
    return len(set(win)) >= min_distinct


def shift_histogram(a, b, w=16):
    idx = {}
    for i in range(len(a) - w):
        win = a[i:i + w]
        if informative(win):
            idx.setdefault(win, []).append(i)
    hist = Counter()
    for j in range(len(b) - w):
        win = b[j:j + w]
        if not informative(win):
            continue
        for i in idx.get(win, ()):
            hist[j - i] += 1
    return hist


def cluster(hist, gap=64):
    """Соседние сдвиги -- одна и та же область совпадения, а не фон.

    Без слияния вершина и её сосед различаются на проценты, и любой порог
    "пик против второго значения" ошибочно объявляет, что пика нет.
    """
    out = []
    for sh, n in sorted(hist.items()):
        if out and sh - out[-1][1] <= gap:
            lo, hi, tot, peak = out[-1]
            out[-1] = (lo, sh, tot + n, max(peak, n))
        else:
            out.append((sh, sh, n, n))
    return sorted(((lo, hi, peak) for lo, hi, _t, peak in out),
                  key=lambda x: -x[2])


def report(pa, pb, w=16, top=5):
    a, b = open(pa, "rb").read(), open(pb, "rb").read()
    h = shift_histogram(a, b, w)
    print(f"{pa} ({len(a)} б)  vs  {pb} ({len(b)} б),  окно {w} б")
    if not h:
        print("   совпадений нет"); return
    cl = cluster(h)
    for lo, hi, peak in cl[:top]:
        rng = f"{lo:+}" if lo == hi else f"{lo:+}..{hi:+}"
        print(f"   сдвиг {rng:>16}   совпало окон: {peak:>6}   ~{peak + w - 1:>6} байт подряд")
    peak = cl[0][2]
    floor = cl[1][2] if len(cl) > 1 else 0
    if floor and peak > 2 * floor:
        print(f"   => выраженный пик ({peak / floor:.1f}x над фоном): общий код")
    else:
        print("   => пика нет, всё на уровне фона: общего кода не видно")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    report(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 16)
