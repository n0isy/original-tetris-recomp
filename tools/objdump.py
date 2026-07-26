#!/usr/bin/env python3
"""
Разбор объектного файла RT-11 (.OBJ) в образ памяти, чтобы извлекать строки.

Формат двухслойный, и наивный grep по файлу врёт: строки рвутся границами.

  1. Форматные двоичные записи:  01 00 <длина 2б> <данные> <кс 1б>
     Длина считает и 4-байтный заголовок.
  2. Внутри данных -- блок объектного формата, первое слово -- тип:
       1 GSD  2 ENDGSD  3 TXT  4 RLD  5 ISD  6 ENDMOD  7/8 библиотека
     У TXT следующее слово -- адрес загрузки, дальше сами байты.

Строки лежат только в TXT. Склеивать надо ТОЛЬКО их и по адресам, иначе между
кусками строки попадают заголовки блоков и данные RLD -- ровно так и получались
обрубки вида `Bad support p` + `ackage`.

  objdump.py strings <файл.obj> [миндлина]   -- строки из образа памяти
  objdump.py blocks  <файл.obj>              -- статистика блоков
"""
import sys
from collections import Counter


def records(data):
    """Выдать полезную нагрузку каждой форматной двоичной записи."""
    i = 0
    while i < len(data) - 4:
        if data[i] == 1 and data[i + 1] == 0:
            ln = data[i + 2] | (data[i + 3] << 8)
            if 6 <= ln <= len(data) - i:
                yield data[i + 4:i + ln]
                i += ln + 1
                continue
        i += 1


R50 = " ABCDEFGHIJKLMNOPQRSTUVWXYZ$.?0123456789"


def unrad50(w):
    return R50[(w // 1600) % 40] + R50[(w // 40) % 40] + R50[w % 40]


def modules(data):
    """Собрать образ памяти каждого модуля: [(имя_или_None, bytes), ...].

    Имя берётся из GSD (блок типа 1): записи по 8 байт, первые два слова --
    имя в RADIX-50, затем флаги, тип и значение. Тип 0 -- имя модуля.
    """
    out, mem, cur = [], {}, None
    for blk in records(data):
        if len(blk) < 2:
            continue
        typ = blk[0] | (blk[1] << 8)
        if typ == 1:                                  # GSD
            for o in range(2, len(blk) - 7, 8):
                if blk[o + 5] == 0 and cur is None:   # запись типа 0 -- имя модуля
                    n1 = blk[o] | (blk[o + 1] << 8)
                    n2 = blk[o + 2] | (blk[o + 3] << 8)
                    cur = (unrad50(n1) + unrad50(n2)).strip()
        elif typ == 3 and len(blk) > 4:               # TXT: адрес + данные
            addr = blk[2] | (blk[3] << 8)
            for k, b in enumerate(blk[4:]):
                mem[addr + k] = b
        elif typ == 6:                                # ENDMOD -- модуль кончился
            if mem:
                out.append((cur, flatten(mem)))
            mem, cur = {}, None
    if mem:
        out.append((cur, flatten(mem)))
    return out


def flatten(mem):
    """Разрывы в адресах заполнить нулём, чтобы строки не склеивались через дыру."""
    lo, hi = min(mem), max(mem)
    buf = bytearray(hi - lo + 1)
    for a, b in mem.items():
        buf[a - lo] = b
    return bytes(buf)


def strings(data, minlen=6):
    out, cur = [], bytearray()
    for b in data:
        if 0x20 <= b < 0x7F:
            cur.append(b)
        else:
            if len(cur) >= minlen: out.append(cur.decode())
            cur = bytearray()
    if len(cur) >= minlen: out.append(cur.decode())
    return out


def is_obj(data):
    """Настоящий .OBJ начинается записью с нулевого смещения и весь ею покрыт.

    Проверять просто наличие пары 01 00 нельзя: в образе памяти (.SAV) она
    встречается случайно, и файл ошибочно уходит в объектную ветку.
    """
    if len(data) < 8 or data[0] != 1 or data[1] != 0:
        return False
    covered = sum(len(r) + 5 for r in records(data))
    return covered >= 0.9 * len(data)


def obj_strings(path, minlen=6):
    data = open(path, "rb").read()
    if not is_obj(data):                              # обычный образ памяти
        return strings(data, minlen)
    res = []
    for _, mem in modules(data):
        res += strings(mem, minlen)
    return res


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "strings":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 6
        for s in obj_strings(path, n): print(s)
    elif cmd == "blocks":
        d = open(path, "rb").read()
        c = Counter((b[0] | (b[1] << 8)) for b in records(d) if len(b) >= 2)
        names = {1: "GSD", 2: "ENDGSD", 3: "TXT", 4: "RLD", 5: "ISD",
                 6: "ENDMOD", 7: "LIBHDR", 8: "LIBEND"}
        print(f"записей: {sum(c.values())}, модулей: {len(modules(d))}")
        for t, n in sorted(c.items()): print(f"  тип {t} {names.get(t,'?'):<8} {n}")
