"""Package verified IPS patches and their complete build/verification sources."""
from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "dist/manifest.json").read_text(encoding="utf-8"))
    report_path = ROOT / "build/verification/report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for name, data in manifest["variants"].items():
        if data["rom_sha256"] != report["rom_sha256"][name]:
            raise ValueError(f"Verification is for a different ROM: {name}")
    (ROOT / "dist/verification.json").write_bytes(report_path.read_bytes())
    files = [ROOT / "README.md", *sorted((ROOT / "tools").glob("*.py")),
             *sorted((ROOT / "dist").glob("*.ips")), ROOT / "dist/manifest.json", ROOT / "dist/verification.json",
             *sorted((ROOT / "docs/images").glob("*"))]
    target = ROOT / "dist/VAMPIREKILLER_MSX_PLUS_patches.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            entry = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all(not name.lower().endswith(".rom") for name in archive.namelist())
    print(f"Packaged {len(files)} files: {target.name} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
