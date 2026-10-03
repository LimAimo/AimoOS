"""Single native source for the user-provided paper-and-ink design tokens."""
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication
from pathlib import Path
import os

LIGHT = dict(bg="#F2EDE4", elevated="#FFFDF8", sunken="#E9E1D5", panel="#F7F2E9",
             text="#1D1B18", secondary="#625B52", tertiary="#6B6257",
             border="#D7CCBD", soft="#E6DED3", accent="#95654F",
             accent_hover="#7E523F", accent_soft="#EDE0D8", accent_text="#FFFDF8",
             danger="#A64B40", success="#4C7257", overlay="#1D1B18")
DARK = dict(bg="#171613", elevated="#24211D", sunken="#12110F", panel="#1F1D19",
            text="#F4EEE4", secondary="#C2B8AA", tertiary="#A99E90",
            border="#51493F", soft="#37322C", accent="#C3977F",
            accent_hover="#D3AC96", accent_soft="#382B24", accent_text="#171613",
            danger="#DE9586", success="#91B59B", overlay="#000000")
RADII = dict(control=4, item=4, surface=6, popover=8, modal=12, sheet=16)


class Theme(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.dark = False
        self.reduced_motion = False
        self.text_scale = 1.0
        self.wallpaper = True
        self.wallpaper_path = ""

    def c(self, name):
        return QColor((DARK if self.dark else LIGHT)[name])

    def value(self, name):
        return (DARK if self.dark else LIGHT)[name]

    def duration(self, ms):
        return 0 if self.reduced_motion else ms

    def apply(self, *, dark=None, reduced_motion=None, text_scale=None, wallpaper=None, wallpaper_path=None):
        for name, value in locals().copy().items():
            if name != "self" and value is not None:
                setattr(self, name, value)
        app = QApplication.instance()
        if app:
            palette = QPalette()
            for role, key in [(QPalette.ColorRole.Window, "bg"),
                              (QPalette.ColorRole.WindowText, "text"),
                              (QPalette.ColorRole.Base, "elevated"),
                              (QPalette.ColorRole.AlternateBase, "panel"),
                              (QPalette.ColorRole.Text, "text"),
                              (QPalette.ColorRole.Button, "panel"),
                              (QPalette.ColorRole.ButtonText, "text"),
                              (QPalette.ColorRole.Highlight, "accent_soft"),
                              (QPalette.ColorRole.HighlightedText, "text")]:
                palette.setColor(role, self.c(key))
            app.setPalette(palette)
            app.setFont(font(10))
            app.setStyleSheet(self.stylesheet())
            for window in app.topLevelWidgets():
                window.update()
                for widget in window.findChildren(QObject):
                    if hasattr(widget, "update"):
                        widget.update()
        self.changed.emit()

    def stylesheet(self):
        t = DARK if self.dark else LIGHT
        size = round(14 * self.text_scale)
        return f"""
        QWidget {{ color:{t['text']}; }}
        QLabel {{ background:transparent; }}
        QLabel#heading {{ font-family:'Noto Serif CJK SC'; font-size:30px; font-weight:500; }}
        QLabel#section {{ color:{t['secondary']}; font-size:12px; font-weight:600; }}
        QLabel#muted {{ color:{t['tertiary']}; font-size:12px; }}
        QLineEdit,QPlainTextEdit,QTextEdit {{ background:{t['elevated']}; color:{t['text']}; font-size:{size}px;
            border:1px solid {t['border']}; border-radius:4px; padding:8px 10px;
            selection-background-color:{t['accent_soft']}; selection-color:{t['text']}; }}
        QLineEdit:focus,QPlainTextEdit:focus,QTextEdit:focus {{ border-color:{t['accent']}; }}
        QTreeView {{ background:{t['bg']}; border:0; outline:0;
            selection-background-color:{t['accent_soft']}; selection-color:{t['text']}; }}
        QTreeView::item {{ height:38px; padding:0 8px; border:0; }}
        QTreeView::item:hover {{ background:{t['panel']}; }}
        QHeaderView::section {{ background:{t['bg']}; color:{t['secondary']}; border:0;
            border-bottom:1px solid {t['soft']}; padding:9px 8px; text-align:left; }}
        QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
        QScrollBar::handle:vertical {{ background:{t['border']}; min-height:30px; border-radius:3px; }}
        QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{ height:0; }}
        QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{ background:none; }}
        QScrollBar:horizontal {{ background:transparent; height:8px; margin:2px; }}
        QScrollBar::handle:horizontal {{ background:{t['border']}; min-width:30px; border-radius:3px; }}
        QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{ width:0; }}
        QMenu {{ background:{t['bg']}; border:1px solid {t['soft']}; border-radius:8px; padding:6px; }}
        QMenu::item {{ padding:8px 20px 8px 12px; border-radius:4px; }}
        QMenu::item:selected {{ background:{t['sunken']}; }}
        QMenu::separator {{ height:1px; background:{t['soft']}; margin:5px; }}
        QToolTip {{ color:{t['text']}; background:{t['elevated']}; border:1px solid {t['soft']};
            border-radius:6px; padding:6px 9px; }}
        QSlider::groove:horizontal {{ height:3px; background:{t['border']}; }}
        QSlider::sub-page:horizontal {{ background:{t['accent']}; }}
        QSlider::handle:horizontal {{ width:14px; margin:-6px 0; border-radius:7px;
            background:{t['accent']}; }}
        """


THEME = Theme()


def font(points=10, *, serif=False, mono=False, weight=QFont.Weight.Normal):
    family = "DejaVu Sans Mono" if mono else ("Noto Serif CJK SC" if serif else "Noto Sans CJK SC")
    f = QFont(family)
    f.setPointSizeF(points * THEME.text_scale)
    f.setWeight(weight)
    return f


def load_fonts():
    root = Path(os.environ.get("AIMO_FONT_DIR", "/usr/share/fonts/opentype/noto"))
    for name in ["NotoSansCJK-Regular.ttc", "NotoSerifCJK-Regular.ttc"]:
        path = root / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
