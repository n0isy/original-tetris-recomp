#!/usr/bin/env python3
"""
Снять обёртку записей с образа магнитной ленты (формат SIMH .TAP).

В образе лента лежит не сплошным потоком: каждая запись обрамлена своей длиной
-- `<длина 4б> <данные, до чётного> <длина 4б>`, нулевая длина означает метку
конца файла. Если резать файл прямо из такого образа, в середину попадают эти
поля, и вырезанное расходится с оригиналом примерно наполовину -- ровно так у
меня и вышло с первого раза.

Отдельная сложность: остатки прежних записей в образах HX1: начинаются не с
начала файла и в каталоге не числятся. Поэтому цепочка записей не берётся с
нуля, а *ищется*: позиция считается началом, если длина в заголовке совпадает
с длиной в хвосте и так сходится несколько записей подряд.

  tapdeframe.py <образ> [<выход>]
"""
import os, struct, sys


def _rec(d, p):
    """(длина, позиция следующей записи) или None, если тут не запись."""
    if p + 8 > len(d):
        return None
    n = struct.unpack_from("<I", d, p)[0]
    if n == 0:                                  # метка конца файла
        return 0, p + 4
    if not (0 < n <= 1 << 20) or p + 8 + n > len(d):
        return None
    pad = n + (n & 1)
    if struct.unpack_from("<I", d, p + 4 + pad)[0] != n:
        return None
    return n, p + 8 + pad


def find_start(d, need=4):
    """Первая позиция, с которой сходится подряд `need` записей."""
    for p in range(0, len(d) - 8, 2):
        q, ok = p, True
        for _ in range(need):
            r = _rec(d, q)
            if r is None:
                ok = False
                break
            q = r[1]
        if ok:
            return p
    return None


def deframe(d, start=None):
    """Склеить данные всех записей в один поток."""
    p = find_start(d) if start is None else start
    if p is None:
        return b""
    out = bytearray()
    while p < len(d):
        r = _rec(d, p)
        if r is None:
            break
        n, nxt = r
        if n:
            out += d[p + 4:p + 4 + n]
        p = nxt
    return bytes(out)


if __name__ == "__main__":
    d = open(sys.argv[1], "rb").read()
    out = deframe(d)
    dst = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1] + ".raw"
    open(dst, "wb").write(out)
    print(f"{sys.argv[1]}: {len(d)} б -> {dst}: {len(out)} б")
