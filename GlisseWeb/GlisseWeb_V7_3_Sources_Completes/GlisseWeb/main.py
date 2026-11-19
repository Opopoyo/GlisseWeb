# -*- coding: utf-8 -*-
"""GlisseWeb 7.3 - navigateur Windows plein ecran, panneau lateral optimise,
page d'accueil animée et securite renforcee.
Qt WebEngine / Chromium. Prototype : ne remplace pas un navigateur majeur.
"""
from __future__ import annotations

import json
import shutil
import math
import os
import random
import sys
from datetime import datetime
from pathlib import Path

from guard import HOME, is_allowed_main_url, query_to_url, suspicious_download
from layout_math import sidebar_grid, card_preview_height, compact_icon_width, cycle_tab_index, window_rail_bottom_reserve, compact_close_geometry
from icon_cache import favicon_path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QStandardPaths, Qt, QTimer, QUrl, QRectF, QSize, QEvent
from PySide6.QtGui import QAction, QColor, QCursor, QDesktopServices, QFontMetrics, QIcon, QKeySequence, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

APP_NAME = "GlisseWeb"
VERSION = "7.3"
SIDE_WIDTH = 416
RAIL_WIDTH = 62  # barre permanente des favicons, sans aperçu ni titres visibles
BASE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GlisseWeb"
DATA = BASE / "Data"
PROFILE_DIR = BASE / "Profil"
ICON = Path(__file__).with_name("glisseweb.ico")
FAVICON_DIR = DATA / "Favicons"

DEFAULT_HOME_SITES = [
    {"glyph": "▶", "name": "YouTube", "url": "https://www.youtube.com/"},
    {"glyph": "⌘", "name": "GitHub", "url": "https://github.com/"},
    {"glyph": "✦", "name": "ChatGPT", "url": "https://chatgpt.com/"},
    {"glyph": "◇", "name": "AliExpress", "url": "https://www.aliexpress.com/"},
    {"glyph": "◉", "name": "Google Earth", "url": "https://earth.google.com/web/"},
]


def save_json(path: Path, value: object) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
    except OSError:
        pass


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return fallback


class GuardedPage(QWebEnginePage):
    def __init__(self, profile, owner, parent):
        super().__init__(profile, parent)
        self.owner = owner

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if is_main_frame:
            target = url.toString()
            if not is_allowed_main_url(target):
                QTimer.singleShot(0, lambda u=target: self.owner.blocked_navigation(u))
                return False
            if url.scheme().lower() == "http" and not self.owner.allow_http(url):
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


def secure_settings(settings):
    A = QWebEngineSettings.WebAttribute
    for attr, val in (
        (A.JavascriptCanOpenWindows, False),
        (A.JavascriptCanAccessClipboard, False),
        (A.JavascriptCanPaste, False),
        (A.LocalContentCanAccessFileUrls, False),
        (A.LocalContentCanAccessRemoteUrls, False),
        (A.AllowRunningInsecureContent, False),
        (A.AllowGeolocationOnInsecureOrigins, False),
        (A.ScreenCaptureEnabled, False),
        (A.PluginsEnabled, False),
        (A.HyperlinkAuditingEnabled, False),
        (A.NavigateOnDropEnabled, False),
        (A.DnsPrefetchEnabled, False),
        (A.PlaybackRequiresUserGesture, True),
        (A.WebRTCPublicInterfacesOnly, True),
    ):
        settings.setAttribute(attr, val)
    settings.setUnknownUrlSchemePolicy(
        QWebEngineSettings.UnknownUrlSchemePolicy.DisallowUnknownUrlSchemes
    )


class StarFieldWidget(QWidget):
    """Fond animé subtil : particules stellaires et orbites ovales."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0.0
        self.stars = []
        for _ in range(96):
            band = random.choice((0, 1, 2))
            self.stars.append({
                "band": band,
                "ang": random.random() * math.tau,
                "speed": random.uniform(0.0008, 0.003) * (1.0 + band * 0.18),
                "rx": random.uniform(0.18, 0.48),
                "ry": random.uniform(0.10, 0.28),
                "size": random.uniform(0.9, 2.5),
                "alpha": random.randint(70, 210),
                "twinkle": random.uniform(0.7, 1.4),
            })
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.timer.start(33)

    def advance(self):
        self.phase += 0.02
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(8, 14, 22))
        grad.setColorAt(0.45, QColor(11, 22, 34))
        grad.setColorAt(1.0, QColor(6, 10, 18))
        painter.fillRect(self.rect(), grad)

        w = max(1, self.width())
        h = max(1, self.height())
        cx, cy = w * 0.50, h * 0.47

        painter.setPen(QPen(QColor(90, 170, 210, 22), 1.0))
        for factor in (0.28, 0.38, 0.48):
            rect = QRectF(cx - w * factor, cy - h * factor * 0.42, w * factor * 2, h * factor * 0.84)
            painter.drawEllipse(rect)

        for star in self.stars:
            ang = star["ang"] + self.phase * star["speed"] * 90
            rx = w * star["rx"]
            ry = h * star["ry"]
            x = cx + math.cos(ang) * rx
            y = cy + math.sin(ang) * ry
            flicker = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(self.phase * 2.7 + star["ang"] * star["twinkle"]))
            alpha = min(255, max(20, int(star["alpha"] * flicker)))
            size = star["size"]
            color = QColor(180, 235, 255, alpha) if star["band"] == 0 else QColor(120, 215, 210, alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(x - size / 2, y - size / 2, size, size))

    def showEvent(self, event):
        super().showEvent(event)
        if not self.timer.isActive():
            self.timer.start(33)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)


class HomeShortcutTile(QFrame):
    def __init__(self, glyph: str, name: str, url: str, callback, parent=None):
        super().__init__(parent)
        self.url = url
        self.callback = callback
        self.setObjectName("homeTileFrame")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(url)
        self.setFixedSize(132, 118)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.addStretch(1)
        self.glyph_label = QLabel((glyph or name[:1] or "✦")[:1], self)
        self.glyph_label.setObjectName("homeTileGlyph")
        self.glyph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.glyph_label)
        self.name_label = QLabel(name, self)
        self.name_label.setObjectName("homeTileName")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)
        layout.addStretch(1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.callback:
            self.callback(self.url)
        super().mousePressEvent(event)


class BrowserView(QWebEngineView):
    def __init__(self, browser: "GlisseWeb", parent: QWidget | None = None):
        super().__init__(parent)
        self.browser = browser

    def createWindow(self, _window_type):
        return self.browser.add_tab(None, switch=True, private=self.browser.is_private(self))


class GlisseWeb(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        if ICON.exists():
            self.setWindowIcon(QIcon(str(ICON)))
        self.setStyleSheet(STYLE)

        DATA.mkdir(parents=True, exist_ok=True)
        FAVICON_DIR.mkdir(parents=True, exist_ok=True)
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self.bookmarks = load_json(DATA / "favoris.json", [])
        self.history = load_json(DATA / "historique.json", [])
        self.config = load_json(DATA / "config.json", {"previews": True, "home_sites": DEFAULT_HOME_SITES})
        if not isinstance(self.bookmarks, list):
            self.bookmarks = []
        if not isinstance(self.history, list):
            self.history = []
        if not isinstance(self.config, dict):
            self.config = {"previews": True, "home_sites": DEFAULT_HOME_SITES}
        self.config.setdefault("previews", True)
        sites = self.config.get("home_sites")
        if not isinstance(sites, list) or not sites:
            self.config["home_sites"] = [dict(x) for x in DEFAULT_HOME_SITES]

        self.preview_enabled = bool(self.config.get("previews", True))
        self.tab_titles: dict[BrowserView, str] = {}
        self.snapshots: dict[BrowserView, QPixmap] = {}
        self.private_tabs: set[BrowserView] = set()
        self.home_tabs: set[BrowserView] = set()
        self.http_allowed: set[str] = set()
        self.sidebar_visible = False
        self.panel_pinned = False
        self.compact_mode = bool(self.config.get("compact_rail", False))  # option mémorisée
        self.media_fullscreen = False
        self.panel_mode = "tabs"
        self.closed_urls: list[str] = []
        self.restore_sidebar_after_overview = False

        self.profile = QWebEngineProfile("GlisseWeb", self)
        self.profile.setPersistentStoragePath(str(PROFILE_DIR / "storage"))
        self.profile.setCachePath(str(PROFILE_DIR / "cache"))
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.OnlyPersistentCookies
        )
        self.profile.setPersistentPermissionsPolicy(
            QWebEngineProfile.PersistentPermissionsPolicy.AskEveryTime
        )
        self.profile.downloadRequested.connect(self.handle_download)

        self.private_profile = QWebEngineProfile(self)
        self.private_profile.setPersistentPermissionsPolicy(
            QWebEngineProfile.PersistentPermissionsPolicy.AskEveryTime
        )
        self.private_profile.downloadRequested.connect(self.handle_download)

        for profile in (self.profile, self.private_profile):
            secure_settings(profile.settings())
            if hasattr(profile, "setPushServiceEnabled"):
                profile.setPushServiceEnabled(False)

        self.root = QWidget(self)
        self.root.setObjectName("root")
        self.setCentralWidget(self.root)
        self.root_layout = QHBoxLayout(self.root)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # La colonne de favicons est un vrai panneau Qt qui reduit la largeur
        # de la page, et non un calque pose par-dessus le contenu web.
        self.compact_rail = QFrame(self.root)
        self.compact_rail.setObjectName("compactRail")
        self.compact_rail.setFixedWidth(RAIL_WIDTH)
        self.compact_rail.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.compact_rail.hide()
        self.root_layout.addWidget(self.compact_rail, 0)

        self.sidebar = QFrame(self.root)
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(0)
        self.sidebar.setMaximumWidth(0)
        self.sidebar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.root_layout.addWidget(self.sidebar, 0)

        self.content = QStackedWidget(self.root)
        self.content.setObjectName("content")
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.root_layout.addWidget(self.content, 1)

        self.pages = QStackedWidget(self.content)
        self.pages.setObjectName("pages")
        self.content.addWidget(self.pages)
        self.home_page = self.build_home_page()
        self.content.addWidget(self.home_page)
        self.overview_page = self.build_overview_page()
        self.content.addWidget(self.overview_page)
        self.overview_visible = False

        self.animation = QPropertyAnimation(self.sidebar, b"maximumWidth", self)
        self.animation.setDuration(205)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self.refresh_rows)
        self.animation.finished.connect(self.sync_compact_rail_visibility)

        self.rows_refresh_timer = QTimer(self)
        self.rows_refresh_timer.setSingleShot(True)
        self.rows_refresh_timer.timeout.connect(self.refresh_rows)
        self.build_sidebar()
        self.build_compact_rail()
        self.shortcuts()

        self.mouse_monitor = QTimer(self)
        self.mouse_monitor.timeout.connect(self.check_mouse_edge)
        self.mouse_monitor.start(120)

        self.add_tab(None, internal_home=True)
        # Mémorise une vraie taille de fenêtre adaptée à la résolution Windows.
        screen = QApplication.primaryScreen()
        if screen:
            bounds = screen.availableGeometry()
            width = min(1200, max(480, bounds.width() - 70))
            height = min(800, max(400, bounds.height() - 70))
            self.resize(width, height)
            self.move(bounds.x() + (bounds.width() - width) // 2,
                      bounds.y() + (bounds.height() - height) // 2)
        else:
            self.resize(1100, 740)
        self.showFullScreen()
        self.refresh_window_button()
        self.adjust_rail_for_window()
        self.sync_compact_rail_visibility()
        # Filtre clavier limité aux flèches lorsque le curseur ou le focus
        # est sur la barre compacte (pas pendant la navigation Web normale).
        QApplication.instance().installEventFilter(self)

    def build_sidebar(self):
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(10, 9, 10, 5)
        layout.setSpacing(4)

        head = QHBoxLayout()
        title = QLabel("◉ GLISSEWEB")
        title.setObjectName("brand")
        head.addWidget(title)
        head.addStretch()
        self.pin_btn = self.make_btn("◇", "Épingler / désépingler le panneau", self.toggle_pin, "icon")
        head.addWidget(self.pin_btn)
        head.addWidget(self.make_btn("▥", "Passer à la barre compacte des onglets", self.enable_compact_mode, "icon"))
        head.addWidget(self.make_btn("❮", "Masquer le panneau (ou revenir à la barre compacte)", lambda: self.set_sidebar(False), "icon"))
        self.window_btn = self.make_btn("▢", "Passer en mode fenêtre / plein écran (F11)", self.toggle_fullscreen, "icon")
        head.addWidget(self.window_btn)
        head.addWidget(self.make_btn("×", "Fermer GlisseWeb", self.close, "iconDanger"))
        layout.addLayout(head)

        self.address = QLineEdit(self.sidebar)
        self.address.setObjectName("address")
        self.address.setPlaceholderText("Rechercher ou saisir une adresse complète…")
        self.address.setMinimumHeight(39)
        self.address.setToolTip("Ctrl+L pour sélectionner toute l'URL")
        self.address.returnPressed.connect(self.navigate_address)
        layout.addWidget(self.address)

        self.connection_info = QLabel("HTTPS · verifier le domaine")
        self.connection_info.setObjectName("connectionInfo")
        self.connection_info.setWordWrap(False)
        self.connection_info.setMinimumWidth(0)
        self.connection_info.setFixedHeight(19)
        layout.addWidget(self.connection_info)

        self.find_input = QLineEdit(self.sidebar)
        self.find_input.setObjectName("findInput")
        self.find_input.setPlaceholderText("Trouver dans la page…")
        self.find_input.textChanged.connect(self.find_in_page)
        self.find_input.hide()
        layout.addWidget(self.find_input)

        tools = QHBoxLayout()
        tools.setSpacing(5)
        for glyph, hint, callback in (
            ("←", "Retour", self.back),
            ("→", "Suivant", self.forward),
            ("↻", "Actualiser", self.reload),
            ("⌂", "Accueil", self.go_home),
            ("G", "Google", self.open_google),
            ("☆", "Favori", self.toggle_favorite),
        ):
            tools.addWidget(self.make_btn(glyph, hint, callback, "tool"))
        layout.addLayout(tools)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(5)
        self.tab_nav = self.make_btn("▣", "Afficher les onglets", lambda: self.change_mode("tabs"), "mode")
        self.fav_nav = self.make_btn("★", "Afficher les favoris", lambda: self.change_mode("favorites"), "mode")
        self.hist_nav = self.make_btn("🕘", "Afficher l'historique", lambda: self.change_mode("history"), "mode")
        for btn in (self.tab_nav, self.fav_nav, self.hist_nav):
            mode_row.addWidget(btn)
        mode_row.addStretch()
        self.new_tab_btn = self.make_btn("＋", "Nouvel onglet", self.new_tab, "mode")
        self.private_btn = self.make_btn("◌", "Nouvel onglet prive", self.new_private_tab, "mode")
        self.overview_btn = self.make_btn("▦", "Vue generale des onglets (F9)", self.show_overview, "mode")
        mode_row.addWidget(self.new_tab_btn)
        mode_row.addWidget(self.private_btn)
        mode_row.addWidget(self.overview_btn)
        layout.addLayout(mode_row)

        self.section_title = QLabel("ONGLETS")
        self.section_title.setObjectName("sectionTitle")
        layout.addWidget(self.section_title)

        self.scroll = QScrollArea(self.sidebar)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Empêche la grille de changer de largeur lorsque le défilement apparaît.
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.items_holder = QWidget()
        self.items_holder.setObjectName("itemsHolder")
        self.items_layout = QGridLayout(self.items_holder)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setHorizontalSpacing(6)
        self.items_layout.setVerticalSpacing(6)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.items_holder)
        layout.addWidget(self.scroll, 1)

        self.main_action = QPushButton("＋ Nouvel onglet")
        self.main_action.setObjectName("primary")
        self.main_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.main_action.clicked.connect(self.new_tab)
        self.main_action.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.main_action)

        # Une seule rangée ultra-compacte ; le reste de la hauteur revient aux onglets.
        footer = QHBoxLayout()
        footer.setSpacing(4)
        self.preview_btn = self.make_btn("▣", "Afficher ou masquer les miniatures", self.toggle_previews, "footerIcon")
        footer.addWidget(self.preview_btn)
        footer.addWidget(self.make_btn("↓", "Ouvrir les téléchargements", self.open_downloads, "footerIcon"))
        footer.addStretch(1)
        footer.addWidget(self.make_btn("−", "Réduire le zoom (Ctrl+-)", lambda: self.adjust_zoom(-0.1), "footerIcon"))
        footer.addWidget(self.make_btn("100%", "Zoom à 100% (Ctrl+0)", self.reset_zoom, "footerIcon"))
        footer.addWidget(self.make_btn("+", "Augmenter le zoom (Ctrl++)", lambda: self.adjust_zoom(0.1), "footerIcon"))
        layout.addLayout(footer)

        self.update_preview_button()
        self.change_mode("tabs")

    def build_compact_rail(self):
        """Panneau permanent d'icônes, indépendant du panneau détaillé V7."""
        rail_layout = QVBoxLayout(self.compact_rail)
        rail_layout.setContentsMargins(4, 8, 4, 8)
        rail_layout.setSpacing(7)
        expand = self.make_btn("☰", "Déployer le panneau complet", self.expand_compact_mode, "railAction")
        expand.setFixedSize(44, 40)
        rail_layout.addWidget(expand, 0, Qt.AlignmentFlag.AlignHCenter)

        self.rail_scroll = QScrollArea(self.compact_rail)
        self.rail_scroll.setObjectName("railScroll")
        self.rail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.rail_scroll.setWidgetResizable(True)
        self.rail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.rail_holder = QWidget(self.rail_scroll)
        self.rail_holder.setObjectName("railHolder")
        self.rail_items = QVBoxLayout(self.rail_holder)
        self.rail_items.setContentsMargins(2, 3, 2, 3)
        self.rail_items.setSpacing(6)
        self.rail_items.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.rail_scroll.setWidget(self.rail_holder)
        rail_layout.addWidget(self.rail_scroll, 1)

        plus = self.make_btn("+", "Ouvrir un nouvel onglet", self.new_tab, "railAction")
        plus.setFixedSize(44, 42)
        rail_layout.addWidget(plus, 0, Qt.AlignmentFlag.AlignHCenter)
        hide = self.make_btn("−", "Quitter le mode compact et masquer la barre", self.disable_compact_mode, "railMini")
        hide.setFixedSize(31, 24)
        rail_layout.addWidget(hide, 0, Qt.AlignmentFlag.AlignHCenter)

        # Réserve une bande inférieure de 100 pixels seulement en mode fenêtre.
        # Les boutons « + » et « − » restent au-dessus de cette bande ; les
        # favicons défilent dans la zone centrale, même sur un petit écran.
        self.rail_bottom_reserve = QWidget(self.compact_rail)
        self.rail_bottom_reserve.setObjectName("railBottomReserve")
        self.rail_bottom_reserve.setFixedHeight(0)
        rail_layout.addWidget(self.rail_bottom_reserve, 0)
        self.adjust_rail_for_window()
        self.refresh_rail()

    def adjust_rail_for_window(self):
        """Décale les commandes basses de 100 px en fenêtre (pas en plein écran)."""
        if not hasattr(self, "rail_bottom_reserve"):
            return
        height = window_rail_bottom_reserve(self.isFullScreen(), self.height())
        self.rail_bottom_reserve.setFixedHeight(height)
        self.rail_bottom_reserve.setVisible(height > 0)

    def focus_current_rail_tab(self):
        """Garde l'onglet sélectionné visible après navigation clavier."""
        if not hasattr(self, "rail_buttons") or not self.compact_rail.isVisible():
            return
        button = self.rail_buttons.get(self.current_view())
        if button is not None:
            self.rail_scroll.ensureWidgetVisible(button, 0, 12)
            # Permet d'enchaîner plusieurs ↑/↓ sans ramener la souris.
            button.setFocus(Qt.FocusReason.OtherFocusReason)

    def move_compact_tab(self, delta: int):
        """↑ onglet précédent, ↓ suivant, en rebouclant en fin de liste."""
        if not (self.compact_mode and self.compact_rail.isVisible()):
            return
        index = cycle_tab_index(self.pages.currentIndex(), self.pages.count(), delta)
        if index < 0:
            return
        target = self.pages.widget(index)
        if isinstance(target, BrowserView):
            self.select_tab(target)
            QTimer.singleShot(0, self.focus_current_rail_tab)

    def eventFilter(self, watched, event):
        """Flèches seules seulement près du rail : préserve le scroll du web."""
        if (event.type() == QEvent.Type.KeyPress
                and self.isActiveWindow()
                and getattr(self, "compact_rail", None) is not None
                and self.compact_rail.isVisible()
                and event.modifiers() == Qt.KeyboardModifier.NoModifier
                and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)):
            pointer_here = self.compact_rail.rect().contains(
                self.compact_rail.mapFromGlobal(QCursor.pos())
            )
            focus = QApplication.focusWidget()
            focus_here = focus is not None and (focus is self.compact_rail or self.compact_rail.isAncestorOf(focus))
            if pointer_here or focus_here:
                self.move_compact_tab(-1 if event.key() == Qt.Key.Key_Up else 1)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def refresh_rail(self):
        """Rafraîchit la liste sans aucune requête réseau supplémentaire."""
        if not hasattr(self, "rail_items"):
            return
        bar = self.rail_scroll.verticalScrollBar()
        former_scroll = bar.value()
        self.rail_scroll.setUpdatesEnabled(False)
        self.rail_buttons = {}
        while self.rail_items.count():
            item = self.rail_items.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index in range(self.pages.count()):
            view = self.pages.widget(index)
            if not isinstance(view, BrowserView):
                continue
            title = self.tab_titles.get(view, "Nouvel onglet")
            host = self.display_domain(view)
            # Le favicon et la croix vivent dans la MÊME vignette, sans
            # agrandir le rail ni gêner le défilement des onglets.
            icon_width = compact_icon_width(RAIL_WIDTH)
            tile = QWidget(self.rail_holder)
            tile.setObjectName("railEntry")
            tile.setFixedSize(icon_width, 41)
            button = self.make_btn("", f"{index + 1}. {title} — {host}",
                                   lambda _checked=False, v=view: self.select_tab(v), "railTab")
            button.setParent(tile)
            button.setGeometry(0, 0, icon_width, 41)
            button.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            self.rail_buttons[view] = button
            button.setAccessibleName(f"Onglet {index + 1} : {title}")
            button.setProperty("selected", view is self.current_view())
            button.style().unpolish(button)
            button.style().polish(button)

            # Un favicon réel lorsque le site en fournit un ; sinon un repère
            # distinctif. Les onglets privés ne consultent pas le cache disque.
            icon = view.icon()
            fallback = None if (self.is_private(view) or view in self.home_tabs) else self.icon_for_url(view.url().toString())
            if view in self.home_tabs:
                button.setText("⌂")
            elif not icon.isNull():
                button.setIcon(icon)
                button.setIconSize(QSize(25, 25))
            elif fallback is not None and not fallback.isNull():
                button.setIcon(QIcon(fallback))
                button.setIconSize(QSize(25, 25))
            else:
                button.setText("◌" if self.is_private(view) else (host[:1] or "•").upper())
            # Un petit × est superposé au coin supérieur droit de l’icône.
            # Son clic est indépendant : il ne sélectionne pas l’onglet.
            x, y, size = compact_close_geometry(icon_width, 41)
            close = QToolButton(tile)
            close.setObjectName("railClose")
            close.setText("×")
            close.setFixedSize(size, size)
            close.move(x, y)
            close.setToolTip(f"Fermer l'onglet : {title}")
            close.setAccessibleName(f"Fermer l'onglet {index + 1} : {title}")
            close.setCursor(Qt.CursorShape.PointingHandCursor)
            close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            close.clicked.connect(lambda _checked=False, v=view: self.close_tab(v))
            close.raise_()
            self.rail_items.addWidget(tile, 0, Qt.AlignmentFlag.AlignHCenter)

        self.rail_scroll.setUpdatesEnabled(True)
        QTimer.singleShot(0, lambda value=former_scroll: bar.setValue(value))

    def scroll_rail_to_last_tab(self):
        if hasattr(self, "rail_scroll"):
            bar = self.rail_scroll.verticalScrollBar()
            QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))

    def sync_compact_rail_visibility(self):
        if not hasattr(self, "compact_rail"):
            return
        should_show = (self.compact_mode and not self.sidebar_visible
                       and not self.overview_visible and not self.media_fullscreen)
        self.compact_rail.setVisible(should_show)

    def enable_compact_mode(self):
        """Réduit la barre V7 en rail de favicons permanent."""
        self.compact_mode = True
        self.config["compact_rail"] = True
        save_json(DATA / "config.json", self.config)
        self.panel_pinned = False
        self.pin_btn.setText("◇")
        self.pin_btn.setToolTip("Épingler / désépingler le panneau")
        self.set_sidebar(False, immediate=True)
        self.refresh_rail()

    def expand_compact_mode(self):
        """Déploie et épingle le panneau complet depuis le rail."""
        self.panel_pinned = True
        self.pin_btn.setText("◆")
        self.pin_btn.setToolTip("Désépingler le panneau pour revenir au rail au survol")
        self.set_sidebar(True)

    def disable_compact_mode(self):
        """Reprend le comportement escamotable d'origine de GlisseWeb V7."""
        self.compact_mode = False
        self.config["compact_rail"] = False
        save_json(DATA / "config.json", self.config)
        self.panel_pinned = False
        self.pin_btn.setText("◇")
        self.pin_btn.setToolTip("Épingler / désépingler le panneau")
        self.set_sidebar(False, immediate=True)

    def toggle_compact_mode(self):
        if self.compact_mode:
            self.disable_compact_mode()
        else:
            self.enable_compact_mode()

    @staticmethod
    def make_btn(text: str, tooltip: str, callback, kind="tool") -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(kind)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def build_home_page(self) -> QWidget:
        root = StarFieldWidget(self.content)
        root.setObjectName("homeSky")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(10)
        outer.addStretch(1)

        shell = QWidget(root)
        shell.setObjectName("homeShell")
        shell.setMaximumWidth(1100)
        shell_l = QVBoxLayout(shell)
        shell_l.setContentsMargins(0, 0, 0, 0)
        shell_l.setSpacing(12)

        kicker = QLabel("ESPACE PERSONNEL")
        kicker.setObjectName("homeKicker")
        kicker.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        shell_l.addWidget(kicker)

        # Affiche le vrai logo de GlisseWeb à la place de l'ancien slogan.
        logo = QLabel(shell)
        logo.setObjectName("homeLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if ICON.exists():
            logo_icon = QIcon(str(ICON))
            logo.setPixmap(logo_icon.pixmap(110, 110))
        else:
            logo.setText("◉")
        shell_l.addWidget(logo)
        logo_name = QLabel("GLISSEWEB", shell)
        logo_name.setObjectName("homeLogoName")
        logo_name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        shell_l.addWidget(logo_name)

        subt = QLabel("Recherche Google, accès direct à tes sites et page d'accueil personnalisable.")
        subt.setObjectName("homeSubtitle")
        subt.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subt.setWordWrap(True)
        shell_l.addWidget(subt)
        shell_l.addSpacing(8)

        search_wrap = QHBoxLayout()
        search_wrap.addStretch(1)
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self.home_search = QLineEdit(shell)
        self.home_search.setObjectName("homeSearch")
        self.home_search.setPlaceholderText("Rechercher sur Google ou saisir une adresse…")
        self.home_search.setMinimumWidth(420)
        self.home_search.setMaximumWidth(680)
        self.home_search.returnPressed.connect(self.search_from_home)
        search_row.addWidget(self.home_search, 1)
        search_button = self.make_btn("Rechercher", "Lancer la recherche", self.search_from_home, "homeSearchBtn")
        search_row.addWidget(search_button)
        search_wrap.addLayout(search_row, 1)
        search_wrap.addStretch(1)
        shell_l.addLayout(search_wrap)

        actions = QHBoxLayout()
        actions.addStretch(1)
        inner_actions = QHBoxLayout()
        inner_actions.setSpacing(8)
        inner_actions.addWidget(self.make_btn("＋ Ajouter un site", "Ajouter un raccourci à l'accueil", self.add_home_site_dialog, "homeMiniBtn"))
        inner_actions.addWidget(self.make_btn("☆ Ajouter la page actuelle", "Ajouter l'onglet courant aux raccourcis", self.add_current_page_to_home, "homeMiniBtn"))
        inner_actions.addWidget(self.make_btn("Réinitialiser", "Réinitialiser les raccourcis par défaut", self.reset_home_sites, "homeMiniBtn"))
        actions.addLayout(inner_actions)
        actions.addStretch(1)
        shell_l.addLayout(actions)

        shortcuts_label = QLabel("ACCÈS RAPIDES")
        shortcuts_label.setObjectName("homeKicker")
        shortcuts_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        shell_l.addWidget(shortcuts_label)

        self.home_tiles_container = QWidget(shell)
        self.home_tiles_container.setObjectName("homeTilesContainer")
        self.home_tiles_grid = QGridLayout(self.home_tiles_container)
        self.home_tiles_grid.setContentsMargins(0, 0, 0, 0)
        self.home_tiles_grid.setHorizontalSpacing(16)
        self.home_tiles_grid.setVerticalSpacing(16)
        self.home_tiles_grid.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        shell_l.addWidget(self.home_tiles_container, 0, Qt.AlignmentFlag.AlignHCenter)
        self.rebuild_home_tiles()

        hint = QLabel("Bord gauche : onglets · F9 : vue générale des onglets · ajoute tes propres sites depuis cette page")
        hint.setObjectName("homeHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hint.setWordWrap(True)
        shell_l.addWidget(hint)

        outer.addWidget(shell, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)
        return root

    def rebuild_home_tiles(self):
        if not hasattr(self, "home_tiles_grid"):
            return
        self.clear_layout_recursive(self.home_tiles_grid)
        sites = self.config.get("home_sites", [])
        available = max(320, getattr(self.home_page, 'width', lambda: 920)() - 120 if hasattr(self, 'home_page') else 920)
        cols = max(1, min(6, available // 148))
        for i in range(cols):
            self.home_tiles_grid.setColumnStretch(i, 0)
            self.home_tiles_grid.setColumnMinimumWidth(i, 132)
        for i, entry in enumerate(sites):
            glyph = (entry.get("glyph") or entry.get("name", "?")[:1] or "✦").strip()[:1]
            name = entry.get("name", "Site")
            url = entry.get("url", HOME)
            tile = HomeShortcutTile(glyph, name, url, self.open_in_current, self.home_tiles_container)
            self.home_tiles_grid.addWidget(tile, i // cols, i % cols, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

    def add_home_site_dialog(self):
        name, ok = QInputDialog.getText(self, "Ajouter un site", "Nom du site :")
        if not ok or not name.strip():
            return
        url, ok = QInputDialog.getText(self, "Ajouter un site", "Adresse du site (https://...) :")
        if not ok or not url.strip():
            return
        normalized = query_to_url(url)
        glyph = name.strip()[0].upper()
        self.config.setdefault("home_sites", []).append({"glyph": glyph, "name": name.strip(), "url": normalized})
        save_json(DATA / "config.json", self.config)
        self.rebuild_home_tiles()

    def add_current_page_to_home(self):
        view = self.current_view()
        if not view:
            return
        url = view.url().toString()
        title = self.tab_titles.get(view, "Nouveau site")
        if not url.startswith(("https://", "http://")):
            QMessageBox.information(self, "Ajouter à l'accueil", "Ouvre d'abord un vrai site web pour l'ajouter à l'accueil.")
            return
        for entry in self.config.setdefault("home_sites", []):
            if entry.get("url") == url:
                QMessageBox.information(self, "Ajouter à l'accueil", "Ce site est déjà présent dans l'accueil.")
                return
        self.config["home_sites"].append({"glyph": title[:1].upper() or "✦", "name": title[:20], "url": url})
        save_json(DATA / "config.json", self.config)
        self.rebuild_home_tiles()

    def reset_home_sites(self):
        if QMessageBox.question(self, "Réinitialiser l'accueil", "Réinitialiser la liste des sites proposés sur l'accueil ?") == QMessageBox.StandardButton.Yes:
            self.config["home_sites"] = [dict(x) for x in DEFAULT_HOME_SITES]
            save_json(DATA / "config.json", self.config)
            self.rebuild_home_tiles()

    def build_overview_page(self) -> QWidget:
        root = QWidget(self.content)
        root.setObjectName("overviewRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 23, 28, 18)
        layout.setSpacing(14)
        head = QHBoxLayout()
        text_area = QVBoxLayout()
        heading = QLabel("Tous les onglets")
        heading.setObjectName("overviewHeading")
        text_area.addWidget(heading)
        self.overview_count = QLabel("Toutes tes pages, en un seul coup d'œil")
        self.overview_count.setObjectName("overviewSub")
        text_area.addWidget(self.overview_count)
        head.addLayout(text_area)
        head.addStretch()
        home_button = self.make_btn("⌂ Accueil", "Retour a la page d'accueil", self.go_home_from_overview, "overviewButton")
        head.addWidget(home_button)
        close = self.make_btn("Fermer la vue  ×", "Retour à l'onglet actif (Échap)", self.close_overview, "overviewButton")
        head.addWidget(close)
        layout.addLayout(head)
        self.overview_search = QLineEdit(root)
        self.overview_search.setObjectName("overviewSearch")
        self.overview_search.setPlaceholderText("Filtrer les onglets par titre ou domaine…")
        self.overview_search.textChanged.connect(self.refresh_overview)
        layout.addWidget(self.overview_search)
        self.overview_scroll = QScrollArea(root)
        self.overview_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.overview_scroll.setObjectName("overviewScroll")
        self.overview_scroll.setWidgetResizable(True)
        self.overview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.overview_holder = QWidget()
        self.overview_holder.setObjectName("overviewHolder")
        self.overview_grid = QGridLayout(self.overview_holder)
        self.overview_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.overview_grid.setSpacing(14)
        self.overview_grid.setContentsMargins(0, 0, 0, 0)
        self.overview_scroll.setWidget(self.overview_holder)
        layout.addWidget(self.overview_scroll, 1)
        return root

    def search_from_home(self):
        raw = self.home_search.text().strip()
        if raw:
            self.open_in_current(query_to_url(raw))

    def go_home_from_overview(self):
        self.close_overview()
        self.go_home()

    def open_in_current(self, url: str):
        view = self.current_view()
        if view is None:
            self.add_tab(url)
            return
        self.home_tabs.discard(view)
        self.overview_visible = False
        self.content.setCurrentWidget(self.pages)
        view.setUrl(QUrl(url))
        view.setFocus()
        self.sync_address()
        self.maybe_hide_sidebar()

    def toggle_overview(self):
        if self.overview_visible:
            self.close_overview()
        else:
            self.show_overview()

    def show_overview(self):
        if self.media_fullscreen:
            return
        self.capture_thumbnail(self.current_view())
        self.restore_sidebar_after_overview = self.panel_pinned and self.sidebar_visible
        self.set_sidebar(False, immediate=True)
        self.overview_visible = True
        self.sync_compact_rail_visibility()
        self.content.setCurrentWidget(self.overview_page)
        self.overview_search.clear()
        self.refresh_overview()

    def close_overview(self):
        if not self.overview_visible:
            return
        self.overview_visible = False
        self.sync_content()
        if self.restore_sidebar_after_overview and self.panel_pinned:
            self.set_sidebar(True)
        self.restore_sidebar_after_overview = False
        self.sync_compact_rail_visibility()

    def sync_content(self):
        if self.overview_visible:
            self.content.setCurrentWidget(self.overview_page)
        elif self.current_view() in self.home_tabs:
            self.content.setCurrentWidget(self.home_page)
        else:
            self.content.setCurrentWidget(self.pages)

    def refresh_overview(self, _text=None):
        if not hasattr(self, "overview_grid") or not self.overview_visible:
            return
        position = 0 if _text is not None else self.overview_scroll.verticalScrollBar().value()
        self.overview_scroll.setUpdatesEnabled(False)
        self.clear_layout_recursive(self.overview_grid)
        needle = self.overview_search.text().strip().casefold()
        matched = []
        for i in range(self.pages.count()):
            view = self.pages.widget(i)
            if not isinstance(view, BrowserView):
                continue
            title = self.tab_titles.get(view, "Onglet")
            host = self.display_domain(view)
            if needle in (title + " " + host).casefold():
                matched.append(view)
        self.overview_count.setText(f"{len(matched)} affiché(s) sur {self.pages.count()} onglet(s) · cliquer pour ouvrir · × pour fermer")
        usable = max(160, self.overview_scroll.viewport().width() - 20)
        cols = max(1, min(6, (usable + 14) // 236))
        width = min(288, (usable - (cols - 1) * 14) // cols)
        for i, view in enumerate(matched):
            frame = self.tab_card(view, width=width, height=210, overview=True)
            self.overview_grid.addWidget(frame, i // cols, i % cols, Qt.AlignmentFlag.AlignTop)
        if not matched:
            label = QLabel("Aucun onglet correspondant.")
            label.setObjectName("empty")
            self.overview_grid.addWidget(label, 0, 0)
        self.overview_scroll.setUpdatesEnabled(True)
        QTimer.singleShot(0, lambda v=position: self.overview_scroll.verticalScrollBar().setValue(v))

    def display_domain(self, view: BrowserView) -> str:
        if view in self.home_tabs:
            return "Page d'accueil"
        return view.url().host() or "Nouvel onglet"

    def preview_for_size(self, view: BrowserView, width: int, height: int) -> QPixmap | None:
        if not self.preview_enabled or self.is_private(view):
            return None
        original = self.snapshots.get(view)
        if original is None or original.isNull():
            return None
        resized = original.scaled(
            width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        off_x = max(0, (resized.width() - width) // 2)
        off_y = max(0, (resized.height() - height) // 2)
        return resized.copy(off_x, off_y, width, height)

    def shortcuts(self):
        def add(combo, callback):
            action = QAction(self)
            action.setShortcut(QKeySequence(combo))
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            action.triggered.connect(callback)
            self.addAction(action)

        for combo, callback in (
            ("Ctrl+T", self.new_tab), ("Ctrl+W", self.close_current),
            ("Ctrl+L", self.focus_address), ("Ctrl+R", self.reload),
            ("F5", self.reload), ("Alt+Left", self.back),
            ("Alt+Right", self.forward), ("Ctrl+Tab", self.next_tab),
            ("Ctrl+Shift+Tab", self.previous_tab),
            ("Ctrl+D", self.toggle_favorite), ("Ctrl+F", self.focus_find),
            ("Ctrl+H", lambda: self.change_mode("history", True)),
            ("Ctrl+J", self.open_downloads), ("F11", self.toggle_fullscreen),
            ("Ctrl+Shift+T", self.restore_last_closed), ("Ctrl+Shift+N", self.new_private_tab),
            ("Ctrl++", lambda: self.adjust_zoom(0.1)), ("Ctrl+-", lambda: self.adjust_zoom(-0.1)),
            ("Ctrl+0", self.reset_zoom),
            ("F9", self.toggle_overview), ("Escape", self.close_overview),
            ("F8", self.toggle_compact_mode),
            ("Alt+Up", lambda: self.move_compact_tab(-1)),
            ("Alt+Down", lambda: self.move_compact_tab(1)),
        ):
            add(combo, callback)

    def current_view(self) -> BrowserView | None:
        widget = self.pages.currentWidget()
        return widget if isinstance(widget, BrowserView) else None

    def is_private(self, view: BrowserView | None) -> bool:
        return view in self.private_tabs

    def add_tab(self, url: str | None = None, switch: bool = True, private=False, internal_home=False) -> BrowserView:
        previous = self.current_view()
        if switch and previous is not None:
            self.capture_thumbnail(previous)
        view = BrowserView(self, self.pages)
        chosen_profile = self.private_profile if private else self.profile
        page = GuardedPage(chosen_profile, self, view)
        view.setPage(page)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        page.fullScreenRequested.connect(lambda req, v=view: self.handle_web_fullscreen(req, v))
        if hasattr(page, "permissionRequested"):
            page.permissionRequested.connect(self.handle_permission)
        elif hasattr(page, "featurePermissionRequested"):
            page.featurePermissionRequested.connect(
                lambda origin, feature, p=page: self.handle_legacy_permission(p, origin, feature)
            )
        view.titleChanged.connect(lambda title, v=view: self.update_title(v, title))
        view.urlChanged.connect(lambda changed, v=view: self.update_url(v, changed))
        view.loadFinished.connect(lambda ok, v=view: self.finished_loading(v, ok))
        view.iconChanged.connect(lambda _icon, v=view: self.on_favicon_changed(v))
        self.tab_titles[view] = "Onglet prive" if private else "Nouvel onglet"
        if private:
            self.private_tabs.add(view)
        index = self.pages.addWidget(view)
        if switch:
            self.pages.setCurrentIndex(index)
        if internal_home or not url:
            self.show_home(view)
        else:
            self.home_tabs.discard(view)
            view.setUrl(QUrl(url))
            if switch:
                self.overview_visible = False
                self.content.setCurrentWidget(self.pages)
        self.refresh_rows()
        self.sync_address()
        return view

    def show_home(self, view: BrowserView):
        """Native Qt start page, so the WebEngine security policy never blocks it."""
        if self.pages.indexOf(view) < 0:
            return
        self.home_tabs.add(view)
        self.snapshots.pop(view, None)
        self.tab_titles[view] = "Accueil"
        if view.url().toString() not in ("", "about:blank"):
            view.setUrl(QUrl("about:blank"))
        self.overview_visible = False
        if view is self.current_view():
            self.content.setCurrentWidget(self.home_page)
            self.home_search.clear()
        self.sync_address()
        self.refresh_rows()

    def new_private_tab(self):
        self.add_tab(None, private=True, internal_home=True)
        self.change_mode("tabs", not self.compact_mode)
        if self.compact_mode:
            self.scroll_rail_to_last_tab()

    def new_tab(self):
        self.add_tab(None, switch=True, internal_home=True)
        self.change_mode("tabs", not self.compact_mode)
        if self.compact_mode:
            self.scroll_rail_to_last_tab()

    def close_current(self):
        view = self.current_view()
        if view:
            self.close_tab(view)

    def close_tab(self, view: BrowserView):
        if self.pages.indexOf(view) < 0:
            return
        url = view.url().toString()
        if url.startswith(("https://", "http://")) and not self.is_private(view):
            self.closed_urls.append(url)
            self.closed_urls = self.closed_urls[-20:]
        self.pages.removeWidget(view)
        self.tab_titles.pop(view, None)
        self.snapshots.pop(view, None)
        self.private_tabs.discard(view)
        self.home_tabs.discard(view)
        view.deleteLater()
        if self.pages.count() == 0:
            self.add_tab(None, internal_home=True)
        if not self.overview_visible:
            self.sync_content()
        self.refresh_rows()
        self.refresh_overview()
        self.sync_address()

    def restore_last_closed(self):
        if self.closed_urls:
            self.add_tab(self.closed_urls.pop())

    def select_tab(self, view: BrowserView):
        if self.pages.indexOf(view) >= 0:
            self.capture_thumbnail(self.current_view())
            self.pages.setCurrentWidget(view)
            was_overview = self.overview_visible
            self.overview_visible = False
            self.sync_content()
            self.sync_address()
            self.refresh_rows()
            if was_overview and self.restore_sidebar_after_overview and self.panel_pinned:
                self.set_sidebar(True)
            self.restore_sidebar_after_overview = False
            self.maybe_hide_sidebar()
            self.sync_compact_rail_visibility()

    def next_tab(self):
        if self.pages.count():
            self.capture_thumbnail(self.current_view())
            self.pages.setCurrentIndex((self.pages.currentIndex() + 1) % self.pages.count())
            self.overview_visible = False
            self.sync_content()
            self.sync_address()
            self.refresh_rows()

    def previous_tab(self):
        if self.pages.count():
            self.capture_thumbnail(self.current_view())
            self.pages.setCurrentIndex((self.pages.currentIndex() - 1) % self.pages.count())
            self.overview_visible = False
            self.sync_content()
            self.sync_address()
            self.refresh_rows()

    def update_title(self, view: BrowserView, title: str):
        if self.pages.indexOf(view) == -1:
            return
        if view in self.home_tabs:
            self.tab_titles[view] = "Accueil"
        else:
            self.tab_titles[view] = (title or "Nouvel onglet").strip()
        self.schedule_rows_refresh()
        self.refresh_overview()

    def update_url(self, view: BrowserView, changed: QUrl):
        raw = changed.toString()
        if raw and raw != "about:blank":
            self.home_tabs.discard(view)
        if view is self.current_view():
            if not self.overview_visible:
                self.sync_content()
            self.sync_address()
        self.schedule_rows_refresh()

    def finished_loading(self, view: BrowserView, ok: bool):
        if not ok or self.pages.indexOf(view) < 0:
            return
        QTimer.singleShot(650, lambda v=view: self.capture_thumbnail(v))
        # L'icône peut arriver avant ou après la fin du chargement.
        self.on_favicon_changed(view)
        if self.is_private(view):
            return
        address = view.url().toString()
        if not address.startswith(("https://", "http://")):
            return
        if not self.history or self.history[-1].get("url") != address:
            self.history.append({
                "title": self.tab_titles.get(view, address),
                "url": address,
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            })
            self.history = self.history[-250:]
            save_json(DATA / "historique.json", self.history)
        if self.panel_mode == "history":
            self.refresh_rows()

    def sync_address(self):
        view = self.current_view()
        if not view:
            return
        if not self.address.hasFocus():
            raw = view.url().toString()
            self.address.setText("" if view in self.home_tabs else raw)
        self.address.setToolTip(view.url().toString() if view not in self.home_tabs
                                else "Page d'accueil GlisseWeb")
        self.update_connection_info()

    def navigate_address(self):
        self.open_in_current(query_to_url(self.address.text()))

    def focus_address(self):
        self.find_input.hide()
        self.change_mode("tabs", True)
        self.address.setFocus()
        self.address.selectAll()

    def focus_find(self):
        self.find_input.show()
        self.change_mode("tabs", True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def find_in_page(self, phrase: str):
        view = self.current_view()
        if view:
            view.findText(phrase)

    def back(self):
        view = self.current_view()
        if view:
            view.back()

    def forward(self):
        view = self.current_view()
        if view:
            view.forward()

    def reload(self):
        view = self.current_view()
        if view:
            view.reload()

    def go_home(self):
        view = self.current_view()
        if view:
            self.show_home(view)

    def open_google(self):
        self.open_in_current(HOME)

    def toggle_favorite(self):
        view = self.current_view()
        if not view:
            return
        url = view.url().toString()
        if not url.startswith(("http://", "https://")):
            return
        exists = next((i for i, b in enumerate(self.bookmarks) if b.get("url") == url), None)
        if exists is None:
            self.bookmarks.append({"title": self.tab_titles.get(view, url), "url": url})
        else:
            self.bookmarks.pop(exists)
        save_json(DATA / "favoris.json", self.bookmarks)
        if self.panel_mode == "favorites":
            self.refresh_rows()

    def change_mode(self, mode: str, open_bar: bool = False):
        self.panel_mode = mode
        titles = {"tabs": f"ONGLETS · {self.pages.count()}", "favorites": "FAVORIS", "history": "HISTORIQUE"}
        labels = {"tabs": "＋ Nouvel onglet", "favorites": "＋ Ajouter cette page", "history": "Effacer l'historique"}
        actions = {"tabs": self.new_tab, "favorites": self.toggle_favorite, "history": self.clear_history}
        self.section_title.setText(titles[mode])
        self.main_action.setText(labels[mode])
        # Le bouton « nouvel onglet » est deja dans la rangée de pictogrammes.
        # Masquer ce grand bouton en mode Onglets libere une ligne de vignettes.
        self.main_action.setVisible(mode != "tabs")
        try:
            self.main_action.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.main_action.clicked.connect(actions[mode])
        for button, active in ((self.tab_nav, mode == "tabs"), (self.fav_nav, mode == "favorites"), (self.hist_nav, mode == "history")):
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)
        self.refresh_rows()
        if open_bar:
            self.set_sidebar(True)

    def clear_history(self):
        ans = QMessageBox.question(self, "Effacer l'historique", "Supprimer l'historique local de GlisseWeb ?")
        if ans == QMessageBox.StandardButton.Yes:
            self.history.clear()
            save_json(DATA / "historique.json", self.history)
            # Les icônes mémorisées font partie des données de navigation locales.
            shutil.rmtree(FAVICON_DIR, ignore_errors=True)
            FAVICON_DIR.mkdir(parents=True, exist_ok=True)
            self.refresh_rows()

    def clear_layout_recursive(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            widget = item.widget()
            if child_layout is not None:
                self.clear_layout_recursive(child_layout)
                child_layout.deleteLater()
            elif widget is not None:
                widget.deleteLater()

    def tab_card(self, view: BrowserView, *, width: int, height: int, overview=False) -> QFrame:
        """Carte d'onglet compacte : aperçu en haut, ligne titre+favicon en bas."""
        active = view is self.current_view()
        frame = QFrame(self.overview_holder if overview else self.items_holder)
        frame.setObjectName("tabCardActive" if active else "tabCard")
        frame.setToolTip(view.url().toString() or "Accueil")
        frame.setFixedSize(width, height)

        pad = 7 if overview else 5
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(5 if overview else 4)

        info_height = 24 if overview else 22
        # Le contenu (aperçu + titre + marges) doit rester dans la carte même à 80 px.
        spacing = 5 if overview else 4
        thumb_height = card_preview_height(height, pad, info_height, spacing)

        thumb = QLabel(frame)
        thumb.setObjectName("thumb")
        thumb.setFixedSize(width - pad * 2, thumb_height)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setCursor(Qt.CursorShape.PointingHandCursor)
        thumb.setToolTip("Afficher cet onglet")
        thumb.mousePressEvent = lambda _event, v=view: self.select_tab(v)
        pix = self.preview_for_size(view, thumb.width(), thumb.height())
        if pix is not None:
            thumb.setPixmap(pix)
        elif self.is_private(view):
            thumb.setText("◌  PRIVÉ")
        elif view in self.home_tabs:
            thumb.setText("⌂  ACCUEIL")
        elif not self.preview_enabled:
            thumb.setText("APERÇU OFF")
        else:
            thumb.setText("APERÇU À VENIR")
        layout.addWidget(thumb)

        info = QHBoxLayout()
        info.setSpacing(5)
        icon_label = QLabel(frame)
        icon_label.setObjectName("siteIcon")
        icon_label.setFixedSize(18 if overview else 16, 18 if overview else 16)
        icon = view.icon()
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(icon_label.size()))
        else:
            icon_label.setText("⌂" if view in self.home_tabs else ("◌" if self.is_private(view) else "•"))
        info.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        title = self.tab_titles.get(view, "Onglet")
        title_btn = QPushButton(frame)
        title_btn.setObjectName("tabTitle")
        title_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        title_btn.setFixedHeight(info_height)
        title_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        title_btn.setToolTip(title)
        title_btn.setText(QFontMetrics(title_btn.font()).elidedText(title, Qt.TextElideMode.ElideRight, max(32, width - 2 * pad - 54)))
        title_btn.clicked.connect(lambda _checked=False, v=view: self.select_tab(v))
        info.addWidget(title_btn, 1)

        close = self.make_btn("×", "Fermer directement cet onglet", lambda _checked=False, v=view: self.close_tab(v), "closeTab")
        close.setFixedSize(22 if not overview else 25, info_height)
        info.addWidget(close, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(info)
        return frame

    def on_favicon_changed(self, view: BrowserView):
        """Mémorise uniquement les favicons des onglets non privés, sans téléchargement externe."""
        if self.pages.indexOf(view) < 0 or self.is_private(view) or view in self.home_tabs:
            return
        location = favicon_path(FAVICON_DIR, view.url().toString())
        if location is not None:
            icon = view.icon()
            if not icon.isNull():
                pixmap = icon.pixmap(32, 32)
                if not pixmap.isNull():
                    pixmap.save(str(location), "PNG")
        self.schedule_rows_refresh()
        if self.panel_mode == "history":
            self.schedule_rows_refresh()

    def icon_for_url(self, url: str) -> QPixmap | None:
        location = favicon_path(FAVICON_DIR, url)
        if location is None or not location.exists():
            return None
        pixmap = QPixmap(str(location))
        return None if pixmap.isNull() else pixmap

    def item_row(self, title: str, sub: str, select_cb, close_cb=None, active=False, icon_url=None):
        frame = QFrame(self.items_holder)
        frame.setObjectName("tabItemActive" if active else "tabItem")
        line = QHBoxLayout(frame)
        line.setContentsMargins(8, 6, 7, 6)
        line.setSpacing(7)
        if icon_url:
            favicon = QLabel(frame)
            favicon.setObjectName("historyFavicon")
            favicon.setFixedSize(22, 22)
            favicon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = self.icon_for_url(icon_url)
            if pixmap is not None:
                favicon.setPixmap(pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
            else:
                host = QUrl(icon_url).host()
                favicon.setText((host[:1] or "◉").upper())
            favicon.setToolTip(QUrl(icon_url).host())
            line.addWidget(favicon)
        selector = QPushButton(frame)
        selector.setObjectName("listTitle")
        selector.setCursor(Qt.CursorShape.PointingHandCursor)
        selector.setToolTip(sub)
        selector.setText((title or sub or "Element")[:92])
        selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        selector.clicked.connect(select_cb)
        line.addWidget(selector, 1)
        if close_cb:
            close = self.make_btn("×", "Fermer / supprimer", close_cb, "closeTab")
            line.addWidget(close)
        return frame

    def schedule_rows_refresh(self):
        if hasattr(self, "rows_refresh_timer"):
            self.rows_refresh_timer.start(65)
        else:
            self.refresh_rows()

    def refresh_rows(self):
        if not hasattr(self, "items_layout"):
            return
        current_scroll = self.scroll.verticalScrollBar().value()
        self.scroll.setUpdatesEnabled(False)
        self.clear_layout_recursive(self.items_layout)
        viewport_width = max(160, self.scroll.viewport().width() - 2)
        self.items_holder.setMinimumWidth(viewport_width)
        self.items_holder.setMaximumWidth(viewport_width)
        if self.panel_mode == "tabs":
            count = self.pages.count()
            self.section_title.setText(f"ONGLETS · {count}")
            columns, card_width, card_height = sidebar_grid(
                count, viewport_width, SIDE_WIDTH,
                viewport_height=self.scroll.viewport().height(),
            )
            for i in range(max(3, columns)):
                self.items_layout.setColumnStretch(i, 0)
                self.items_layout.setColumnMinimumWidth(i, 0)
            for i in range(count):
                view = self.pages.widget(i)
                if isinstance(view, BrowserView):
                    self.items_layout.addWidget(self.tab_card(view, width=card_width, height=card_height), i // columns, i % columns, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        elif self.panel_mode == "favorites":
            for i, entry in enumerate(list(self.bookmarks)):
                url = entry.get("url", "")
                frame = self.item_row(entry.get("title", url), url,
                    lambda _checked=False, u=url: self.open_url(u),
                    lambda _checked=False, u=url: self.remove_favorite(u))
                self.items_layout.addWidget(frame, i, 0)
        else:
            for i, entry in enumerate(reversed(self.history[-150:])):
                url = entry.get("url", "")
                frame = self.item_row(entry.get("title", url), f"{entry.get('date', '')} • {url}",
                    lambda _checked=False, u=url: self.open_url(u), icon_url=url)
                self.items_layout.addWidget(frame, i, 0)
        if self.items_layout.count() == 0:
            empty = QLabel({"tabs": "Aucun onglet", "favorites": "Aucun favori enregistré", "history": "Aucune page visitée"}[self.panel_mode])
            empty.setObjectName("empty")
            self.items_layout.addWidget(empty, 0, 0)
        self.scroll.setUpdatesEnabled(True)
        self.refresh_rail()
        if self.scroll.verticalScrollBar().value() != current_scroll:
            QTimer.singleShot(0, lambda v=current_scroll: self.scroll.verticalScrollBar().setValue(v))

    def open_url(self, url: str):
        if url.startswith(("http://", "https://")):
            self.add_tab(url)
            self.maybe_hide_sidebar()

    def remove_favorite(self, url: str):
        self.bookmarks = [b for b in self.bookmarks if b.get("url") != url]
        save_json(DATA / "favoris.json", self.bookmarks)
        self.refresh_rows()

    def capture_thumbnail(self, view):
        if not view or not self.preview_enabled or self.is_private(view):
            return
        if view in self.home_tabs or self.pages.indexOf(view) < 0:
            return
        if self.content.currentWidget() is not self.pages or not view.isVisible():
            return
        if view.width() < 50 or view.height() < 50:
            return
        shot = view.grab()
        if shot.isNull():
            return
        self.snapshots[view] = shot.scaled(
            420, 240, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if self.sidebar_visible and self.panel_mode == "tabs":
            self.schedule_rows_refresh()

    def update_preview_button(self):
        if hasattr(self, "preview_btn"):
            self.preview_btn.setText("▣" if self.preview_enabled else "▢")

    def toggle_previews(self):
        self.preview_enabled = not self.preview_enabled
        if not self.preview_enabled:
            self.snapshots.clear()
        self.refresh_overview()
        self.config["previews"] = self.preview_enabled
        save_json(DATA / "config.json", self.config)
        self.update_preview_button()
        self.refresh_rows()

    def toggle_pin(self):
        self.panel_pinned = not self.panel_pinned
        self.pin_btn.setText("◆" if self.panel_pinned else "◇")
        self.pin_btn.setToolTip("Desepingler" if self.panel_pinned else "Epingler le panneau")
        self.set_sidebar(True)

    def maybe_hide_sidebar(self):
        if not self.panel_pinned:
            self.set_sidebar(False)

    def update_connection_info(self):
        view = self.current_view()
        if not view:
            self.connection_info.setText("Aucune page")
            return
        if view in self.home_tabs:
            self.connection_info.setText("● Accueil intégré · aucun accès à un fichier local")
            self.connection_info.setProperty("status", "secure")
        else:
            url = view.url()
            host = url.host() or "Page vierge"
            if url.scheme().lower() == "https":
                prefix, state = "● HTTPS chiffré", "secure"
            elif url.scheme().lower() == "http":
                prefix, state = "! HTTP NON chiffré", "insecure"
            else:
                prefix, state = "· Page locale", "neutral"
            privacy = " · PRIVÉ" if self.is_private(view) else ""
            short_host = host if len(host) <= 35 else host[:32] + "…"
            self.connection_info.setText(f"{prefix} · {short_host}{privacy}")
            self.connection_info.setProperty("status", state)
        self.connection_info.style().unpolish(self.connection_info)
        self.connection_info.style().polish(self.connection_info)
        self.connection_info.setToolTip("HTTPS chiffre la connexion, mais ne garantit pas que le site est legitime.")

    def plain_confirm(self, title: str, message: str, danger=True) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        return dialog.exec() == QMessageBox.StandardButton.Yes

    def allow_http(self, url: QUrl) -> bool:
        host = url.host().lower()
        origin = f"http://{host}:{url.port(80)}"
        if origin in self.http_allowed:
            return True
        choice = self.plain_confirm(
            "Connexion HTTP non chiffree",
            f"Le site {host} utilise HTTP.\n"
            "La connexion n'est pas chiffree : ne saisissez pas de mot de passe ou de donnees sensibles.\n\n"
            "Continuer sur ce site pour cette session ?",
        )
        if choice:
            self.http_allowed.add(origin)
            return True
        return False

    def blocked_navigation(self, target: str):
        warning = QMessageBox(self)
        warning.setWindowTitle("Navigation bloquee")
        warning.setIcon(QMessageBox.Icon.Information)
        warning.setTextFormat(Qt.TextFormat.PlainText)
        warning.setText(
            f"Cette adresse a ete bloquee :\n{target}\n\n"
            "GlisseWeb autorise uniquement les pages Web http/https dans la zone principale."
        )
        warning.exec()

    def adjust_zoom(self, step: float):
        view = self.current_view()
        if view:
            view.setZoomFactor(max(0.3, min(3.0, view.zoomFactor() + step)))

    def reset_zoom(self):
        view = self.current_view()
        if view:
            view.setZoomFactor(1.0)

    def open_downloads(self):
        path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path or str(Path.home() / "Downloads")))

    def handle_download(self, item):
        name = item.downloadFileName() or "telechargement"
        if suspicious_download(name):
            if not self.plain_confirm(
                "Attention : fichier potentiellement dangereux",
                f"Le fichier « {name} » peut lancer du code sur Windows.\n\n"
                "Ne telechargez ce type de fichier que depuis un site fiable et verifie. "
                "Windows Defender doit rester active.\n\n"
                "Choisir quand meme un dossier d'enregistrement ?",
            ):
                item.cancel()
                return
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        initial = str(Path(base or str(Path.home() / "Downloads")) / name)
        filename, _ = QFileDialog.getSaveFileName(self, "Enregistrer le fichier", initial)
        if not filename:
            item.cancel()
            return
        target = Path(filename)
        if suspicious_download(target.name) and not suspicious_download(name):
            if not self.plain_confirm("Extension executable", "Le nom choisi correspond a un fichier executable. Continuer ?"):
                item.cancel()
                return
        if target.exists():
            if not self.plain_confirm("Remplacer le fichier ?", f"Le fichier {target.name} existe deja. Le remplacer ?", False):
                item.cancel()
                return
        item.setDownloadDirectory(str(target.parent))
        item.setDownloadFileName(target.name)
        item.accept()

    def handle_permission(self, permission):
        kind = permission.permissionType().name
        askable = {
            "MediaAudioCapture": "microphone",
            "MediaVideoCapture": "camera",
            "MediaAudioVideoCapture": "microphone et camera",
            "Geolocation": "position geographique",
        }
        if kind not in askable:
            permission.deny()
            return
        origin = permission.origin()
        if origin.scheme().lower() != "https":
            permission.deny()
            return
        if self.plain_confirm(
            "Autorisation requise",
            f"Le site {origin.host()} demande l'acces a : {askable[kind]}.\n\n"
            "Autoriser uniquement pour cette demande ?",
            False,
        ):
            permission.grant()
        else:
            permission.deny()

    def handle_legacy_permission(self, page, origin, feature):
        allowed = {"MediaAudioCapture", "MediaVideoCapture", "MediaAudioVideoCapture", "Geolocation"}
        if feature.name not in allowed or origin.scheme().lower() != "https":
            decision = False
        else:
            decision = QMessageBox.question(
                self, "Autorisation requise", f"Autoriser {origin.host()} a utiliser {feature.name} ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes
        policy = (QWebEnginePage.PermissionPolicy.PermissionGrantedByUser if decision
                  else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
        page.setFeaturePermission(origin, feature, policy)

    def handle_web_fullscreen(self, request, _view):
        is_on = request.toggleOn()
        request.accept()
        self.media_fullscreen = is_on
        if is_on:
            self.set_sidebar(False, immediate=True)
        self.sync_compact_rail_visibility()

    def check_mouse_edge(self):
        if self.media_fullscreen or self.overview_visible or not self.isActiveWindow():
            return
        at = self.root.mapFromGlobal(QCursor.pos())
        inside = (0 <= at.y() < self.root.height()) and (0 <= at.x() < self.root.width())
        if not inside:
            return
        if not self.sidebar_visible and not self.compact_mode and at.x() <= 9:
            self.set_sidebar(True)
        elif self.sidebar_visible and not self.panel_pinned and at.x() > SIDE_WIDTH + 42:
            focus = QApplication.focusWidget()
            if focus not in (self.address, self.find_input):
                self.set_sidebar(False)

    def set_sidebar(self, visible: bool, immediate=False):
        if (self.media_fullscreen or self.overview_visible) and visible:
            return
        if self.sidebar_visible == visible and not immediate:
            self.sync_compact_rail_visibility()
            return
        if visible:
            self.capture_thumbnail(self.current_view())
        self.sidebar_visible = visible
        self.animation.stop()
        target = SIDE_WIDTH if visible else 0
        if visible:
            self.compact_rail.hide()  # jamais deux colonnes simultanément
        if immediate:
            self.sidebar.setMaximumWidth(target)
            self.sync_compact_rail_visibility()
        else:
            self.animation.setStartValue(self.sidebar.maximumWidth())
            self.animation.setEndValue(target)
            self.animation.start()
        if visible:
            self.sync_address()
            self.refresh_rows()

    def toggle_fullscreen(self):
        if self.isFullScreen() or self.isMaximized():
            self.showNormal()  # vraie fenêtre redimensionnable, pas une fenêtre maximisée
            QTimer.singleShot(0, self.keep_window_in_work_area)
        else:
            self.showFullScreen()
        self.refresh_window_button()
        QTimer.singleShot(0, self.adjust_rail_for_window)

    def keep_window_in_work_area(self):
        """Ne laisse pas la fenêtre empiéter sur la barre des tâches Windows."""
        if self.isFullScreen() or self.isMaximized():
            return
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        safe = screen.availableGeometry()
        if not safe.isValid():
            return
        new_width = min(self.width(), safe.width())
        new_height = min(self.height(), safe.height())
        new_x = min(max(self.x(), safe.x()), safe.x() + safe.width() - new_width)
        new_y = min(max(self.y(), safe.y()), safe.y() + safe.height() - new_height)
        if new_width != self.width() or new_height != self.height():
            self.resize(new_width, new_height)
        if self.x() != new_x or self.y() != new_y:
            self.move(new_x, new_y)
        self.adjust_rail_for_window()

    def refresh_window_button(self):
        if not hasattr(self, "window_btn"):
            return
        fullscreen = self.isFullScreen()
        self.window_btn.setText("▢" if fullscreen else "⛶")
        self.window_btn.setToolTip("Revenir en mode fenêtre (F11)" if fullscreen
                                   else "Passer en plein écran (F11)")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_rail_for_window()
        if hasattr(self, "home_tiles_grid"):
            QTimer.singleShot(0, self.rebuild_home_tiles)
        if getattr(self, "overview_visible", False):
            QTimer.singleShot(0, self.refresh_overview)
        elif getattr(self, "sidebar_visible", False) and hasattr(self, "items_layout"):
            QTimer.singleShot(0, self.refresh_rows)

    def closeEvent(self, event):
        if QApplication.instance() is not None:
            QApplication.instance().removeEventFilter(self)
        save_json(DATA / "favoris.json", self.bookmarks)
        save_json(DATA / "historique.json", self.history)
        save_json(DATA / "config.json", self.config)
        event.accept()


STYLE = """
QFrame#compactRail { background: #111c27; border-right: 1px solid #375269; }
QScrollArea#railScroll { background: transparent; border: none; }
QWidget#railHolder { background: transparent; }
QPushButton#railAction { background: #203442; color: #aaf5e6; border: 1px solid #3b6071; border-radius: 9px; font-size: 20px; font-weight: 700; }
QPushButton#railAction:hover { background: #2b5564; color: #edffff; border-color: #5fbaaa; }
QPushButton#railMini { background: transparent; color: #889ead; border: none; border-radius: 6px; font-size: 18px; }
QPushButton#railMini:hover { background: #334954; color: #fff; }
QPushButton#railTab { background: #1b2e3c; color: #dbeaf0; border: 1px solid #304b5d; border-radius: 10px; font-size: 17px; font-weight: 700; padding: 0px; }
QPushButton#railTab:hover { background: #2d4b5b; border-color: #6cb5aa; }
QPushButton#railTab[selected="true"] { background: #275a58; border: 2px solid #75e6cf; color: white; }
QToolButton#railClose { background: #293a48; color: #d1e2e9; border: 1px solid #576e7e; border-radius: 6px; font-size: 11px; font-weight: 800; padding: 0px; }
QToolButton#railClose:hover { background: #78394a; color: #ffffff; border-color: #f0a5b4; }
QToolButton#railClose:pressed { background: #a34253; }
QWidget#homeSky { background: #09121c; }
QWidget#homeShell { background: transparent; }
QLabel#homeKicker { color: #74e9d8; font-weight: 800; letter-spacing: 2px; font-size: 12px; }
QLabel#homeLogo { color: #9beee1; font-size: 78px; }
QLabel#homeLogoName { color: #edfaff; font-size: 20px; font-weight: 800; letter-spacing: 5px; }
QLabel#homeSubtitle { color: #a9bcc9; font-size: 16px; }
QLabel#homeHint { color: #95acbc; font-size: 12px; padding-top: 8px; }
QLineEdit#homeSearch { background: rgba(28, 48, 64, 200); color: #f4ffff; border: 1px solid rgba(84, 114, 127, 210); border-radius: 13px; padding: 16px 17px; font-size: 16px; }
QLineEdit#homeSearch:focus { border-color: #65e0cc; }
QPushButton#homeSearchBtn { background: rgba(62, 196, 180, 230); color: #0b2124; border-radius: 12px; font-weight: 800; font-size: 14px; padding: 12px 22px; }
QPushButton#homeSearchBtn:hover { background: #78ead7; }
QPushButton#homeMiniBtn { background: rgba(31, 54, 69, 160); color: #daf3f6; border: 1px solid rgba(68, 102, 122, 180); border-radius: 10px; padding: 8px 12px; font-size: 12px; }
QPushButton#homeMiniBtn:hover { background: rgba(44, 82, 99, 210); color: #88f2df; }
QWidget#homeTilesContainer { background: transparent; }
QFrame#homeTileFrame { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(43, 73, 95, 190), stop:0.6 rgba(22, 39, 54, 185), stop:1 rgba(17, 31, 45, 175)); border: 1px solid rgba(104, 151, 177, 120); border-radius: 18px; }
QFrame#homeTileFrame:hover { border-color: rgba(110, 228, 208, 210); background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(53, 93, 119, 220), stop:0.6 rgba(27, 50, 68, 210), stop:1 rgba(18, 35, 49, 205)); }
QLabel#homeTileGlyph { color: #eafcff; font-size: 32px; font-weight: 800; }
QLabel#homeTileName { color: #d7eef5; font-size: 12px; font-weight: 700; }
QWidget#overviewRoot, QWidget#overviewHolder { background: #0d1822; }
QLabel#overviewHeading { color: #eefbff; font-size: 28px; font-weight: 800; }
QLabel#overviewSub { color: #98acbb; font-size: 12px; }
QLineEdit#overviewSearch { background: #1b3040; color: #f2fdff; border: 1px solid #476878; border-radius: 11px; padding: 12px; font-size: 14px; }
QLineEdit#overviewSearch:focus { border-color: #6de4d3; }
QPushButton#overviewButton { background: #1e3746; color: #d2e8ee; border: 1px solid #39566b; border-radius: 9px; padding: 11px 14px; }
QPushButton#overviewButton:hover { background: #2a5362; color: #7ff1df; }

QMainWindow, QWidget#root { background: #0e141b; }
QFrame#sidebar { background: #101821; border-right: 1px solid #2d4252; }
QLabel { color: #dbe7ef; font-family: 'Segoe UI'; }
QLabel#brand { color: #6be9d5; font-size: 17px; font-weight: 800; letter-spacing: 1px; }
QLabel#sectionTitle { color: #8ea2b2; font-size: 11px; font-weight: 700; letter-spacing: 1px; margin-top: 4px; }
QLabel#empty { color: #718597; padding: 22px 8px; font-size: 12px; }
QLabel#tiny { color: #6f8292; font-size: 10px; margin-top: 2px; }
QLabel#connectionInfo { color: #88d0c4; font-size: 11px; padding: 1px 0 2px 2px; }
QLabel#connectionInfo[status='insecure'] { color: #f0b184; }
QLabel#connectionInfo[status='neutral'] { color: #9aabba; }
QLabel#domain { color: #92a4b2; font-size: 10px; padding-left: 2px; }
QLabel#siteIcon { color: #9fded6; font-size: 12px; }
QLabel#historyFavicon { background: #192e3b; color: #87d9ce; border: 1px solid #355263; border-radius: 6px; font-size: 12px; font-weight: 700; }
QLabel#thumb { background: #14222d; color: #6b8797; border: 1px solid #345162; border-radius: 10px; font-size: 11px; }
QLineEdit#address { color: #f4ffff; background: #1a2732; border: 1px solid #3f5d70; border-radius: 10px; padding: 8px 10px; selection-background-color: #248a8b; font-size: 12px; }
QLineEdit#address:focus { border-color: #61dec9; }
QLineEdit#findInput { background: #203343; color: #f1ffff; border: 1px solid #537582; border-radius: 9px; padding: 8px 10px; }
QPushButton { font-family: 'Segoe UI'; }
QPushButton#tool, QPushButton#icon, QPushButton#mode, QPushButton#footerIcon { background: #1f2d38; color: #d9e8ef; border: 1px solid #314654; border-radius: 8px; }
QPushButton#iconDanger { background: #30232b; color: #f8c1c9; border: 1px solid #67434d; border-radius: 8px; min-width: 28px; min-height: 28px; font-size: 18px; }
QPushButton#iconDanger:hover { background: #8c3346; color: white; }
QPushButton#footerIcon { min-width: 28px; max-height: 25px; min-height: 25px; font-size: 12px; padding: 0px 8px; }
QPushButton#footerIcon:hover { background: #294252; color: #78f5de; }
QPushButton#tool:hover, QPushButton#icon:hover, QPushButton#mode:hover { background: #294252; color: #78f5de; }
QPushButton#tool { min-width: 32px; min-height: 32px; font-size: 15px; padding: 0px; }
QPushButton#icon { min-width: 28px; min-height: 28px; font-size: 13px; padding: 0px; }
QPushButton#mode { min-width: 30px; min-height: 30px; font-size: 13px; padding: 0px; }
QPushButton#mode[active='true'] { border-color: #4c9d92; color: #77f2dc; background: #214043; }
QPushButton#small { min-height: 28px; font-size: 11px; padding: 0 8px; }
QPushButton#smallWarn { min-height: 28px; font-size: 11px; padding: 0 8px; background: #2d1f27; color: #f3d7df; border: 1px solid #664050; }
QPushButton#smallWarn:hover { background: #4a2836; color: white; }
QFrame#tabCard { background: #18242f; border-radius: 12px; border: 1px solid #2b3d4b; }
QFrame#tabCard:hover { background: #1d3240; border-color: #3c6670; }
QFrame#tabCardActive { background: #214043; border-radius: 12px; border: 1px solid #4ea89b; }
QFrame#tabItem, QFrame#tabItemActive { background: #18242f; border-radius: 10px; border: 1px solid #2b3d4b; }
QFrame#tabItemActive { border-color: #4ea89b; background: #214043; }
QPushButton#tabTitle, QPushButton#listTitle { background: transparent; border: none; color: #d8e7ef; font-size: 11px; text-align: left; padding: 1px 0px; }
QPushButton#tabTitle:hover, QPushButton#listTitle:hover { color: #7bf3dc; }
QPushButton#closeTab { background: transparent; border: none; color: #97aabb; font-size: 17px; padding: 0px 3px; min-width: 20px; }
QPushButton#closeTab:hover { color: #ff9d9d; }
QPushButton#primary { background: #227f82; color: #f3ffff; border: none; border-radius: 10px; padding: 12px; font-size: 13px; font-weight: 700; }
QPushButton#primary:hover { background: #2f9898; }
QScrollArea { background: transparent; border: none; }
QWidget#itemsHolder { background: transparent; }
QScrollBar:vertical { background: #15212a; width: 6px; }
QScrollBar::handle:vertical { background: #425e6c; border-radius: 3px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""


def main():
    chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").lower()
    forbidden_flags = (
        "--no-sandbox", "--disable-web-security", "--ignore-certificate-errors",
        "--allow-running-insecure-content", "--disable-site-isolation-trials",
    )
    bad_environment = (
        os.environ.get("QTWEBENGINE_DISABLE_SANDBOX", "").strip().lower() in ("1", "true", "yes")
        or any(flag in chromium_flags for flag in forbidden_flags)
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("GlisseWeb")
    if bad_environment:
        QMessageBox.critical(None, "Protection Chromium desactivee",
            "GlisseWeb refuse de demarrer car des options externes desactivent des protections du moteur web.\n\n"
            "Supprimez les variables QTWEBENGINE_DISABLE_SANDBOX ou options dangereuses "
            "dans QTWEBENGINE_CHROMIUM_FLAGS, puis relancez.")
        sys.exit(2)
    if ICON.exists():
        app.setWindowIcon(QIcon(str(ICON)))
    window = GlisseWeb()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
