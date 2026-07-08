from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

MODIFIER_NAMES = {
    "CTRL": ("Ctrl", MOD_CONTROL),
    "CONTROL": ("Ctrl", MOD_CONTROL),
    "ALT": ("Alt", MOD_ALT),
    "SHIFT": ("Shift", MOD_SHIFT),
    "WIN": ("Win", MOD_WIN),
    "WINDOWS": ("Win", MOD_WIN),
    "META": ("Win", MOD_WIN),
}

SPECIAL_KEYS = {
    "TAB": (0x09, "Tab"),
    "ENTER": (0x0D, "Enter"),
    "RETURN": (0x0D, "Enter"),
    "ESC": (0x1B, "Esc"),
    "ESCAPE": (0x1B, "Esc"),
    "SPACE": (0x20, "Space"),
    "LEFT": (0x25, "Left"),
    "UP": (0x26, "Up"),
    "RIGHT": (0x27, "Right"),
    "DOWN": (0x28, "Down"),
    "INSERT": (0x2D, "Insert"),
    "DELETE": (0x2E, "Delete"),
    "HOME": (0x24, "Home"),
    "END": (0x23, "End"),
    "PAGEUP": (0x21, "PageUp"),
    "PGUP": (0x21, "PageUp"),
    "PAGEDOWN": (0x22, "PageDown"),
    "PGDN": (0x22, "PageDown"),
}

for index in range(1, 25):
    SPECIAL_KEYS[f"F{index}"] = (0x6F + index, f"F{index}")


@dataclass(slots=True)
class HotkeySpec:
    modifiers: int
    vk: int
    display: str


class HotkeyParseError(ValueError):
    pass


def parse_hotkey_string(text: str) -> HotkeySpec:
    raw_tokens = [token.strip() for token in text.split("+") if token.strip()]
    if not raw_tokens:
        raise HotkeyParseError("请输入快捷键，例如 F4 或 Ctrl+Alt+K。")

    modifiers = 0
    display_parts: list[str] = []
    key_token = raw_tokens[-1].upper()

    for token in raw_tokens[:-1]:
        normalized, mask = MODIFIER_NAMES.get(token.upper(), (None, None))
        if normalized is None:
            raise HotkeyParseError(f"不支持的修饰键: {token}")
        if modifiers & mask:
            continue
        modifiers |= mask
        display_parts.append(normalized)

    if len(key_token) == 1 and key_token.isalpha():
        if modifiers == 0:
            raise HotkeyParseError("单独字母键风险太高，请使用 Ctrl/Alt/Shift/Win 加字母。")
        vk = ord(key_token)
        display_key = key_token.upper()
    elif len(key_token) == 1 and key_token.isdigit():
        if modifiers == 0:
            raise HotkeyParseError("单独数字键风险太高，请使用 Ctrl/Alt/Shift/Win 加数字。")
        vk = ord(key_token)
        display_key = key_token
    elif key_token in SPECIAL_KEYS:
        if modifiers == 0 and not key_token.startswith("F"):
            raise HotkeyParseError("只有 F1-F24 支持单键快捷键，其他特殊键请加修饰键。")
        vk, display_key = SPECIAL_KEYS[key_token]
    else:
        raise HotkeyParseError(f"不支持的主键: {raw_tokens[-1]}")

    display_parts.append(display_key)
    return HotkeySpec(modifiers=modifiers, vk=vk, display="+".join(display_parts))


def hotkey_to_dict(spec: HotkeySpec | None) -> dict[str, Any] | None:
    if spec is None:
        return None
    return {
        "modifiers": spec.modifiers,
        "vk": spec.vk,
        "display": spec.display,
    }


def hotkey_from_config(value: Any) -> HotkeySpec | None:
    if not isinstance(value, dict):
        return None
    try:
        modifiers = int(value["modifiers"])
        vk = int(value["vk"])
        display = str(value["display"]).strip()
    except (KeyError, TypeError, ValueError):
        return None
    if not display:
        return None
    return HotkeySpec(modifiers=modifiers, vk=vk, display=display)
