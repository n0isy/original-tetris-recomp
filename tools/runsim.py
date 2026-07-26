#!/usr/bin/env python3
"""
Загрузить образ RX01 в SIMH, запустить программу, снять экран.

    runsim.py <образ.rx01> [--run ИМЯ] [--keys СТРОКА] [--raw] [--wait СЕК]

    --run ИМЯ     выполнить `R ИМЯ` после появления приглашения ФОДОС
    --keys ...    отправить символы по одному (для тетриса: 7/9 влево-вправо,
                  8 поворот, 4 ускорить, 5 сбросить, 1 показать следующую)
    --raw         показать сырой поток байт вместо отрисованного экрана
    --wait N      сколько секунд собирать вывод после запуска (по умолчанию 3)

Путь к эмулятору берётся из переменной PDP11, иначе ./pdp11 рядом со скриптом.

ВАЖНО: в .ini обязателен `set tto 8b`. По умолчанию консоль SIMH выбрасывает
непечатные байты, а с ними -- переключатели регистра SO/SI и код 0x7F, которым
часть версий тетриса рисует фигуры. С фильтром игра рисует пустой стакан и
выглядит сломанной.
"""
import os, sys, time, argparse, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vt52 import Screen                                        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PDP11 = os.environ.get("PDP11") or os.path.join(HERE, "pdp11")

INI = """set cpu 11/23
set cpu 256k
set tto 8b
attach rx0 {img}
boot rx0
"""


def run(img, prog=None, keys="", wait=3.0, raw=False):
    import pexpect
    ini = tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False)
    ini.write(INI.format(img=os.path.abspath(img)))
    ini.close()
    c = pexpect.spawn(f"{PDP11} {ini.name}", timeout=30, encoding="latin-1",
                      dimensions=(24, 80))
    sc, chunks = Screen(), []

    def drain(t):
        end = time.time() + t
        while time.time() < end:
            try:
                d = c.read_nonblocking(4096, 0.2)
            except Exception:
                continue
            chunks.append(d)
            sc.feed(d.encode("latin-1"))

    c.expect(r"w02\.00")                  # баннер "ФОДОС Ф В02.00" в КОИ-7
    drain(1.5)
    if prog:
        c.send(f"R {prog}\r"); drain(wait)
        c.send("0\r");         drain(1.5)      # уровень 0 -- медленный
    for k in keys:
        c.send(k); drain(0.35)
    drain(0.8)
    c.terminate(force=True)
    os.unlink(ini.name)
    return "".join(chunks).encode("latin-1") if raw else sc.render()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("image")
    p.add_argument("--run"); p.add_argument("--keys", default="")
    p.add_argument("--raw", action="store_true"); p.add_argument("--wait", type=float, default=3.0)
    a = p.parse_args()
    if not os.access(PDP11, os.X_OK):
        sys.exit(f"эмулятор не найден: {PDP11} (задайте PDP11=/путь/к/pdp11)")
    out = run(a.image, a.run, a.keys, a.wait, a.raw)
    print(repr(out) if a.raw else out)
