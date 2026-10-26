"""Hover tips and a persistent, scrollable reader for long fix explanations."""
import tkinter as tk
from tkinter import font, ttk


class HelpPopup:
    def __init__(self, root):
        self.root = root
        self.tip = self.tip_text = self.anchor = None
        self.pending = self.pending_hide = None
        self.detail_window = self.detail_text = None
        root.bind("<Destroy>", self._root_destroyed, add="+")

    def _root_destroyed(self, event):
        if event.widget == self.root:
            self.hide()

    def bind(self, widget, get_text):
        widget.bind("<Enter>", lambda event: self.schedule(widget, get_text), add="+")
        widget.bind("<Leave>", lambda event: self.schedule_hide(), add="+")
        widget.bind("<ButtonPress>", lambda event: self.hide(), add="+")
        widget.bind("<Destroy>", lambda event: self.hide() if self.anchor == widget else None, add="+")

    def _cancel(self, name):
        token = getattr(self, name)
        if token is not None:
            self.root.after_cancel(token)
            setattr(self, name, None)

    def schedule(self, widget, get_text):
        self.hide()
        self.anchor = widget
        self.pending = self.root.after(450, lambda: self.show_tip(widget, get_text()))

    def show_tip(self, widget, text):
        self.hide()
        if not widget.winfo_exists():
            return
        self.anchor = widget
        tip = self.tip = tk.Toplevel(self.root)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.transient(self.root)
        tip.configure(background="#777777")
        frame = tk.Frame(tip, background="#ffffe1", padx=10, pady=8)
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        scrollbar = ttk.Scrollbar(frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        content = self.tip_text = tk.Text(frame, wrap="word", relief="flat", borderwidth=0,
                                         background="#ffffe1", foreground="#202020", cursor="arrow",
                                         font="TkDefaultFont", yscrollcommand=scrollbar.set)
        content.pack(fill="both", expand=True)
        scrollbar.configure(command=content.yview)
        content.insert("1.0", text)
        content.configure(state="disabled")
        screen_width, screen_height = widget.winfo_screenwidth(), widget.winfo_screenheight()
        width = min(560, screen_width - 32)
        text_font = font.nametofont("TkDefaultFont", root=self.root)
        lines = sum(max(1, (text_font.measure(line) + width - 51) // (width - 50))
                    for line in text.split("\n"))
        height = min(500, screen_height - 48, max(100, lines * text_font.metrics("linespace") + 24))
        x = min(widget.winfo_rootx() + 24, screen_width - width - 8)
        y = widget.winfo_rooty() + widget.winfo_height() + 5
        if y + height > screen_height - 8:
            y = widget.winfo_rooty() - height - 5
        tip.geometry(f"{width}x{height}+{max(8, x)}+{max(8, y)}")
        tip.bind("<Enter>", lambda event: self._cancel("pending_hide"))
        tip.bind("<Leave>", lambda event: self.schedule_hide())
        tip.bind("<Escape>", lambda event: self.hide())
        tip.deiconify()

    def schedule_hide(self):
        self._cancel("pending_hide")
        self.pending_hide = self.root.after(180, self.hide_unless_hovered)

    def hide_unless_hovered(self):
        self.pending_hide = None
        if self.tip is not None:
            x, y = self.root.winfo_pointerxy()
            for widget in (self.anchor, self.tip):
                if (widget is not None and widget.winfo_exists()
                        and widget.winfo_rootx() <= x < widget.winfo_rootx() + widget.winfo_width()
                        and widget.winfo_rooty() <= y < widget.winfo_rooty() + widget.winfo_height()):
                    return
        self.hide()

    def hide(self):
        self._cancel("pending")
        self._cancel("pending_hide")
        if self.tip is not None:
            self.tip.destroy()
        self.tip = self.tip_text = self.anchor = None

    def show_details(self, title, text, close_label):
        self.hide()
        if self.detail_window is None or not self.detail_window.winfo_exists():
            window = self.detail_window = tk.Toplevel(self.root)
            window.transient(self.root)
            window.geometry("740x560")
            window.minsize(420, 300)
            frame = ttk.Frame(window, padding=16)
            frame.pack(fill="both", expand=True)
            self.detail_close = ttk.Button(frame, command=window.destroy)
            self.detail_close.pack(side="bottom", anchor="e", pady=(12, 0))
            scrollbar = ttk.Scrollbar(frame, orient="vertical")
            scrollbar.pack(side="right", fill="y")
            self.detail_text = tk.Text(frame, wrap="word", font="TkDefaultFont", padx=12, pady=10,
                                       yscrollcommand=scrollbar.set)
            self.detail_text.pack(fill="both", expand=True)
            scrollbar.configure(command=self.detail_text.yview)
            window.bind("<Escape>", lambda event: window.destroy())
        self.detail_window.title(title)
        self.detail_close.configure(text=close_label)
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")
        self.detail_window.lift()
        return self.detail_window
