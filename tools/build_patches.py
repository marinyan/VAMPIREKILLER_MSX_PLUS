"""Build three IPS patches; the original cartridge is never included."""
from pathlib import Path
import argparse
import hashlib
import json
import struct

from patches import VARIANTS, make_rom

ROOT = Path(__file__).resolve().parents[1]


def ips_patch(source, target):
    out = bytearray(b"PATCH")
    offset = 0

    def run_length(start):
        end = start + 1
        while end < len(target) and end - start < 65535 and target[end] == target[start]:
            end += 1
        return end - start

    while offset < len(target):
        if offset < len(source) and source[offset] == target[offset]:
            offset += 1
            continue
        start = offset
        run = run_length(start)
        if run >= 8:
            out.extend(start.to_bytes(3, "big") + b"\0\0" + struct.pack(">H", run) + target[start:start + 1])
            offset += run
            continue
        while offset < len(target) and offset - start < 65535:
            if offset < len(source) and source[offset] == target[offset]:
                break
            if run_length(offset) >= 8:
                break
            offset += 1
        block = target[start:offset]
        out.extend(start.to_bytes(3, "big"))
        if len(block) > 3 and len(set(block)) == 1:
            out.extend(b"\0\0" + struct.pack(">H", len(block)) + block[:1])
        else:
            out.extend(struct.pack(">H", len(block)) + block)
    out.extend(b"EOF")
    return bytes(out)


def apply_ips(source, patch):
    if not patch.startswith(b"PATCH"):
        raise ValueError("Invalid IPS header")
    result, p = bytearray(source), 5
    while patch[p:p + 3] != b"EOF":
        offset = int.from_bytes(patch[p:p + 3], "big")
        size = int.from_bytes(patch[p + 3:p + 5], "big")
        p += 5
        if size:
            data = patch[p:p + size]
            p += size
        else:
            count = int.from_bytes(patch[p:p + 2], "big")
            data = patch[p + 2:p + 3] * count
            p += 3
        if len(result) < offset + len(data):
            result.extend(bytes(offset + len(data) - len(result)))
        result[offset:offset + len(data)] = data
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="Unmodified 128 KiB Japanese cartridge dump")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--rom-out", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    source = args.rom.read_bytes()
    # Validate before creating output directories.
    variants = [(name, *make_rom(source, fall=flags[0], edges=flags[1])) for name, flags in VARIANTS.items()]
    args.out.mkdir(parents=True, exist_ok=True)
    args.rom_out.mkdir(parents=True, exist_ok=True)
    manifest = {"format": "IPS", "variants": {}}
    for name, target, info, code, loader in variants:
        patch = ips_patch(source, target)
        if apply_ips(source, patch) != target:
            raise RuntimeError(f"IPS round-trip failed: {name}")
        (args.out / f"{name}.ips").write_bytes(patch)
        (args.rom_out / f"{name}.rom").write_bytes(target)
        (args.rom_out / f"{name}.asm").write_text("\n".join(loader.lines + code.lines) + "\n", encoding="utf-8")
        info["ips_sha256"] = hashlib.sha256(patch).hexdigest()
        info["ips_bytes"] = len(patch)
        manifest["variants"][name] = info
        print(f"{name}: IPS {len(patch)} B; ROM {len(target)} B; helpers {info['helper_bytes']} B")
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
