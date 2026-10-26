"""Check full-fix graphics, asset preservation, boot, and ordinary-input smoke."""
from pathlib import Path
import argparse
import hashlib
import json

from feature_catalog import CATALOG
from patches import SOURCE_SHA256, make_selected_rom
from verify_bugs import script_for
from verify_compact_rom import asset_cases
from verify_emulator import read_rows, run
import verify_emulator

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--openmsx", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "build/expanded-verification")
    args = parser.parse_args()
    source = args.rom.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        parser.error("Unsupported input ROM")
    selected = [fix.id for fix in CATALOG]
    product = make_selected_rom(source, selected)
    target, info, _, _ = product
    assert len(target) == 262144 and info["asset_repack"] is None
    assert target[0x8000:0x20000] == source[0x8000:0x20000]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    fixtures = asset_cases(source)
    captures, vram = {}, {}
    for name, rom, details in (("original", source, {}), ("all", target, info)):
        path, output = out / f"{name}.rom", out / f"{name}.tsv"
        path.write_bytes(rom)
        run(args.openmsx.resolve(), path, script_for(fixtures, output, rom, details), out, name)
        captures[name] = read_rows(output, fixtures)[0]
        vram[name] = output.with_suffix(".vram").read_bytes()
    for pose in range(168):
        assert captures["all"][pose, 1][2:5] == captures["original"][pose, 1][2:5], pose
    assert vram["all"] == vram["original"] and len(vram["all"]) == 131072
    original_variants, original_builder = verify_emulator.VARIANTS, verify_emulator.make_rom
    try:
        verify_emulator.VARIANTS = {"all": (True, True, True)}
        verify_emulator.make_rom = lambda *args, **kwargs: product
        smoke = verify_emulator.smoke_test(args.openmsx.resolve(), source, out)
    finally:
        verify_emulator.VARIANTS, verify_emulator.make_rom = original_variants, original_builder
    report = dict(status="passed", source_sha256=SOURCE_SHA256, rom_sha256=info["rom_sha256"],
                  rom_bytes=len(target), selected_fixes=selected,
                  original_asset_bank_bytes_unchanged=0x18000, asset_banks_unchanged=True,
                  asset_recompression=False, poses_equal=168, item_candle_vram_bytes_equal=131072,
                  resident_bytes=info["helper_bytes"], extension_code_bytes=info["extension_code_bytes"],
                  extension_free_bytes=info["extension_free_bytes"], smoke=smoke,
                  limitations=["function diagnostics and opening-section input test", "not a full campaign or hardware test"])
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS: unchanged asset banks, 168 pose transfers, full item/candle VRAM, ordinary-input opening test.")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
