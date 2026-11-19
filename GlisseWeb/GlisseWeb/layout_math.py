# -*- coding: utf-8 -*-
"""Disposition deterministe des onglets, sans dépendance à Qt.

La hauteur dépend de la place disponible : priorité aux dix premiers onglets
visibles dans cinq rangées de deux. Les petits écrans gardent le défilement.
"""
from __future__ import annotations


def sidebar_grid(
    tab_count: int,
    viewport_width: int,
    panel_width: int = 416,
    viewport_height: int = 600,
) -> tuple[int, int, int]:
    """Retourne (colonnes, largeur fixe, hauteur fixe) d'une vignette en px."""
    if tab_count < 0:
        raise ValueError("Le nombre d'onglets doit être positif")
    # Pendant l'animation de repli, la largeur peut valoir 0 : valeur de repli.
    effective_width = viewport_width if viewport_width >= 210 else panel_width - 48
    available = max(140, min(effective_width - 8, panel_width - 28))
    columns = 2 if tab_count >= 4 and available >= 245 else 1
    gap = 6
    card_width = max(72, (available - (columns - 1) * gap) // columns)

    rows = (tab_count + columns - 1) // columns if tab_count else 1
    if tab_count <= 3:
        ideal_height = 142
    elif tab_count <= 6:
        ideal_height = 116
    elif tab_count <= 10:
        ideal_height = 102
    elif tab_count <= 20:
        ideal_height = 92
    else:
        ideal_height = 82

    # Lorsque 10 onglets (ou plus) sont ouverts, faire tenir 5 rangées si
    # l'espace le permet ; sinon, préférer garder les titres lisibles et scroller.
    fit_rows = min(5, rows)
    if tab_count > 3 and viewport_height > 0:
        room = (viewport_height - 4 - max(0, fit_rows - 1) * gap) // max(1, fit_rows)
        ideal_height = min(ideal_height, room)

    return columns, card_width, max(80, ideal_height)


def card_preview_height(card_height: int, padding: int, info_height: int, spacing: int) -> int:
    """Aperçu qui laisse assez de place au favicon, titre et bouton fermer."""
    return max(32, card_height - 2 * padding - info_height - spacing - 2)


def compact_icon_width(
    rail_width: int,
    outer_padding: int = 4,
    scrollbar_reserve: int = 8,
    inner_padding: int = 2,
    desired_width: int = 39,
) -> int:
    """Taille maximale d'un favicon-cliquable qui ne déborde pas du rail.

    Réserve la largeur de la scrollbar avant qu'elle apparaisse afin que
    l'ouverture de nombreux onglets ne coupe pas la colonne.
    """
    usable = rail_width - 2 * outer_padding - scrollbar_reserve - 2 * inner_padding
    if usable < 24:
        raise ValueError("barre trop étroite pour une icône accessible")
    return min(desired_width, usable)


def compact_close_geometry(tile_width: int, tile_height: int, size: int = 15) -> tuple[int, int, int]:
    """Cadre (x,y,côté) du ×, entier dans la vignette compacte.

    Garde 1 pixel de marge en haut et à droite, même quand la colonne
    affiche sa barre de défilement verticale.
    """
    if tile_width < size + 2 or tile_height < size + 2:
        raise ValueError("Vignette trop petite pour le bouton de fermeture")
    return tile_width - size - 1, 1, size


def cycle_tab_index(current: int, count: int, delta: int) -> int:
    """Index cyclique des onglets, -1 lorsqu'il n'y en a aucun."""
    if count <= 0:
        return -1
    return ((current if 0 <= current < count else 0) + delta) % count


def window_rail_bottom_reserve(fullscreen: bool, window_height: int) -> int:
    """Espace bas en px. Limité dans les petites fenêtres pour garder + visible."""
    if fullscreen:
        return 0
    return min(100, max(0, window_height - 210))
