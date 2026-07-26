#!/usr/bin/env python3
"""
Мини-эмулятор терминала VT52 с декодированием КОИ-7 (ГОСТ 19768-74).

Тетрис и прочие программы ДВК адресуют курсор через `ESC Y строка столбец`
(координаты со смещением 32) и переключают регистр знакогенератора
управляющими SO (0x0E, РУС) и SI (0x0F, ЛАТ). В режиме РУС кириллица лежит
и в 0x40-0x5F, и в 0x60-0x7F.

Класс Screen копит байты и отдаёт готовый текстовый снимок экрана:

    sc = Screen()
    sc.feed(b"...")
    print(sc.render())
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rt11 import KOI7                                  # noqa: E402


def koi7ch(b, cyr):
    if cyr and 0x40 <= b <= 0x5F: return KOI7[b - 0x40]
    if cyr and 0x60 <= b <= 0x7F: return KOI7[b - 0x60]
    if b == 0x7F: return "█"      # заливка знакоместа на терминале Электроники
    return chr(b) if 0x20 <= b < 0x7F else " "


class Screen:
    def __init__(self, rows=24, cols=80):
        self.r, self.c = rows, cols
        self.buf = [[" "] * cols for _ in range(rows)]
        self.y = self.x = 0
        self.pend = b""                # незавершённая ESC-последовательность
        self.cyr = False               # регистр знакогенератора

    def feed(self, data):
        data, self.pend, i = self.pend + data, b"", 0
        while i < len(data):
            b = data[i]
            if b == 0x1B:
                # последовательность не влезла в эту порцию -- отложить целиком
                if i + 1 >= len(data) or (data[i + 1] == ord("Y") and i + 3 >= len(data)):
                    self.pend = data[i:]
                    return
                cmd = data[i + 1]
                i += 2
                if cmd == ord("H"):
                    self.y = self.x = 0
                elif cmd == ord("J"):                  # стереть до конца экрана
                    for xx in range(self.x, self.c): self.buf[self.y][xx] = " "
                    for yy in range(self.y + 1, self.r): self.buf[yy] = [" "] * self.c
                elif cmd == ord("K"):                  # стереть до конца строки
                    for xx in range(self.x, self.c): self.buf[self.y][xx] = " "
                elif cmd == ord("Y"):                  # прямая адресация курсора
                    self.y = max(0, min(self.r - 1, data[i] - 32))
                    self.x = max(0, min(self.c - 1, data[i + 1] - 32))
                    i += 2
                elif cmd == ord("A"): self.y = max(0, self.y - 1)
                elif cmd == ord("B"): self.y = min(self.r - 1, self.y + 1)
                elif cmd == ord("C"): self.x = min(self.c - 1, self.x + 1)
                elif cmd == ord("D"): self.x = max(0, self.x - 1)
                continue
            i += 1
            if b == 0x0E: self.cyr = True              # SO -- регистр РУС
            elif b == 0x0F: self.cyr = False           # SI -- регистр ЛАТ
            elif b == 0x0D: self.x = 0
            elif b == 0x0A:
                self.y += 1
                if self.y >= self.r:
                    self.buf.pop(0); self.buf.append([" "] * self.c); self.y = self.r - 1
            elif b == 0x08: self.x = max(0, self.x - 1)
            elif b >= 0x20:
                self.buf[self.y][self.x] = koi7ch(b, self.cyr)
                if self.x < self.c - 1: self.x += 1

    def render(self):
        lines = ["".join(r).rstrip() for r in self.buf]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)
