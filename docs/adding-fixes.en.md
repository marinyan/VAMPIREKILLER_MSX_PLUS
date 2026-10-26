# Adding fixes

[日本語](adding-fixes.md) | [English](adding-fixes.en.md)

The selector links the requested fixes and generates one IPS from the original ROM. It neither stacks IPS files nor enumerates all possible combinations.

## Source layout

| File | Purpose |
|---|---|
| `tools/fixes/__init__.py` | `Fix` metadata, dependency/conflict declarations, and callbacks |
| `tools/fixes/*.py` | Each fix's resident helpers and ROM edits |
| `tools/feature_catalog.py` | Stable registration order, dependency resolution, selection validation |
| `tools/patches.py` | Z80 linking, labels, placement, original-byte and edit-range checks |
| `tools/selection_build.py` | Single-IPS builds, build records, selection JSON, output handling |
| `tools/patch_selector.py` / `tools/selector_gui.py` | CLI and GUI; both read their item list from the catalog |

## Register an item

1. Create a module in `tools/fixes/`. `shield_fix.py` is a short working example.
2. Define a `Fix` with a stable ID, Japanese/English titles and descriptions. IDs use lowercase letters, digits, and underscores, beginning with a letter.
3. Import its `FIX` in `tools/feature_catalog.py` and append it to `CATALOG`, retaining the existing order. The CLI and GUI discover the entry automatically.
4. Add behavioral checks for the fix and relevant interactions; check placement and actual game behavior.

A module has the following shape. Replace the comments with helpers and edits verified against the original ROM.

```python
from fixes import Fix


def emit_helpers(c):
    # c.label("your_fix_entry")
    # c.emit("...", "corresponding Z80 instructions")
    # c.call("shared_label") / c.jp(...) / c.jr(...)
    pass


def apply(edit, hook, c):
    # edit(offset, expected_bytes, replacement_bytes, "Reason for the edit")
    # hook(offset, expected_bytes, "your_fix_entry", "Reason for the hook")
    pass


FIX = Fix(
    id="your_fix",
    title_ja="修正名", title_en="Fix title",
    description_ja="挙動の説明", description_en="Behavior description",
    emit_helpers=emit_helpers, apply=apply,
    requires=(), conflicts=(),
)
```

Omit `emit_helpers` if the fix only edits existing instructions. Builds containing only inline fixes do not emit zero-length RAM transfers. Use labels that do not collide with other modules.

`edit` takes a file offset, equal-length original/replacement bytes, and a reason. Byte arguments accept `bytes` or hexadecimal strings. `hook` normally emits a three-byte CALL; pass `0xC3` as its final argument for JP. Label addresses are resolved after linking.

## Dependencies and conflicts

`requires=("other_fix",)` automatically includes the dependency and links its helpers and edits first. The GUI reflects these dependencies in its checkboxes. Selection order does not affect the generated IPS.

Declare incompatible items with `conflicts=("other_fix",)`. A declaration on either side rejects the pair. Unknown IDs, duplicate registrations, missing references, and dependency cycles are also errors.

Overlapping ROM edits are rejected, even if they write identical bytes. To support both fixes at the same hook, consolidate the hook in the core or a shared module with appropriate dependencies.

## Capacity and placement

Output remains 1 Mbit. Shared asset repacking and decompression are included once. Resident helpers currently use `$E618–E7FF` and `$F100–F1C8`. The screen-edge module switches to `$F100` partway through; later modules continue in that segment.

The builder checks bank 6 storage, reserved RAM bounds and overlaps, and startup-loader size. If a new helper does not fit, reduce the implementation or investigate and revise the placement design. The tool does not expand the ROM automatically. The `.ips.json` record exposes `bank6_free_bytes`, `ram_chunks`, and the responsible module for each edit in `changes[].owner`.

## Verification and distribution

```powershell
python tools/patch_selector.py --list
python tools/patch_selector.py path/to/original.rom --enable your_fix --out build/your-fix.ips
python tools/patch_selector.py path/to/original.rom --all --out build/all-fixes.ips
python tools/verify_selector.py path/to/original.rom
```

`verify_selector.py` checks the current three fixes against all seven published patches, CLI/Tcl-Tk workflows, saved selections, dependencies, conflicts, and capacity limits. It also registers twenty synthetic inline fixes to exercise extension without combination tables. These fixtures are integration tests, not twenty implemented game fixes.

For each new fix, add behavioral diagnostics and check relevant interactions and an all-fixes build. Do not claim every combination has been tested. `VARIANTS` and `build_patches.py` retain the seven existing releases for reproducibility; new fixes do not require new combinations there.

`python tools/package_patches.py` packages nested fix modules, both languages' documentation, and selector verification alongside the existing distribution. ROMs and emulator snapshots are excluded.
