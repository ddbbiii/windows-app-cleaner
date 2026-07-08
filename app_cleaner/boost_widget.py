from __future__ import annotations

import tkinter as tk


COLORS = {
    "shell": "#eaf5f2",
    "card": "#fbfffd",
    "surface": "#f0faf7",
    "surface_2": "#e2f5ef",
    "line": "#b7d8d1",
    "text": "#12322f",
    "muted": "#607874",
    "teal": "#0f9f8d",
    "teal_dark": "#08786e",
    "orange": "#f97316",
    "orange_dark": "#d8550d",
    "yellow": "#facc15",
    "blue": "#2563eb",
    "danger": "#ef4444",
    "white": "#ffffff",
}


class FloatingBoostWindow:
    def __init__(self, controller) -> None:
        self.controller = controller
        self.window = tk.Toplevel(controller.root)
        self.window.title("一键加速")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.98)
        self.window.configure(bg=COLORS["shell"])
        self.window.resizable(False, False)

        self.expanded = False
        self.pinned = True
        self.pos_x = 1200
        self.pos_y = 340
        self.drag_start: tuple[int, int] | None = None
        self.drag_origin: tuple[int, int] | None = None
        self.dragged = False
        self.width = 88
        self.height = 88
        self.row_offset = 0
        self.row_hitboxes: dict[tuple[int, int, int, int], str] = {}
        self.action_hitboxes: dict[tuple[int, int, int, int], str] = {}

        self.cleanable_count = 0
        self.foreground_count = 0
        self.background_count = 0
        self.app_rows = []
        self.status_text = "正常关闭，不强退"
        self.pulse = 0

        self.canvas = tk.Canvas(self.window, width=self.width, height=self.height, bg=COLORS["shell"], highlightthickness=0, cursor="hand2")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._click)
        self.canvas.bind("<MouseWheel>", self._scroll)
        self.canvas.bind("<Enter>", lambda _event: self._draw(hover=True))
        self.canvas.bind("<Leave>", lambda _event: self._draw(hover=False))
        self.window.bind("<FocusOut>", self._on_focus_out)

        self.refresh()

    def refresh(self) -> None:
        apps = self.controller.current_apps
        allowset = {name.lower() for name in self.controller.config["allowlist_process_names"]}
        rows = []
        foreground = 0
        background = 0
        for app in apps:
            is_allowed = app.process_name.lower() in allowset
            if not is_allowed:
                if app.foreground_window_count:
                    foreground += 1
                if app.background_window_count:
                    background += 1
            priority = 0 if app.foreground_window_count else 1
            rows.append((priority, app.process_name.lower(), app.process_name, app.state_label, is_allowed))

        self.app_rows = [(process_name, state, is_allowed) for _, _, process_name, state, is_allowed in sorted(rows)]
        self.foreground_count = foreground
        self.background_count = background
        self.cleanable_count = foreground + background
        self.row_offset = min(self.row_offset, max(0, len(self.app_rows) - self._visible_row_count()))
        result = getattr(self.controller, "last_close_result", None)
        if result:
            self.status_text = f"上次关闭 {result.attempted_windows} 个，失败 {len(result.failures)}"
        else:
            self.status_text = "点应用行右侧可切换保留"
        self._resize(336, 314) if self.expanded else self._resize(88, 88)
        self._draw()

    def expand(self) -> None:
        self.expanded = True
        self._resize(336, 314)
        self.window.focus_force()
        self.canvas.focus_set()
        self._draw()

    def collapse(self) -> None:
        self.expanded = False
        self._resize(88, 88)
        self._draw()

    def toggle_pin(self) -> None:
        self.pinned = not self.pinned
        self.window.attributes("-topmost", self.pinned)
        self._draw()

    def _resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.window.geometry(f"{width}x{height}+{self.pos_x}+{self.pos_y}")
        self.canvas.configure(width=width, height=height)

    def _start_drag(self, event) -> None:
        self.dragged = False
        self.drag_start = (event.x_root - self.pos_x, event.y_root - self.pos_y)
        self.drag_origin = (event.x_root, event.y_root)

    def _drag(self, event) -> None:
        if self.drag_start is None:
            return
        if self.drag_origin is not None:
            self.dragged = abs(event.x_root - self.drag_origin[0]) > 3 or abs(event.y_root - self.drag_origin[1]) > 3
        offset_x, offset_y = self.drag_start
        self.pos_x = event.x_root - offset_x
        self.pos_y = event.y_root - offset_y
        self.window.geometry(f"+{self.pos_x}+{self.pos_y}")

    def _click(self, event) -> None:
        if self.dragged:
            return
        if not self.expanded:
            self.expand()
            return

        x, y = event.x, event.y
        for box, action in self.action_hitboxes.items():
            if self._inside(box, x, y):
                if action == "pin":
                    self.toggle_pin()
                elif action == "clean_foreground":
                    self._clean_foreground()
                elif action == "clean_background":
                    self._clean_background()
                return

        for box, process_name in self.row_hitboxes.items():
            if self._inside(box, x, y):
                self._toggle_allowlist(process_name)
                return

    def _scroll(self, event) -> None:
        if not self.expanded or len(self.app_rows) <= self._visible_row_count():
            return
        direction = -1 if event.delta > 0 else 1
        self.row_offset = max(0, min(self.row_offset + direction, len(self.app_rows) - self._visible_row_count()))
        self._draw()

    def _draw(self, *, hover: bool = False) -> None:
        self.canvas.delete("all")
        self.row_hitboxes.clear()
        self.action_hitboxes.clear()
        if self.expanded:
            self._draw_expanded()
        else:
            self._draw_collapsed(hover=hover)

    def _draw_collapsed(self, *, hover: bool = False) -> None:
        c = self.canvas
        c.create_oval(10, 12, 84, 86, fill="#c7d9d5", outline="", stipple="gray50")
        fill = COLORS["white"] if not hover else "#f1fffb"
        self._round_rect(5, 4, 81, 80, 25, fill=fill, outline=COLORS["line"], width=2)
        c.create_oval(13, 12, 73, 72, fill=COLORS["surface_2"], outline="")
        c.create_oval(20, 18, 66, 65, fill=COLORS["white"], outline=COLORS["line"])
        self._rocket(43, 39, 0.68)
        c.create_oval(56, 56, 78, 78, fill=COLORS["orange"], outline=COLORS["white"], width=2)
        c.create_text(67, 67, text=str(self.cleanable_count), fill=COLORS["white"], font=("Microsoft YaHei UI", 8, "bold"))

    def _draw_expanded(self) -> None:
        c = self.canvas
        c.create_rectangle(8, 10, 328, 308, fill="#c8dcd7", outline="", stipple="gray50")
        self._round_rect(6, 4, 330, 300, 18, fill=COLORS["card"], outline=COLORS["line"], width=2)
        self._round_rect(14, 12, 322, 67, 15, fill=COLORS["surface"], outline="")

        c.create_oval(22, 20, 58, 56, fill=COLORS["white"], outline=COLORS["line"])
        self._rocket(40, 40, 0.40)
        c.create_text(70, 27, text="一键加速", anchor="w", fill=COLORS["text"], font=("Microsoft YaHei UI", 12, "bold"))
        c.create_text(70, 48, text=f"可清理 {self.cleanable_count} | 前台 {self.foreground_count} | 后台 {self.background_count}", anchor="w", fill=COLORS["muted"], font=("Microsoft YaHei UI", 8))

        pin_label = "置顶中" if self.pinned else "置顶"
        self._pill(264, 18, 316, 42, pin_label, active=self.pinned)
        self.action_hitboxes[(264, 18, 316, 42)] = "pin"

        c.create_text(20, 84, text="当前应用", anchor="w", fill=COLORS["muted"], font=("Microsoft YaHei UI", 8, "bold"))
        visible_rows = self.app_rows[self.row_offset : self.row_offset + self._visible_row_count()]
        row_top = 96
        for index, (process_name, state, is_allowed) in enumerate(visible_rows):
            y = row_top + index * 32
            self._draw_app_row(18, y, 300, 27, process_name, state, is_allowed)
        if len(self.app_rows) > self._visible_row_count():
            self._draw_scrollbar(318, row_top, self._visible_row_count() * 32 - 5)

        self._button(18, 266, 155, 298, "清理前台", COLORS["teal"], COLORS["teal_dark"])
        self.action_hitboxes[(18, 266, 155, 298)] = "clean_foreground"
        self._button(181, 266, 318, 298, "清理后台", COLORS["orange"], COLORS["orange_dark"])
        self.action_hitboxes[(181, 266, 318, 298)] = "clean_background"

    def _draw_app_row(self, x: int, y: int, width: int, height: int, process_name: str, state: str, is_allowed: bool) -> None:
        fill = "#ffffff" if not is_allowed else "#edf9f5"
        outline = "#d9e9e5" if not is_allowed else COLORS["teal"]
        self._round_rect(x, y, x + width, y + height, 9, fill=fill, outline=outline)
        name = self._clip_text(process_name, 18)
        self.canvas.create_text(x + 10, y + 13, text=name, anchor="w", fill=COLORS["text"], font=("Microsoft YaHei UI", 9, "bold"))
        self.canvas.create_text(x + 147, y + 13, text=state, anchor="w", fill=COLORS["muted"], font=("Microsoft YaHei UI", 8))
        label = "保留" if is_allowed else "清理"
        switch_x1 = x + width - 76
        switch_x2 = x + width - 10
        fill = COLORS["teal"] if is_allowed else "#ffffff"
        outline = COLORS["teal"] if is_allowed else "#d7e2df"
        knob_x = switch_x2 - 14 if is_allowed else switch_x1 + 14
        text_x = switch_x1 + 24 if is_allowed else switch_x1 + 43
        self._round_rect(switch_x1, y + 4, switch_x2, y + height - 4, 10, fill=fill, outline=outline)
        self.canvas.create_oval(knob_x - 8, y + 6, knob_x + 8, y + height - 6, fill=COLORS["white"] if is_allowed else "#7a8582", outline="")
        self.canvas.create_text(text_x, y + 13, text=label, fill=COLORS["white"] if is_allowed else COLORS["muted"], font=("Microsoft YaHei UI", 8, "bold"))
        self.row_hitboxes[(switch_x1 - 6, y, switch_x2 + 4, y + height)] = process_name

    def _button(self, x1: int, y1: int, x2: int, y2: int, text: str, fill: str, outline: str) -> None:
        self._round_rect(x1, y1, x2, y2, 10, fill=fill, outline=outline, width=1)
        self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=text, fill=COLORS["white"], font=("Microsoft YaHei UI", 9, "bold"))

    def _pill(self, x1: int, y1: int, x2: int, y2: int, text: str, *, active: bool) -> None:
        fill = COLORS["teal"] if active else COLORS["white"]
        text_fill = COLORS["white"] if active else COLORS["muted"]
        outline = COLORS["teal"] if active else "#d5e7e4"
        self._round_rect(x1, y1, x2, y2, 9, fill=fill, outline=outline)
        self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=text, fill=text_fill, font=("Microsoft YaHei UI", 8, "bold"))

    def _rocket(self, cx: int, cy: int, scale: float) -> None:
        c = self.canvas

        def p(dx: float, dy: float) -> tuple[float, float]:
            return cx + dx * scale, cy + dy * scale

        c.create_polygon(*p(0, -36), *p(-18, -4), *p(18, -4), fill=COLORS["orange"], outline=COLORS["orange_dark"], width=1)
        c.create_polygon(*p(0, -18), *p(-19, 15), *p(19, 15), fill=COLORS["white"], outline=COLORS["teal_dark"], width=2)
        c.create_oval(*p(-8, -5), *p(8, 11), fill="#dbeafe", outline=COLORS["blue"], width=1)
        c.create_polygon(*p(-17, 14), *p(-34, 33), *p(-9, 26), fill=COLORS["teal"], outline=COLORS["teal_dark"])
        c.create_polygon(*p(17, 14), *p(34, 33), *p(9, 26), fill=COLORS["teal"], outline=COLORS["teal_dark"])
        c.create_polygon(*p(-8, 23), *p(0, 50), *p(8, 23), fill=COLORS["yellow"], outline="")
        c.create_polygon(*p(-4, 23), *p(0, 39), *p(4, 23), fill="#fff7ed", outline="")

    def _round_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> None:
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _draw_scrollbar(self, x: int, y: int, height: int) -> None:
        total = len(self.app_rows)
        visible = self._visible_row_count()
        if total <= visible:
            return
        thumb_height = max(24, int(height * visible / total))
        max_offset = total - visible
        thumb_y = y + int((height - thumb_height) * self.row_offset / max_offset)
        self._round_rect(x, y, x + 4, y + height, 2, fill="#dce9e6", outline="#dce9e6")
        self._round_rect(x, thumb_y, x + 4, thumb_y + thumb_height, 2, fill=COLORS["teal"], outline=COLORS["teal"])

    def _visible_row_count(self) -> int:
        return 5

    def _toggle_allowlist(self, process_name: str) -> None:
        allowset = {name.lower() for name in self.controller.config["allowlist_process_names"]}
        if process_name.lower() in allowset:
            self.controller.remove_allowlist_entries([process_name])
        else:
            self.controller.add_allowlist_entries([process_name])
        self.refresh()

    def _on_focus_out(self, _event) -> None:
        if self.expanded:
            self.window.after(120, self._collapse_if_unfocused)

    def _collapse_if_unfocused(self) -> None:
        focused = self.window.focus_get()
        if focused is None or focused.winfo_toplevel() != self.window:
            self.collapse()

    def _clean_foreground(self) -> None:
        self._pulse()
        self.controller.clean_foreground_now()
        self.refresh()

    def _clean_background(self) -> None:
        self._pulse()
        self.controller.clean_background_now()
        self.refresh()

    def _pulse(self) -> None:
        for delay, alpha in [(0, 0.90), (70, 1.0), (140, 0.96), (210, 0.98)]:
            self.window.after(delay, lambda value=alpha: self.window.attributes("-alpha", value))

    @staticmethod
    def _inside(box: tuple[int, int, int, int], x: int, y: int) -> bool:
        x1, y1, x2, y2 = box
        return x1 <= x <= x2 and y1 <= y <= y2

    @staticmethod
    def _clip_text(text: str, max_len: int) -> str:
        return text if len(text) <= max_len else f"{text[: max_len - 1]}..."
