"""Portable visual resources. Font registration is private to this process."""

from pathlib import Path
import sys

BASE = "#F4F6F6"
PANEL = "#FFFFFF"
FIELD = "#FFFFFF"
BORDER = "#CED3D4"
DIVIDER = "#E7EBEB"
INK = "#171C1D"
MUTED = "#5D6567"
NUMERIC = INK
ACCENT = "#1B6C80"
ACCENT_HOVER = "#15596A"
PRIMARY_HOVER = "#343B3D"
SELECTED_HOVER = "#F9FAFA"
CONTROL_HOVER = "#E0E5E5"
MODEL_COLOR = "#5794A0"
SECONDARY = "#EBEEEE"
SECONDARY_BORDER = "#CED3D4"
OK = "#247B50"
WARNING = "#92400E"
ERROR = "#B52C35"
UI_FONT = "IBM Plex Sans"
MONO_FONT = "IBM Plex Mono"
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"


def load_fonts():
    """Use bundled typefaces without installing them or writing outside the app."""
    from matplotlib import font_manager

    for path in FONT_DIR.glob("*.ttf"):
        font_manager.fontManager.addfont(str(path))
        if sys.platform == "win32":
            import ctypes
            # FR_PRIVATE: visible to this process only; Windows releases on exit.
            ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, None)


def status_copy(text):
    """Translate engine progress messages at the presentation boundary only."""
    messages = {
        "INITIALIZING": "Preparing your propeller…",
        "READY": "Ready",
        "INPUT ERROR": "Check the dimensions",
        "PARAMETERS CHANGED / UPDATE VIEWPORT": "Dimensions changed · Update preview to apply",
        "LOFTING B-REP SOLID...": "Building propeller…",
        "VALIDATING MANIFOLD TOPOLOGY...": "Checking the solid…",
        "TESSELLATING VALIDATED SOLID...": "Preparing preview…",
        "STEP EXPORTED": "STEP exported",
        "GEOMETRY / KERNEL ERROR": "Couldn’t build this propeller",
    }
    if text in messages:
        return messages[text]
    # Keep unlisted worker progress readable without changing its event or state.
    return text[:1].upper() + text[1:].lower().replace("b-rep", "solid")
