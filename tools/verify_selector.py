"""Check selector output compatibility, CLI/GUI workflows, and extension guards."""
from pathlib import Path
from itertools import permutations
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from build_patches import apply_ips
from feature_catalog import CATALOG, legacy_selection, resolve_selection
from fixes import Fix
from patches import (OUTPUT_SIZE, RAM_BASE, SOURCE_SHA256, VARIANTS,
                     make_selected_rom)
from selection_build import (artifact_files, build_selection, json_bytes, read_config,
                             selection_config, write_files)

ROOT = Path(__file__).resolve().parents[1]


def dummy(fix_id, **kwargs):
    return Fix(fix_id, fix_id, fix_id, fix_id, fix_id, **kwargs)


class SelectorChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="selector-", dir=ROOT / "build")
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)

    def cli(self, *args, success=True):
        environment = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/patch_selector.py"),
                                 *map(str, args)], capture_output=True, text=True,
                                encoding="utf-8", env=environment, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def test_all_existing_selections_and_input_order(self):
        for name, flags in VARIANTS.items():
            ids = legacy_selection(*flags)
            expected = self.manifest[name]["ips_sha256"]
            for order in permutations(ids):
                artifact = build_selection(self.source, order)
                self.assertEqual(hashlib.sha256(artifact.patch).hexdigest(), expected, (name, order))
                self.assertEqual(len(apply_ips(self.source, artifact.patch)), OUTPUT_SIZE)
                self.assertEqual(artifact.report["rom_sha256"], self.manifest[name]["rom_sha256"])

    def test_cli_every_existing_selection(self):
        for name, flags in VARIANTS.items():
            target = self.folder / (name + ".ips")
            self.cli(self.rom_path, "--enable", *legacy_selection(*flags), "--out", target)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), self.manifest[name]["ips_sha256"])
            record = json.loads(Path(str(target) + ".json").read_text(encoding="utf-8"))
            self.assertEqual(record["rom_sha256"], self.manifest[name]["rom_sha256"])

    def test_cli_all_and_config_replay(self):
        first, second = self.folder / "選択版.ips", self.folder / "replayed.ips"
        config = self.folder / "選択内容.json"
        self.cli(self.rom_path, "--all", "--out", first, "--save-config", config)
        self.cli(self.rom_path, "--config", config, "--out", second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        record = json.loads(Path(str(first) + ".json").read_text(encoding="utf-8"))
        report = ROOT / "build/bug-verification/report.json"
        if not report.exists():
            report = ROOT / "dist/bug-verification.json"
        expected = json.loads(report.read_text(encoding="utf-8"))["profiles"]["all"]
        self.assertEqual(record["rom_sha256"], expected["rom_sha256"])
        patched = apply_ips(self.source, first.read_bytes())
        self.assertEqual(len(patched), 262144)
        self.assertEqual(patched[0x8000:0x20000], self.source[0x8000:0x20000])

    def test_saved_legacy_selection_does_not_add_new_fixes(self):
        target = self.folder / "legacy.ips"
        self.cli(self.rom_path, "--config", ROOT / "examples/selection.json", "--out", target)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), self.manifest["combined_shield"]["ips_sha256"])
        record = json.loads(Path(str(target) + ".json").read_text(encoding="utf-8"))
        self.assertEqual(record["selected_fixes"], ["fall_attack", "screen_edges", "shield_fix"])
        self.assertEqual(record["rom_bytes"], 131072)

    def test_build_records_do_not_embed_rom_data(self):
        for ids in (["fall_attack", "screen_edges", "shield_fix"], [fix.id for fix in CATALOG]):
            record = build_selection(self.source, ids).report
            for change in record["changes"]:
                self.assertNotIn("before", change)
                self.assertNotIn("after", change)

    def test_cli_list_does_not_need_rom(self):
        for language in ("ja", "en"):
            result = self.cli("--list", "--lang", language)
            for fix in CATALOG:
                self.assertIn(fix.title(language), result.stdout)
                self.assertIn(fix.explanation_text(language), result.stdout)

    def test_registered_fixes_have_complete_bug_explanations(self):
        for fix in CATALOG:
            self.assertIsNotNone(fix.explanation, fix.id)
            for language in ("ja", "en"):
                for section in ("symptom", "trigger", "correction"):
                    self.assertTrue(getattr(fix.explanation, f"{section}_{language}").strip(), (fix.id, section, language))
                self.assertGreater(len(fix.explanation_text(language)), len(fix.description(language)))

    def test_cli_invalid_inputs_do_not_write(self):
        wrong = self.folder / "wrong.rom"
        wrong.write_bytes(bytes(OUTPUT_SIZE))
        unknown_config = self.folder / "unknown.json"
        unknown_config.write_bytes(json_bytes({"schema": 1, "fixes": ["unknown"]}))
        target = self.folder / "absent" / "custom.ips"
        for args in ((wrong, "--all"), (self.rom_path, "--enable", "unknown"),
                     (self.rom_path,), (self.rom_path, "--config", unknown_config)):
            self.cli(*args, "--out", target, success=False)
            self.assertFalse(target.parent.exists())

    def test_cli_requires_explicit_overwrite(self):
        target = self.folder / "chosen.ips"
        self.cli(self.rom_path, "--all", "--out", target)
        before = {path: path.read_bytes() for path in self.folder.iterdir()}
        self.cli(self.rom_path, "--enable", "shield_fix", "--out", target, success=False)
        self.assertEqual(before, {path: path.read_bytes() for path in self.folder.iterdir()})
        self.cli(self.rom_path, "--enable", "shield_fix", "--out", target, "--force")
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), self.manifest["shield_fix"]["ips_sha256"])

    def test_input_cannot_be_output_even_with_force(self):
        source = self.folder / "source.ips"
        source.write_bytes(self.source)
        self.cli(source, "--all", "--out", source, "--force", success=False)
        self.assertEqual(source.read_bytes(), self.source)
        self.assertFalse(Path(str(source) + ".json").exists())

    def test_source_revision_guards(self):
        for source in (self.source[:-1], bytes(OUTPUT_SIZE),
                       apply_ips(self.source, build_selection(self.source, ["fall_attack", "screen_edges", "shield_fix"]).patch)):
            with self.assertRaisesRegex(ValueError, "Unsupported input ROM"):
                build_selection(source, ["shield_fix"])

    def test_dependency_closure_and_stable_order(self):
        catalog = (dummy("dependent", requires=("shared",)), dummy("independent"), dummy("shared"))
        ids = lambda requested: [fix.id for fix in resolve_selection(requested, catalog)]
        self.assertEqual(ids(["dependent"]), ["shared", "dependent"])
        self.assertEqual(ids(["independent", "dependent"]), ids(["dependent", "independent"]))

    def test_invalid_catalogs_and_conflicts(self):
        cases = (([], CATALOG, "at least"), (["unknown"], CATALOG, "Unknown fix"),
                 (["a"], (dummy("a"), dummy("a")), "duplicate"),
                 (["a"], (dummy("a", requires=("missing",)),), "Unknown reference"),
                 (["a"], (dummy("a", requires=("b",)), dummy("b", requires=("a",))), "cycle"),
                 (["a", "b"], (dummy("a", conflicts=("b",)), dummy("b")), "Conflicting"))
        for ids, catalog, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                resolve_selection(ids, catalog)

    def test_add_twenty_inline_fixes_without_combination_table(self):
        def inline(index):
            def apply(edit, hook, code):
                offset = 0x1000 + index
                edit(offset, self.source[offset:offset + 1], bytes([self.source[offset] ^ 1]), "Synthetic inline fixture")
            return dummy(f"fixture_{index}", apply=apply)
        catalog = tuple(inline(index) for index in range(20))
        target, info, _, _ = make_selected_rom(self.source, [fix.id for fix in catalog], catalog=catalog)
        self.assertEqual(len(target), OUTPUT_SIZE)
        self.assertEqual(info["helper_bytes"], 0)
        self.assertEqual(info["ram_chunks"], [])
        self.assertEqual(len(info["selected_fixes"]), 20)
        self.assertEqual(target[0x1000:0x1014], bytes(value ^ 1 for value in self.source[0x1000:0x1014]))

    def test_overlapping_edits_are_rejected_even_if_bytes_match(self):
        def apply(edit, hook, code):
            edit(0x1000, self.source[0x1000:0x1001], self.source[0x1000:0x1001], "Same bytes")
        with self.assertRaisesRegex(ValueError, "Overlapping ROM edits: a and b"):
            make_selected_rom(self.source, ["a", "b"], catalog=(dummy("a", apply=apply), dummy("b", apply=apply)))

    def test_core_overlap_and_hook_revision_are_rejected(self):
        for offset, expected, replacement, message in ((0xA9, self.source[0xA9:0xAC], b"\0\0\0", "Overlapping"),
                                                       (0x1000, bytes([self.source[0x1000] ^ 1]), b"\0", "Hook mismatch"),
                                                       (OUTPUT_SIZE, b"", b"\0", "Out-of-range")):
            def apply(edit, hook, code):
                edit(offset, expected, replacement, "Invalid fixture")
            with self.assertRaisesRegex(ValueError, message):
                make_selected_rom(self.source, ["a"], catalog=(dummy("a", apply=apply),))

    def test_rom_ram_capacity_and_segment_overlap(self):
        def rom_overflow(c):
            c.emit("00 " * 3000, "fixture")
        def ram_overflow(c):
            c.org(0xE7FF)
            c.emit("00 00", "fixture")
        def overlap(c):
            c.emit("00", "fixture")
            c.org(RAM_BASE)
            c.emit("00", "fixture")
        for emit, message in ((rom_overflow, "bank 6 storage"), (ram_overflow, "reserved RAM"),
                              (overlap, "Overlapping resident")):
            with self.assertRaisesRegex(ValueError, message):
                make_selected_rom(self.source, ["a"], catalog=(dummy("a", emit_helpers=emit),))

    def test_config_schema_and_utf8_bom(self):
        config = self.folder / "config.json"
        config.write_text(json.dumps(selection_config(["shield_fix"])), encoding="utf-8-sig")
        self.assertEqual(read_config(config), ["shield_fix"])
        for bad in ({}, {"schema": True, "fixes": ["shield_fix"]}, {"schema": 2, "fixes": ["shield_fix"]},
                    {"schema": 1, "fixes": "shield_fix"}, {"schema": 1, "fixes": []},
                    {"schema": 1, "fixes": ["unknown"]}, {"schema": 1, "fixes": [1]}):
            config.write_bytes(json_bytes(bad))
            with self.assertRaises(ValueError):
                read_config(config)

    def test_output_collisions_and_extension_guard(self):
        artifact = build_selection(self.source, ["shield_fix"])
        output = self.folder / "chosen.ips"
        with self.assertRaises(ValueError):
            artifact_files(artifact, output.with_suffix(".rom"))
        with self.assertRaises(ValueError):
            artifact_files(artifact, output, output)
        with self.assertRaises(ValueError):
            write_files(artifact_files(artifact, output), protected=[output], overwrite=True)
        self.assertFalse(output.exists())


class WindowChecks(SelectorChecks):
    # The inherited CLI/core checks are loaded only once by the suite below.
    def setUp(self):
        super().setUp()
        import tkinter as tk
        from selector_gui import SelectorWindow
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.window = SelectorWindow(self.root, "ja", self.rom_path)
        self.root.update_idletasks()

    def test_window_selection_and_both_languages(self):
        self.assertEqual(len(self.window.selected_ids()), len(CATALOG))
        self.window.clear.invoke()
        self.assertFalse(self.window.selected_ids())
        self.assertTrue(self.window.generate.instate(["disabled"]))
        self.window.labels["shield_fix"][0].invoke()
        self.assertEqual(self.window.selected_ids(), ["shield_fix"])
        self.assertTrue(self.window.generate.instate(["!disabled"]))
        self.window.lang_choice.set("English")
        self.window.change_language()
        self.assertEqual(self.window.generate.cget("text"), "Generate IPS…")
        self.assertEqual(self.window.labels["shield_fix"][0].cget("text"), CATALOG[2].title_en)

    def test_window_generate_save_reload_and_invalid_rom(self):
        output, config = self.folder / "gui.ips", self.folder / "gui.json"
        self.window.set_selection(["fall_attack", "shield_fix"])
        with patch("selector_gui.filedialog.asksaveasfilename", return_value=str(config)):
            self.window.save.invoke()
        self.window.clear.invoke()
        with patch("selector_gui.filedialog.askopenfilename", return_value=str(config)):
            self.window.load.invoke()
        self.assertEqual(self.window.selected_ids(), ["fall_attack", "shield_fix"])
        with patch("selector_gui.filedialog.asksaveasfilename", return_value=str(output)), \
             patch("selector_gui.messagebox.showinfo") as success:
            self.window.generate.invoke()
        self.assertTrue(success.called)
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), self.manifest["fall_attack_shield"]["ips_sha256"])
        wrong = self.folder / "wrong.rom"
        wrong.write_bytes(bytes(OUTPUT_SIZE))
        self.window.rom.set(str(wrong))
        with patch("selector_gui.messagebox.showerror") as error, \
             patch("selector_gui.filedialog.asksaveasfilename") as dialog:
            self.window.generate.invoke()
        self.assertTrue(error.called)
        self.assertFalse(dialog.called)

    def test_window_layout_and_long_catalog_scroll(self):
        self.root.deiconify()
        for language in ("ja", "en"):
            self.window.language = language
            self.window.render_language()
            self.root.geometry("700x580")
            self.root.update()
            self.assertLessEqual(self.window.heading.winfo_x() + self.window.heading.winfo_width(),
                                 self.window.lang_choice.winfo_x())
            self.assertGreater(self.window.canvas.winfo_height(), 50)
            self.assertLessEqual(self.window.hint.winfo_rooty() + self.window.hint.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())
        import tkinter as tk
        from selector_gui import SelectorWindow
        catalog = tuple(dummy(f"fixture_{index}") for index in range(20))
        extended = tk.Toplevel(self.root)
        self.addCleanup(extended.destroy)
        with patch("selector_gui.CATALOG", catalog), \
             patch("selector_gui.resolve_selection", side_effect=lambda ids: resolve_selection(ids, catalog)):
            window = SelectorWindow(extended, "en")
            extended.update()
            self.assertEqual(len(window.labels), 20)
            self.assertGreater(window.canvas.bbox("all")[3], window.canvas.winfo_height())
            window.canvas.yview_moveto(1)
            self.assertGreater(window.canvas.yview()[0], 0)

    def test_window_hover_tip_and_cleanup(self):
        fix = CATALOG[0]
        checkbox = self.window.labels[fix.id][0]
        helper = self.window.help
        self.assertTrue(checkbox.bind("<Enter>"))
        helper.schedule(checkbox, lambda: fix.explanation_text("ja"))
        token = helper.pending
        self.assertTrue(self.root.tk.call("after", "info", token))
        helper.show_tip(checkbox, fix.explanation_text("ja"))
        self.assertIsNone(helper.pending)
        self.assertEqual(helper.tip_text.get("1.0", "end-1c"), fix.explanation_text("ja"))
        self.assertEqual(str(helper.tip_text.cget("state")), "disabled")
        tip = helper.tip
        helper.hide()
        self.assertFalse(tip.winfo_exists())
        self.assertIsNone(helper.tip)

    def test_window_details_full_text_and_language_change(self):
        before = self.window.selected_ids()
        self.window.detail_buttons["shield_fix"].invoke()
        helper = self.window.help
        self.assertEqual(before, self.window.selected_ids())
        self.assertEqual(helper.detail_text.get("1.0", "end-1c"), CATALOG[2].explanation_text("ja"))
        self.assertEqual(str(helper.detail_text.cget("state")), "disabled")
        self.window.lang_choice.set("English")
        self.window.change_language()
        self.assertEqual(helper.detail_text.get("1.0", "end-1c"), CATALOG[2].explanation_text("en"))
        self.assertEqual(helper.detail_close.cget("text"), "Close")
        helper.detail_close.invoke()
        self.assertFalse(helper.detail_window.winfo_exists())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "build/selector-verification")
    parser.add_argument("--skip-gui", action="store_true", help="For systems without Tcl/Tk or a display")
    args = parser.parse_args()
    source = args.rom.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        parser.error("Unsupported input ROM")
    (ROOT / "build").mkdir(exist_ok=True)
    SelectorChecks.source = source
    SelectorChecks.rom_path = args.rom.resolve()
    SelectorChecks.manifest = json.loads((ROOT / "dist/manifest.json").read_text(encoding="utf-8"))["variants"]
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SelectorChecks)
    if not args.skip_gui:
        for name in ("test_window_selection_and_both_languages", "test_window_generate_save_reload_and_invalid_rom",
                     "test_window_layout_and_long_catalog_scroll", "test_window_hover_tip_and_cleanup",
                     "test_window_details_full_text_and_language_change"):
            suite.addTest(WindowChecks(name))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    campaign_config = ROOT / "examples/verified-campaign-29.json"
    campaign_record = json.loads((ROOT / "dist/expanded-route-verification.json").read_text(encoding="utf-8"))
    verified_campaign_hash = build_selection(source, read_config(campaign_config)).report["rom_sha256"]
    if verified_campaign_hash != campaign_record["rom_sha256"]:
        raise ValueError("The frozen campaign configuration no longer reproduces its verified ROM")
    report = dict(status="passed" if result.wasSuccessful() else "failed", tests=result.testsRun,
                  gui_tested=not args.skip_gui, source_sha256=SOURCE_SHA256,
                  registered_fixes=[fix.id for fix in CATALOG],
                  all_fixes_rom_sha256=build_selection(source, [fix.id for fix in CATALOG]).report["rom_sha256"],
                  matches_published_patches={name: data["rom_sha256"] for name, data in SelectorChecks.manifest.items()},
                  verified_campaign_rom_sha256=verified_campaign_hash,
                  synthetic_inline_extension_fixes=20)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_bytes(json_bytes(report))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
