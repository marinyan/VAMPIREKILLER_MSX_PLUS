"""Arranged Z80/VDP display tests; these are separate from campaign evidence."""
from pathlib import Path
import argparse
import hashlib
import itertools
import json

from feature_catalog import CATALOG
from patches import SOURCE_SHA256, make_selected_rom
from verify_bugs import script_for
from verify_emulator import read_rows, run
from fixes.weapon_graphics import weapon_patterns

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    result = []
    positions = ((68, 89), (67, 104), (98, 151), (99, 104), (83, 88), (83, 152),
                 (83, 121), (83, 120), (83, 183), (83, 184), (75, 130), (90, 110))
    for rotation in (0, 8, 56, 120):
        for mode in range(4):
            sat, colors = bytearray(128), bytearray(512)
            for slot in range(32):
                sat[slot * 4] = 224
                if slot < len(positions):
                    sat[slot * 4:slot * 4 + 2] = bytes(positions[slot])
                for row in range(16):
                    early = mode == 1 or mode >= 2 and (row + slot + mode) % 2 == 0
                    colors[slot * 16 + row] = 15 | (128 if early else 0)
            result.append(dict(name=f"pause-{rotation}-{mode}", group="display_pause",
                               player=bytes(80).hex(), registers={}, tiles=[],
                               memory={0xD600: sat.hex(), 0xD400: colors.hex(), 0xC00F: rotation},
                               steps=[(0x53B6, {}, {}), (0x654B, {}, {}), (0x484C, {}, {}),
                                      (0x428C, {}, {}), (0x484C, {}, {}),
                                      (0x43DF, {}, {}), (0x484C, {}, {})],
                               metadata=dict(initial=2, visible=4, resumed=6)))
    for name, memory in (("boss-priority", {0xCE0C: 1}), ("death", {0xCE00: 5}),
                         ("special-door", {0xC5AC: 5})):
        base = result[0]
        result.append(dict(base, name="pause-linear-" + name,
                           memory={**base["memory"], **memory, 0xC00F: 56}))
    order_key = lambda item: (0 if item == 25 else 2 if item == 2 else 3 if item == 1 else 1)
    for order in itertools.permutations((25, 7, 2, 1)):
        records = bytearray(128)
        for slot, item in enumerate(order):
            base = slot * 16
            records[base], records[base + 1], records[base + 2] = 132, 128, 128
            records[base + 4], records[base + 6] = item, 255
        restore = (0x8CE6, {}, {"IX": 0xC500, "DE": 0x8080})
        draw = lambda item: (0x8CC1, {}, {"AF": (item - 1) << 8, "DE": 0x8080})
        steps = [(0x548D, {}, {}), restore, (0x8A4D, {}, {}), (0x484C, {}, {})]
        steps += [restore, *[draw(item) for item in sorted(order, key=order_key)], (0x484C, {}, {})]
        oracle = len(steps) - 1
        steps += [(0x8A4D, {0xC506 + order.index(1) * 16: 1, 0xC003: 0}, {}), (0x484C, {}, {})]
        removed = len(steps) - 1
        steps += [*[draw(item) for item in sorted(order, key=order_key) if item != 1], (0x484C, {}, {})]
        player = bytearray(80)
        player[5], player[7] = 192, 16
        result.append(dict(name="items-" + "-".join(map(str, order)), group="display_items",
                           player=player.hex(), registers={}, tiles=[], memory={0xC500: records.hex()},
                           steps=steps, metadata=dict(initial=3, oracle=oracle, removed=removed,
                                                     removed_oracle=len(steps) - 1)))
    for weapon in (2, 3, 4):
        result.append(dict(name=f"weapon-reference-{weapon}", group="display_weapon_reference",
                           player=bytes(80).hex(), registers={}, tiles=[], memory={0xC416: weapon},
                           steps=[(0x5593, {}, {}), (0x484C, {}, {})],
                           metadata=dict(reference=1, weapon=weapon)))
    for equipment in (2, 3, 4):
        for old_type in (2, 3, 4):
            for pose in ((24, 32) if old_type == 2 else (24, 32, 40, 48)):
                for count in (1, 2):
                    projectiles, sat = bytearray(32), bytearray(128)
                    for slot in range(32):
                        sat[slot * 4] = 224
                    types, poses = [], []
                    for slot in range(count):
                        kind = old_type if slot == 0 else old_type % 3 + 2
                        image = pose if slot == 0 else 32 if kind == 2 else 48
                        base = slot * 16
                        projectiles[base], projectiles[base + 1] = 2, kind
                        projectiles[base + 4], projectiles[base + 5] = 96 + slot * 32, 112 + slot * 48
                        projectiles[base + 6] = image
                        types.append(kind)
                        poses.append(image)
                    steps = [(0x56E1, {}, {}), (0x5593, {}, {}), (0x7535, {}, {"IX": 0xC450}),
                             (0x7535, {}, {"IX": 0xC460}), (0x654B, {}, {}), (0x484C, {}, {}),
                             (0x4058, {}, {}), (0x484C, {}, {}),
                             (0x428C, {}, {}), (0x4058, {}, {}), (0x484C, {}, {}),
                             (0x43DF, {}, {}), (0x4058, {}, {}), (0x484C, {}, {}),
                             (0x4058, {0xC42E: 1, 0xC42F: 1}, {}), (0x484C, {}, {}),
                             (0x4058, {0xC450: bytes(32).hex()}, {}), (0x484C, {}, {})]
                    result.append(dict(name=f"weapon-owner-{equipment}-{old_type}-{pose}-{count}",
                                       group="display_weapon_owner", player=bytes(80).hex(), registers={}, tiles=[],
                                       memory={0xC416: equipment, 0xC450: projectiles.hex(), 0xD600: sat.hex()}, steps=steps,
                                       metadata=dict(initial=5, composed=7, paused=10, resumed=13, refreshed=15, cleaned=17,
                                                     types=types, poses=poses, equipment=equipment)))
    base = next(case for case in result if case["name"] == "weapon-owner-3-2-24-2")
    for name, memory in (("boss-priority", {0xCE0C: 1}), ("death", {0xCE00: 5}),
                         ("special-door", {0xC5AC: 5})):
        result.append(dict(base, name="weapon-linear-" + name,
                           memory={**base["memory"], **memory, 0xC00F: 56},
                           metadata={**base["metadata"], "linear": True}))
    return result


def make_script(cases, output, rom, info, capture_dir):
    script = script_for(cases, output, rom, info)
    script = script.replace('if {[lindex $cfg 5] eq "asset_vram"} {debug write_block VRAM 0',
                            'if {1} {debug write_block VRAM 0')
    capture = capture_dir.as_posix()
    keys = {"initial", "visible", "resumed", "oracle", "removed", "removed_oracle",
            "reference", "composed", "paused", "refreshed", "cleaned"}
    capture_steps = " ".join("{" + " ".join(str(value) for key, value in case["metadata"].items() if key in keys) + "}"
                             for case in cases)
    script = f"set display_capture_steps {{{capture_steps}}}\n" + script
    script = script.replace('debug set_bp 0x414d {$::active} return_now', '''debug set_bp 0x414d {$::active} {
 if {[lindex [lindex $::fixtures $::ci] 5] eq "display_weapon_owner" && $::si>=14} {
  # A normal player-pattern transfer stands in for the dispatch body in this
  # arranged function test, verifying restoration before a new frame's upload.
  reg PC 0x56e1
 } else {return_now}
}''')
    start = script.index("proc returned {} {")
    end = script.index("\n}", start)
    block = script[start:end].replace("\n nextstep", f"\n if {{$si in [lindex $::display_capture_steps $ci]}} {{save_debuggable VRAM {capture}/$ci-$si.vram}}\n nextstep")
    script = script[:start] + block + script[end:]
    return script


def expected_pause_sat(vram):
    result = bytearray(vram[0xF600:0xF680])
    hidden = 0
    for slot in range(32):
        raw_y, x = result[slot * 4:slot * 4 + 2]
        if raw_y == 216:
            break
        top = raw_y + 1
        if top >= 256:
            top -= 256
        if raw_y >= 240:
            top -= 256
        for row in range(16):
            if not 84 <= top + row < 100:
                continue
            effective_x = x - (32 if vram[0xF400 + slot * 16 + row] & 128 else 0)
            if effective_x < 152 and effective_x + 16 > 104:
                result[slot * 4] = 224
                hidden += 1
                break
    return bytes(result), hidden


def bitmap(vram, x, y, width, height):
    return b"".join(vram[(y + row) * 128 + x // 2:(y + row) * 128 + (x + width) // 2]
                    for row in range(height))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rom", type=Path)
    p.add_argument("--openmsx", type=Path, required=True)
    p.add_argument("--out", type=Path, default=ROOT / "build/display-verification")
    args = p.parse_args()
    source = args.rom.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        p.error("Unsupported input ROM")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cases = fixtures()
    profiles = {"original": [], "pause_visibility": ["pause_visibility"],
                "item_priority": ["item_priority"], "weapon_graphics": ["weapon_graphics"],
                "all": [f.id for f in CATALOG]}
    captures, records, hashes = {}, {}, {}
    for name, selected in profiles.items():
        rom, info = (source, {}) if not selected else make_selected_rom(source, selected)[:2]
        folder = out / name
        folder.mkdir(exist_ok=True)
        rom_path, output = folder / "test.rom", folder / "states.tsv"
        rom_path.write_bytes(rom)
        run(args.openmsx.resolve(), rom_path, make_script(cases, output, rom, info, folder), folder, "run")
        records[name] = read_rows(output, cases)[0]
        captures[name] = lambda ci, si, folder=folder: (folder / f"{ci}-{si}.vram").read_bytes()
        hashes[name] = hashlib.sha256(rom).hexdigest()
    hidden, original_order_differences, removal_differences, original_weapon_differences = 0, 0, 0, 0
    canonical = {case["metadata"]["weapon"]: captures["original"](ci, 1)[0xF8C0:0xF9C0]
                 for ci, case in enumerate(cases) if case["group"] == "display_weapon_reference"}
    generated = weapon_patterns(source)
    for weapon in (2, 3, 4):
        size = 128 if weapon == 2 else 256
        assert generated[(weapon - 2) * 256:(weapon - 2) * 256 + size] == canonical[weapon][:size], (weapon, "input-ROM image generation")
    for ci, case in enumerate(cases):
        meta = case["metadata"]
        for name in profiles:
            for si in range(len(case["steps"])):
                assert records[name][ci, si][:6] == records["original"][ci, si][:6], (name, ci, si, "game state changed")
        if case["group"] == "display_weapon_reference":
            continue
        if case["group"] == "display_weapon_owner":
            initial = captures["original"](ci, meta["initial"])
            # 654B starts at logical pair13 after the fixture's zero rotation.
            def displayed_image(vram, slot):
                physical_pair = 3 + slot if meta.get("linear") else ((3 + slot - 13) * 9) & 15
                indices = (vram[0xF600 + physical_pair * 8 + offset] & 252 for offset in (2, 6))
                return b"".join(vram[0xF800 + index * 8:0xF800 + index * 8 + 32] for index in indices)
            for slot, (kind, pose) in enumerate(zip(meta["types"], meta["poses"])):
                expected = canonical[kind][(pose - 24) * 8:(pose - 24) * 8 + 64]
                original_weapon_differences += displayed_image(initial, slot) != expected
                for name in ("weapon_graphics", "all"):
                    for field in ("composed", "paused", "resumed", "refreshed"):
                        actual = captures[name](ci, meta[field])
                        assert displayed_image(actual, slot) == expected, (name, ci, slot, field, "projectile image")
            for name in ("weapon_graphics", "all"):
                clean = captures[name](ci, meta["cleaned"])
                reference = captures["original"](ci, meta["cleaned"])
                assert clean[0xF800:0x10000] == reference[0xF800:0x10000], (name, ci, "borrowed patterns were not restored before a new frame")
                assert clean[0xF600:0xF680] == initial[0xF600:0xF680], (name, ci, "SAT was not restored")
            continue
        if case["group"] == "display_pause":
            initial = captures["original"](ci, meta["initial"])
            wanted, count = expected_pause_sat(initial)
            hidden += count
            assert captures["original"](ci, meta["visible"])[0xF600:0xF680] == initial[0xF600:0xF680]
            for name in profiles:
                paused, resumed = captures[name](ci, meta["visible"]), captures[name](ci, meta["resumed"])
                expected = wanted if name in ("pause_visibility", "all") else initial[0xF600:0xF680]
                assert paused[0xF600:0xF680] == expected, (name, ci, "pause SAT")
                assert resumed[0xF600:0xF680] == initial[0xF600:0xF680], (name, ci, "resume SAT")
                assert paused[0xF400:0xF600] == initial[0xF400:0xF600], (name, ci, "sprite colors")
                assert bitmap(resumed, 104, 84, 48, 16) == bitmap(initial, 104, 84, 48, 16), (name, ci, "pause background")
        else:
            original = captures["original"](ci, meta["initial"])
            oracle = captures["original"](ci, meta["oracle"])
            after = captures["original"](ci, meta["removed"])
            removed_oracle = captures["original"](ci, meta["removed_oracle"])
            original_order_differences += bitmap(original, 128, 128, 16, 16) != bitmap(oracle, 128, 128, 16, 16)
            removal_differences += bitmap(after, 128, 128, 16, 16) != bitmap(removed_oracle, 128, 128, 16, 16)
            for name in ("item_priority", "all"):
                assert bitmap(captures[name](ci, meta["initial"]), 128, 128, 16, 16) == bitmap(oracle, 128, 128, 16, 16), (name, ci, "item order")
                assert bitmap(captures[name](ci, meta["removed"]), 128, 128, 16, 16) == bitmap(removed_oracle, 128, 128, 16, 16), (name, ci, "item removal")
    assert hidden and original_order_differences and removal_differences and original_weapon_differences
    report = dict(status="passed", source_sha256=SOURCE_SHA256, rom_sha256=hashes,
                  selected_fixes=profiles["all"], pause_cases=sum(case["group"] == "display_pause" for case in cases), item_order_permutations=24,
                  pause_intersections=hidden, original_item_order_differences=original_order_differences,
                  original_removal_differences=removal_differences,
                  weapon_cases=sum(case["group"] == "display_weapon_owner" for case in cases), original_weapon_image_differences=original_weapon_differences,
                  linear_boss_and_door_priority_preserved=True,
                  input_ROM_weapon_images_match_original_transfers=True,
                  original_slot_order_gameplay_preserved=True,
                  scope="Arranged original Z80 routines and V9938 VRAM; separate from ordinary-input campaign verification.")
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
