"""Local checkbox interface; the fix catalog supplies every selectable row."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from feature_catalog import CATALOG, resolve_selection
from selector_help import HelpPopup
from selection_build import (artifact_files, build_selection, json_bytes, read_config,
                             selection_config, write_files)

TEXT = {
    "ja": {
        "heading": "使いたい修正を選んで、IPSを1枚生成",
        "intro": "無改変の原ROMを指定してください。処理はすべてこのPC内で行います。",
        "source": "原ROM", "browse": "参照…", "fixes": "修正項目とバグ説明",
        "help": "項目にマウスを重ねるとバグ説明を表示します。「詳細」でも全文を読めます。",
        "details": "詳細…", "close": "閉じる",
        "all": "すべて選択", "none": "選択を解除", "load": "選択を読込…",
        "save": "選択を保存…", "generate": "IPSを生成…",
        "count": "{count}項目を選択中 · 出力ROMは{size}",
        "empty": "修正を1つ以上選んでください。",
        "hint": "生成したIPSを、無改変ROMのコピーに1つだけ適用してください。",
        "error": "生成できません", "source_missing": "原ROMを指定してください。",
        "rom_dialog": "無改変の原ROMを選択", "ips_dialog": "IPSの保存先",
        "config_dialog": "選択内容のJSON", "overwrite": "ファイルの置換",
        "overwrite_body": "次のファイルを置き換えますか？\n\n{files}",
        "saved": "選択内容を保存しました。",
        "success": "IPSを生成しました",
        "result": "{names}\n\nIPS: {path}\n適用後: {size:,}バイト\n追加コード領域の空き: {free}バイト\n\n選択内容とハッシュは {record} に保存しました。",
    },
    "en": {
        "heading": "Choose fixes and generate one IPS",
        "intro": "Choose an unmodified source ROM. All processing stays on this computer.",
        "source": "Source ROM", "browse": "Browse…", "fixes": "Fixes and bug descriptions",
        "help": "Hover over an item to read its bug description, or open Details for the full text.",
        "details": "Details…", "close": "Close",
        "all": "Select all", "none": "Clear", "load": "Load selection…",
        "save": "Save selection…", "generate": "Generate IPS…",
        "count": "{count} items selected · Output ROM: {size}",
        "empty": "Select at least one fix.",
        "hint": "Apply the generated IPS once to a copy of the unmodified ROM.",
        "error": "Unable to generate", "source_missing": "Choose a source ROM first.",
        "rom_dialog": "Choose the unmodified source ROM", "ips_dialog": "Save IPS",
        "config_dialog": "Selection JSON", "overwrite": "Replace files",
        "overwrite_body": "Replace these existing files?\n\n{files}",
        "saved": "Selection saved.",
        "success": "IPS generated",
        "result": "{names}\n\nIPS: {path}\nPatched ROM: {size:,} bytes\nFree code storage: {free} bytes\n\nSelection and hashes saved in {record}.",
    },
}


class SelectorWindow:
    def __init__(self, root, language="ja", source=None):
        self.root, self.language = root, language
        root.title("VAMPIRE KILLER MSX PLUS — IPS Selector")
        root.geometry("820x670")
        root.minsize(700, 580)
        self.rom = tk.StringVar(value=str(source) if source else "")
        self.status = tk.StringVar()
        self.variables = {fix.id: tk.BooleanVar(value=True) for fix in CATALOG}
        self.labels, self.descriptions = {}, []
        self.detail_buttons = {}
        self.detail_fix = None
        self.help = HelpPopup(root)

        main = ttk.Frame(root, padding=24)
        main.pack(fill="both", expand=True)
        top = ttk.Frame(main)
        top.pack(fill="x")
        self.heading = ttk.Label(top, font=("Yu Gothic UI", 17, "bold"))
        self.heading.pack(side="left")
        self.lang_choice = ttk.Combobox(top, state="readonly", values=("日本語", "English"), width=10)
        self.lang_choice.set("日本語" if language == "ja" else "English")
        self.lang_choice.pack(side="right")
        self.lang_choice.bind("<<ComboboxSelected>>", self.change_language)
        self.intro = ttk.Label(main)
        self.intro.pack(anchor="w", pady=(10, 20))

        source_row = ttk.Frame(main)
        source_row.pack(fill="x")
        self.source_label = ttk.Label(source_row, width=11)
        self.source_label.pack(side="left")
        ttk.Entry(source_row, textvariable=self.rom).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.browse = ttk.Button(source_row, command=self.choose_rom)
        self.browse.pack(side="right")

        self.fix_frame = ttk.LabelFrame(main, padding=10)
        self.fix_frame.pack(fill="both", expand=True, pady=20)
        controls = ttk.Frame(self.fix_frame)
        controls.pack(fill="x", pady=(0, 10))
        self.select_all = ttk.Button(controls, command=lambda: self.set_selection([fix.id for fix in CATALOG]))
        self.select_all.pack(side="left")
        self.clear = ttk.Button(controls, command=lambda: self.set_selection([]))
        self.clear.pack(side="left", padx=6)
        self.help_hint = ttk.Label(self.fix_frame, wraplength=620)
        self.help_hint.pack(anchor="w", pady=(0, 10))
        self.canvas = tk.Canvas(self.fix_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.fix_frame, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        rows = ttk.Frame(self.canvas)
        self.row_window = self.canvas.create_window(0, 0, window=rows, anchor="nw")
        rows.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self.resize_rows)
        # Bind only this window; a longer catalog stays scrollable without resizing it.
        root.bind("<MouseWheel>", self.scroll_rows)
        root.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-1, "units"))
        root.bind("<Button-5>", lambda event: self.canvas.yview_scroll(1, "units"))
        for fix in CATALOG:
            row = ttk.Frame(rows, padding=(5, 5, 5, 12))
            row.pack(fill="x")
            title_row = ttk.Frame(row)
            title_row.pack(fill="x")
            checkbox = ttk.Checkbutton(title_row, variable=self.variables[fix.id], command=self.selection_changed)
            checkbox.pack(side="left")
            checkbox.bind("<FocusIn>", lambda event, item=row: self.reveal_row(item))
            checkbox.bind("<F1>", lambda event, item=fix: self.show_details(item))
            details = ttk.Button(title_row, command=lambda item=fix: self.show_details(item))
            details.pack(side="right")
            self.detail_buttons[fix.id] = details
            description = ttk.Label(row, wraplength=620, justify="left")
            description.pack(anchor="w", padx=(23, 0), pady=(4, 0))
            self.labels[fix.id] = (checkbox, description)
            self.descriptions.append(description)
            self.help.bind(checkbox, lambda item=fix: item.explanation_text(self.language))
            self.help.bind(description, lambda item=fix: item.explanation_text(self.language))

        self.status_label = ttk.Label(main, textvariable=self.status, wraplength=740)
        self.status_label.pack(anchor="w")
        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=(16, 12))
        self.load = ttk.Button(actions, command=self.load_selection)
        self.load.pack(side="left")
        self.save = ttk.Button(actions, command=self.save_selection)
        self.save.pack(side="left", padx=8)
        self.generate = ttk.Button(actions, command=self.generate_patch)
        self.generate.pack(side="right", ipadx=18, ipady=5)
        self.hint = ttk.Label(main, wraplength=740)
        self.hint.pack(anchor="w")
        self.render_language()

    def tr(self, key, **values):
        return TEXT[self.language][key].format(**values)

    def render_language(self):
        self.heading.configure(text=self.tr("heading"))
        self.intro.configure(text=self.tr("intro"))
        self.source_label.configure(text=self.tr("source"))
        self.fix_frame.configure(text=self.tr("fixes"))
        self.help_hint.configure(text=self.tr("help"))
        self.help.hide()
        self.hint.configure(text=self.tr("hint"))
        for widget, key in ((self.browse, "browse"), (self.select_all, "all"), (self.clear, "none"),
                            (self.load, "load"), (self.save, "save"), (self.generate, "generate")):
            widget.configure(text=self.tr(key))
        for fix in CATALOG:
            checkbox, description = self.labels[fix.id]
            checkbox.configure(text=fix.title(self.language))
            description.configure(text=fix.description(self.language))
            self.detail_buttons[fix.id].configure(text=self.tr("details"))
        if self.detail_fix is not None and self.help.detail_window is not None and self.help.detail_window.winfo_exists():
            self.show_details(self.detail_fix)
        self.selection_changed()

    def change_language(self, event=None):
        self.language = "ja" if self.lang_choice.get() == "日本語" else "en"
        self.render_language()

    def resize_rows(self, event):
        self.help.hide()
        self.canvas.itemconfigure(self.row_window, width=event.width)
        self.help_hint.configure(wraplength=max(200, event.width))
        for description in self.descriptions:
            description.configure(wraplength=max(200, event.width - 48))

    def scroll_rows(self, event):
        self.help.hide()
        if self.canvas.bbox("all") and self.canvas.bbox("all")[3] > self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def reveal_row(self, row):
        """Keep a checkbox reached with Tab visible above its long explanation."""
        bounds = self.canvas.bbox("all")
        if bounds and bounds[3]:
            top = self.canvas.canvasy(0)
            if not top <= row.winfo_y() < top + self.canvas.winfo_height() - 24:
                self.canvas.yview_moveto(row.winfo_y() / bounds[3])

    def show_details(self, fix):
        self.detail_fix = fix
        return self.help.show_details(fix.title(self.language), fix.explanation_text(self.language), self.tr("close"))

    def selected_ids(self):
        return [fix_id for fix_id, variable in self.variables.items() if variable.get()]

    def set_selection(self, feature_ids):
        selected = set(feature_ids)
        for fix_id, variable in self.variables.items():
            variable.set(fix_id in selected)
        self.selection_changed()

    def selection_changed(self):
        ids = self.selected_ids()
        try:
            chosen = resolve_selection(ids)
            for fix in chosen:
                self.variables[fix.id].set(True)
            expanded = any(fix.extended_helpers for fix in chosen)
            size = "2 Mbit (256 KiB)" if expanded else "1 Mbit (128 KiB)"
            self.status.set(self.tr("count", count=len(chosen), size=size))
            self.generate.state(["!disabled"])
            self.save.state(["!disabled"])
        except ValueError as error:
            self.status.set(str(error) if ids else self.tr("empty"))
            self.generate.state(["disabled"])
            self.save.state(["disabled"])

    def choose_rom(self):
        path = filedialog.askopenfilename(parent=self.root, title=self.tr("rom_dialog"),
                                          filetypes=[("ROM", "*.rom *.ROM"), ("All files", "*")])
        if path:
            self.rom.set(path)

    def confirm_write(self, files, protected=()):
        existing = [str(path) for path in files if path.exists()]
        if existing and not messagebox.askyesno(self.tr("overwrite"), self.tr("overwrite_body", files="\n".join(existing)),
                                                parent=self.root):
            return False
        write_files(files, protected=protected, overwrite=bool(existing))
        return True

    def load_selection(self):
        path = filedialog.askopenfilename(parent=self.root, title=self.tr("config_dialog"),
                                          filetypes=[("JSON", "*.json")])
        if path:
            try:
                self.set_selection(read_config(path))
            except (OSError, ValueError) as error:
                messagebox.showerror(self.tr("error"), str(error), parent=self.root)

    def save_selection(self):
        path = filedialog.asksaveasfilename(parent=self.root, title=self.tr("config_dialog"),
                                           defaultextension=".json", initialfile="my-fixes.json",
                                           filetypes=[("JSON", "*.json")], confirmoverwrite=False)
        if path:
            try:
                files = {Path(path): json_bytes(selection_config(self.selected_ids()))}
                if self.confirm_write(files, protected=[self.rom.get()] if self.rom.get() else []):
                    self.status.set(self.tr("saved"))
            except (OSError, ValueError) as error:
                messagebox.showerror(self.tr("error"), str(error), parent=self.root)

    def generate_patch(self):
        try:
            if not self.rom.get().strip():
                raise ValueError(self.tr("source_missing"))
            source = Path(self.rom.get())
            artifact = build_selection(source.read_bytes(), self.selected_ids())
            path = filedialog.asksaveasfilename(parent=self.root, title=self.tr("ips_dialog"),
                                               defaultextension=".ips", initialfile="VAMPIREKILLER_custom.ips",
                                               filetypes=[("IPS", "*.ips")], confirmoverwrite=False)
            if not path or not self.confirm_write(artifact_files(artifact, path), protected=[source]):
                return
            report = artifact.report
            self.status.set(self.tr("success"))
            names = ", ".join(fix.title(self.language) for fix in resolve_selection(report["selected_fixes"]))
            messagebox.showinfo(self.tr("success"), self.tr("result", names=names, path=path,
                                size=report["rom_bytes"], free=report.get("extension_free_bytes", report["bank6_free_bytes"]), record=Path(path).name + ".json"),
                                parent=self.root)
        except (OSError, ValueError) as error:
            messagebox.showerror(self.tr("error"), str(error), parent=self.root)


def launch(language="ja", source=None):
    root = tk.Tk()
    SelectorWindow(root, language, source)
    root.mainloop()
