"""Check IPS round trips, patch scope, determinism, and revision guards."""
from pathlib import Path
import argparse
import hashlib
import json

from build_patches import apply_ips, ips_patch
from patches import VARIANTS, make_rom, SOURCE_SHA256, RAM_BASE, RAM_END, SIDE_BASE, SIDE_END, OUTPUT_SIZE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--dist", type=Path, default=Path(__file__).resolve().parents[1] / "dist")
    args = parser.parse_args()
    source = args.rom.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA256
    manifest = json.loads((args.dist / "manifest.json").read_text(encoding="utf-8"))
    for name, (fall, edges, shield) in VARIANTS.items():
        target, info, _, _ = make_rom(source, fall=fall, edges=edges, shield=shield)
        patch = ips_patch(source, target)
        assert hashlib.sha256(patch).hexdigest() == manifest["variants"][name]["ips_sha256"], name
        assert apply_ips(source, patch) == target, name
        assert manifest["variants"][name]["rom_sha256"] == info["rom_sha256"], name
        touched = set()
        for change in info["changes"]:
            touched.update(range(change["offset"], change["offset"] + change["size"]))
        assert all(a == b or index in touched for index, (a, b) in enumerate(zip(source, target))), name
        assert info["helper_start"] == RAM_BASE and info["helper_end"] <= RAM_END, name
        assert len(patch) < 4096 and len(target) == OUTPUT_SIZE == len(source) == 131072, name
        assert info["asset_repack"]["all_atlas_bytes_equal"]
        assert info["asset_repack"]["poses"]["all_decoded_parts_equal"]
        for chunk in info["ram_chunks"]:
            assert (RAM_BASE <= chunk["address"] < RAM_END and chunk["address"] + chunk["size"] <= RAM_END or
                    SIDE_BASE <= chunk["address"] < SIDE_END and chunk["address"] + chunk["size"] <= SIDE_END)
        for invalid in (source[:-1], bytes([source[0] ^ 1]) + source[1:], target):
            try:
                make_rom(invalid, fall=fall, edges=edges, shield=shield)
            except ValueError:
                pass
            else:
                raise AssertionError("Revision guard accepted unsupported ROM")
        print(f"PASS {name}: IPS round trip, deterministic build, scoped changes, input guard")


if __name__ == "__main__":
    main()
