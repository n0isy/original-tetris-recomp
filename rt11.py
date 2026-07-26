#!/usr/bin/env python3
"""
rt11.py -- reader for RT-11 / ФОДОС floppy images (.DSK) from Электроника-60 / ДВК.

  ./rt11.py ls   <image.dsk> [...]        list directory
  ./rt11.py cat  <image.dsk> FILE.TXT     print a text file (KOI-7 -> UTF-8)
  ./rt11.py x    <image.dsk> <outdir>     extract every file

Запись доступна как API, не через CLI: RT11.rm(name), RT11.put(name, data),
RT11.save(path) -- ими пользуется tools/mkboot.py. Правится только первый
сегмент каталога, для этих дискет этого достаточно.

Text files on these disks are КОИ-7 Н2 (ГОСТ 19768-74): Cyrillic lives in the
same byte range as Latin and is toggled with SO (0x0E) / SI (0x0F).
"""
import os, sys, struct

R50 = " ABCDEFGHIJKLMNOPQRSTUVWXYZ$.?0123456789"
# КОИ-7 Н2: bytes 0x40..0x5F (and lowercase 0x60..0x7F) in "Cyrillic mode"
KOI7 = "ЮАБЦДЕФГХИЙКЛМНОПЯРСТУЖВЬЫЗШЭЩЧЪ"

def r50(w):
    return R50[(w // 1600) % 40] + R50[(w // 40) % 40] + R50[w % 40]

def koi7(data):
    """Decode КОИ-7 Н2 with SO/SI shifting into Unicode."""
    out, cyr = [], False
    for b in data:
        if b == 0x0E: cyr = True; continue
        if b == 0x0F: cyr = False; continue
        if cyr and 0x40 <= b <= 0x5F: out.append(KOI7[b - 0x40])
        elif cyr and 0x60 <= b <= 0x7F: out.append(KOI7[b - 0x60])
        elif b in (0x0D, 0x00, 0x1A): continue
        elif b == 0x0A: out.append("\n")
        elif 0x20 <= b < 0x7F: out.append(chr(b))
        else: out.append(".")
    return "".join(out)

class RT11:
    def __init__(self, path):
        self.path, self.img = path, open(path, "rb").read()
        self.blocks = len(self.img) // 512

    def blk(self, n, count=1):
        return self.img[n * 512:(n + count) * 512]

    def home(self):
        h = self.blk(1)
        dec = lambda s: s.decode("ascii", "replace").rstrip()
        return dict(sysid=dec(h[496:508]), volid=dec(h[472:484]),
                    owner=dec(h[484:496]), dirstart=struct.unpack_from("<H", h, 468)[0])

    def files(self):
        """Yield (name, length_blocks, start_block, date) for every permanent file."""
        out, seg, seen = [], 1, set()
        while seg and seg not in seen and len(seen) < 32:
            seen.add(seg)
            s = self.blk(6 + (seg - 1) * 2, 2)
            if len(s) < 10: break
            nseg, nxt, _high, extra, start = struct.unpack_from("<5H", s, 0)
            if not 1 <= nseg <= 31: break
            off, b = 10, start
            while off + 14 <= len(s):
                st, n1, n2, ext, ln, _job, dt = struct.unpack_from("<7H", s, off)
                off += 14 + extra
                if st & 0o4000: break                       # end-of-segment
                if st & 0o2000:                             # permanent file
                    nm = (r50(n1) + r50(n2)).rstrip()
                    tp = r50(ext).rstrip()
                    y = 1972 + (dt & 31) + 32 * ((dt >> 14) & 3)
                    d, m = (dt >> 5) & 31, (dt >> 10) & 15
                    out.append((f"{nm}.{tp}" if tp else nm, ln, b,
                                f"{d:02d}-{m:02d}-{y}" if m else ""))
                b += ln
            seg = nxt
        return out

    # ---- write support (single directory segment, enough for these floppies) ----
    E_MPTY, E_PERM, E_EOS = 0o1000, 0o2000, 0o4000

    def _seg(self):
        """Return (extra, startblk, [entry dicts]) for directory segment 1."""
        s = bytearray(self.blk(6, 2))
        _nseg, _nxt, _high, extra, start = struct.unpack_from("<5H", s, 0)
        ents, off = [], 10
        while off + 14 <= len(s):
            w = list(struct.unpack_from("<7H", s, off))
            off += 14 + extra
            if w[0] & self.E_EOS: break
            ents.append(w)
        return extra, start, ents

    def _write_seg(self, extra, ents):
        s = bytearray(self.blk(6, 2))
        off = 10
        for w in ents:
            struct.pack_into("<7H", s, off, *w); off += 14 + extra
        struct.pack_into("<H", s, off, self.E_EOS)          # end-of-segment marker
        self.img = bytearray(self.img)
        self.img[6 * 512:8 * 512] = s

    def _coalesce(self, ents):
        out = []
        for w in ents:
            if out and out[-1][0] & self.E_MPTY and w[0] & self.E_MPTY:
                out[-1][4] += w[4]                          # merge adjacent free areas
            else:
                out.append(w)
        return out

    def rm(self, name):
        extra, start, ents = self._seg()
        for w in ents:
            nm = (r50(w[1]) + r50(w[2])).rstrip() + "." + r50(w[3]).rstrip()
            if w[0] & self.E_PERM and nm.upper() == name.upper():
                w[0] = self.E_MPTY; w[1] = w[2] = w[3] = 0
                self._write_seg(extra, self._coalesce(ents)); return True
        raise KeyError(name)

    def put(self, name, data):
        nb = (len(data) + 511) // 512
        extra, start, ents = self._seg()
        ents = self._coalesce(ents)
        blk, idx = start, None
        for i, w in enumerate(ents):
            if w[0] & self.E_MPTY and w[4] >= nb: idx = i; break
            blk += w[4]
        if idx is None: raise RuntimeError(f"нет свободной области на {nb} блоков")
        base, stem = name.upper().split("."), None
        stem, typ = (base + [""])[0][:6].ljust(6), (base + [""])[1][:3].ljust(3)
        enc = lambda t: (R50.index(t[0]) * 1600 + R50.index(t[1]) * 40 + R50.index(t[2]))
        rest = ents[idx][4] - nb
        ents[idx] = [self.E_PERM, enc(stem[:3]), enc(stem[3:]), enc(typ), nb, 0, 0]
        if rest: ents.insert(idx + 1, [self.E_MPTY, 0, 0, 0, rest, 0, 0])
        self._write_seg(extra, ents)
        self.img = bytearray(self.img)
        self.img[blk * 512: blk * 512 + nb * 512] = data.ljust(nb * 512, b"\0")
        return blk

    def save(self, path):
        open(path, "wb").write(bytes(self.img))

    def read(self, name):
        for n, ln, b, _ in self.files():
            if n.upper() == name.upper():
                return self.blk(b, ln)
        raise KeyError(name)


def cmd_ls(args):
    for p in args:
        v = RT11(p); h = v.home(); fs = v.files()
        print(f"\n=== {p}  ({len(v.img)} bytes = {v.blocks} blocks)")
        print(f"    system={h['sysid']!r}  volume={h['volid']!r}  owner={h['owner']!r}")
        for n, ln, b, d in fs:
            print(f"      {n:<12} {ln:>5} blk  @{b:<6} {d}")
        print(f"    {len(fs)} files, {sum(f[1] for f in fs)} blocks used, "
              f"{v.blocks - sum(f[1] for f in fs)} free")

def cmd_cat(args):
    print(koi7(RT11(args[0]).read(args[1])))

def cmd_x(args):
    src, dst = args[0], args[1]
    v = RT11(src); os.makedirs(dst, exist_ok=True)
    for n, ln, b, _ in v.files():
        with open(os.path.join(dst, n), "wb") as fh:
            fh.write(v.blk(b, ln))
        print(f"  {n}  ({ln} blocks)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    {"ls": cmd_ls, "cat": cmd_cat, "x": cmd_x}[sys.argv[1]](sys.argv[2:])
