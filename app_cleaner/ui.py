from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .desktop_apps import AppCandidate
from .hotkey import HotkeyParseError


class SettingsWindow:
    def __init__(self, controller) -> None:
        self.controller = controller
        self.window = tk.Toplevel(controller.root)
        self.window.title("桌面应用清理器 - 设置")
        self.window.geometry("900x640")
        self.window.minsize(820, 560)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(2, weight=1)

        self.status_var = tk.StringVar(value=controller.status_text)
        self.hotkey_var = tk.StringVar(value=controller.hotkey_display)
        self.autostart_var = tk.BooleanVar(value=controller.config["autostart_enabled"])
        self.minimize_var = tk.BooleanVar(value=controller.config["minimize_to_tray_on_launch"])
        self.cleanup_mode_var = tk.StringVar(value=controller.config["cleanup_mode"])
        self.app_rows: dict[str, AppCandidate] = {}

        self._configure_styles()
        self._build_settings_header()
        self._build_toolbar()
        self._build_lists()
        self._build_footer()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.window)
        style.configure("Cleaner.Treeview", rowheight=27, font=("Microsoft YaHei UI", 9))
        style.configure("Cleaner.Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"))

    def _build_settings_header(self) -> None:
        frame = ttk.Frame(self.window, padding=12)
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="全局快捷键").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.hotkey_var, width=24).grid(row=0, column=1, sticky="w", padx=(8, 12))
        ttk.Label(frame, text="例如 F4 / Ctrl+Alt+K").grid(row=0, column=2, sticky="w")

        ttk.Checkbutton(frame, text="开机启动", variable=self.autostart_var).grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Checkbutton(frame, text="启动后最小化到托盘", variable=self.minimize_var).grid(row=1, column=1, sticky="w", pady=(10, 0))

        mode_frame = ttk.LabelFrame(frame, text="快捷键默认清理范围", padding=(10, 6))
        mode_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Radiobutton(
            mode_frame,
            text="前台+后台",
            value="foreground_and_background",
            variable=self.cleanup_mode_var,
        ).pack(side="left")
        ttk.Radiobutton(
            mode_frame,
            text="仅前台",
            value="foreground_only",
            variable=self.cleanup_mode_var,
        ).pack(side="left", padx=(16, 0))

    def _build_toolbar(self) -> None:
        frame = ttk.Frame(self.window, padding=(12, 0, 12, 8))
        frame.grid(row=1, column=0, sticky="ew")
        ttk.Button(frame, text="刷新应用列表", command=self.controller.refresh_apps).pack(side="left")
        ttk.Button(frame, text="按默认范围清理", command=self.controller.clean_now).pack(side="left", padx=(8, 0))
        ttk.Label(frame, textvariable=self.status_var).pack(side="left", padx=(16, 0))

    def _build_lists(self) -> None:
        container = ttk.Panedwindow(self.window, orient="horizontal")
        container.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))

        apps_panel = ttk.Frame(container, padding=12)
        apps_panel.columnconfigure(0, weight=1)
        apps_panel.rowconfigure(1, weight=1)
        container.add(apps_panel, weight=4)

        whitelist_panel = ttk.Frame(container, padding=12)
        whitelist_panel.columnconfigure(0, weight=1)
        whitelist_panel.rowconfigure(1, weight=1)
        container.add(whitelist_panel, weight=2)

        ttk.Label(apps_panel, text="当前桌面应用").grid(row=0, column=0, sticky="w")
        apps_actions = ttk.Frame(apps_panel)
        apps_actions.grid(row=0, column=1, sticky="e")
        ttk.Button(apps_actions, text="加入白名单", command=self._add_selected_to_allowlist).pack(side="left")
        ttk.Button(apps_actions, text="手动关闭所选", command=self._close_selected_apps).pack(side="left", padx=(8, 0))

        self.apps_tree = ttk.Treeview(
            apps_panel,
            columns=("rule", "state", "title", "path"),
            show="tree headings",
            selectmode="extended",
            style="Cleaner.Treeview",
        )
        self.apps_tree.heading("#0", text="进程名")
        self.apps_tree.heading("rule", text="规则")
        self.apps_tree.heading("state", text="窗口")
        self.apps_tree.heading("title", text="标题")
        self.apps_tree.heading("path", text="路径")
        self.apps_tree.column("#0", width=150, stretch=False)
        self.apps_tree.column("rule", width=72, stretch=False, anchor="center")
        self.apps_tree.column("state", width=86, stretch=False, anchor="center")
        self.apps_tree.column("title", width=220, stretch=True)
        self.apps_tree.column("path", width=300, stretch=True)
        apps_scrollbar = ttk.Scrollbar(apps_panel, orient="vertical", command=self.apps_tree.yview)
        self.apps_tree.configure(yscrollcommand=apps_scrollbar.set)
        self.apps_tree.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        apps_scrollbar.grid(row=1, column=2, sticky="ns", pady=(8, 0))

        ttk.Label(whitelist_panel, text="白名单").grid(row=0, column=0, sticky="w")
        ttk.Button(whitelist_panel, text="移出白名单", command=self._remove_selected_from_allowlist).grid(row=0, column=1, sticky="e")
        self.allowlist_listbox = tk.Listbox(whitelist_panel, selectmode="extended", exportselection=False)
        allowlist_scrollbar = ttk.Scrollbar(whitelist_panel, orient="vertical", command=self.allowlist_listbox.yview)
        self.allowlist_listbox.configure(yscrollcommand=allowlist_scrollbar.set)
        self.allowlist_listbox.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        allowlist_scrollbar.grid(row=1, column=2, sticky="ns", pady=(8, 0))
        ttk.Label(whitelist_panel, text="白名单条目即使当前未运行也会保留。").grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _build_footer(self) -> None:
        frame = ttk.Frame(self.window, padding=(12, 0, 12, 12))
        frame.grid(row=3, column=0, sticky="ew")
        ttk.Button(frame, text="保存设置", command=self._save).pack(side="right")
        ttk.Button(frame, text="隐藏到托盘", command=self.hide).pack(side="right", padx=(0, 8))

    def hide(self) -> None:
        self.window.withdraw()

    def show(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self.window.attributes("-topmost", True)
        self.window.after(250, lambda: self.window.attributes("-topmost", False))

    def destroy(self) -> None:
        self.window.destroy()

    def refresh(self, apps: list[AppCandidate], allowlist: list[str], status_text: str) -> None:
        self.status_var.set(status_text)
        self.hotkey_var.set(self.controller.hotkey_display)
        self.autostart_var.set(self.controller.config["autostart_enabled"])
        self.minimize_var.set(self.controller.config["minimize_to_tray_on_launch"])
        self.cleanup_mode_var.set(self.controller.config["cleanup_mode"])
        selected_running = {item for item in self.apps_tree.selection()}
        selected_allowlist_indices = tuple(self.allowlist_listbox.curselection())

        self.app_rows = {app.process_name: app for app in apps}
        allowset = {name.lower() for name in allowlist}

        for item in self.apps_tree.get_children():
            self.apps_tree.delete(item)
        for app in apps:
            rule = "保留" if app.process_name.lower() in allowset else "可清理"
            self.apps_tree.insert(
                "",
                "end",
                iid=app.process_name,
                text=app.process_name,
                values=(rule, app.state_label, app.display_title, app.exe_path or "路径不可读取"),
            )
        for item in selected_running:
            if self.apps_tree.exists(item):
                self.apps_tree.selection_add(item)

        self.allowlist_listbox.delete(0, tk.END)
        for entry in allowlist:
            self.allowlist_listbox.insert(tk.END, entry)
        for index in selected_allowlist_indices:
            if index < self.allowlist_listbox.size():
                self.allowlist_listbox.selection_set(index)

    def _get_selected_running_process_names(self) -> list[str]:
        return list(self.apps_tree.selection())

    def _get_selected_allowlist_entries(self) -> list[str]:
        return [self.allowlist_listbox.get(index) for index in self.allowlist_listbox.curselection()]

    def _add_selected_to_allowlist(self) -> None:
        process_names = self._get_selected_running_process_names()
        if not process_names:
            messagebox.showinfo("未选择应用", "请先在左侧列表中选择至少一个应用。", parent=self.window)
            return
        self.controller.add_allowlist_entries(process_names)

    def _remove_selected_from_allowlist(self) -> None:
        process_names = self._get_selected_allowlist_entries()
        if not process_names:
            messagebox.showinfo("未选择白名单条目", "请先在右侧白名单中选择至少一个条目。", parent=self.window)
            return
        self.controller.remove_allowlist_entries(process_names)

    def _close_selected_apps(self) -> None:
        process_names = self._get_selected_running_process_names()
        if not process_names:
            messagebox.showinfo("未选择应用", "请先在左侧列表中选择至少一个应用。", parent=self.window)
            return
        self.controller.close_selected_apps(process_names)

    def _save(self) -> bool:
        try:
            self.controller.apply_settings(
                hotkey_text=self.hotkey_var.get().strip(),
                allowlist_process_names=self.controller.config["allowlist_process_names"],
                autostart_enabled=self.autostart_var.get(),
                minimize_to_tray_on_launch=self.minimize_var.get(),
                cleanup_mode=self.cleanup_mode_var.get(),
            )
        except HotkeyParseError as exc:
            messagebox.showerror("快捷键无效", str(exc), parent=self.window)
            return False
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.window)
            return False

        messagebox.showinfo("已保存", "设置已保存。", parent=self.window)
        self.controller.refresh_apps()
        return True
