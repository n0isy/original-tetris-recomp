#!/usr/bin/env python3
"""
Определить версию Паскаля: и по собранным программам, и по самим компиляторам.

Рантайм OMSI сверяет номер версии компилятора первыми же командами программы --
компилятор вписывает его как абсолютный символ `$VER`, а рантайм сравнивает со
своей константой и при несовпадении печатает `BAD COMPILER VERSION`.
В слинкованном `.SAV` это выглядит так:

    022727  CMP  #14, #14      ; $VER программы против константы рантайма
    000014
    000014
    001410  BEQ                ; совпало -- ошибку пропустить

Отсюда версию можно просто прочитать. В этом архиве: `$VER = 59` у всего, что
собрано здешним компилятором (OMSI PASCAL-1 RT11 V1.1G), и `$VER = 12` у тетриса
и остальных программ линии ПАСКАЛЬ/РАФОС, компилятора которой здесь нет.

Компилятор ищется по своей сигнатуре -- таблице зарезервированных слов, а НЕ по
сообщениям рантайма: последние выдают лишь то, что Паскалем *собрано*.

  pasver.py ver <файл.sav> [...]   прочитать $VER
  pasver.py scan                   $VER у всех программ архива
  pasver.py compilers              найти компиляторы по таблице ключевых слов
"""
import os, struct, sys, hashlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rt11 import RT11                                            # noqa: E402

CMP_IMM = 0o022727            # CMP (PC)+,(PC)+ -- сравнение двух непосредственных
KEYWORDS = [b"DOWNTO", b"FORWARD", b"PACKED", b"REPEAT", b"UNTIL", b"PROCEDURE",
            b"FUNCTION", b"RECORD", b"LABEL", b"CONST", b"PROGRAM", b"EXTERNAL",
            b"MAXINT", b"DISPOSE"]


def ver(data):
    """Прочитать $VER из образа программы, иначе None."""
    if len(data) < 0o60: return None
    entry = struct.unpack_from("<H", data, 0o40)[0]
    if entry + 6 < len(data) and struct.unpack_from("<H", data, entry)[0] == CMP_IMM:
        a, b = struct.unpack_from("<HH", data, entry + 2)
        if a == b: return a
    for off in range(0, len(data) - 6, 2):      # сверка бывает и не в первом слове
        if struct.unpack_from("<H", data, off)[0] == CMP_IMM:
            a, b = struct.unpack_from("<HH", data, off + 2)
            if a == b and 0 < a < 4096: return a
    return None


def kw_score(data):
    return sum(k in data for k in KEYWORDS)


def each_file(base):
    """(откуда, имя, байты) для всего в образах дискет и в extracted/."""
    imgs = os.path.join(base, "images.txt")
    if os.path.exists(imgs):
        for line in open(imgs):
            p = line.strip()
            if not p: continue
            p = p if os.path.isabs(p) else os.path.join(base, p)
            try: v = RT11(p)
            except Exception: continue
            for name, ln, blk, _ in v.files():
                try: yield f"{p}::{name}", name, v.blk(blk, ln)
                except Exception: continue
    for dp, _, fs in os.walk(os.path.join(base, "extracted")):
        for fn in fs:
            q = os.path.join(dp, fn)
            try:
                if os.path.getsize(q) > 20_000_000: continue
                yield q, fn, open(q, "rb").read()
            except Exception: continue


def main():
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "ver":
        for p in sys.argv[2:]:
            print(f"  {ver(open(p,'rb').read())!s:>6}  {p}")
    elif cmd == "scan":
        seen = {}
        for where, name, data in each_file(base):
            if not name.upper().endswith(".SAV"): continue
            v = ver(data)
            if v: seen.setdefault(v, []).append(where)
        for v in sorted(seen):
            print(f"\n$VER = {v}  ({len(seen[v])} файлов)")
            for w in sorted(seen[v])[:40]: print("   ", w)
    elif cmd == "compilers":
        hits = {}
        for where, name, data in each_file(base):
            if not name.upper().endswith((".SAV", ".OBJ", ".LDA")): continue
            s = kw_score(data)
            if s >= 9:
                hits.setdefault(hashlib.md5(data).hexdigest()[:8],
                                [s, len(data), name, []])[3].append(where)
        print(f"компиляторов (>= 9 из {len(KEYWORDS)} ключевых слов): {len(hits)}\n")
        for m, (s, ln, name, ws) in sorted(hits.items(), key=lambda x: -x[1][0]):
            print(f"  {s}/{len(KEYWORDS)}  md5 {m}  {ln:>7}б  {name:<12} копий: {len(ws)}")
            for w in ws[:3]: print(f"        {w}")


if __name__ == "__main__":
    main()
