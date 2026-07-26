# original-tetris-recomp

A byte-exact reconstruction of the Soviet **ТЕТРИС** for the Электроника-60 /
ДВК — recovered all the way back to a **Pascal source file** that compiles,
with the original 1980s toolchain under emulation, into the very same binary.

```
program 001000..032415: 0 words differ out of 6535
md5 ours     49d72cad48c6b34aa7f56cc4fe032622
md5 original 49d72cad48c6b34aa7f56cc4fe032622
```

The whole file matches — all 13824 bytes, header included. The copy on the
original disk is 512 bytes longer: past the end of the program lies the tail of
a block holding garbage from a file deleted long ago.

## Building

Needs Python 3 and `pexpect`. The PDP-11 emulator (SIMH) is included as
`tools/pdp11`; set `PDP11=/path/to/pdp11` to use your own.

```sh
pip install pexpect
./pascal/rebuild/rebuild.py
```

One command runs the authentic chain — ПАСКАЛЬ compiles `GAME.PAS` to
MACRO-11, MACRO assembles it and the five reconstructed runtime modules, LINK
lays everything out in the original module order — and compares the result
against `tetris/dis/TETRISB.SAV` down to the md5. Exit code 0 means identical.

`./pascal/pas/build.py` rebuilds just the game from source and links it against
the previously built runtime.

## What is here

| path | what |
|---|---|
| `pascal/pas/GAME.PAS` | **the game, 589 lines of Pascal** — recovered source |
| `pascal/pas/NOTES.md` | how every construct was worked out (Russian) |
| `pascal/rebuild/INIT.MAC` | `$INIT` — startup and trap handling |
| `pascal/rebuild/IO.MAC` | `$IO` — input and output |
| `pascal/rebuild/ARITH.MAC` | `$ARITH` — integer multiply and divide |
| `pascal/rebuild/ERR.MAC` | `$ERROR` — reporting run-time errors |
| `pascal/rebuild/FPSIM.MAC` | `$FPSIM` — floating point in software |
| `pascal/gold/` | the PASCAL compiler and runtime libraries as found |
| `pascal/sys-macro-link.rx01` | bootable RT-11 volume with MACRO and LINK |
| `disks/blank.dsk` | scratch volume the builds run on |
| `tools/` | assemble, link, disassemble, compare — all via the emulator |
| `tetris/dis/TETRISB.SAV` | the original, for comparison |
| `docs/` | module-by-module analysis, full listings |

The other eight runtime modules are taken as they are from the surviving
libraries in `pascal/gold/`.

## The recovered source

The game is OMSI PASCAL-1 (ПАСКАЛЬ/РАФОС) work, and the surviving compiler is
the very version it was built with: both announce `$VER=12.`. That makes the
reconstruction testable — the compiler is deterministic, so a candidate source
either produces the original bytes or it does not. `GAME.PAS` does, to the last
word.

Pascal cannot ask the keyboard "is a key down?" without waiting, and the
machine may have no clock, so the author dropped to assembler in exactly seven
places, through the compiler's `(*$C ... *)` splice. All of them are preserved
as they were:

| where | what it does |
|---|---|
| `KEYIN` — whole body | wait for a key, **counting the polling loops**; the count seeds the random generator |
| `RANDOM` — two lines | move the count into the Pascal `SEED` variable and back |
| `SCORES` | drain typed-ahead keys before reading the player's name |
| `WAIT` — whole body | delay calibrated against the terminal status register, so speed follows the terminal, not the CPU |
| `KEY` | take a key without waiting; empty buffer leaves `CHR(0)` |
| main, once | now plain Pascal: `JSW ORIGIN 44B` + `JSW := JSW OR 10100B` — same `BIS` instruction; the ORIGIN idiom is attested by period editors found on the tapes |
| main, game over | drain keys pressed during play before "another game?" |

Everything else is plain Pascal. The randomness is the player: how long they
took to press a key, measured in polling loops, fed through
`SEED := (SEED * 13077 + 6925) mod 32768`.

Some of what the source revealed:

* **The pieces are computed, not stored.** The square is built as
  `DY[I] := I div 3; DX[I] := -(I mod 2)`; a bar-with-bump family makes the
  I, L, T and J pieces in one loop; S and Z are copies of T with one cell
  moved. A nested `ROTATE` procedure turns each piece three times at startup,
  so play-time rotation is a table lookup — 19 distinct orientations chained
  through the `NXT` array.
* **Showing the next piece costs 5 points**, and every step down costs 1.
* The compiler generates unchecked arithmetic (`$B116`) for the unsigned
  subrange `0..65535` and checked (`$B78`) for `integer` — the score is
  unsigned; that one type decides which runtime routines get linked in.
* The build needed `(*$T-,A-*)` — stack and bounds checks off. With them on,
  the compiler emits calls the binary does not have, so this is how the author
  actually compiled it.

## Verifying

Nothing here is taken on trust.

* `pascal/rebuild/rebuild.py` — the full build; compares every byte and both
  md5 sums, and fails loudly otherwise.
* `pascal/rebuild/check.py` — one runtime module at a time, before any
  linking: non-relocated bytes against the original image, relocation lists
  against the library.
* `pascal/rebuild/shift.py` — loads the game at a different address and plays
  both builds in the emulator. A `.SAV` always loads at 001000, so a constant
  and an address can assemble to the same word; shifting the base is the only
  way to prove the relocations right.
* `pascal/pas/step.py` — the tool the reconstruction was made with: compile,
  find the first diverging byte, show the original's disassembly at that spot.

## What this is not

The bytes are right and the behaviour is right, but this is a reconstruction,
not an excavation:

* identifiers are invented. The compiler's output holds no variable, procedure
  or label names — `SETUP`, `CANFIT`, `XPOS` are ours. Only the runtime's
  global symbols are original.
* comments and layout are ours.
* the runtime's object files are not byte-identical to the lost library's —
  only the linked image is provably identical.

None of that is recoverable: the information is not in the binary.

## Provenance

The binaries under `pascal/gold/` and the original `TETRISB.SAV` come from
magnetic tapes and floppy images preserved by the Soviet-computing community.
`pascal/tape017/PASCAL-1988.OBJ` was recovered from the remains of earlier
recordings on tapes 017 and 018, which had been written over.

`tools/pdp11` is a build of [SIMH](https://github.com/simh/simh).
