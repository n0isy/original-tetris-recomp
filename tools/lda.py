#!/usr/bin/env python3
"""
Завернуть кусок памяти в ленту абсолютного загрузчика (.LDA), чтобы скормить SIMH.

Свой дизассемблер писать незачем: в SIMH он уже есть и он авторитетный --
`examine -m` печатает команды в синтаксисе DEC. Не хватает только способа
положить произвольный образ в память эмулятора. `LOAD` умеет читать формат
бумажной ленты, его и делаем.

Блок: 001 000 <длина 2б> <адрес 2б> <данные> <кс 1б>, где длина считает шесть
своих байт, а контрольная сумма дополняет сумму блока до нуля по модулю 256.
Последний блок -- без данных, его адрес становится точкой запуска.

  lda.py <вход.bin> <выход.lda> [адрес_загрузки] [--skip N] [--len N]
"""
import sys, argparse


def block(addr, data):
    n = len(data) + 6
    b = bytearray([1, 0, n & 0xFF, n >> 8, addr & 0xFF, addr >> 8])
    b += data
    b.append((-sum(b)) & 0xFF)
    return bytes(b)


def lda(data, addr=0, start=1, chunk=64):
    out = bytearray()
    for o in range(0, len(data), chunk):
        out += block(addr + o, data[o:o + chunk])
    out += block(start, b"")            # нечётный адрес -- загрузчик не стартует
    return bytes(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("addr", nargs="?", default="0")
    ap.add_argument("--skip", default="0"); ap.add_argument("--len", default=None)
    a = ap.parse_args()
    d = open(a.src, "rb").read()
    s = int(a.skip, 8); d = d[s:s + int(a.len, 8)] if a.len else d[s:]
    open(a.dst, "wb").write(lda(d, int(a.addr, 8)))
    print(f"{len(d)} б -> {a.dst}, загрузка по {int(a.addr,8):06o}")
