"""Цвета, шрифты и таблица стилей."""

from PySide6.QtGui import QColor, QFont

BG = "#F4F2EE"
SIDEBAR = "#EBE8E1"
CARD = "#FFFFFF"
TEXT = "#1C1C1E"
MUTED = "#6F6E73"
FAINT = "#A3A19C"
BORDER = "#E2DED6"
ACCENT = "#1F8A65"
ACCENT_HOVER = "#17714F"
ACCENT_SOFT = "#E2F1EA"
WARN = "#9A5B00"
WARN_BG = "#FFF3DC"
DANGER = "#C4402F"
DANGER_SOFT = "#FBE9E6"

ZONE = QColor(ACCENT)

FONT_FAMILY = "Segoe UI"


def font(size: float = 10, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(FONT_FAMILY)
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


QSS = f"""
* {{
    font-family: "{FONT_FAMILY}";
    color: {TEXT};
}}
QMainWindow, QDialog, #Page {{ background: {BG}; }}
QWidget#Sidebar {{ background: {SIDEBAR}; }}

QLabel#H1 {{ font-size: 22pt; font-weight: 600; }}
QLabel#H2 {{ font-size: 13pt; font-weight: 600; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Faint {{ color: {FAINT}; font-size: 9pt; }}
QLabel#Brand {{ font-size: 13pt; font-weight: 700; }}

QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#Hero {{
    border-radius: 18px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1F8A65, stop:1 #2E6F8E);
}}
QFrame#Hero QLabel {{ color: white; background: transparent; }}
QFrame#Banner {{
    background: {WARN_BG};
    border: 1px solid #F1D9A8;
    border-radius: 10px;
}}
QFrame#Banner QLabel {{ color: {WARN}; }}
QFrame#Info {{
    background: {ACCENT_SOFT};
    border-radius: 10px;
}}

QPushButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: #F8F7F4; border-color: #D3CEC4; }}
QPushButton:pressed {{ background: #EFEDE8; }}
QPushButton:disabled {{ color: {FAINT}; }}
QPushButton#Primary {{
    background: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
    padding: 9px 20px;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Primary:disabled {{ background: #9CC9B7; }}
QPushButton#HeroButton {{
    background: white;
    color: {ACCENT};
    border: none;
    border-radius: 12px;
    font-size: 12pt;
    font-weight: 700;
    padding: 12px 28px;
}}
QPushButton#HeroButton:hover {{ background: #F2FBF7; }}
QPushButton#HeroButton:disabled {{ color: {FAINT}; }}
QPushButton#Danger {{ color: {DANGER}; }}
QPushButton#Danger:hover {{ background: {DANGER_SOFT}; border-color: #EBC2BB; }}
QPushButton#Danger:disabled {{ color: {FAINT}; background: {CARD}; border-color: {BORDER}; }}
QPushButton#Link {{
    background: transparent;
    border: none;
    color: {ACCENT};
    padding: 2px 4px;
}}
QPushButton#Link:hover {{ text-decoration: underline; }}

QPushButton#SegLeft, QPushButton#SegRight {{
    background: #EFECE6;
    border: 1px solid {BORDER};
    padding: 6px 14px;
    color: {MUTED};
}}
QPushButton#SegLeft {{ border-top-right-radius: 0; border-bottom-right-radius: 0; border-right: none; }}
QPushButton#SegRight {{ border-top-left-radius: 0; border-bottom-left-radius: 0; }}
QPushButton#SegLeft:checked, QPushButton#SegRight:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton#Nav {{
    background: transparent;
    border: none;
    border-radius: 9px;
    padding: 9px 12px;
    text-align: left;
    color: #3A3A3C;
    font-size: 10.5pt;
}}
QPushButton#Nav:hover {{ background: rgba(0,0,0,0.04); }}
QPushButton#Nav:checked {{
    background: {CARD};
    color: {ACCENT};
    font-weight: 600;
}}

QLineEdit, QSpinBox, QTimeEdit {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QTimeEdit:focus {{ border-color: {ACCENT}; }}
QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px 10px;
}}
QComboBox:disabled {{ color: {FAINT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button,
QTimeEdit::up-button, QTimeEdit::down-button {{ width: 16px; border: none; }}

QListWidget, QTreeWidget, QTableWidget {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    outline: none;
    alternate-background-color: #FAF9F7;
}}
QListWidget::item, QTreeWidget::item, QTableWidget::item {{
    padding: 5px 4px;
    border-radius: 6px;
}}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background: {ACCENT_SOFT};
    color: {TEXT};
}}
QHeaderView::section {{
    background: {CARD};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 4px;
    color: {MUTED};
    font-weight: 600;
}}
QProgressBar {{
    background: #E9E6E0;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #D2CDC4; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}

QMenu {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
QToolTip {{
    background: {TEXT};
    color: white;
    border: none;
    padding: 5px 8px;
    border-radius: 6px;
}}
"""
