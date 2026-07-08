from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from app_cleaner.app import AppController


def main() -> None:
    root = tk.Tk()
    try:
        AppController(root)
    except Exception as exc:  # pragma: no cover - startup guard
        messagebox.showerror("启动失败", str(exc))
        root.destroy()
        raise
    root.mainloop()


if __name__ == "__main__":
    main()

