"""Loads QSS stylesheet for dark theme."""
from pathlib import Path

def load_dark_theme(app):
    style_path = Path(__file__).parent.parent / "assets" / "style.qss"
    if style_path.exists():
        with open(style_path, "r") as f:
            app.setStyleSheet(f.read())