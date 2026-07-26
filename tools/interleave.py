#!/usr/bin/env python3
"""
Логический образ RT-11 <-> физический образ RX01 (8" дискета).

Образы с форума лежат в логическом порядке блоков: home block ровно по смещению
512, каталог с блока 6. SIMH же читает RX01 как есть, физическими секторами,
поэтому перед загрузкой образ надо переразложить:

  * чередование 2:1 внутри дорожки (сектор n -> 2n, нечётная половина со сдвигом);
  * перекос 6 секторов на каждую следующую дорожку;
  * дорожка 0 зарезервирована, данные начинаются с дорожки 1.

Отсюда и разница в размере: 76 дорожек (252 928 б) против 77 (256 256 б).

  interleave.py to-phys    logical.dsk  out.rx01
  interleave.py to-logical in.rx01      out.dsk
"""
import sys

SECTORS, TRACKS, SECSIZE = 26, 77, 128


def _map(n):
    """Логический сектор n -> смещение физического сектора в байтах."""
    trk, sec = divmod(n, SECTORS)
    ps = (2 * sec) % SECTORS + (1 if sec >= SECTORS // 2 else 0)   # чередование 2:1
    ps = (ps + 6 * trk) % SECTORS                                  # перекос дорожки
    return ((trk + 1) * SECTORS + ps) * SECSIZE                    # дорожка 0 пропущена


def to_physical(src):
    out = bytearray(TRACKS * SECTORS * SECSIZE)
    for n in range(len(src) // SECSIZE):
        out[_map(n):_map(n) + SECSIZE] = src[n * SECSIZE:(n + 1) * SECSIZE]
    return bytes(out)


def to_logical(src):
    n_sec = (TRACKS - 1) * SECTORS
    out = bytearray(n_sec * SECSIZE)
    for n in range(n_sec):
        out[n * SECSIZE:(n + 1) * SECSIZE] = src[_map(n):_map(n) + SECSIZE]
    return bytes(out)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("to-phys", "to-logical"):
        print(__doc__)
        sys.exit(1)
    fn = to_physical if sys.argv[1] == "to-phys" else to_logical
    data = fn(open(sys.argv[2], "rb").read())
    open(sys.argv[3], "wb").write(data)
    print(f"{sys.argv[2]} -> {sys.argv[3]}  ({len(data)} байт)")
