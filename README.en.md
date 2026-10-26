# VAMPIRE KILLER MSX PLUS — ROM-to-IPS generator

[日本語](README.md) | [English](README.en.md)

A tool that **reads your own original MSX2 Akumajō Dracula / Vampire Killer ROM and generates one IPS for the fixes you select**. The distribution contains the tool, correction sources, documentation, and verification records. It contains no prebuilt IPS, original ROM, or patched ROM.

[Download the generator](dist/VAMPIREKILLER_MSX_PLUS_generator.zip)

## Using the tool

Extract the ZIP and use Python 3.10 or later, with Tcl/Tk for the window. No additional packages are needed.

```powershell
python tools/patch_selector.py --lang en
```

On Windows, you can also double-click [select_patches.pyw](select_patches.pyw). Choose an unmodified source ROM, select fixes, and click **Generate IPS**. Apply that one IPS to a copy of the unmodified ROM. Processing stays on your computer; the source ROM is neither uploaded nor modified.

Hover over an item's name or summary for its **bug description, trigger, corrected behavior, and notes**. **Details**, or F1 while a checkbox has focus, opens the full text in a scrollable window. Explanations follow the Japanese/English language choice. The item list also scrolls.

Selections can be saved and loaded as JSON. They use stable IDs, so adding new fixes does not silently add them to an older selection.

```powershell
python tools/patch_selector.py --list --lang en
python tools/patch_selector.py path/to/original.rom --all --out build/all-fixes.ips --save-config build/my-selection.json
python tools/patch_selector.py path/to/original.rom --enable stairs hurt_clip shield_fix --out build/custom.ips
python tools/patch_selector.py path/to/original.rom --config build/my-selection.json --out build/rebuilt.ips
```

Output consists of an IPS and a `name.ips.json` build record. The record contains selected IDs, source/target/IPS hashes, changed ranges, and size information; it does not store original data bytes. Save a reusable selection separately with `--save-config`. Existing outputs require confirmation in the window or `--force` on the CLI.

## Supported ROM and output size

The title changes with the machine's BIOS region. Identify the source by **131,072 bytes (1 Mbit)** and this SHA-256, rather than by title-screen language:

```text
99eabaaeb2b6c02220e131043d5a6401d0d8c5f413d89204547adcc04d65e7e2
```

A selection containing any new bug correction produces a **2 Mbit (256 KiB / 262,144-byte)** ROM. Original graphics, music, and stage banks remain at their original offsets; the extension holds correction code. These builds do not recompress or relocate game assets. If your emulator needs an explicit mapper, use **Konami without SCC**.

Selecting only the original `fall_attack`, `screen_edges`, and `shield_fix` items reproduces the earlier 1 Mbit builds. Only this compatibility mode losslessly repacks graphics read from your ROM on your computer. The resulting binaries are not included in the distribution.

The generator checks the input size and hash before building. IPS itself does not identify an input ROM or detect conflicts; do not stack generated patches on a modified ROM.

## Available items

The current tool covers 29 bugs plus the screen-edge behavior improvement. The two shield bugs share one checkbox, leaving 29 selectable items. The catalog is extensible and has no fixed item count.

| ID | Item |
|---|---|
| `fall_attack` | Weapons during falls |
| `screen_edges` | Screen-edge behavior |
| `shield_fix` | Shield durability |
| `stairs` | Stair endpoint checks |
| `trap_contact` | Repeated trap damage |
| `trap_attack` | Stuck attack after a trap hit |
| `patrol_timer` | Patrol timer wrap |
| `mummy_start` | Mummy initial velocity |
| `reform_hp` | Reforming enemy health |
| `stun_hp` | Stunned companion health |
| `hourglass` | Permanent time stop after an area change |
| `actor_alloc` | Enemy allocation rollback |
| `projectile_alloc` | Projectile allocation rollback |
| `empty_projectile` | Empty projectile collision |
| `projectile_box` | Second projectile collision size |
| `crouch_fall` | Floating crouch |
| `platform_land` | Moving-platform landing height |
| `platform_turn` | Moving-platform reversal carry |
| `shop_input` | Stale shop input |
| `boss_spawn` | Boss spawn retry |
| `weapon_owner` | Projectile equipment ownership |
| `axe_wall` | Per-axe wall notification |
| `hurt_clip` | Injury movement collision |
| `water_edge` | Holy-water edge equipment loss |
| `bat_y` | Ceiling-bat descent height |
| `jumper_land` | Carried jumper landing |
| `water_pending` | Holy-water and pending-throw overlap |
| `actor_order` | Actor scan order after spawning |
| `phantom_gate` | Phantom gate at the screen origin |

The earlier Weapons during falls item also protects pending throws. `water_pending` makes this correction independently selectable without enabling falling attacks. Selecting both is supported.

Full symptoms and triggers appear in the tool and the [catalog JSON](dist/catalog.json). Axes and crosses still turn back at the screen edges.

[examples/all-fixes.json](examples/all-fixes.json) selects all current items; [examples/selection.json](examples/selection.json) selects the original three. `--all` chooses every item registered when the command runs.

## Verification scope

The 26 new items were checked in 28 configurations: original, each new item alone, and all items together. Each ran 5,895 cases and 6,612 function returns in openMSX 21.0 / C-BIOS MSX2 JP. These are arranged function/segment diagnostics using the original cartridge routines with input RAM/registers. They cover disabled controls, shared projectile metadata, two-slot collisions, allocation rollback, and area transitions combining shields and time stop. See the [bug verification record](dist/bug-verification.json).

For the all-items build, all 98,304 bytes in the original asset banks remain unchanged. All 168 pose position/pattern/color transfers and all 128 KiB of VRAM after item/candle upload match the original. A separate 63.5-second run from power-on using ordinary keyboard input traversed three outdoor and three castle screens and checked resident code in 82 samples. See the [size, graphics, and opening-input record](dist/expanded-verification.json).

The original and all-items build also passed 478 shield cases and 582 function returns each. See the [expanded shield record](dist/expanded-shield-verification.json).

The seven selections using only the original three items reproduce their previous IPS and ROM hashes. Their [hashes](dist/manifest.json), [function diagnostics](dist/verification.json), [graphics checks](dist/compact-verification.json), and [shield diagnostics](dist/shield-verification.json) remain available. Public build records do not contain original data bytes.

The earlier full-campaign run applies to the 1 Mbit falling-attack + screen-edge selection. It visited all 19 areas and 139 screens, defeated six bosses including both final forms, observed 41 ending entries and the next loop, and matched all 56,792 updates in two independent replays. The [campaign report](dist/campaign-verification.json) and [ROM-free input archive](dist/campaign-inputs.json.gz) are retained.

The 2 Mbit build with all 29 options also completed all 19 areas, 137 screens, six bosses and both final forms, all 41 ending messages, and the active start and movement of the next loop. A recording replay and a second replay from a fresh power-on seed matched all 59,346 observations and 594 work-RAM samples. The route includes two ordinary deaths and life recoveries, with no midgame restores or game RAM, PC, or ROM writes. The [complete-campaign record](dist/expanded-route-verification.json), [ROM-free input archive](dist/expanded-route-inputs.json.gz), and [frozen 29-option selection](examples/verified-campaign-29.json) are included.

This covers the first clear and next-loop start. It does not establish absence of every bug, a complete second loop, or operation on physical hardware.

## Repeating checks and adding fixes

```powershell
python tools/verify_patch_files.py path/to/original.rom
python tools/verify_bugs.py path/to/original.rom --openmsx path/to/openmsx.exe
python tools/verify_expanded.py path/to/original.rom --openmsx path/to/openmsx.exe
python tools/verify_shield.py path/to/original.rom --openmsx path/to/openmsx.exe --all-fixes --out build/expanded-shield-verification
python tools/verify_selector.py path/to/original.rom
python tools/verify_campaign.py --rom path/to/patched.rom --source-rom path/to/original.rom --config examples/verified-campaign-29.json --inputs dist/expanded-route-inputs.json.gz --out build/expanded-route-replay
```

Results and diagnostic ROMs stay in your local `build/`. Use `--skip-gui` for selector checks without a windowing environment; the report records that GUI checks were skipped.

See [Adding fixes](docs/adding-fixes.en.md) for extension, dependencies, conflicts, and code placement. `python tools/build_patches.py path/to/original.rom` regenerates the seven earlier selections locally, defaulting to `build/patches/` and `build/`.

## Enemy entry example

![A zombie entering from the edge](docs/images/zombie-left-edge.png)

An unedited openMSX screenshot of the 1 Mbit falling-attack + screen-edge selection, driven from power-on by ordinary keyboard input.
