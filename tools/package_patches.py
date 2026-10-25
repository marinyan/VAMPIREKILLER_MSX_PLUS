"""Package verified IPS patches and their complete build/verification sources."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "dist/manifest.json").read_text(encoding="utf-8"))
    report_path = ROOT / "build/verification/report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    compact_path = ROOT / "build/compact-verification/report.json"
    compact = json.loads(compact_path.read_text(encoding="utf-8"))
    for name, data in manifest["variants"].items():
        if data["rom_sha256"] != report["rom_sha256"][name]:
            raise ValueError(f"Verification is for a different ROM: {name}")
        if data["rom_sha256"] != compact["rom_sha256"][name] or data["rom_bytes"] != 131072:
            raise ValueError(f"Compact verification is for a different ROM: {name}")
    (ROOT / "dist/verification.json").write_bytes(report_path.read_bytes())
    (ROOT / "dist/compact-verification.json").write_bytes(compact_path.read_bytes())
    campaign_path = ROOT / "dist/campaign-verification.json"
    campaign_inputs = ROOT / "dist/campaign-inputs.json.gz"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    if campaign["status"] != "passed" or not campaign["completed_campaign"]:
        raise ValueError("A completed campaign verification is required")
    if campaign["rom_sha256"] != manifest["variants"]["combined"]["rom_sha256"]:
        raise ValueError("Campaign verification is for a different ROM")
    if hashlib.sha256(campaign_inputs.read_bytes()).hexdigest() != campaign["input_archive_sha256"]:
        raise ValueError("Campaign input archive does not match verification")
    files = [ROOT / "README.md", *sorted((ROOT / "tools").glob("*.py")),
             *sorted((ROOT / "dist").glob("*.ips")), ROOT / "dist/manifest.json", ROOT / "dist/verification.json",
             ROOT / "dist/compact-verification.json",
             campaign_path, campaign_inputs,
             *sorted((ROOT / "docs/images").glob("*"))]
    target = ROOT / "dist/VAMPIREKILLER_MSX_PLUS_patches.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            entry = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all(not name.lower().endswith((".rom", ".omr")) for name in archive.namelist())
    print(f"Packaged {len(files)} files: {target.name} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
