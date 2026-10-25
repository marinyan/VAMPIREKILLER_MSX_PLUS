"""Verify the 1 Mbit layout against original graphics and prior gameplay captures."""
from pathlib import Path
import argparse
import hashlib
import json
import struct

from compact_assets import ATLAS_START, ATLAS_END, POSE_TABLE, decode_pose, physical, repack, unpack_lz
from patches import VARIANTS, make_rom
from verify_emulator import run, tcl_script, read_rows, cases

ROOT = Path(__file__).resolve().parents[1]


def asset_cases(source):
    pointers = struct.unpack("<168H", source[physical(POSE_TABLE):physical(POSE_TABLE) + 336])
    unique = sorted(set(pointers))
    ends = dict(zip(unique, unique[1:] + [ATLAS_START]))
    result = []
    for pose, address in enumerate(pointers):
        parts = decode_pose(source[physical(address):physical(ends[address])])
        raw = bytearray(128)
        raw[0], raw[3], raw[5], raw[11], raw[32] = 1, 160, 128, pose, len(parts)
        for part in range(len(parts)):
            raw[33 + part * 5], raw[37 + part * 5] = part, 2 if part % 2 == 0 else 76
        result.append(dict(name=f"pose-{pose}", group="pose", player=bytes(80).hex(),
                           memory={0xC800: raw.hex()}, steps=[(0x6445, {}, {"IX": 0xC800}), (0x64EC, {}, {})],
                           registers={}, tiles=[], metadata={}))
    result.append(dict(name="item-candle-upload", group="asset_vram", player=bytes(80).hex(),
                       memory={}, steps=[(0x548D, {}, {})], registers={}, tiles=[], metadata={}))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--openmsx", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "build/compact-verification")
    parser.add_argument("--baseline", type=Path, help="Optional previous release captures (same gameplay fixture set)")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = args.rom.read_bytes()
    table, poses, compressed, static = repack(source)
    assert unpack_lz(compressed) == source[physical(ATLAS_START):physical(ATLAS_END)]
    fixtures = asset_cases(source)
    captures, vram, hashes = {}, {}, {}
    for name in ("original", *VARIANTS):
        rom = source if name == "original" else make_rom(source, fall=VARIANTS[name][0], edges=VARIANTS[name][1], shield=VARIANTS[name][2])[0]
        assert len(rom) == 131072
        rompath, output = out / f"{name}.rom", out / f"{name}.tsv"
        rompath.write_bytes(rom)
        run(args.openmsx.resolve(), rompath, tcl_script(fixtures, output), out, name)
        captures[name] = read_rows(output, fixtures)[0]
        vram[name] = output.with_suffix(".vram").read_bytes()
        hashes[name] = hashlib.sha256(rom).hexdigest()
        if name != "original":
            for pose in range(168):
                actual, reference = captures[name][pose, 1], captures["original"][pose, 1]
                assert actual[2:5] == reference[2:5], (name, pose, "pose state/SAT/colors differ")
            assert len(vram[name]) == 131072 and vram[name] == vram["original"], (name, "item/candle VRAM differs")
        print(f"PASS {name}: 168 pose transfers and item/candle upload captured", flush=True)
    baseline_result = None
    if args.baseline:
        gameplay_fixtures = cases()
        baseline_result = {}
        for name in VARIANTS:
            if VARIANTS[name][2] and not (args.baseline / f"{name}.tsv").exists():
                continue
            old, _ = read_rows(args.baseline / f"{name}.tsv", gameplay_fixtures)
            new, _ = read_rows(ROOT / "build/verification" / f"{name}.tsv", gameplay_fixtures)
            assert old.keys() == new.keys()
            for key in old:
                # Data state/display buffers; CPU flag scratch is not part of the gameplay contract.
                assert old[key][:6] + old[key][7:] == new[key][:6] + new[key][7:], (name, key, "previous release state differs")
            baseline_result[name] = dict(observations=len(old), all_game_state_and_display_buffers_equal=True)
    report = dict(rom_bytes=131072, rom_sha256=hashes, lossless_asset_repack=static,
                  poses_per_rom=168, item_candle_vram_bytes=131072, all_graphics_equal=True,
                  previous_release_comparison=baseline_result,
                  limitations=["arranged function diagnostics", "not hardware or full-campaign verification"])
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
