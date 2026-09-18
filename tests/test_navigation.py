"""Tests for `visionarcade.ui.navigation.FocusGroup`."""

from __future__ import annotations

import pygame

from visionarcade.ui.navigation import FocusGroup, SelectableItem


def _items(*ids_and_enabled):
    return [
        SelectableItem(item_id=item_id, rect=pygame.Rect(i * 100, 0, 80, 80), enabled=enabled)
        for i, (item_id, enabled) in enumerate(ids_and_enabled)
    ]


def test_empty_group_has_no_focus():
    group = FocusGroup()
    assert group.focus_index is None
    assert group.focused_id is None


def test_initial_focus_is_first_enabled_item():
    group = FocusGroup(_items(("a", True), ("b", True)))
    assert group.focused_id == "a"


def test_initial_focus_skips_disabled_items():
    group = FocusGroup(_items(("a", False), ("b", True)))
    assert group.focused_id == "b"


def test_move_focus_forward_and_backward():
    group = FocusGroup(_items(("a", True), ("b", True), ("c", True)))
    group.move_focus(1)
    assert group.focused_id == "b"
    group.move_focus(1)
    assert group.focused_id == "c"
    group.move_focus(-1)
    assert group.focused_id == "b"


def test_move_focus_wraps_around():
    group = FocusGroup(_items(("a", True), ("b", True)))
    group.move_focus(-1)
    assert group.focused_id == "b"


def test_move_focus_skips_disabled_items():
    group = FocusGroup(_items(("a", True), ("b", False), ("c", True)))
    group.move_focus(1)
    assert group.focused_id == "c"


def test_update_pointer_focuses_item_under_point():
    group = FocusGroup(_items(("a", True), ("b", True)))
    group.update_pointer((150, 40))  # inside b's rect (x=100..180)
    assert group.focused_id == "b"


def test_update_pointer_none_leaves_focus_unchanged():
    group = FocusGroup(_items(("a", True), ("b", True)))
    group.move_focus(1)
    group.update_pointer(None)
    assert group.focused_id == "b"


def test_update_pointer_outside_any_item_leaves_focus_unchanged():
    group = FocusGroup(_items(("a", True), ("b", True)))
    group.update_pointer((9999, 9999))
    assert group.focused_id == "a"


def test_update_pointer_ignores_disabled_items():
    group = FocusGroup(_items(("a", True), ("b", False)))
    group.update_pointer((150, 40))  # inside disabled b's rect
    assert group.focused_id == "a"


def test_activate_focused_returns_id_when_enabled():
    group = FocusGroup(_items(("a", True)))
    assert group.activate_focused() == "a"


def test_activate_focused_returns_none_when_disabled():
    group = FocusGroup([SelectableItem(item_id="a", rect=pygame.Rect(0, 0, 10, 10), enabled=False)])
    assert group.focused_id is None  # no enabled item to focus
    assert group.activate_focused() is None


def test_handle_key_moves_focus_right_and_down():
    group = FocusGroup(_items(("a", True), ("b", True)))
    group.handle_key(pygame.K_RIGHT)
    assert group.focused_id == "b"


def test_handle_key_moves_focus_left_and_up():
    group = FocusGroup(_items(("a", True), ("b", True)))
    group.move_focus(1)
    group.handle_key(pygame.K_LEFT)
    assert group.focused_id == "a"


def test_handle_key_enter_activates_focused():
    group = FocusGroup(_items(("a", True)))
    assert group.handle_key(pygame.K_RETURN) == "a"


def test_handle_key_space_activates_focused():
    group = FocusGroup(_items(("a", True)))
    assert group.handle_key(pygame.K_SPACE) == "a"


def test_handle_key_unrelated_key_returns_none():
    group = FocusGroup(_items(("a", True)))
    assert group.handle_key(pygame.K_a) is None


def test_set_items_preserves_focus_index_when_possible():
    group = FocusGroup(_items(("a", True), ("b", True)))
    group.move_focus(1)
    group.set_items(_items(("x", True), ("y", True)))
    assert group.focused_id == "y"  # same index (1) preserved


def test_set_items_resets_focus_when_new_list_is_shorter():
    group = FocusGroup(_items(("a", True), ("b", True), ("c", True)))
    group.move_focus(2)  # focus index 2
    group.set_items(_items(("x", True),))
    assert group.focused_id == "x"


def test_set_items_with_empty_list_clears_focus():
    group = FocusGroup(_items(("a", True)))
    group.set_items([])
    assert group.focused_id is None
