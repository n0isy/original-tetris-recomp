#!/usr/bin/env python3
"""
Разбор библиотеки .OBJ на модули: имя, образ кода, глобальные символы, релокации.

Нужно, чтобы разложить готовую программу обратно на слагаемые. Компоновщик
склеивает модули встык, но какой кусок откуда -- в .SAV не записано. Зато у
каждого модуля из библиотеки известен его код, и его можно найти в программе
сопоставлением.

Что берётся из объектного файла:

* **GSD** (блок 1) -- записи по 8 байт: имя в RADIX-50 (2 слова), флаги, тип,
  значение. Тип 0 -- имя модуля, 4 -- глобальный символ, 5 -- программная
  секция. У глобального символа бит 0o10 означает *определение* (иначе это
  ссылка), значение -- смещение от начала своей секции.
* **TXT** (блок 3) -- адрес загрузки и байты.
* **RLD** (блок 4) -- какие слова компоновщик подменит адресами. Их надо
  исключать при сопоставлении: в библиотеке там нули или смещения, в готовой
  программе -- настоящие адреса.

У всех модулей PASSIM ровно одна секция с кодом -- безымянная, и её TXT идут
с нуля. Данные (RTSDAT) не инициализированы, TXT для них нет.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from objdump import records, unrad50                          # noqa: E402

# длина данных записи RLD после команды и смещения, по коду команды
RLD_LEN = {0o1: 2, 0o2: 4, 0o3: 2, 0o4: 4, 0o5: 6, 0o6: 6, 0o7: 6,
           0o10: 2, 0o11: 0, 0o12: 4, 0o14: 4, 0o15: 6, 0o16: 6}

# длина аргумента операции внутри сложного выражения (команда 0o17)
CPX_ARG = {0o16: 4, 0o17: 3, 0o20: 2}


def _rld(blk, txt_addr):
    """Адреса слов, которые компоновщик подменит. Смещение считается от адреса
    предыдущего блока TXT: loc = txt_addr + disp - 4.

    Сложную релокацию (0o17) пропустить нельзя: за ней идёт выражение
    переменной длины, и без его разбора теряется весь остаток блока. Именно так
    у меня «терялись» таблицы адресов -- модуль потом не опознавался.
    Выражение -- цепочка операций, аргумент есть у 0o16 (имя), 0o17 (секция и
    смещение) и 0o20 (константа); конец -- 0o12 или 0o13 (запись результата).
    """
    out, i = [], 2
    while i + 1 < len(blk):
        cmd = blk[i] & 0o177
        disp = blk[i + 1]
        if cmd not in (0o7, 0o10, 0o11):
            out.append(txt_addr + disp - 4)
        if cmd == 0o17:
            i += 2
            while i < len(blk):
                op = blk[i]; i += 1
                if op in (0o12, 0o13):
                    break
                i += CPX_ARG.get(op, 0)
            continue
        n = RLD_LEN.get(cmd)
        if n is None:
            break
        i += 2 + n
    return out


def modules(data):
    """[{name, size, image, defs, refs, rld}] по порядку в библиотеке."""
    out = []
    cur = dict(name=None, txt={}, defs={}, refs=[], rld=[], size=0, psects={})
    psect = None
    last_txt = 0
    for blk in records(data):
        if len(blk) < 2:
            continue
        typ = blk[0] | (blk[1] << 8)
        if typ == 1:                                        # GSD
            for o in range(2, len(blk) - 7, 8):
                nm = (unrad50(blk[o] | (blk[o + 1] << 8))
                      + unrad50(blk[o + 2] | (blk[o + 3] << 8))).strip()
                fl, ty = blk[o + 4], blk[o + 5]
                val = blk[o + 6] | (blk[o + 7] << 8)
                if ty == 0 and cur["name"] is None:
                    cur["name"] = nm
                elif ty == 5:
                    psect = nm
                    cur["psects"][nm] = val
                    if nm == "":                            # безымянная -- код
                        cur["size"] = val
                elif ty == 4:
                    if fl & 0o10:                           # определение
                        cur["defs"][nm] = (psect, val)
                    else:
                        cur["refs"].append(nm)
        elif typ == 3 and len(blk) > 4:                     # TXT
            last_txt = blk[2] | (blk[3] << 8)
            for k, b in enumerate(blk[4:]):
                cur["txt"][last_txt + k] = b
        elif typ == 4:                                      # RLD
            cur["rld"] += _rld(blk, last_txt)
        elif typ == 6:                                      # ENDMOD
            if cur["name"]:
                out.append(_finish(cur))
            cur = dict(name=None, txt={}, defs={}, refs=[], rld=[], size=0, psects={})
            psect = None
    if cur["name"]:
        out.append(_finish(cur))
    return out


def _finish(m):
    n = m["size"] or (max(m["txt"]) + 1 if m["txt"] else 0)
    buf = bytearray(n)
    for a, b in m["txt"].items():
        if a < n:
            buf[a] = b
    m["image"] = bytes(buf)
    m["size"] = n
    m["rld"] = sorted(a for a in set(m["rld"]) if 0 <= a < n)
    # какие байты модуль задаёт на самом деле: остальное -- пропуски, и в
    # готовой программе там лежит что осталось в буфере компоновщика
    m["set"] = frozenset(a for a in m["txt"] if a < n)
    del m["txt"]
    return m


if __name__ == "__main__":
    mods = modules(open(sys.argv[1], "rb").read())
    print(f"модулей: {len(mods)}")
    for m in mods:
        print(f"  {m['name']:<8} {m['size']:>6o}б  символов {len(m['defs']):>3}"
              f"  ссылок {len(m['refs']):>3}  релокаций {len(m['rld']):>4}")
        if len(sys.argv) > 2:
            for s, (p, v) in sorted(m["defs"].items(), key=lambda x: x[1][1]):
                print(f"        {s:<8} {p or '.BLK.':<7} {v:06o}")
