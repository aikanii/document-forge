"""Hephaestus visual theme — 'The Document Forge'.

A manuscript/archive aesthetic: parchment backgrounds, iron-gall ink text,
oxblood accents, and serif (Times New Roman) typography throughout.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

PARCHMENT      = "#F3ECDB"   # app background
PARCHMENT_DEEP = "#EBE2CC"   # recessed areas / input fields
CARD           = "#FAF6EA"   # tool cards
CARD_HOVER     = "#FFFCF2"
INK            = "#2B2119"   # primary text
INK_SOFT       = "#6B5B47"   # secondary text
RULE           = "#C9B99A"   # hairlines / borders
RULE_STRONG    = "#A9926B"
OXBLOOD        = "#7A1F1F"   # primary accent
OXBLOOD_DARK   = "#5E1414"
GOLD           = "#A87F2C"   # secondary accent
SEAL_RED       = "#8C2F24"
SUCCESS        = "#3F6B35"
ERROR          = "#9A2B1E"
SHADOW         = "#D8CBAE"

CATEGORY_COLORS = {
    "compose":   "#7A1F1F",  # Compose & Arrange
    "optimize":  "#A87F2C",  # Optimize & Restore
    "to_pdf":    "#3F6B35",  # Convert to PDF
    "from_pdf":  "#33566B",  # Convert from PDF
    "secure":    "#5E4470",  # Secure & Sign
    "edit":      "#8A5A2B",  # Edit & Annotate
}

# ---------------------------------------------------------------------------
# Fonts — Times New Roman where available, metric-compatible fallbacks else
# ---------------------------------------------------------------------------

_FALLBACK_CHAIN = [
    "Times New Roman",
    "Liberation Serif",   # Linux, metric-compatible with Times
    "Nimbus Roman",
    "Tinos",              # ChromeOS / some Linux, metric-compatible
    "DejaVu Serif",
    "Georgia",
    "serif",
]

_MONO_FALLBACKS = ["Courier New", "Nimbus Mono PS", "DejaVu Sans Mono", "Courier"]


def _first_available(families: set[str], chain: list[str], default: str) -> str:
    for name in chain:
        if name in families:
            return name
    return default


class Theme:
    def __init__(self, root: tk.Tk):
        self.root = root
        available = set(tkfont.families(root))
        self.serif = _first_available(available, _FALLBACK_CHAIN, "TkDefaultFont")
        self.mono = _first_available(available, _MONO_FALLBACKS, "Courier")
        self._cache: dict[tuple, tkfont.Font] = {}

    def font(self, size: int = 11, bold: bool = False, italic: bool = False,
             underline: bool = False) -> tkfont.Font:
        key = (self.serif, size, bold, italic, underline)
        if key not in self._cache:
            self._cache[key] = tkfont.Font(
                family=self.serif, size=size,
                weight="bold" if bold else "normal",
                slant="italic" if italic else "roman",
                underline=underline)
        return self._cache[key]

    def mono_font(self, size: int = 10) -> tkfont.Font:
        return tkfont.Font(family=self.mono, size=size)


def apply_ttk_style(theme: Theme) -> ttk.Style:
    """Configure ttk widgets to match the parchment theme."""
    style = ttk.Style(theme.root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    default_font = theme.font(11)
    small_font = theme.font(9)
    bold_font = theme.font(11, bold=True)

    style.configure(".", font=default_font, background=PARCHMENT, foreground=INK)

    style.configure("TFrame", background=PARCHMENT)
    style.configure("Card.TFrame", background=CARD)
    style.configure("Deep.TFrame", background=PARCHMENT_DEEP)
    style.configure("TLabel", background=PARCHMENT, foreground=INK, font=default_font)
    style.configure("Card.TLabel", background=CARD, foreground=INK, font=default_font)
    style.configure("Muted.TLabel", background=PARCHMENT, foreground=INK_SOFT, font=small_font)
    style.configure("CardMuted.TLabel", background=CARD, foreground=INK_SOFT, font=small_font)
    style.configure("Heading.TLabel", background=PARCHMENT, foreground=INK,
                    font=theme.font(17, bold=True))
    style.configure("Section.TLabel", background=PARCHMENT, foreground=OXBLOOD,
                    font=theme.font(13, bold=True))

    # Buttons
    style.configure("TButton", font=bold_font, padding=(14, 7),
                    background=PARCHMENT_DEEP, foreground=INK,
                    bordercolor=RULE_STRONG, lightcolor=CARD, darkcolor=SHADOW)
    style.map("TButton",
              background=[("active", CARD_HOVER), ("pressed", PARCHMENT_DEEP)],
              foreground=[("disabled", RULE_STRONG)])
    style.configure("Accent.TButton", font=theme.font(12, bold=True),
                    padding=(20, 9), background=OXBLOOD, foreground="#F7EFDD",
                    bordercolor=OXBLOOD_DARK, lightcolor=OXBLOOD, darkcolor=OXBLOOD_DARK)
    style.map("Accent.TButton",
              background=[("active", OXBLOOD_DARK), ("disabled", RULE)],
              foreground=[("disabled", PARCHMENT_DEEP)])
    style.configure("Quiet.TButton", font=default_font, padding=(10, 5),
                    background=PARCHMENT, foreground=INK_SOFT,
                    bordercolor=RULE, relief="flat")
    style.map("Quiet.TButton", background=[("active", CARD)])

    # Entry / Combobox / Spinbox
    style.configure("TEntry", fieldbackground=PARCHMENT_DEEP, foreground=INK,
                    bordercolor=RULE_STRONG, lightcolor=PARCHMENT_DEEP,
                    darkcolor=PARCHMENT_DEEP, insertcolor=INK, padding=5)
    style.configure("TCombobox", fieldbackground=PARCHMENT_DEEP,
                    background=CARD, foreground=INK, bordercolor=RULE_STRONG,
                    arrowcolor=INK, padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", PARCHMENT_DEEP)],
              foreground=[("readonly", INK)])
    theme.root.option_add("*TCombobox*Listbox.background", PARCHMENT_DEEP)
    theme.root.option_add("*TCombobox*Listbox.foreground", INK)
    theme.root.option_add("*TCombobox*Listbox.selectBackground", OXBLOOD)
    theme.root.option_add("*TCombobox*Listbox.selectForeground", "#F7EFDD")
    style.configure("TSpinbox", fieldbackground=PARCHMENT_DEEP, foreground=INK,
                    bordercolor=RULE_STRONG, arrowcolor=INK, padding=3)

    # Check / radio
    style.configure("TCheckbutton", background=PARCHMENT, foreground=INK,
                    font=default_font, indicatorcolor=PARCHMENT_DEEP)
    style.map("TCheckbutton", background=[("active", PARCHMENT)],
              indicatorcolor=[("selected", OXBLOOD), ("!selected", CARD)])
    style.configure("Card.TCheckbutton", background=CARD)
    style.map("Card.TCheckbutton", background=[("active", CARD)])
    style.configure("TRadiobutton", background=PARCHMENT, foreground=INK,
                    font=default_font, indicatorcolor=PARCHMENT_DEEP)
    style.map("TRadiobutton", background=[("active", PARCHMENT)],
              indicatorcolor=[("selected", OXBLOOD), ("!selected", CARD)])

    # Progress bar — a filling ink bar
    style.configure("TProgressbar", background=OXBLOOD, troughcolor=PARCHMENT_DEEP,
                    bordercolor=RULE_STRONG, lightcolor=OXBLOOD, darkcolor=OXBLOOD,
                    thickness=12)

    # Notebook (used sparingly)
    style.configure("TNotebook", background=PARCHMENT, bordercolor=RULE)
    style.configure("TNotebook.Tab", font=default_font, padding=(14, 6),
                    background=PARCHMENT_DEEP, foreground=INK_SOFT)
    style.map("TNotebook.Tab",
              background=[("selected", CARD)],
              foreground=[("selected", OXBLOOD)])

    # Scrollbars
    style.configure("Vertical.TScrollbar", background=RULE, troughcolor=PARCHMENT_DEEP,
                    bordercolor=PARCHMENT, arrowcolor=INK_SOFT, gripcount=0)
    style.map("Vertical.TScrollbar", background=[("active", RULE_STRONG)])

    # Listbox / canvas defaults for classic widgets
    theme.root.option_add("*Listbox.background", PARCHMENT_DEEP)
    theme.root.option_add("*Listbox.foreground", INK)
    theme.root.option_add("*Listbox.selectBackground", OXBLOOD)
    theme.root.option_add("*Listbox.selectForeground", "#F7EFDD")
    theme.root.option_add("*Listbox.font", default_font)
    theme.root.option_add("*Text.background", PARCHMENT_DEEP)
    theme.root.option_add("*Text.foreground", INK)
    theme.root.option_add("*Text.insertBackground", INK)
    theme.root.option_add("*Text.selectBackground", OXBLOOD)
    theme.root.option_add("*Text.selectForeground", "#F7EFDD")
    theme.root.option_add("*Text.font", default_font)
    theme.root.option_add("*Menu.font", default_font)
    theme.root.option_add("*Toplevel.background", PARCHMENT)

    return style
