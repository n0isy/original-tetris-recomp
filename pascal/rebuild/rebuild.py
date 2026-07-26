#!/usr/bin/env python3
"""
Пересобрать рантайм тетриса из исходников и сверить с оригиналом.

Проверка устроена так, чтобы сравнивать было с чем: вместо игрового модуля
берётся заглушка **ровно того же размера** (`GAME.MAC`, 001000..017251).
Тогда все модули рантайма ложатся по тем же адресам, что в `TETRIS.SAV`, и
их можно сличать байт в байт, а не «по смыслу».

Порядок модулей задаётся списком ORDER: компоновщик берёт из обычного
объектного файла всё подряд, в порядке файлов, и порядок влияет на адреса.

  rebuild.py [-v]
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
from objmix import spans                                       # noqa: E402
from macasm import assemble                                    # noqa: E402
from maclink import link                                       # noqa: E402

ORDER = ["$INIT", "READS", "$READC", "$WRITI", "$WRITC", "$ARITH", "$CNVRT",
         "$REG", "$ALLOC", "$ERROR", "$IO", "$FPSIM", "$FSIM", "ERROR"]
LIB = os.path.join(ROOT, "pascal", "gold", "PASMIX.OBJ")
ORIG = os.path.join(ROOT, "tetris", "dis", "TETRISB.SAV")
LO, HI = 0o1000, 0o32416            # вся программа в оригинале
WORK = os.path.join(HERE, "work")


def main():
    os.makedirs(WORK, exist_ok=True)
    built = {}
    for src in ("GAME", "INIT", "IO", "ARITH", "ERR", "FPSIM"):
        res, errs, log = assemble(os.path.join(HERE, src + ".MAC"), src, WORK)
        if errs:
            print(f"{src}.MAC: ошибок {errs}"); print(log[-1200:]); return 1
        built[src] = os.path.join(WORK, src + ".OBJ")
        print(f"  {src}.MAC -> {src}.OBJ, ошибок 0")

    lib = open(LIB, "rb").read()
    sp = spans(lib)
    own = {"$INIT": built["INIT"], "$IO": built["IO"],
           "$ARITH": built["ARITH"], "$ERROR": built["ERR"],
           "$FPSIM": built["FPSIM"]}
    out = bytearray()
    for nm in ORDER:
        if nm in own:
            d = open(own[nm], "rb").read()
            a, b = spans(d)[nm]
        else:
            d, (a, b) = lib, sp[nm]
        out += d[a:b]
    rt = os.path.join(WORK, "RT.OBJ")
    open(rt, "wb").write(out)
    print(f"  RT.OBJ: {len(out)} б, модулей {len(ORDER)} в порядке оригинала")

    sav, log = link([built["GAME"], rt], "TET")
    if sav is None:
        print("компоновка не удалась:", log[-300:]); return 1
    dst = os.path.join(WORK, "TETNEW.SAV")
    open(dst, "wb").write(sav)
    print(f"  {dst}: {len(sav)} б")

    orig = open(ORIG, "rb").read()
    w = lambda b, a: b[a] | (b[a + 1] << 8)                     # noqa: E731
    for a, nm in ((0o40, "точка входа"), (0o42, "стек"), (0o50, "верх")):
        m = "" if w(sav, a) == w(orig, a) else "   <>"
        print(f"  {nm:<12} наш {w(sav,a):06o}  оригинал {w(orig,a):06o}{m}")
    diff = sorted({o - (o & 1) for o in range(LO, HI) if sav[o] != orig[o]})
    print(f"\nпрограмма {LO:06o}..{HI-1:06o}: "
          f"различий {len(diff)} слов из {(HI-LO)//2}")
    for a in diff:
        print(f"   {a:06o}  наш {w(sav,a):06o}   оригинал {w(orig,a):06o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
