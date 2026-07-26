#!/usr/bin/env python3
"""
Применить к `$IO` три найденные правки и проверить результат по байтам.

Смысл проверки: если список правок полон, то наш модуль после них должен
совпасть с тем, что лежит внутри `TETRIS.SAV`, везде -- кроме слов, которые
подставляет компоновщик, и байтов номеров ошибок. Любое лишнее расхождение
означает, что разбор неполон.

Удаление байт сдвигает всё, что ниже, поэтому мало вырезать куски: у каждого
условного перехода и `SOB`, чья цель оказалась по другую сторону правки, надо
пересчитать смещение. Границы команд берутся из листинга SIMH, а не угадываются.

  iopatch.py <листинг-наш.asm> <наш.sav> <база8> <тетрис.sav> <база8> <длина8>
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from objlib import modules                                     # noqa: E402

LINE = re.compile(r"^([0-7]{6})  ((?:[0-7]{6} ?)+)")

# правки, в смещениях исходного модуля
DEL = [(0o620, 2),          # лишний BEQ после BIC #177000,R0
       (0o2610, 10)]        # INC/ASR/BCS/CLRB перед блоком запроса
INS = [(0o2646, bytes([0o201, 0o012, 0o201, 0o014]))]   # INC R1 / ASR R1 ниже
SET = [(0o1152, 0o000010)]  # маска BIT #14 -> #10

# Байты номеров ошибок во встроенных дескрипторах $ERROR. Это данные, а не код:
# длину модуля они не меняют и на поведение не влияют (штатный обработчик
# ERROR.PAS принимает номер параметром и не использует его). Номера взяты из
# TETRIS.SAV -- своей библиотеки с ними у нас нет ни одной.
SETB = [(0o155, 30), (0o243, 18), (0o273, 17), (0o465, 19),
        (0o767, 33), (0o2375, 33), (0o2423, 30), (0o2453, 33)]


def parse(path):
    """[(смещение, число слов)] по листингу."""
    out, base = [], None
    for ln in open(path):
        m = LINE.match(ln)
        if not m:
            continue
        a = int(m.group(1), 8)
        if base is None:
            base = a
        out.append((a - base, len(m.group(2).split())))
    return out


def edit_map(size):
    """старое смещение -> новое, и признак «байт удалён»."""
    mp, cur = {}, 0
    dels = {}
    for off, n in DEL:
        for k in range(n):
            dels[off + k] = True
    ins = dict(INS)
    for o in range(size):
        if o in ins:
            cur += len(ins[o])
        if o in dels:
            mp[o] = None
            continue
        mp[o] = cur
        cur += 1
    return mp, cur


def patch(img):
    mp, newsize = edit_map(len(img))
    out = bytearray(newsize)
    ins = dict(INS)
    for o in range(len(img)):
        if o in ins:
            at = mp[o] if mp[o] is not None else None
            if at is not None:
                out[at - len(ins[o]):at] = ins[o]
        if mp[o] is not None:
            out[mp[o]] = img[o]
    for off, val in SET:
        at = mp[off]
        out[at] = val & 0xFF
        out[at + 1] = val >> 8
    for off, val in SETB:
        out[mp[off]] = val
    return bytes(out), mp


BR = [(0o000400, 0o003777), (0o100000, 0o103777)]


def fields(op):
    """Поля адресации команды: сколько операндов и какие 6-битные поля.

    Нужно, чтобы найти операнды в режиме «относительно PC» (режимы 6 и 7 при
    регистре 7): у них следующее слово -- смещение до цели, и при сдвиге кода
    его тоже надо пересчитать. Непосредственные операнды (режим 2, регистр 7)
    -- константы, их трогать нельзя.
    """
    hi = op >> 12
    if hi in (1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14):        # двухоперандные
        return [(op >> 6) & 0o77, op & 0o77]
    if 0o004000 <= op <= 0o004777:                             # JSR
        return [op & 0o77]
    if 0o000100 <= op <= 0o000177:                             # JMP
        return [op & 0o77]
    if 0o000300 <= op <= 0o000377 or 0o005000 <= op <= 0o006777 \
            or 0o105000 <= op <= 0o106777:                     # одноместные
        return [op & 0o77]
    if 0o070000 <= op <= 0o074777:                             # MUL/DIV/ASH/XOR
        return [op & 0o77]
    return []


def fix_branches(img, new, mp, instrs):
    """Пересчитать смещения переходов, пересёкших правку."""
    w = lambda b, a: b[a] | (b[a + 1] << 8)                     # noqa: E731
    n = 0
    for off, nw in instrs:
        if mp.get(off) is None or off + 1 >= len(img):
            continue
        op = w(img, off)
        isbr = any(lo <= op <= hi for lo, hi in BR)
        issob = 0o077000 <= op <= 0o077777
        if not (isbr or issob):
            # относительные к PC операнды: пересчитать смещение
            pos = off + 2
            for f in fields(op):
                mode, reg = f >> 3, f & 7
                if mode in (2, 3) and reg == 7:                 # #конст / @#адрес
                    pos += 2
                elif mode in (6, 7):
                    if reg == 7 and pos + 1 < len(img):
                        d = w(img, pos)
                        tgt = (pos + 2 + d) & 0xFFFF
                        if tgt < len(img) and mp.get(tgt) is not None \
                                and mp.get(pos) is not None:
                            nd = (mp[tgt] - (mp[pos] + 2)) & 0xFFFF
                            if nd != d:
                                new = bytearray(new)
                                new[mp[pos]] = nd & 0xFF
                                new[mp[pos] + 1] = nd >> 8
                                new = bytes(new)
                                n += 1
                    pos += 2
            continue
        at = mp[off]
        if isbr:
            d = op & 0xFF
            d = d - 256 if d & 0x80 else d
            tgt = off + 2 + 2 * d
        else:
            tgt = off + 2 - 2 * (op & 0o77)
        if tgt >= len(img) or mp.get(tgt) is None:
            continue
        nd = (mp[tgt] - (at + 2)) // 2
        if isbr:
            newop = (op & 0xFF00) | (nd & 0xFF)
        else:
            newop = (op & 0o177700) | ((-nd) & 0o77)
        if newop != op:
            new = bytearray(new)
            new[at] = newop & 0xFF
            new[at + 1] = newop >> 8
            new = bytes(new)
            n += 1
    return new, n


def main():
    lst, ours_p, ob, tet_p, tb, tlen = sys.argv[1:7]
    ob, tb, tlen = int(ob, 8), int(tb, 8), int(tlen, 8)
    ours_all = open(ours_p, "rb").read()
    img = ours_all[ob:ob + 0o2704]
    tet = open(tet_p, "rb").read()[tb:tb + tlen]
    instrs = parse(lst)
    new, mp = patch(img)
    new, nfix = fix_branches(img, new, mp, instrs)
    print(f"исходный {len(img)} б -> после правок {len(new)} б;  нужно {len(tet)} б"
          f";  пересчитано переходов: {nfix}")
    if len(new) != len(tet):
        print("РАЗМЕР НЕ СОШЁЛСЯ"); return

    # маска: слова, которые подставляет компоновщик (по RLD исходного модуля)
    m = next(x for x in modules(open(os.path.join(HERE, "..", "pascal", "gold",
                                                  "PASSIM.OBJ"), "rb").read())
             if x["name"] == "$IO")
    ok = bytearray(b"\1" * len(img))
    for a in m["rld"]:
        ok[a:a + 2] = b"\0\0"
    diff, reloc, num = [], 0, 0
    for o in range(len(img)):
        if mp[o] is None:
            continue
        if new[mp[o]] == tet[mp[o]]:
            continue
        if not ok[o]:
            reloc += 1
        else:
            diff.append((o, mp[o]))
    print(f"расхождений после правок: {len(diff)}  (в релоцируемых словах: {reloc})")
    for o, a in diff:
        print(f"   исх +{o:04o} -> нов +{a:04o}   наш {new[a]:03o}   тетрис {tet[a]:03o}")


if __name__ == "__main__":
    main()
