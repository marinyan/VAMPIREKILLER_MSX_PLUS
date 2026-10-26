# VAMPIRE KILLER MSX PLUS

[日本語](README.md) | [English](README.en.md)

IPS patches that improve weapon use and screen-edge behavior in the MSX2 game *Akumajō Dracula / Vampire Killer*.

The displayed title changes according to the machine's BIOS region. Identify the supported source ROM by its size and SHA-256 below, rather than by the language of the title screen.

**All seven patched ROMs remain 1 Mbit (128 KiB / 131,072 bytes).** Graphics, music, and stages are retained. Lossless compression and deduplication make room within the original ROM size.

[Download the patches, source code, and verification records as a ZIP](dist/VAMPIREKILLER_MSX_PLUS_patches.zip)

## Generate an IPS with selected fixes

**Choose the fixes you want and generate one IPS.** The initial selection contains three items:

- `fall_attack`: weapons during falls
- `screen_edges`: screen-edge behavior for enemies, small hearts, swords, and straight-moving enemy projectiles
- `shield_fix`: shield durability across areas, equipment removal, and exhaustion

Extract the ZIP and use Python 3.10 or later. The window requires Tcl/Tk, which is available with the standard Windows Python installer. No extra packages are needed.

```powershell
python tools/patch_selector.py --lang en
```

On Windows, you can also double-click [select_patches.pyw](select_patches.pyw). Choose an unmodified source ROM, check the desired fixes, then click **Generate IPS** and choose a destination. All processing stays on your computer; the source ROM is neither uploaded nor modified. Selections can be saved and loaded as JSON. The list scrolls as more fixes are added.

Hover over an item's name or summary to see **the bug description, when it happens, the corrected behavior, and notes**. Long tips can be scrolled. Click **Details**, or focus a checkbox and press F1, to open the full explanation in a separate scrollable window. The two shield bugs are explained individually; the screen-edge option is identified as a behavior change. Explanations follow the Japanese/English language selection.

The command-line interface generates only the selection you request:

```powershell
python tools/patch_selector.py --list --lang en
python tools/patch_selector.py path/to/original.rom --enable fall_attack shield_fix --out build/my-fixes.ips --save-config build/my-selection.json
python tools/patch_selector.py path/to/original.rom --config build/my-selection.json --out build/rebuilt.ips
python tools/patch_selector.py path/to/original.rom --all --out build/all-fixes.ips
```

Output consists of the IPS and a `name.ips.json` build record containing the selected fixes and SHA-256 hashes of the source ROM, patched ROM, and IPS. It does not write a patched ROM. The JSON created by `--save-config` is a reusable selection; `name.ips.json` is the build record. Replacing existing files requires confirmation in the window or `--force` in the CLI. Unsupported ROMs, empty selections, unknown IDs, dependency cycles, conflicts, and ROM or reserved-RAM overflows are rejected.

Future fixes are added as individual modules, without creating files for every combination. See [Adding fixes](docs/adding-fixes.en.md). The [selector verification record](dist/selector-verification.json) covers byte-for-byte agreement with all seven existing patches, GUI/CLI generation, saved selections, and dependency, conflict, and capacity checks.

## Ready-made IPS files

The seven existing files remain available. Future fixes will be added to the selector catalog.

| Patch | Falling attacks | Screen edges | Shield fix |
|---|:---:|:---:|:---:|
| [fall_attack.ips](dist/fall_attack.ips) | ✓ | — | — |
| [screen_edges.ips](dist/screen_edges.ips) | — | ✓ | — |
| [combined.ips](dist/combined.ips) | ✓ | ✓ | — |
| [shield_fix.ips](dist/shield_fix.ips) | — | — | ✓ |
| [fall_attack_shield.ips](dist/fall_attack_shield.ips) | ✓ | — | ✓ |
| [screen_edges_shield.ips](dist/screen_edges_shield.ips) | — | ✓ | ✓ |
| [combined_shield.ips](dist/combined_shield.ips) | ✓ | ✓ | ✓ |

Falling attacks cover the whip, sword, axe, cross, holy water, and stopwatch. Screen-edge changes improve enemy entry and the behavior of small hearts, swords, and straight-moving enemy projectiles. The shield fix carries remaining durability across ordinary area transitions and corrects exhaustion while preserving equipment removal after bosses. **Choose `combined_shield.ips` for all three features.**

**Axes and crosses still turn back at the screen edge and can be caught on their return.**

## Enemy entry example

![A zombie entering from the left edge, with only part of its body visible](docs/images/zombie-left-edge.png)

This is an unedited openMSX screenshot of `combined.ips` in use. The game was driven from power-on using ordinary keyboard input, and the zombie spawned naturally at the left edge.

## Applying a patch

1. Check the size and SHA-256 of your unmodified ROM.
2. Apply **one** generated IPS or one of the seven ready-made IPS files to a copy of that ROM. Do not stack patches.
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
- **Shield durability:** Both shield types start with 16 uses. Ordinary area transitions retain the remaining durability; equipment resets after bosses or a lost life remove the shield and clear its durability. Exhausted shields are removed before zero can decrement to 255. When a projectile shield uses its final charge, it stops blocking further projectiles in that same update. This applies to both contact-damage reduction and projectile-blocking shields.

## Verification

The original ROM and all seven patched variants were each checked with 1,653 conditions and 8,875 function-return observations in openMSX 21.0 with C-BIOS MSX2 JP. JP identifies the emulated machine configuration used for these tests. These function-level diagnostics set input RAM and registers. They cover movement and landing, BCD heart consumption, weapon-slot management, enemy spawning, edge rendering and removal, small-heart landing, sword collision checks, and axe/cross reversal and recovery.

Each patched variant was also run from power-on for 63.5 seconds using ordinary keyboard input, passing through three outdoor and three castle screens. See the [function and opening-section verification record](dist/verification.json).

Separate shield diagnostics checked the original and all seven variants with 478 cases and 582 function returns per ROM. They reproduce the original zero-to-255 bug after an area transition. For the four shield-fixed variants, they verify remaining durability, equipment removal after bosses, 16-use pickups, zero durability, eight simultaneous projectiles with one use remaining, and a 16-use sequence interrupted by area transitions. See the [shield verification record](dist/shield-verification.json).

**The falling-attack + screen-edge variant, `combined.ips`, was cleared by an automated playthrough using ordinary keyboard input from power-on.** It visited all 19 areas and 139 distinct screens, defeated all six bosses including both forms of the final boss, observed all 41 ending text entries, and confirmed rightward movement after the second loop began. The run includes one life lost and a normal restart. It used no mid-game save-state restores or writes to game RAM, the program counter, or ROM.

Two independent replays matched all 56,792 observed updates, including timing, inputs, game state, and the Z80 R register. Each replay checked the added code regions 568 times. The two replays also matched 568 samples of 9,344 bytes of work RAM. Falling and an active attack overlapped in 48 observed updates. The [full-playthrough verification record](dist/campaign-verification.json) and [replay input archive](dist/campaign-inputs.json.gz) are included. The input archive contains no ROM or emulator snapshot.

The full-playthrough record applies to `combined.ips`. Full campaigns with the four shield-fixed variants, every branch or equipment combination, other machine configurations, and physical hardware have not been verified.

For the 1 Mbit asset repack, positions, patterns, and colors for all 168 poses were compared with the original in all seven variants. All 128 KiB of VRAM also matched after loading items and candles under matching initial conditions. Twelve images totaling 1,536 bytes are losslessly compressed to 932 bytes. See the [size and graphics verification record](dist/compact-verification.json).

## Building and repeating the checks

Patch generation requires only Python 3.10 or later and its standard library. The selector above generates one requested selection; the following command rebuilds the seven existing releases.

```powershell
python tools/build_patches.py path/to/original.rom
python tools/verify_patch_files.py path/to/original.rom
python tools/verify_selector.py path/to/original.rom
```

The builder writes IPS files and a hash manifest to `dist/`, and patched ROMs and code listings to `build/`. It stops if the source ROM hash does not match.

Selector verification exercises the CLI and Tcl/Tk callbacks. On a system without Tcl/Tk or a display, add `--skip-gui` to `verify_selector.py`; the report records that GUI checks were skipped.

To repeat the emulator diagnostics, provide a portable openMSX installation:

```powershell
python tools/verify_emulator.py path/to/original.rom --openmsx path/to/openmsx.exe
python tools/verify_compact_rom.py path/to/original.rom --openmsx path/to/openmsx.exe
python tools/verify_shield.py path/to/original.rom --openmsx path/to/openmsx.exe
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

Individual fixes live in [tools/fixes/](tools/fixes/), their registry in [tools/feature_catalog.py](tools/feature_catalog.py), linking and placement in [tools/patches.py](tools/patches.py), and asset compression and deduplication in [tools/compact_assets.py](tools/compact_assets.py). Added code fits inside bank 6 of the original ROM and is loaded at startup into RAM ranges `$E618–E7FF` and `$F100–F1C8`. The three-feature variant uses 683 bytes of added code and leaves 113 bytes free in the repacked ROM area. It does not add bank switching to the ordinary update loop.

RAM placement was chosen after checking the original stack, variables, and image buffers, together with the [cartridge work-area description in the MSX2 Technical Handbook](https://konamiman.github.io/MSX2-Technical-Handbook/md/Chapter5b.html).
