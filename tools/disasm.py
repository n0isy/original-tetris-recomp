#!/usr/bin/env python3
"""
Дизассемблировать образ памяти PDP-11 через SIMH и сложить листинг в файл.

Своего дизассемблера тут нет и не надо: в SIMH он уже есть, в синтаксисе DEC,
и он же исполняет этот код -- значит толкует команды ровно так, как машина.
Не хватало только способа положить произвольный образ в его память; это делает
`lda.py`, заворачивая байты в ленту абсолютного загрузчика.

SIMH печатает лишь `адрес: команда`. Здесь к этому добавляется то, без чего
листинг не читается: восьмеричные слова команды, текстовая расшифровка (КОИ-7,
с учётом переключателей регистра) и метки -- имена глобальных символов рантайма
и точки, на которые кто-то ссылается.

  disasm.py <образ> --from 1000 --to 32416 [--base 0] [-o листинг.asm]
  disasm.py <образ> --lib PASSIM.OBJ ...      подписать модули и символы
"""
import os, re, sys, argparse, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lda import lda                                            # noqa: E402
sys.path.insert(0, os.path.join(HERE, ".."))
from rt11 import KOI7                                          # noqa: E402

PDP11 = os.environ.get("PDP11") or os.path.join(HERE, "pdp11")
LINE = re.compile(r"^([0-7]+):\t(.*)$")


def run(image, base, lo, hi):
    """[(адрес, текст)] -- то, что выдал дизассемблер SIMH."""
    with tempfile.NamedTemporaryFile(suffix=".lda", delete=False) as f:
        f.write(lda(image, base))
        tape = f.name
    cmd = (f"set cpu 11/73\nset cpu 256k\nload {tape}\n"
           f"examine -m {lo:o}-{hi:o}\nquit\n")
    out = subprocess.run([PDP11], input=cmd, capture_output=True,
                         text=True, timeout=300).stdout
    os.unlink(tape)
    res = []
    for ln in out.splitlines():
        m = LINE.match(ln.replace("sim> ", ""))
        if m:
            res.append((int(m.group(1), 8), m.group(2).strip()))
    return res


def koi(data, cyr=False):
    """Текстовая колонка.

    В КОИ-7 Н2 кириллица занимает тот же диапазон, что и латиница, а регистр
    переключается кодами SO/SI. В памяти программы переключателей нет -- их
    выводят отдельно, поэтому русский текст лежит байтами 0o140..0o177 и без
    расшифровки читается как `sbrositx`. Ключ --cyr включает чтение этого
    диапазона как кириллицы.
    """
    out, ru = [], False
    for b in data:
        if b == 0x0E: ru = True;  out.append("<")
        elif b == 0x0F: ru = False; out.append(">")
        elif (ru or cyr) and 0x60 <= b <= 0x7F: out.append(KOI7[b - 0x60])
        elif ru and 0x40 <= b <= 0x5F: out.append(KOI7[b - 0x40])
        elif 0x20 <= b < 0x7F: out.append(chr(b))
        else: out.append(".")
    return "".join(out)


TARGET = re.compile(r"(?<![0-9(@#])([0-7]{4,6})(?![0-7])")
JUMPS = ("BR ", "BNE", "BEQ", "BGE", "BLT", "BGT", "BLE", "BPL", "BMI",
         "BHI", "BLO", "BCC", "BCS", "BVC", "BVS", "SOB", "JMP", "JSR")


def listing(image, base, lo, hi, syms=None, heads=None, cyr=False):
    syms, heads = dict(syms or {}), dict(heads or {})
    ins = run(image, base, lo, hi)
    # адреса, на которые кто-то ссылается -- им нужны метки
    refs = set()
    for a, t in ins:
        if t[:3] in JUMPS:
            for m in TARGET.finditer(t):
                v = int(m.group(1), 8)
                if lo <= v <= hi:
                    refs.add(v)
    n = 0
    for v in sorted(refs):
        if v not in syms:
            syms[v] = f"L{n}"; n += 1
    out = []
    for i, (a, t) in enumerate(ins):
        end = ins[i + 1][0] if i + 1 < len(ins) else a + 2
        raw = image[a - base:end - base]
        words = " ".join(f"{raw[k] | (raw[k+1] << 8):06o}" for k in range(0, len(raw) - 1, 2))
        lbl = syms.get(a, "")
        if a in heads:
            out.append("")
            out.append(f";{'=' * 76}")
            out.append(f"; {heads[a]}")
            out.append(f";{'=' * 76}")
        elif lbl and not lbl.startswith("L"):
            out.append("")
        # подставить имена в операнды
        def sub(m):
            v = int(m.group(1), 8)
            return syms.get(v, m.group(1)) if v in syms else m.group(1)
        txt = TARGET.sub(sub, t) if t[:3] in JUMPS else t
        out.append(f"{a:06o}  {words:<21} {lbl:<8} {txt:<28} ; {koi(raw, cyr)}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--base", default="0")
    ap.add_argument("--from", dest="lo", default="1000")
    ap.add_argument("--to", dest="hi", required=True)
    ap.add_argument("--lib", default=None)
    ap.add_argument("--mark", action="append", default=[],
                    help="адрес:имя -- своя метка, можно повторять")
    ap.add_argument("--cyr", action="store_true",
                    help="читать 0o140..0o177 как кириллицу КОИ-7")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    img = open(a.image, "rb").read()
    base = int(a.base, 8)
    syms, heads = {}, {}
    if a.lib:
        from laylink import layout, symbols
        sav, found = layout(a.lib, a.image)
        syms = symbols(found, sav)
        for b, m, r in found:
            # Долю совпадения тут не печатать: округление до процентов
            # превращает три разошедшихся слова в «совпало 100%». Считать
            # надо байты, и байты не совпавшие.
            skip = {o + k for o in m["rld"] for k in (0, 1)}
            n = sum(1 for i, c in enumerate(m["image"])
                    if i not in skip and b + i < len(sav) and sav[b + i] != c)
            heads[b] = (f"МОДУЛЬ РАНТАЙМА {m['name']}   ({m['size']:o} б в библиотеке; "
                        f"кроме перемещаемых, разошлось байт: {n})")
    for s in a.mark:
        k, _, v = s.partition(":")
        syms[int(k, 8)] = v
    txt = listing(img, base, int(a.lo, 8), int(a.hi, 8), syms, heads, a.cyr)
    if a.out:
        open(a.out, "w").write(txt + "\n")
        print(f"{a.out}: {txt.count(chr(10)) + 1} строк")
    else:
        print(txt)


if __name__ == "__main__":
    main()
