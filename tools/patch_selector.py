"""Select fixes and generate one IPS. With no arguments, open the selector window."""
from pathlib import Path
import argparse
import locale
import sys

from feature_catalog import CATALOG, resolve_selection
from selection_build import artifact_files, build_selection, read_config, write_files


def default_language():
    language = locale.getlocale()[0] or ""
    return "ja" if language.lower().startswith("ja") else "en"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, nargs="?", help="Supported unmodified 128 KiB ROM")
    parser.add_argument("--lang", choices=("ja", "en"), default=default_language())
    parser.add_argument("--gui", action="store_true", help="Open the checkbox selector")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--enable", nargs="+", metavar="FIX_ID", help="Choose one or more IDs from --list")
    group.add_argument("--all", action="store_true", help="Choose every registered fix")
    group.add_argument("--config", type=Path, help="Load a saved selection JSON")
    parser.add_argument("--list", action="store_true", help="List IDs and descriptions; no ROM needed")
    parser.add_argument("--out", type=Path, help="Output .ips file (also writes .ips.json)")
    parser.add_argument("--save-config", type=Path, help="Save this selection as reusable JSON")
    parser.add_argument("--force", action="store_true", help="Replace existing output files")
    args = parser.parse_args(argv)
    if args.list:
        for fix in CATALOG:
            print(f"{fix.id}: {fix.title(args.lang)}\n{fix.explanation_text(args.lang)}\n")
            if fix.requires:
                print("  requires: " + ", ".join(fix.requires))
            if fix.conflicts:
                print("  conflicts: " + ", ".join(fix.conflicts))
        return 0
    gui = args.gui or (args.rom is None and not any((args.enable, args.all, args.config,
                                                   args.out, args.save_config, args.force)))
    if gui:
        if any((args.enable, args.all, args.config, args.out, args.save_config, args.force)):
            parser.error("Use selection/output arguments in CLI mode, or choose them in the window")
        try:
            from selector_gui import launch
        except ImportError:
            parser.error("The window requires tkinter. Install Python with Tcl/Tk support, or use the CLI")
        launch(args.lang, args.rom)
        return 0
    if args.rom is None or args.out is None:
        parser.error("CLI generation requires an input ROM and --out FILE.ips")
    try:
        ids = (read_config(args.config) if args.config else
               [fix.id for fix in CATALOG] if args.all else args.enable or [])
        selected = resolve_selection(ids)
        artifact = build_selection(args.rom.read_bytes(), [fix.id for fix in selected])
        files = artifact_files(artifact, args.out, args.save_config)
        write_files(files, protected=[args.rom, *([args.config] if args.config else [])],
                    overwrite=args.force)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print("Selected: " + ", ".join(artifact.report["selected_fixes"]))
    print(f"IPS: {args.out} ({len(artifact.patch)} bytes)")
    print(f"ROM: {artifact.report['rom_bytes']} bytes; SHA-256 {artifact.report['rom_sha256']}")
    print(f"Bank 6 free: {artifact.report['bank6_free_bytes']} bytes")
    print(f"Build record: {args.out}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
