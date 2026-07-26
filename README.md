# original-tetris-recomp

A byte-exact reconstruction of the Soviet **ТЕТРИС** for the Электроника-60 /
ДВК, rebuilt from source with the original 1980s toolchain running under
emulation.

```
program 001000..032415: 0 words differ out of 6535
md5 ours     49d72cad48c6b34aa7f56cc4fe032622
md5 original 49d72cad48c6b34aa7f56cc4fe032622
```

The whole file matches — all 13824 bytes, header included. The copy on the
original disk is 512 bytes longer: past the end of the program lies the tail of
a block holding garbage from a file deleted long ago.

## What is here

The game is OMSI PASCAL-1 output linked against ПАСКАЛЬ/РАФОС runtime modules.
None of the surviving copies of that runtime library matches the one the game
was built with, so six modules had to be written again as MACRO-11 source. The
game module itself was read back out of the binary the same way.

| path | what |
|---|---|
| `pascal/rebuild/GAME.MAC` | the game, 7338 bytes of compiler output read back |
| `pascal/rebuild/INIT.MAC` | `$INIT` — startup and trap handling |
| `pascal/rebuild/IO.MAC` | `$IO` — input and output |
| `pascal/rebuild/ARITH.MAC` | `$ARITH` — integer multiply and divide |
| `pascal/rebuild/ERR.MAC` | `$ERROR` — reporting run-time errors |
| `pascal/rebuild/FPSIM.MAC` | `$FPSIM` — floating point in software |
| `pascal/gold/` | the PASCAL compiler and runtime libraries as found |
| `pascal/sys-macro-link.rx01` | bootable RT-11 volume with MACRO and LINK |
| `tools/` | everything needed to assemble, link, disassemble and compare |
| `tetris/dis/TETRISB.SAV` | the original, for comparison |
| `docs/` | how each module was worked out, with full listings |

The other eight runtime modules are taken as they are from `pascal/gold/`.

## Building

Needs Python 3 and `pexpect`. The PDP-11 emulator (SIMH) is included as
`tools/pdp11`; set `PDP11=/path/to/pdp11` to use your own.

```sh
pip install pexpect
./pascal/rebuild/rebuild.py
```

This assembles seven sources with the real MACRO under emulation, splices the
object file in the original module order, links it with the real LINK, and
compares the result against `tetris/dis/TETRISB.SAV`.

Build products land in `pascal/rebuild/work/`; the rebuilt game is
`work/TETNEW.SAV`.

## Verifying

Nothing here is taken on trust, and the checks are worth more than the result.

**One module at a time, without linking.** Non-relocated bytes are compared
against the image inside the finished program, and the list of relocations
against the same module in the library. If one offset has moved, the source has
drifted from the original — and it shows before the linker is ever run.

```sh
./pascal/rebuild/check.py pascal/rebuild/work/FPSIM.OBJ '$FPSIM' 27154
```

```
$FPSIM: 1714 bytes ours, 1714 original   size agrees
  17 relocations -- all in place
  938 non-relocated bytes, 0 differ
```

**The relocations in the game module, by moving it.** Matching bytes does not
prove those: an RT-11 `.SAV` always loads at 001000, the game module is based at
001000 too, so `MOV #2770,-(SP)` (a constant) and `MOV #CELL,-(SP)` (an address)
assemble to the very same word. Put an empty module in front of the game and
they stop being the same. A missing relocation then reads from the old address
and prints rubbish; a spurious one drags a constant along with the base.

```sh
./pascal/rebuild/shift.py
```

```
  shift 2000
  entry point: was 017272, now 021272
  static text: 23 lines of 23 agree
```

Both builds are run in the emulator and the screens compared. The inside of the
well and the score are left out — pieces fall at random, and the seed is how
long the player took to press a key. Everything else agrees.

That run doubles as an end-to-end test of the rebuilt runtime: the game draws,
takes keys, plays to the end and asks for a name. `$FPSIM` earns its keep, since
`RANDOM` executes FIS instructions the machine does not have.

## What was found along the way

**`KEYIN` is hand-written assembler, not compiler output.** PASCAL has no way to
ask whether a key is down without waiting for one, so this was linked in as an
EXTERNAL procedure. It counts how many times `.TTINR` had to be tried before a
character turned up.

**That count is the game's randomness.** `RANDOM` multiplies it by 31425, adds
15415 and drops the sign bit. The seed is how long the player thought, measured
in polling loops.

**The controls are the numeric keypad**, through a 26-entry jump table indexed
by the character less 40: 7 and 9 move, 8 turns, 5 or space drops, 4 speeds up,
1 shows the next piece, 0 wipes the help text.

**The runtime carries a defect that had to be reproduced.** The RADIX-50
alphabet at the end of `$ERROR` has lost the digit 8: code 38 gives "9" and code
39 gives nothing, so a file on `DX8:` would be misnamed in an error message. The
library still has the table intact, but every program on the tapes carrying this
runtime has it broken. We are reconstructing what was, not what should have been.

**Error numbers are missing from the surviving library.** Where a linked program
has a real number in a message descriptor, the library holds zero — the class
byte is there, the number is not. The numbers used here are not taken from the
target: each is attested by 13 to 25 unrelated programs found in the archive,
with no conflicting value anywhere.

## What this is not

The bytes are right and the behaviour is right, but this is a reconstruction of
the **code**, not a recovery of the **source text**:

* internal label names are invented. Only globals are real, because only they
  are recorded in the object file. Names like `SU1`, `CANFIT`, `NORM` are ours.
* comments and layout are ours. The originals surely used macros and
  conditional assembly.
* the object files are not byte-identical to the library's — only the linked
  image is. At a section boundary one address has two encodings, and neither the
  blocking of records nor the order of symbols is unique.

None of that is recoverable: the information is not in the binary.

## Provenance

The binaries under `pascal/gold/` and the original `TETRISB.SAV` come from
magnetic tapes and floppy images preserved by the Soviet-computing community.
`pascal/tape017/PASCAL-1988.OBJ` was recovered from the remains of earlier
recordings on tapes 017 and 018, which had been written over.

`tools/pdp11` is a build of [SIMH](https://github.com/simh/simh).
