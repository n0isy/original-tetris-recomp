#!/usr/bin/env python3
"""
Определить, какие модули рантайма компоновщик вложил в готовую программу.

Компоновщик RT-11 берёт из библиотеки только те модули, на которые есть ссылки.
Значит набор вложенных модулей -- отпечаток того, какими возможностями языка
пользовалась программа. Сравнив набор у восстановленной программы с набором у
оригинала, можно понять, что именно там было.

Опознание -- по фрагментам кода, уникальным для одного модуля: часть байт
переставляет компоновщик, но достаточно много участков переживает перемещение.

  modset.py <библиотека.obj> <программа.sav> [...]
  modset.py --diff <библиотека.obj> <эталон.sav> <кандидат.sav>
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from objdump import modules                                    # noqa: E402

W = 16          # длина фрагмента
MIN_DISTINCT = 6
MIN_HITS = 8      # минимум уникальных фрагментов
MIN_RATIO = 0.05  # ...и не меньше этой доли от всех фрагментов модуля

# Порога «просто несколько фрагментов» мало: у крупного модуля случайно
# совпадает горсть окон, и он ошибочно числится вложенным. Так отладчик DBG
# показывался в тетрисе по 4 совпадениям из 3646 -- то есть шум.


def signatures(lib_path, w=W):
    """{имя модуля: множество фрагментов, встречающихся только в нём}."""
    mods = modules(open(lib_path, "rb").read())
    wins, seen = {}, {}
    for nm, mem in mods:
        s = {mem[i:i + w] for i in range(len(mem) - w)
             if len(set(mem[i:i + w])) >= MIN_DISTINCT}
        wins[nm] = s
        for x in s:
            seen[x] = seen.get(x, 0) + 1
    return {nm: {x for x in s if seen[x] == 1} for nm, s in wins.items()}


def present(sig, prog_path, w=W):
    d = open(prog_path, "rb").read()
    have = {d[i:i + w] for i in range(len(d) - w)}
    out = {}
    for nm, s in sig.items():
        if not s:
            continue
        n = len(s & have)
        if n >= MIN_HITS and n / len(s) >= MIN_RATIO:
            out[nm] = (n, len(s))
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__); return
    if sys.argv[1] == "--diff":
        sig = signatures(sys.argv[2])
        a, b = present(sig, sys.argv[3]), present(sig, sys.argv[4])
        na, nb = os.path.basename(sys.argv[3]), os.path.basename(sys.argv[4])
        print(f"  только в {na}: {sorted(set(a) - set(b))}")
        print(f"  только в {nb}: {sorted(set(b) - set(a))}")
        print(f"  общих: {len(set(a) & set(b))}")
        return
    sig = signatures(sys.argv[1])
    for p in sys.argv[2:]:
        got = present(sig, p)
        print(f"\n{p}  --  модулей {len(got)}")
        for nm, (n, tot) in sorted(got.items()):
            print(f"    {nm:<8} {n:>4} из {tot} фрагментов")


if __name__ == "__main__":
    main()
