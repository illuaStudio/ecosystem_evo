"""開発用 tkinter ランチャー: 設定変更 → 保存 → ゲーム起動。"""
from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from dev_launcher_fields import (
    FIELD_SPECS,
    FieldSpec,
    ai_subtabs_for_category,
    coerce_value,
    fields_for_ai_subtab,
    fields_for_category_main,
    format_field_reference,
    has_nested_ai_tabs,
    launcher_tabs,
    project_root,
    read_field_value,
    write_field_value,
)


class DevLauncherApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Ecosystem Evo — 開発ランチャー")
        self.root.geometry("980x720")
        self.root.minsize(760, 560)

        self._widgets: dict[str, tk.Variable] = {}
        self._spec_by_id: dict[str, FieldSpec] = {s.field_id: s for s in FIELD_SPECS}
        self._game_process: subprocess.Popen | None = None

        self._build_ui()
        self._reload_all_fields()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(
            top,
            text="シミュレーション設定を変更して保存し、ゲームを起動・再起動できます。",
        ).pack(anchor=tk.W)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        for category in launcher_tabs():
            tab_frame = ttk.Frame(self.notebook, padding=4)
            self.notebook.add(tab_frame, text=category)
            if has_nested_ai_tabs(category):
                self._build_species_tab(tab_frame, category)
            else:
                self._build_flat_tab(tab_frame, category)

        help_frame = ttk.LabelFrame(self.root, text="説明", padding=8)
        help_frame.pack(fill=tk.X, padx=8, pady=4)

        self.help_title = ttk.Label(
            help_frame, text="項目を選ぶと説明が表示されます", font=("", 10, "bold")
        )
        self.help_title.pack(anchor=tk.W)

        self.help_text = tk.Text(help_frame, height=6, wrap=tk.WORD, relief=tk.FLAT, font=("", 10))
        self.help_text.pack(fill=tk.X)
        self.help_text.configure(state=tk.DISABLED)

        self.file_label = ttk.Label(help_frame, text="", foreground="#666666", font=("", 9))
        self.file_label.pack(anchor=tk.W)

        btn_frame = ttk.Frame(self.root, padding=8)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="設定を再読込", command=self._reload_all_fields).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="保存", command=self._save_all).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="ゲーム起動", command=self._launch_game).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="保存して起動", command=self._save_and_launch).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="ゲーム終了", command=self._stop_game).pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value="準備完了")
        ttk.Label(btn_frame, textvariable=self.status_var).pack(side=tk.RIGHT, padx=8)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bind_scroll(self, canvas: tk.Canvas) -> None:
        def _on_mousewheel(event, c=canvas):
            c.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

    def _make_scroll_area(self, parent: ttk.Frame) -> ttk.Frame:
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind(
            "<Configure>",
            lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._bind_scroll(canvas)
        return inner

    def _build_field_grid(self, parent: ttk.Frame, specs: list[FieldSpec]) -> None:
        for row, spec in enumerate(specs):
            ttk.Label(parent, text=spec.label, width=22).grid(
                row=row, column=0, sticky=tk.W, padx=(4, 8), pady=4
            )
            widget = self._make_widget(parent, spec, row)
            widget.grid(row=row, column=1, sticky=tk.EW, padx=4, pady=4)
        parent.columnconfigure(1, weight=1)

    def _build_flat_tab(self, parent: ttk.Frame, category: str) -> None:
        inner = self._make_scroll_area(parent)
        main = fields_for_category_main(category)
        if main:
            self._build_field_grid(inner, main)

    def _build_species_tab(self, parent: ttk.Frame, category: str) -> None:
        inner = self._make_scroll_area(parent)

        main_specs = fields_for_category_main(category)
        if main_specs:
            main_frame = ttk.LabelFrame(inner, text="基本設定", padding=8)
            main_frame.pack(fill=tk.X, padx=4, pady=(0, 8))
            self._build_field_grid(main_frame, main_specs)

        ai_subtabs = ai_subtabs_for_category(category)
        if ai_subtabs:
            ai_outer = ttk.LabelFrame(inner, text="AI 行動", padding=8)
            ai_outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            ai_notebook = ttk.Notebook(ai_outer)
            ai_notebook.pack(fill=tk.BOTH, expand=True)
            for subtab in ai_subtabs:
                sub_frame = ttk.Frame(ai_notebook, padding=4)
                ai_notebook.add(sub_frame, text=subtab)
                sub_inner = self._make_scroll_area(sub_frame)
                self._build_field_grid(sub_inner, fields_for_ai_subtab(category, subtab))

    def _make_widget(self, parent: ttk.Frame, spec: FieldSpec, row: int) -> tk.Widget:
        if spec.value_type == "bool":
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(
                parent,
                variable=var,
                command=lambda s=spec: self._show_help(s),
            )
            cb.bind("<FocusIn>", lambda _e, s=spec: self._show_help(s))
            self._widgets[spec.field_id] = var
            return cb

        var = tk.StringVar()
        entry = ttk.Entry(parent, textvariable=var, width=18)
        entry.bind("<FocusIn>", lambda _e, s=spec: self._show_help(s))
        entry.bind("<Button-1>", lambda _e, s=spec: self._show_help(s))
        self._widgets[spec.field_id] = var

        if spec.min_val is not None and spec.max_val is not None:
            scale = ttk.Scale(
                parent,
                from_=spec.min_val,
                to=spec.max_val,
                orient=tk.HORIZONTAL,
                command=lambda v, s=spec, vref=var: self._on_scale(v, s, vref),
            )
            scale.bind("<ButtonPress-1>", lambda _e, s=spec: self._show_help(s))
            scale.grid(row=row, column=2, sticky=tk.EW, padx=(8, 4), pady=4)
            self._widgets[f"{spec.field_id}__scale"] = scale  # type: ignore[assignment]

        return entry

    def _on_scale(self, value: str, spec: FieldSpec, var: tk.StringVar) -> None:
        if spec.value_type == "int":
            var.set(str(int(float(value))))
        else:
            var.set(f"{float(value):.4g}")
        self._show_help(spec)

    def _show_help(self, spec: FieldSpec) -> None:
        self.help_title.configure(text=spec.label)
        self.help_text.configure(state=tk.NORMAL)
        self.help_text.delete("1.0", tk.END)
        self.help_text.insert(
            tk.END,
            spec.help_text + "\n\n" + format_field_reference(spec),
        )
        self.help_text.configure(state=tk.DISABLED)
        self.file_label.configure(text="")

    def _reload_all_fields(self) -> None:
        for spec_id, spec in self._spec_by_id.items():
            try:
                value = read_field_value(spec)
            except (OSError, KeyError, json.JSONDecodeError) as exc:
                self.status_var.set(f"読込失敗: {spec.label} ({exc})")
                continue
            var = self._widgets.get(spec_id)
            if var is None:
                continue
            if spec.value_type == "bool":
                var.set(bool(value))
            elif value is None:
                var.set("")
            elif spec.value_type == "int":
                var.set(str(int(value)))
            else:
                var.set(f"{float(value):.4g}")

            scale = self._widgets.get(f"{spec_id}__scale")
            if scale is not None and value is not None:
                try:
                    scale.set(float(value))  # type: ignore[attr-defined]
                except tk.TclError:
                    pass

        self.status_var.set("設定を読み込みました")

    def _save_all(self) -> bool:
        try:
            for spec_id, spec in self._spec_by_id.items():
                var = self._widgets.get(spec_id)
                if var is None:
                    continue
                if spec.value_type == "bool":
                    value = bool(var.get())
                else:
                    raw = str(var.get()).strip()
                    if not raw:
                        continue
                    value = coerce_value(spec, raw)
                write_field_value(spec, value)
        except (OSError, KeyError, ValueError, TypeError) as exc:
            messagebox.showerror("保存エラー", str(exc))
            self.status_var.set(f"保存失敗: {exc}")
            return False

        self.status_var.set("設定を保存しました")
        return True

    def _launch_game(self) -> None:
        if self._game_process is not None and self._game_process.poll() is None:
            messagebox.showinfo(
                "起動中",
                "ゲームはすでに起動しています。\n再起動する場合は「保存して起動」を使ってください。",
            )
            return
        self._start_game()

    def _save_and_launch(self) -> None:
        if not self._save_all():
            return
        self._restart_game()

    def _restart_game(self) -> None:
        self._stop_game()
        self._start_game()

    def _start_game(self) -> None:
        root = project_root()
        try:
            self._game_process = subprocess.Popen(
                [sys.executable, "run.py"],
                cwd=str(root),
            )
        except OSError as exc:
            messagebox.showerror("起動エラー", str(exc))
            self.status_var.set(f"起動失敗: {exc}")
            return
        self.status_var.set(f"ゲーム起動 (PID {self._game_process.pid})")

    def _stop_game(self) -> None:
        if self._game_process is None:
            return
        if self._game_process.poll() is None:
            self._game_process.terminate()
            try:
                self._game_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._game_process.kill()
        self._game_process = None
        self.status_var.set("ゲームを終了しました")

    def _on_close(self) -> None:
        self._stop_game()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    DevLauncherApp().run()


if __name__ == "__main__":
    main()
