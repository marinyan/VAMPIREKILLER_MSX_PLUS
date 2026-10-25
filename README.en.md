# VAMPIRE KILLER MSX PLUS

[日本語](README.md) | [English](README.en.md)

IPS patches that improve weapon use and screen-edge behavior in the MSX2 game *Akumajō Dracula / Vampire Killer*.

The displayed title changes according to the machine's BIOS region. Identify the supported source ROM by its size and SHA-256 below, rather than by the language of the title screen.

**All three patched ROMs remain 1 Mbit (128 KiB / 131,072 bytes).** Graphics, music, and stages are retained. Lossless compression and deduplication make room within the original ROM size.

[Download the patches, source code, and verification records as a ZIP](dist/VAMPIREKILLER_MSX_PLUS_patches.zip)

| Patch | Changes |
|---|---|
| [fall_attack.ips](dist/fall_attack.ips) | Allows the whip, sword, axe, cross, holy water, and stopwatch to be used while falling after walking off a ledge |
| [screen_edges.ips](dist/screen_edges.ips) | Improves enemy entry at screen edges, prevents small hearts from disappearing at horizontal edges, and extends the visible travel of swords and straight-moving enemy projectiles |
| [combined.ips](dist/combined.ips) | Includes both sets of changes |

**Axes and crosses still turn back at the screen edge and can be caught on their return.**

## Enemy entry example

![A zombie entering from the left edge, with only part of its body visible](docs/images/zombie-left-edge.png)

This is an unedited openMSX screenshot of `combined.ips` in use. The game was driven from power-on using ordinary keyboard input, and the zombie spawned naturally at the left edge.

## Applying a patch

1. Check the size and SHA-256 of your unmodified ROM.
2. Apply **one** of the three IPS files to a copy of that ROM. Choose `combined.ips` for both features instead of stacking patches.
3. The result is still 128 KiB. If your emulator requires a mapper selection, choose **Konami without SCC**. When replacing an earlier expanded release, apply the new patch to a fresh copy of the unmodified source ROM.

The supported unmodified source ROM is 128 KiB (131,072 bytes) with this SHA-256:

```text
99eabaaeb2b6c02220e131043d5a6401d0d8c5f413d89204547adcc04d65e7e2
```

IPS files do not identify the source ROM. Do not apply these patches to a different revision or an already modified ROM. Neither the original ROM nor patched ROMs are included in the distribution.

## Scope of the changes

- **Attacking during falls:** Changes attack progression, display, and special-weapon input after walking off a ledge. Falling speed, fractional coordinates, ground detection, and landing sounds are preserved. It also prevents holy water from overwriting a sword slot awaiting launch.
- **Enemy entry:** Moves the spawn coordinates of periodically appearing enemies, such as zombies and bats, to the left or right edge. Zombies fall back to their original spawn position if there is no floor at the edge. Spawn timing and checks that avoid spawning too close to the player are preserved. This does not replace the entry or removal rules for every enemy type.
- **Small hearts:** Clamps their horizontal position within the screen and prevents horizontal edge checks alone from deleting them. Their pickup sprites also remain inside the screen when they land. Swaying, vertical motion, pickup effects, and their lifetime after landing are preserved.
- **Swords and straight-moving enemy projectiles:** Keeps them visible until their final sprite has left the screen. Tracks coordinate wraparound to prevent them from reappearing or colliding on the opposite side. The affected enemy projectile types are `01/02/03/05/0A/0B`. Homing projectiles and special behaviors such as returning enemy axes are outside this change.

## Verification

The original ROM and all three patched variants were each checked with 1,653 conditions and 8,875 function-return observations in openMSX 21.0 with C-BIOS MSX2 JP. JP identifies the emulated machine configuration used for these tests. These function-level diagnostics set input RAM and registers. They cover movement and landing, BCD heart consumption, weapon-slot management, enemy spawning, edge rendering and removal, small-heart landing, sword collision checks, and axe/cross reversal and recovery.

Each patched variant was also run from power-on for 63.5 seconds using ordinary keyboard input, passing through three outdoor and three castle screens. See the [function and opening-section verification record](dist/verification.json).

**The combined 1 Mbit variant was cleared by an automated playthrough using ordinary keyboard input from power-on.** It visited all 19 areas and 139 distinct screens, defeated all six bosses including both forms of the final boss, observed all 41 ending text entries, and confirmed rightward movement after the second loop began. The run includes one life lost and a normal restart. It used no mid-game save-state restores or writes to game RAM, the program counter, or ROM.

Two independent replays matched all 56,792 observed updates, including timing, inputs, game state, and the Z80 R register. Each replay checked the added code regions 568 times. The two replays also matched 568 samples of 9,344 bytes of work RAM. Falling and an active attack overlapped in 48 observed updates. The [full-playthrough verification record](dist/campaign-verification.json) and [replay input archive](dist/campaign-inputs.json.gz) are included. The input archive contains no ROM or emulator snapshot.

This verifies one input route in an emulator. It does not cover every branch, equipment combination, machine configuration, or physical hardware.

For the 1 Mbit asset repack, positions, patterns, and colors for all 168 poses were compared with the original. All 128 KiB of VRAM also matched after loading items and candles under matching initial conditions. Twelve images totaling 1,536 bytes are losslessly compressed to 932 bytes. Comparison with the earlier expanded variants matched game state and display data across 8,875 observations per variant. See the [size and graphics verification record](dist/compact-verification.json).

## Building and repeating the checks

Patch generation requires only Python 3 and its standard library.

```powershell
python tools/build_patches.py path/to/original.rom
python tools/verify_patch_files.py path/to/original.rom
```

The builder writes IPS files and a hash manifest to `dist/`, and patched ROMs and code listings to `build/`. It stops if the source ROM hash does not match.

To repeat the emulator diagnostics, provide a portable openMSX installation:

```powershell
python tools/verify_emulator.py path/to/original.rom --openmsx path/to/openmsx.exe
python tools/verify_compact_rom.py path/to/original.rom --openmsx path/to/openmsx.exe
```

Replay the combined variant's full input record with your locally patched ROM and a fresh power-on state:

```powershell
python tools/verify_campaign.py --rom build/combined.rom --inputs dist/campaign-inputs.json.gz --openmsx path/to/openmsx.exe --out build/campaign-replay
```

Use a new directory for `--out`. Results are saved there as `report.json`. The recorded environment is openMSX 21.0 / C-BIOS MSX2 JP. The distribution ZIP includes the patches, sources, inputs, and verification records.

The zombie screenshot can also be captured again through ordinary play:

```powershell
python tools/capture_edge_screenshot.py --rom build/combined.rom --openmsx path/to/openmsx.exe
```

Images are saved to `build/screenshot/`. The image shown above is `zombie-left-01.png`.

The hooks are implemented in [tools/patches.py](tools/patches.py), and asset compression and deduplication in [tools/compact_assets.py](tools/compact_assets.py). Added code fits inside bank 6 of the original ROM and is loaded at startup into RAM ranges `$E618–E7FF` and `$F100–F1C8`. The combined variant uses 647 bytes of added code and leaves 149 bytes free in the repacked ROM area. It does not add bank switching to the ordinary update loop.

RAM placement was chosen after checking the original stack, variables, and image buffers, together with the [cartridge work-area description in the MSX2 Technical Handbook](https://konamiman.github.io/MSX2-Technical-Handbook/md/Chapter5b.html).
