# Adding fixes and packaging

[日本語](adding-fixes.md) | [English](adding-fixes.en.md)

This project generates a selected IPS from the user's own original ROM. Fixes are managed independently, without enumerating combinations. The distribution contains no prebuilt IPS or ROM.

## Registration

1. Create a module under `tools/fixes/`.
2. Give its `Fix` a stable ID and Japanese/English titles, summaries, and bug explanations. IDs use lowercase letters, digits, and underscores, beginning with a letter.
3. Register it in `CATALOG` in `tools/feature_catalog.py`. The CLI and GUI discover it automatically.
4. Check the original symptom, corrected behavior, disabled controls, and relevant interactions with `tools/verify_bugs.py` or another behavioral diagnostic.

Use `extended_helpers=True` for new fixes. `stairs.py` is a working example. `bug_descriptions.py` holds shared descriptions and offers the `bug_fix` factory.

```python
from fixes import Explanation, Fix


def emit_helpers(c):
    # c.label("your_fix_entry")
    # c.emit("...", "corresponding Z80 instructions")
    pass


def apply(edit, hook, c):
    # hook(offset, expected_bytes, "your_fix_entry", "Reason")
    # edit(offset, expected_bytes, replacement_bytes, "Reason")
    pass


FIX = Fix(
    id="your_fix", title_ja="修正名", title_en="Fix title",
    description_ja="一覧用の要約", description_en="List summary",
    explanation=Explanation(
        symptom_ja="現象とプレイへの影響", symptom_en="Symptom and impact",
        trigger_ja="発生する場面・操作・装備", trigger_en="Triggering situation, inputs, or equipment",
        correction_ja="修正後の動作", correction_en="Corrected behavior",
        notes_ja="補足", notes_en="Notes",
    ),
    extended_helpers=True, bug_ids=("msx.your_fix",),
    emit_helpers=emit_helpers, apply=apply,
    requires=(), conflicts=(),
)
```

Explain the symptom, trigger, and corrected behavior in both languages. If an item groups bugs, explain each and list their `bug_ids`. Use `behavior_change=True` to identify behavior improvements. Hover tips, Details, and CLI `--list` share the full text.

The item count is not fixed. Keep IDs stable so saved selections survive ordering and wording changes. New items are not automatically added to older selections.

## Dependencies, conflicts, and edit checks

`requires=("other_fix",)` includes and builds dependencies first. A `conflicts=("other_fix",)` declaration on either side rejects the pair. Unknown IDs, duplicate registration, missing references, and cycles are errors.

`edit` takes a file offset, equal-length original/replacement bytes, and a reason. Bytes may be `bytes` or hexadecimal strings. `hook` normally emits a three-byte CALL; pass `0xC3` as the last argument for JP. Original bytes and overlapping ranges are always checked.

Do not overwrite the same hook with competing edits. Consolidate shared logic and use `c.enabled` to inspect selected IDs. Existing shared logic coordinates projectile reservations, equipment ownership, axe wall notifications, and sword edge markers.

## Expanded layout

`tools/expanded_rom.py` builds the 2 Mbit output. Original asset banks 4 through 15 stay unchanged. Physical 8 KiB bank 16 holds correction code and the storage copy of resident helpers, without duplicating or recompressing graphics, music, or stages.

The original three items use RAM `$E618–E7FF` and `$F100–F1C8`. Entry adapters and the bank-return bridge use `$F1C9–F37F`. They load at startup and preserve registers, return values, stack balance, and the caller's interrupt-enable state around bank changes. Storage-bank, reserved-RAM, and startup-loader overflow stop generation.

An expanded `emit_helpers(c)` emits labels in CPU window `$8000–9FFF`. `c.call("label")` calls within the extension; `c.call(0x1234)` selects original bank 2 for the call. Numeric `c.jp` is implemented as an original call followed by a return. Repeatedly returning to an already hooked original loop can accumulate nested calls; move the loop into the helper and return at its success/failure boundary instead.

Direct reads from `$8000–9FFF` inside extension code read the extension, not original data. Delegate such reads to a routine running in the original bank. Do not manually use `org` in new extension emitters.

RAM bounds were chosen against original usage and the [MSX2 Technical Handbook's cartridge work-area description](https://konamiman.github.io/MSX2-Technical-Handbook/md/Chapter5b.html). Physical hardware has not been tested.

## Compatibility and distribution

Selections containing only the original three items reproduce the earlier 1 Mbit outputs. Only this mode uses the graphics repacking in `compact_assets.py`, with data read from the user's ROM. `VARIANTS` retains the seven earlier selections for hash checks; new fixes do not require new combinations there.

`build_patches.py` defaults to local `build/patches/` and `build/`. `dist/manifest.json` contains compatibility hashes and verification metadata. Build records omit original data bytes.

Run function diagnostics, expanded graphics/opening-input checks, shield diagnostics, and selector checks before `python tools/package_patches.py`. Packaging refuses prebuilt IPS files and includes sources, documentation, and verification records. Distinguish original reproduction, corrected function checks, opening input, and full-campaign validation by their actual scope.
