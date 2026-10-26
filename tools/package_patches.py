"""Package the ROM-to-IPS generator, sources, documentation, and verification."""
from pathlib import Path
import hashlib
import json
import zipfile
from feature_catalog import CATALOG

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "dist/manifest.json").read_text(encoding="utf-8"))
    report_path = ROOT / "build/verification/report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    compact_path = ROOT / "build/compact-verification/report.json"
    compact = json.loads(compact_path.read_text(encoding="utf-8"))
    shield_path = ROOT / "build/shield-verification/report.json"
    shield = json.loads(shield_path.read_text(encoding="utf-8"))
    selector_path = ROOT / "build/selector-verification/report.json"
    selector = json.loads(selector_path.read_text(encoding="utf-8"))
    if selector["status"] != "passed" or not selector["gui_tested"]:
        raise ValueError("Selector CLI and GUI verification is required")
    bugs_path = ROOT / "build/bug-verification/report.json"
    expanded_path = ROOT / "build/expanded-verification/report.json"
    expanded_shield_path = ROOT / "build/expanded-shield-verification/report.json"
    bugs = json.loads(bugs_path.read_text(encoding="utf-8"))
    expanded = json.loads(expanded_path.read_text(encoding="utf-8"))
    expanded_shield = json.loads(expanded_shield_path.read_text(encoding="utf-8"))
    expected_ids = [fix.id for fix in CATALOG]
    all_build = bugs["profiles"]["all"]
    expected_profiles = {"original", "all", *(fix.id for fix in CATALOG if fix.extended_helpers)}
    if (bugs["status"] != "passed" or expanded["status"] != "passed" or expanded_shield["status"] != "passed"
            or all_build["enabled"] != expected_ids or expanded["selected_fixes"] != expected_ids
            or all_build["rom_sha256"] != expanded["rom_sha256"]
            or all_build["rom_sha256"] != expanded_shield["rom_sha256"]["all"]
            or selector["registered_fixes"] != expected_ids
            or selector["all_fixes_rom_sha256"] != all_build["rom_sha256"]
            or set(bugs["profiles"]) != expected_profiles
            or set(bugs["covered_bug_ids"]) != {bug for fix in CATALOG for bug in fix.bug_ids}):
        raise ValueError("Current all-fixes function, graphics, input, and shield checks are required")
    if not bugs["original_asset_banks_unchanged"] or not expanded["asset_banks_unchanged"]:
        raise ValueError("Expanded builds must retain the original asset banks")
    if shield["status"] != "passed" or not shield["original_zero_to_255_bug_reproduced"]:
        raise ValueError("Shield regression verification is required")
    for name, data in manifest["variants"].items():
        if data["rom_sha256"] != report["rom_sha256"][name]:
            raise ValueError(f"Verification is for a different ROM: {name}")
        if data["rom_sha256"] != compact["rom_sha256"][name] or data["rom_bytes"] != 131072:
            raise ValueError(f"Compact verification is for a different ROM: {name}")
        if data["rom_sha256"] != shield["rom_sha256"][name]:
            raise ValueError(f"Shield verification is for a different ROM: {name}")
        if data["rom_sha256"] != selector["matches_published_patches"][name]:
            raise ValueError(f"Selector verification is for a different ROM: {name}")
    (ROOT / "dist/verification.json").write_bytes(report_path.read_bytes())
    (ROOT / "dist/compact-verification.json").write_bytes(compact_path.read_bytes())
    (ROOT / "dist/shield-verification.json").write_bytes(shield_path.read_bytes())
    (ROOT / "dist/selector-verification.json").write_bytes(selector_path.read_bytes())
    for name, path in (("bug-verification", bugs_path), ("expanded-verification", expanded_path),
                       ("expanded-shield-verification", expanded_shield_path)):
        (ROOT / f"dist/{name}.json").write_bytes(path.read_bytes())
    catalog = dict(format="vampire-killer-ips-catalog-v1", source_sha256=expanded["source_sha256"],
                   all_fixes_rom_sha256=all_build["rom_sha256"],
                   bugs=bugs["covered_bug_ids"],
                   fixes=[dict(id=fix.id, title_ja=fix.title_ja, title_en=fix.title_en,
                               bug_ids=fix.bug_ids, expanded_rom=fix.extended_helpers,
                               description_ja=fix.explanation_text("ja"), description_en=fix.explanation_text("en"))
                          for fix in CATALOG])
    (ROOT / "dist/catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if list((ROOT / "dist").glob("*.ips")):
        raise ValueError("The generator distribution must not contain prebuilt IPS files")
    campaign_path = ROOT / "dist/campaign-verification.json"
    campaign_inputs = ROOT / "dist/campaign-inputs.json.gz"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    if campaign["status"] != "passed" or not campaign["completed_campaign"]:
        raise ValueError("A completed campaign verification is required")
    if campaign["rom_sha256"] != manifest["variants"]["combined"]["rom_sha256"]:
        raise ValueError("Campaign verification is for a different ROM")
    if hashlib.sha256(campaign_inputs.read_bytes()).hexdigest() != campaign["input_archive_sha256"]:
        raise ValueError("Campaign input archive does not match verification")
    files = [ROOT / "README.md", ROOT / "README.en.md", ROOT / "select_patches.pyw",
             *sorted((ROOT / "tools").rglob("*.py")), *sorted((ROOT / "docs").glob("*.md")),
             *sorted((ROOT / "examples").glob("*.json")),
             ROOT / "dist/manifest.json", ROOT / "dist/verification.json", ROOT / "dist/catalog.json",
             ROOT / "dist/compact-verification.json",
             ROOT / "dist/shield-verification.json",
             ROOT / "dist/selector-verification.json",
             ROOT / "dist/bug-verification.json", ROOT / "dist/expanded-verification.json",
             ROOT / "dist/expanded-shield-verification.json",
             campaign_path, campaign_inputs,
             *sorted((ROOT / "docs/images").glob("*"))]
    target = ROOT / "dist/VAMPIREKILLER_MSX_PLUS_generator.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            entry = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all(not name.lower().endswith((".ips", ".rom", ".omr", ".bin", ".dll")) for name in archive.namelist())
    print(f"Packaged {len(files)} files: {target.name} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
