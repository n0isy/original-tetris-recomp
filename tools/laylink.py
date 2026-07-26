#!/usr/bin/env python3
"""
Разложить слинкованную программу обратно на модули и построить таблицу символов.

Компоновщик RT-11 кладёт модули встык и нигде в `.SAV` не отмечает границы.
Но код каждого библиотечного модуля известен, и его можно найти в программе
прямым сопоставлением. Мешают только слова, которые компоновщик подменил
адресами -- их адреса перечислены в RLD, и при сравнении они пропускаются.

Найдя базу модуля, получаем и адреса всех его глобальных символов: значение
символа в GSD -- смещение от начала секции. Отсюда таблица имён для
дизассемблера, включая точки входа рантайма `$Bnn`.

Всё, что осталось непокрытым и лежит ниже первого библиотечного модуля, --
это и есть код самой программы.

  laylink.py <библиотека.obj> <программа.sav>            карта и границы
  laylink.py <библиотека.obj> <программа.sav> --syms     таблица символов
"""
import os, sys, difflib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from objlib import modules                                     # noqa: E402

W = 8                 # окно для голосования за сдвиг
MIN_VOTES = 12        # меньше -- уже совпадения по случайности


def _mask(m):
    """True там, где байт компоновщик не трогает."""
    ok = bytearray(b"\1" * m["size"])
    for a in m["rld"]:
        ok[a:a + 2] = b"\0\0"
    return bytes(ok)


def _index(sav):
    idx = {}
    for i in range(len(sav) - W):
        idx.setdefault(sav[i:i + W], []).append(i)
    return idx


def locate(m, sav, idx):
    """(база, доля совпавших байт) или None.

    Мерить «сколько байт совпало по одинаковым смещениям» здесь нельзя, и я на
    этом обжёгся: часть модулей библиотеки прогнана через оптимизатор переходов
    PASIMP, где `JMP` стал `BR` (-2 байта), а пара `Bxx`+`JMP` -- одиночным
    `Bxx` с обратным условием (-4 байта). После первой же такой замены всё
    уезжает, и модуль с тем же исходником выглядит чужим: у `$IO` совпадение
    падает до 31%, у `ERROR` до 14%, хотя это буквально та же программа.

    Привязка поэтому не по доле, а по точному совпадению **начала** модуля:
    берётся первый участок в 8 байт, которого не касается компоновщик, и ищется
    в программе. До первой оптимизации код ещё сходится байт в байт, а начало
    модуля -- это всегда «до». Доля совпадения затем только сообщается.
    """
    img, ok, n = m["image"], _mask(m), m["size"]
    if n < 24:
        return None
    o0 = next((o for o in range(n - W)
               if b"\0" not in ok[o:o + W] and len(set(img[o:o + W])) >= 4), None)
    if o0 is None:
        return None
    cands = [p - o0 for p in idx.get(img[o0:o0 + W], ()) if p >= o0]
    if len(cands) > 1:                            # начало неуникально --
        o1 = next((o for o in range(o0 + W, min(n, o0 + 128) - W)   # взять второй
                   if b"\0" not in ok[o:o + W] and len(set(img[o:o + W])) >= 4), None)
        if o1 is not None:
            cands = [b for b in cands if sav[b + o1:b + o1 + W] == img[o1:o1 + W]]
    if len(cands) != 1:
        return None
    base = cands[0]
    if base + n > len(sav) + 64:
        return None
    good = tot = 0
    for o in range(min(n, len(sav) - base)):
        if ok[o]:
            tot += 1
            good += (sav[base + o] == img[o])
    return base, (good / tot if tot else 0.0)


def align(m, sav, base, end):
    """Соответствие «смещение в модуле -> адрес в программе».

    У неоптимизированных модулей это просто сложение, у оптимизированных --
    кусочная карта по общим блокам. Возвращает (функция, доля покрытия).
    """
    a, b = m["image"], sav[base:end]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    blocks = [x for x in sm.get_matching_blocks() if x.size >= 4]
    cov = sum(x.size for x in blocks)

    def where(off):
        for x in blocks:
            if x.a <= off < x.a + x.size:
                return base + x.b + (off - x.a)
        return None
    return where, (cov / len(a) if a else 0.0)


def layout(lib_path, sav_path):
    mods = modules(open(lib_path, "rb").read())
    sav = open(sav_path, "rb").read()
    idx = _index(sav)
    hits = []
    for m in mods:
        r = locate(m, sav, idx)
        if r:
            hits.append((r[0], m, r[1]))
    # $INIT искать сопоставлением не нужно: он привязан жёстко. Точка входа
    # программы (слово по смещению 0o40 в .SAV) -- это его символ $START,
    # а $START лежит по смещению 0o20 от начала модуля.
    if not any(m["name"] == "$INIT" for _, m, _ in hits):
        init = next((m for m in mods if m["name"] == "$INIT"), None)
        start = init and init["defs"].get("$START")
        if init and start and len(sav) > 0o42:
            entry = sav[0o40] | (sav[0o41] << 8)
            base = entry - start[1]
            if 0 < base < len(sav):
                hits.append((base, init, 0.0))
    hits.sort(key=lambda h: h[0])
    # выкинуть наложения: побеждает тот, у кого выше доля совпадения
    found, prev = [], None
    for base, m, ratio in hits:
        if prev and base < prev[0] + prev[1]["size"] * 3 // 4:
            if ratio <= prev[2]:
                continue
            found.pop()
        found.append((base, m, ratio))
        prev = (base, m, ratio)
    return sav, [(b, m, r) for b, m, r in found]


def symbols(found, sav=None):
    """{адрес: имя} -- глобальные символы найденных модулей.

    Для модулей, совпавших не полностью, адреса символов берутся не сложением,
    а по карте выравнивания: после замены `JMP` на `BR` смещения внутри модуля
    уже не те.
    """
    syms = {}
    for i, (base, m, ratio) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else base + m["size"]
        where = None
        if ratio < 0.99 and sav is not None:
            where, _ = align(m, sav, base, end)
        for nm, (psect, val) in m["defs"].items():
            if psect != "":                      # символ вне секции кода
                continue
            a = where(val) if where else base + val
            if a is not None:
                syms.setdefault(a, nm)
    return syms


def main():
    if len(sys.argv) < 3:
        print(__doc__); return
    sav, found = layout(sys.argv[1], sys.argv[2])
    if "--syms" in sys.argv:
        for a, nm in sorted(symbols(found, sav).items()):
            print(f"{a:06o}  {nm}")
        return
    first = found[0][0] if found else len(sav)
    top = sav[0o50] | (sav[0o51] << 8)            # верхняя граница из заголовка
    print(f"{sys.argv[2]}: {len(sav)} б, модулей рантайма найдено {len(found)}\n")
    print(f"  {'адрес':>13}   {'длина':>7}  модуль")
    print(f"  {0o1000:06o}..{first - 1:06o}   {first - 0o1000:7o}  <<< КОД ПРОГРАММЫ >>>")
    end = first
    # именованные секции компоновщик собирает вместе и кладёт в конец
    named = {}
    for _, m, _ in found:
        for p, v in m["psects"].items():
            if p not in ("", ". ABS."):
                named[p] = max(named.get(p, 0), v)
    data = top - sum(named.values())
    for i, (base, m, ratio) in enumerate(found):
        # длина в программе -- до следующего модуля, а не из библиотеки:
        # после оптимизатора переходов модуль короче своего библиотечного вида
        nxt = found[i + 1][0] if i + 1 < len(found) else data
        if ratio == 0.0:
            note = "  <- привязан по точке входа, не по совпадению"
        elif ratio > 0.9:
            note = ""
        else:
            # доля тут ничего не доказывает: причиной может быть и оптимизатор
            # переходов, и другая сборка модуля. Разбирается только чтением.
            note = f"  <- код расходится ({ratio:.0%} байт как в библиотеке)"
        print(f"  {base:06o}..{nxt - 1:06o}   {nxt - base:7o}  {m['name']:<8}"
              f"(в библиотеке {m['size']:o}){note}")
        end = nxt
    if end < top:
        print(f"  {end:06o}..{top - 1:06o}   {top - end:7o}  "
              + " + ".join(f"{p} {v:o}" for p, v in named.items()) + "  -- данные рантайма")
    print(f"  {top:06o}..{len(sav) - 1:06o}   {len(sav) - top:7o}  хвост блока (вне программы)")


if __name__ == "__main__":
    main()
