#!/usr/bin/env python3
"""
Восстановить объектный модуль `$INIT` из готовой программы.

`$INIT` в тетрисе -- другая редакция, правкой нашего не получить. Зато он лежит
в `TETRIS.SAV` целиком, и его можно собрать обратно в `.OBJ`.

Главная трудность -- отличить в 548 байтах адреса от констант. Догадки тут не
годятся, поэтому тип каждого слова **измеряется**: тот же `$INIT` слинкован в
семи разных программах по разным адресам, и достаточно посмотреть, как слово
меняется от программы к программе.

    не меняется вовсе          -> константа
    меняется вслед за базой    -> адрес внутри модуля
    вслед за RTSDAT            -> адрес в области данных рантайма
    вслед за чужим модулем     -> ссылка на внешний символ

Отдельно ловятся операнды «относительно PC»: у них меняется не адрес, а
смещение, то есть разность двух баз.

Как хранить найденное в объектном файле -- тоже не выдумано, а взято с эталона:
для каждой релокации в `PASSIM.OBJ` сравнивалось, что лежит в `.OBJ` и что
получилось после компоновки.

  mkinit.py <выход.obj>
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from laylink import layout                                     # noqa: E402

SRC = "extracted/grands/grands/g1_dsk.rar_unpacked/g1_dsk/TETRIS.SAV"
PROGS = [
    "extracted/grands/grands/g1_dsk.rar_unpacked/g1_dsk/TETRIS.SAV",
    "tetris/1985/TET-1985.SAV",
    "extracted/grands/grands/g1_dsk.rar_unpacked/g1_dsk/GOROD.SAV",
    "extracted/grands/grands/g3_dsk.rar_unpacked/g3_dsk/TROPA.SAV",
    "extracted/graph/graph/graph.zip_unpacked/graph/cub2.sav",
    "extracted/graph/graph/graph.zip_unpacked/graph/setup1.sav",
]
SIZE = 0o1044                      # размер модуля в тетрисе
NAMED = 0o614                      # RTSDAT 606 + DBGLNK 4 + SIMLNK 2

R50 = " ABCDEFGHIJKLMNOPQRSTUVWXYZ$.?0123456789"


def rad50(s):
    s = (s + "   ")[:6]
    out = b""
    for i in (0, 3):
        v = 0
        for c in s[i:i + 3]:
            v = v * 40 + R50.index(c)
        out += struct.pack("<H", v)
    return out


def w(b, a):
    return b[a] | (b[a + 1] << 8)


SECS = [("RTSDAT", 0o606), ("DBGLNK", 0o4), ("SIMLNK", 0o2)]


def section(off):
    """Смещение в общей области данных -> (имя секции, смещение в ней)."""
    rest = off
    for nm, ln in SECS:
        if rest < ln:
            return nm, rest
        rest -= ln
    raise SystemExit(f"смещение {off:o} за пределами именованных секций")


def survey():
    """Тип каждого релоцируемого слова, измеренный по нескольким программам."""
    P = []
    for p in PROGS:
        d = open(p, "rb").read()
        _, found = layout("pascal/gold/PASSIM.OBJ", p)
        mods = {m["name"]: b for b, m, _r in found}
        top = w(d, 0o50)
        P.append(dict(d=d, base=w(d, 0o40) - 0o20, rts=top - NAMED, mods=mods))
    kinds = {}
    for o in range(0, SIZE, 2):
        vals = [w(pr["d"], pr["base"] + o) for pr in P]
        if len(set(vals)) == 1:
            continue                                   # константа
        got = None
        if all(vals[i] == w(P[i]["d"], 0o50) for i in range(len(P))):
            # слово всюду равно верхней границе программы -- это вторая половина
            # пары .LIMIT. Проверять надо до перебора якорей: иначе оно ловится
            # как адрес в RTSDAT со смещением ровно на конец области.
            kinds[o] = ("LIMIT", "pair", 0)
            continue
        for nm in ["."] + ["RTSDAT"] + sorted(P[0]["mods"]):
            anc = [pr["base"] if nm == "." else
                   pr["rts"] if nm == "RTSDAT" else pr["mods"].get(nm) for pr in P]
            if any(a is None for a in anc):
                continue
            s = {vals[i] - anc[i] for i in range(len(P))}
            if len(s) == 1 and 0 <= next(iter(s)) < 0o200000:
                got = (nm, "abs", next(iter(s))); break
            s = {(P[i]["base"] + o + 2 + vals[i] - anc[i]) & 0xFFFF for i in range(len(P))}
            if len(s) == 1 and 0 <= next(iter(s)) < 0o200000:
                got = (nm, "disp", next(iter(s))); break
        if got is None:
            t = [(P[i]["base"] + o + 2 + vals[i]) & 0xFFFF for i in range(len(P))]
            if len(set(t)) == 1 and t[0] < 0o1000:     # смещение к абсолютной ячейке
                got = ("ABS", "disp", t[0])
            elif all(0o1000 <= t[i] < P[i]["base"] for i in range(len(P))):
                # цель всюду лежит в области кода программы -- это точка входа
                # паскалевского модуля, символ $BEGIN
                got = ("$BEGIN", "disp", 0)
        kinds[o] = got
    return kinds, P[0]


# --- сборка объектного файла ------------------------------------------------

def rec(payload):
    n = len(payload) + 4
    b = bytearray([1, 0, n & 0xFF, n >> 8]) + payload
    b.append((-sum(b)) & 0xFF)
    return bytes(b)


def gsd(entries):
    out = struct.pack("<H", 1)
    for nm, fl, ty, val in entries:
        out += rad50(nm) + bytes([fl, ty]) + struct.pack("<H", val)
    return out


def main():
    kinds, P0 = survey()
    img = bytearray(P0["d"][P0["base"]:P0["base"] + SIZE])
    base, rts, mods = P0["base"], P0["rts"], P0["mods"]

    # значения, как их хранит объектный файл (соглашение снято с эталона)
    rld = {}
    for o, k in sorted(kinds.items()):
        if k is None:
            raise SystemExit(f"слово +{o:04o} не опознано -- сборка недопустима")
        nm, how, val = k
        if nm == "." and how == "abs":
            store, cmd, arg, con = val, 0o1, None, val        # внутренняя
        elif nm == "ABS" and how == "disp":
            store, cmd, arg, con = val, 0o3, None, val        # смещение к ячейке
        elif nm == "LIMIT":
            img[o - 2] = img[o - 1] = img[o] = img[o + 1] = 0
            rld[o - 2] = (0o11, None, None)
            continue
        elif nm == "RTSDAT":
            # именованные секции идут подряд: RTSDAT, DBGLNK, SIMLNK. Смещение
            # за концом RTSDAT означает следующую секцию, а не выход за границу.
            sec, off = section(val)
            store = off
            cmd, arg, con = (0o15 if how == "abs" else 0o16), sec, off
        else:                                                  # внешний символ
            sym = {"$IO": "$CLOSE"}.get(nm, "$BEGIN")
            store, cmd, arg, con = 0, 0o4, sym, None
        img[o] = store & 0xFF
        img[o + 1] = store >> 8
        rld[o] = (cmd, arg, con)
    # $VER: одинаков во всех программах, поэтому измерением не ловится
    img[0o24] = img[0o25] = 0
    rld[0o24] = (0o2, "$VER", None)

    ent = [("$INIT", 0o0, 0, 0), ("V1.2G", 0o0, 6, 0),
           (". ABS.", 0o114, 5, 0),
           ("$BEGIN", 0o100, 4, 0), ("$CLOSE", 0o100, 4, 0), ("$VER", 0o100, 4, 0),
           ("", 0o050, 5, SIZE),
           ("$B63", 0o150, 4, 0o656), ("$END", 0o150, 4, 0o656),
           ("$START", 0o150, 4, 0o20),
           ("RTSDAT", 0o154, 5, 0o606),
           ("RTAREA", 0o150, 4, 0o132), ("$FILE", 0o150, 4, 0o60),
           ("$FREE", 0o150, 4, 0o64), ("$RESR5", 0o150, 4, 0o2),
           ("$RESR6", 0o150, 4, 0o0), ("$STACK", 0o150, 4, 0o606),
           ("$USRPC", 0o150, 4, 0o54),
           ("DBGLNK", 0o154, 5, 0o4), ("SIMLNK", 0o154, 5, 0o2),
           ("$F8", 0o150, 4, 0o2),
           ("", 0o050, 3, 0o20)]
    out = rec(gsd(ent)) + rec(struct.pack("<H", 2))

    CH = 38
    for a in range(0, SIZE, CH):
        n = min(CH, SIZE - a)
        out += rec(struct.pack("<HH", 3, a) + bytes(img[a:a + n]))
        ent_r = b""
        if a == 0:                       # объявить текущую секцию -- как у эталона
            ent_r += bytes([0o7, 4]) + rad50("") + struct.pack("<H", 0)
        for o in range(a, a + n):
            if o in rld:
                cmd, arg, con = rld[o]
                disp = o - a + 4
                ent_r += bytes([cmd, disp])
                if arg:
                    ent_r += rad50(arg)
                if con is not None and cmd in (0o1, 0o3, 0o15, 0o16):
                    ent_r += struct.pack("<H", con)
        if ent_r:
            out += rec(struct.pack("<H", 4) + ent_r)
    # именованные секции с данными: у $INIT это заглушки в DBGLNK и SIMLNK
    out += rec(struct.pack("<H", 6))
    open(sys.argv[1], "wb").write(out)
    print(f"{sys.argv[1]}: {len(out)} б;  релокаций {len(rld)};  размер модуля {SIZE:o}")
    from collections import Counter
    c = Counter((k[0], k[1]) for k in kinds.values() if k)
    for (nm, how), n in c.most_common():
        print(f"   {nm:<8} {how:<5} {n}")


if __name__ == "__main__":
    main()
