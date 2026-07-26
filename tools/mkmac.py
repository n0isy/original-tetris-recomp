#!/usr/bin/env python3
"""
Сделать исходник на макроассемблере из модуля, вырезанного из готовой программы.

Писать `.OBJ` руками оказалось тупиком: формат приходится угадывать, а на
границе секций «конец RTSDAT» и «начало DBGLNK» -- один адрес, и по байтам их
не различить. В исходнике этой неоднозначности нет: там стоит либо `$STACK`,
либо `DBGLNK`, и выбор делает автор текста. Поэтому правильный путь -- отдать
текст настоящему `MACRO`, он и закодирует всё сам.

Операнды не угадываются: чем является каждое слово, измерено заранее
(`remod.survey`) по нескольким программам, куда модуль слинкован по разным
адресам. Здесь измеренное лишь переводится в имена.

  mkmac.py <библиотека.obj> <модуль> <размер8> <выход.mac> <прог> [<прог> ...]
"""
import os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from remod import survey, gsd_of, named_secs, globals_of, w    # noqa: E402
from lda import lda                                            # noqa: E402

PDP11 = os.environ.get("PDP11") or os.path.join(HERE, "pdp11")
LINE = re.compile(r"^([0-7]+):\t(.*)$")


def disasm(img, base):
    with tempfile.NamedTemporaryFile(suffix=".lda", delete=False) as f:
        f.write(lda(img, base)); tape = f.name
    cmd = (f"set cpu 11/73\nset cpu 256k\nload {tape}\n"
           f"examine -m {base:o}-{base + len(img) - 2:o}\nquit\n")
    out = subprocess.run([PDP11], input=cmd, capture_output=True, text=True).stdout
    os.unlink(tape)
    res = []
    for ln in out.splitlines():
        m = LINE.match(ln.replace("sim> ", ""))
        if m:
            res.append((int(m.group(1), 8) - base, m.group(2).strip()))
    return res


def main():
    lib, name, size, dst = sys.argv[1:5]
    progs = sys.argv[5:]
    size = int(size, 8)
    gsd = gsd_of(lib, name)
    secs = named_secs(gsd)
    kinds, P0 = survey(progs, lib, name, size, secs)
    img = P0["d"][P0["base"]:P0["base"] + size]
    ins = disasm(img, P0["base"])
    ends = {a for a, _ in ins}

    # адреса, на которые ссылаются -- им нужны метки
    labels = {}
    for a, t in ins:
        for m in re.finditer(r"\b[0-7]{4,6}\b", t):
            v = int(m.group(0), 8) - P0["base"]
            if 0 <= v < size:
                labels.setdefault(v, f"{name.strip('$')}{v:o}")

    # имя для каждого релоцируемого слова
    gl = globals_of(lib)
    sym = {}
    off = 0
    secbase = {}
    for sn, ln in secs:
        secbase[sn] = off; off += ln
    for o, k in sorted(kinds.items()):
        if k is None:
            continue
        nm, how, val = k
        if nm == ".":
            sym[o] = labels.get(val) or f"{name.strip('$')}{val:o}"
            labels.setdefault(val, sym[o])
        elif nm == "@DATA":
            for sn, ln in secs:
                if val - secbase[sn] < ln:
                    sym[o] = f"{sn}+{val - secbase[sn]:o}" if val - secbase[sn] else sn
                    break
        elif nm == "ABS":
            sym[o] = f"{val:o}"
        elif nm == "LIMIT":
            sym[o - 2] = ".LIMIT"
        elif nm == "$BEGIN":
            sym[o] = "$BEGIN"
        else:
            sym[o] = gl.get((nm, val), nm)

    out = [f"\t.TITLE\t{name}", "\t.IDENT\t/V1.2G/", "\t.RADIX\t8",
           "\t.GLOBL\t$ERROR,$DISPO"]
    for sn, ln in secs:
        out.append(f"\t.PSECT\t{sn},RW,D,GBL,REL,OVR")
        out.append(f"{sn}:\t.BLKB\t{ln:o}")
    out.append("\t.PSECT")
    gsym = {}
    cur_sec = None
    for nm2, fl, ty, val in gsd:
        if ty == 5:
            cur_sec = nm2
        elif ty == 4 and (fl & 0o10) and cur_sec == "":
            gsym.setdefault(val, []).append(nm2)
    for v, ns in gsym.items():
        labels[v] = ns[0]
    for nm2, fl, ty, val in gsd:
        if ty == 4 and (fl & 0o10):
            out.append(f";\t{nm2} = +{val:o}")
    # За вызовом JSR R0,$ERROR идут не команды, а встроенное описание ошибки:
    # байт класса, байт номера, слово длины и сам текст. Дизассемблер честно
    # показывает их как команды -- значит выделять их надо здесь.
    desc = {}
    for a in range(0, size - 8, 2):
        # Искать по образу, а не по разбору: после нечётной строки текста
        # дизассемблер сбивается, и следующий вызов в его выдачу не попадает.
        if (img[a] | (img[a + 1] << 8)) == 0o004067 and sym.get(a + 2) == "$ERROR":
            d = a + 4
            ln = img[d + 2] | (img[d + 3] << 8)
            if 0 < ln < 40:
                desc[a] = (img[d], img[d + 1], ln,
                           img[d + 4:d + 4 + ln].decode("latin-1"))
                labels.setdefault(a, f"{name.strip('$')}{a:o}")
    i = 0
    while i < len(ins):
        a, t = ins[i]
        if a in desc:
            cls, num, ln, txt = desc[a]
            lb = labels.get(a, "")
            out.append(f"{lb + ':' if lb else '':<10}\tJSR\tR0,$ERROR")
            out.append(f"\t.BYTE\t{cls:o},{num:o}\t\t; class, error number")
            out.append(f"\t.WORD\t{ln:o}")
            out.append(f"\t.ASCII\t/{txt}/")
            out.append("\t.EVEN")
            end = a + 4 + ln + ((a + 4 + ln) & 1)
            while i < len(ins) and ins[i][0] < end:
                i += 1
            continue
        nxt = ins[i + 1][0] if i + 1 < len(ins) else size
        lbl = labels.get(a, "")
        for extra_nm in gsym.get(a, [])[1:]:
            out.append(f"{extra_nm}::")
        if a in gsym:
            lbl = gsym[a][0] + ":"
        if a in sym and sym[a] == ".LIMIT":
            out.append(f"{lbl + ':' if lbl else '':<10}\t.LIMIT")
            i += 1
            continue
        # Каждое дополнительное слово команды SIMH печатает ровно одним
        # числовым лексемом, слева направо. Значит k-й лексем отвечает k-му
        # слову -- так и подставляем, иначе символ уезжает не в тот операнд
        # (было `BIS #44,44` вместо `BIS #60000,44`).
        toks = list(re.finditer(r"(?<![A-Z])[0-7]+(?![0-9A-Z])", t))
        words = list(range(a + 2, nxt, 2))
        body = t
        for k in range(len(toks) - 1, -1, -1):
            if k >= len(words):
                continue
            o, m = words[k], toks[k]
            if o in sym and sym[o] != "$ERROR":
                body = body[:m.start()] + sym[o] + body[m.end():]
            else:
                v = int(m.group(0), 8) - P0["base"]
                if 0 <= v < size and m.start() and t[m.start() - 1] != "#":
                    labels.setdefault(v, f"{name.strip('$')}{v:o}")
                    body = body[:m.start()] + labels[v] + body[m.end():]
        # Цель условного перехода лежит в самом слове команды, а не в
        # дополнительном, поэтому подстановка операндов её не трогает.
        if t.startswith("JSR R0,") and sym.get(a + 2) == "$ERROR":
            body = "JSR\tR0,$ERROR"
        if body[:1] == "B" or body[:3] in ("SOB", "JMP", "JSR"):
            def _lab(m):
                v = int(m.group(0), 8) - P0["base"]
                return labels.get(v, m.group(0))
            body = re.sub(r"(?<![#(@])\b[0-7]{4,6}\b", _lab, body)
        out.append(f"{lbl + ':' if lbl else '':<10}\t{body}")
        i += 1
    out.append("\t.END")
    open(dst, "w").write("\n".join(out) + "\n")
    print(f"{dst}: {len(out)} строк, меток {len(labels)}, символьных операндов {len(sym)}")


if __name__ == "__main__":
    main()
