#!/usr/bin/env python3
"""
Восстановить объектный модуль из готовых программ, в которые он слинкован.

Задача -- отличить в образе модуля адреса от констант. Догадки тут негодны,
поэтому тип каждого слова **измеряется**: один и тот же модуль слинкован в
нескольких программах по разным адресам, и достаточно посмотреть, как слово
меняется от программы к программе.

    не меняется вовсе        -> константа
    меняется вслед за базой  -> адрес внутри модуля
    вслед за именованной секцией -> адрес в общей области данных
    вслед за чужим модулем   -> ссылка на внешний символ
    всюду равно верхней границе программы -> вторая половина пары `.LIMIT`

Операнды «относительно PC» ловятся тем же перебором, только сравнивается не
значение слова, а вычисленная по нему цель.

Формат записей взят с эталона, а не из головы: у секций используются
*дополняющие* команды (0o15 и 0o16) с константой, у внутренних -- 0o1 и 0o3
со словом данных, у внешних символов -- 0o2 и 0o4 с именем.

Проверять восстановитель надо на модуле, для которого есть настоящий `.OBJ`:
собрать несколько программ своим же паскалем, восстановить по ним модуль и
сравнить с оригиналом.

  remod.py <библиотека.obj> <модуль> <размер8> <выход.obj> <прог> [<прог> ...]
"""
import os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from objdump import records, unrad50                           # noqa: E402
from laylink import layout                                     # noqa: E402

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


def txt_layout(lib, name):
    """[(адрес, длина)] блоков TXT нужного модуля.

    Нужно, чтобы воспроизвести разрывы: в модуле есть неинициализированные
    байты (`.BLKB`), TXT на них обрывается, и компоновщик заполняет их нулём.
    Из готовой программы разрывы не видны -- там уже нули, неотличимые от
    настоящих. Поэтому при проверке раскладка берётся с эталона: так
    сравнивается всё остальное, а не умение угадать разрывы.
    """
    out, take = [], False
    for blk in records(open(lib, "rb").read()):
        if len(blk) < 2:
            continue
        t = blk[0] | (blk[1] << 8)
        if t == 1:
            for o in range(2, len(blk) - 7, 8):
                if blk[o + 5] == 0:
                    nm = (unrad50(blk[o] | (blk[o + 1] << 8))
                          + unrad50(blk[o + 2] | (blk[o + 3] << 8))).strip()
                    take = (nm == name)
        elif t == 3 and take:
            out.append((blk[2] | (blk[3] << 8), len(blk) - 4))
        elif t == 6 and take:
            break
    return out


def tail_records(lib, name):
    """Записи после того, как адреса TXT пошли вспять: содержимое именованных
    секций (у `$INIT` это заглушки в DBGLNK и SIMLNK). Берутся как есть."""
    data = open(lib, "rb").read()
    out, take, prev, started = bytearray(), False, None, False
    i = 0
    while i < len(data) - 4:
        if data[i] == 1 and data[i + 1] == 0:
            ln = data[i + 2] | (data[i + 3] << 8)
            if 6 <= ln <= len(data) - i:
                blk = data[i + 4:i + ln]
                t = blk[0] | (blk[1] << 8)
                if t == 1:
                    for o in range(2, len(blk) - 7, 8):
                        if blk[o + 5] == 0:
                            nm = (unrad50(blk[o] | (blk[o + 1] << 8))
                                  + unrad50(blk[o + 2] | (blk[o + 3] << 8))).strip()
                            take = (nm == name)
                if take and t == 3:
                    a = blk[2] | (blk[3] << 8)
                    if prev is not None and a < prev:
                        started = True
                    prev = a
                if take and started and t != 6:
                    out += data[i:i + ln + 1]
                i += ln + 1
                if take and t == 6:
                    break
                continue
        i += 1
    return bytes(out)


_G = {}


def globals_of(lib):
    """{(модуль, смещение): имя} -- глобальные символы кодовой секции."""
    if lib in _G:
        return _G[lib]
    out, cur, sec = {}, None, None
    for blk in records(open(lib, "rb").read()):
        if len(blk) < 2 or (blk[0] | (blk[1] << 8)) != 1:
            continue
        for o in range(2, len(blk) - 7, 8):
            nm = (unrad50(blk[o] | (blk[o + 1] << 8))
                  + unrad50(blk[o + 2] | (blk[o + 3] << 8))).strip()
            fl, ty, val = blk[o + 4], blk[o + 5], blk[o + 6] | (blk[o + 7] << 8)
            if ty == 0:
                cur, sec = nm, None
            elif ty == 5:
                sec = nm
            elif ty == 4 and (fl & 0o10) and sec == "":
                out.setdefault((cur, val), nm)
    _G[lib] = out
    return out


def gsd_of(lib, name):
    """Записи GSD нужного модуля, в исходном порядке."""
    cur, out, take = None, [], False
    for blk in records(open(lib, "rb").read()):
        if len(blk) < 2:
            continue
        t = blk[0] | (blk[1] << 8)
        if t == 1:
            for o in range(2, len(blk) - 7, 8):
                nm = (unrad50(blk[o] | (blk[o + 1] << 8))
                      + unrad50(blk[o + 2] | (blk[o + 3] << 8))).strip()
                fl, ty, val = blk[o + 4], blk[o + 5], blk[o + 6] | (blk[o + 7] << 8)
                if ty == 0:
                    cur = nm
                    take = (nm == name)
                if take:
                    out.append([nm, fl, ty, val])
        elif t == 6:
            if take:
                return out
            cur, out, take = None, [], False
    return out


def named_secs(gsd):
    """Именованные секции модуля в порядке объявления: [(имя, длина)]."""
    return [(nm, val) for nm, fl, ty, val in gsd
            if ty == 5 and nm not in ("", ". ABS.")]


def all_named(lib):
    from objlib import modules as _m
    d = {}
    for x in _m(open(lib, "rb").read()):
        for p, v in x["psects"].items():
            if p not in ("", ". ABS."):
                d[p] = max(d.get(p, 0), v)
    return sum(v for k, v in d.items() if k != "DEBUG")


def sizes_of(lib):
    from objlib import modules as _m
    return {x["name"]: x["size"] for x in _m(open(lib, "rb").read())}


def survey(progs, lib, name, size, secs):
    P = []
    for p in progs:
        d = open(p, "rb").read()
        _, found = layout(lib, p)
        mods = {m["name"]: b for b, m, _r in found}
        if name not in mods:
            raise SystemExit(f"{p}: модуль {name} не найден")
        # Именованные секции компоновщик собирает по всей библиотеке, а не по
        # одному модулю: у $IO объявлена только RTSDAT, но за ней всё равно
        # лежат DBGLNK и SIMLNK. Считать надо общий размер, иначе вся область
        # данных смещается и смещения выходят не те.
        total = all_named(lib)
        P.append(dict(d=d, base=mods[name], data=w(d, 0o50) - total, mods=mods))
    SZ = sizes_of(lib)
    kinds = {}
    for o in range(0, size, 2):
        vals = [w(pr["d"], pr["base"] + o) for pr in P]
        if len(set(vals)) == 1:
            continue
        if all(vals[i] == w(P[i]["d"], 0o50) for i in range(len(P))):
            kinds[o] = ("LIMIT", "pair", 0)
            continue
        got = None
        for nm in ["."] + ["@DATA"] + sorted(P[0]["mods"]):
            anc = [pr["base"] if nm == "." else
                   pr["data"] if nm == "@DATA" else pr["mods"].get(nm) for pr in P]
            if any(a is None for a in anc):
                continue
            # Модули лежат встык, поэтому «конец одного» и «начало другого» --
            # один адрес. Смещение обязано попасть ВНУТРЬ модуля, иначе ссылка
            # приписывается соседу.
            lim = 0o200000 if nm in (".", "@DATA") else SZ.get(nm, 0)
            s = {vals[i] - anc[i] for i in range(len(P))}
            if len(s) == 1 and 0 <= next(iter(s)) < lim:
                got = (nm, "abs", next(iter(s))); break
            s = {(P[i]["base"] + o + 2 + vals[i] - anc[i]) & 0xFFFF for i in range(len(P))}
            if len(s) == 1 and 0 <= next(iter(s)) < lim:
                got = (nm, "disp", next(iter(s))); break
        if got is None:
            t = [(P[i]["base"] + o + 2 + vals[i]) & 0xFFFF for i in range(len(P))]
            if len(set(t)) == 1 and t[0] < 0o1000:
                got = ("ABS", "disp", t[0])
            elif all(0o1000 <= t[i] < P[i]["base"] for i in range(len(P))):
                got = ("$BEGIN", "disp", 0)
        kinds[o] = got
    return kinds, P[0]


def rec(payload):
    n = len(payload) + 4
    b = bytearray([1, 0, n & 0xFF, n >> 8]) + payload
    b.append((-sum(b)) & 0xFF)
    return bytes(b)


def build(lib, name, size, progs, refs, layout_hint=None, tail=b""):
    gsd = gsd_of(lib, name)
    secs = named_secs(gsd)
    # смещение в общей области -> (секция, смещение в ней) для объявленных
    # глобальных символов
    symoff, acc = {}, {}
    base_of = {}
    off = 0
    for sn, ln in secs:
        base_of[sn] = off
        off += ln
    for nm2, fl, ty, val in gsd:
        if ty == 4 and (fl & 0o10) and nm2 in ():
            pass
    cur_sec = None
    for nm2, fl, ty, val in gsd:
        if ty == 5:
            cur_sec = nm2
        elif ty == 4 and (fl & 0o10) and cur_sec in base_of:
            symoff.setdefault(base_of[cur_sec] + val, (cur_sec, val))
    kinds, P0 = survey(progs, lib, name, size, secs)
    img = bytearray(P0["d"][P0["base"]:P0["base"] + size])
    rld = {}
    for o, k in sorted(kinds.items()):
        if k is None:
            raise SystemExit(f"слово +{o:04o} не опознано")
        nm, how, val = k
        if nm == "LIMIT":
            img[o - 2:o + 2] = b"\0\0\0\0"
            rld[o - 2] = (0o11, None, None)
            continue
        if nm == "." and how == "abs":
            store, cmd, arg, con = val, 0o1, None, val
        elif nm == "ABS" and how == "disp":
            store, cmd, arg, con = val, 0o3, None, val
        elif nm == "@DATA":
            # Граница секций неоднозначна: «конец RTSDAT» и «начало DBGLNK» --
            # один адрес. Выбор определяется не арифметикой, а тем, какой
            # символ был в исходнике: если по этому смещению объявлен
            # глобальный символ (например $STACK = RTSDAT+606), берётся его
            # секция; иначе -- обычное деление по длинам.
            if val in symoff:
                sn, rest = symoff[val]
            else:
                rest = val
                for sn, ln in secs:
                    if rest < ln:
                        break
                    rest -= ln
            store, arg, con = rest, sn, rest
            cmd = 0o15 if how == "abs" else 0o16
        else:
            # Имя внешнего символа не угадывается: берётся из таблицы символов
            # модуля-цели -- тот, чьё значение совпало с измеренным смещением.
            sym = refs.get(nm) or globals_of(lib).get((nm, val))
            if sym is None:
                raise SystemExit(f"+{o:04o}: в модуле {nm} нет символа со "
                                 f"смещением {val:o}")
            store, cmd, arg, con = 0, 0o4, sym, None
        img[o] = store & 0xFF
        img[o + 1] = store >> 8
        rld[o] = (cmd, arg, con)
    for o, sym in refs.get("@ABS", {}).items():          # абсолютные символы
        img[o] = img[o + 1] = 0
        rld[o] = (0o2, sym, None)

    # Длина записи ограничена: у эталона ни один блок не длиннее 42 байт --
    # столько же берёт буфер компоновщика. Более длинный блок он отвергает
    # с `?LINK-F-ILLEGAL RECORD TYPE`, что и случилось с первой попыткой.
    LIM = 42

    out = bytearray()
    ent = []
    for nm, fl, ty, val in gsd:
        if ty == 5 and nm == "":
            val = size
        ent.append(rad50(nm) + bytes([fl, ty]) + struct.pack("<H", val))
    for i in range(0, len(ent), (LIM - 2) // 8):
        out += rec(struct.pack("<H", 1) + b"".join(ent[i:i + (LIM - 2) // 8]))
    out += rec(struct.pack("<H", 2))
    # Определение текущей секции идёт ОТДЕЛЬНЫМ блоком RLD и обязательно ДО
    # первого TXT: иначе компоновщик не знает, куда класть данные, и отвергает
    # файл. У эталона порядок именно такой -- это видно при сравнении блоков.
    out += rec(struct.pack("<H", 4) + bytes([0o7, 0]) + rad50("")
               + struct.pack("<H", 0))
    # Нарезка как у эталона: блок закрывается либо на 38 байтах данных, либо
    # когда набралось 5 записей RLD -- что раньше.
    CH, MAXR = 38, 5
    if layout_hint:
        prev_end = None
        for i, (a, n) in enumerate(layout_hint):
            if prev_end is not None and a < prev_end:
                break                       # адрес пошёл вспять -- другая секция
            out += rec(struct.pack("<HH", 3, a) + bytes(img[a:a + n]))
            es = []
            for o in range(a, a + n):
                if o in rld:
                    cmd, arg, con = rld[o]
                    x = bytes([cmd, o - a + 4])
                    if arg:
                        x += rad50(arg)
                    if con is not None:
                        x += struct.pack("<H", con)
                    es.append(x)
            nxt = layout_hint[i + 1][0] if i + 1 < len(layout_hint) else None
            if nxt is not None and nxt > a + n:
                # разрыв: неинициализированные байты. Счётчик переносится
                # отдельной записью, а не молчаливым скачком адреса.
                es.append(bytes([0o10, 0]) + struct.pack("<H", nxt))
            if es:
                out += rec(struct.pack("<H", 4) + b"".join(es))
            prev_end = a + n
        out += tail
        out += rec(struct.pack("<H", 6))
        return bytes(out), kinds
    a = 0
    while a < size:
        es, n = [], 0
        while n < CH and a + n < size:
            o = a + n
            if o in rld:
                if len(es) == MAXR:
                    break
                cmd, arg, con = rld[o]
                x = bytes([cmd, n + 4])
                if arg:
                    x += rad50(arg)
                if con is not None:
                    x += struct.pack("<H", con)
                es.append(x)
            n += 2 if o in rld else 1
        out += rec(struct.pack("<HH", 3, a) + bytes(img[a:a + n]))
        if es:
            out += rec(struct.pack("<H", 4) + b"".join(es))
        a += n
    out += rec(struct.pack("<H", 6))
    return bytes(out), kinds


def main():
    lib, name, size, dst = sys.argv[1:5]
    progs = sys.argv[5:]
    refs = {"$BEGIN": "$BEGIN", "@ABS": {0o24: "$VER"}}
    hint = tail = None
    if os.environ.get("LIKE"):
        hint = txt_layout(lib, name)
        tail = tail_records(lib, name)
    data, kinds = build(lib, name, int(size, 8), progs, refs, hint, tail or b"")
    open(dst, "wb").write(data)
    from collections import Counter
    c = Counter((k[0], k[1]) for k in kinds.values() if k)
    print(f"{dst}: {len(data)} б;  релоцируемых слов {len(kinds)}")
    for (nm, how), n in c.most_common():
        print(f"   {nm:<8} {how:<5} {n}")


if __name__ == "__main__":
    main()
