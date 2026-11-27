"""Überlappende Termine nebeneinander statt übereinander (#135)."""

from timetable.columns import side_by_side


def test_single_block_keeps_full_width():
    assert side_by_side([(540, 630)]) == [{"left": "0.0000", "width": "100.0000"}]


def test_two_overlapping_blocks_share_the_width():
    # 9:00–10:30 und 10:00–11:30
    assert side_by_side([(540, 630), (600, 690)]) == [
        {"left": "0.0000", "width": "50.0000"},
        {"left": "50.0000", "width": "50.0000"},
    ]


def test_blocks_that_only_touch_keep_full_width():
    # 9:00–10:30 und 10:30–12:00 berühren sich nur
    assert side_by_side([(540, 630), (630, 720)]) == [
        {"left": "0.0000", "width": "100.0000"},
        {"left": "0.0000", "width": "100.0000"},
    ]


def test_order_of_the_result_follows_the_input():
    assert side_by_side([(600, 690), (540, 630)]) == [
        {"left": "50.0000", "width": "50.0000"},
        {"left": "0.0000", "width": "50.0000"},
    ]


def test_free_column_is_reused_inside_a_group():
    # A 9–12 überlappt B 9–10 und C 10–11; B und C teilen sich die zweite Spalte.
    result = side_by_side([(540, 720), (540, 600), (600, 660)])

    assert result == [
        {"left": "0.0000", "width": "50.0000"},
        {"left": "50.0000", "width": "50.0000"},
        {"left": "50.0000", "width": "50.0000"},
    ]


def test_three_at_once_get_a_third_each_and_later_blocks_are_independent():
    result = side_by_side([(540, 630), (540, 630), (540, 630), (720, 780)])

    assert [block["left"] for block in result] == ["0.0000", "33.3333", "66.6667", "0.0000"]
    assert [block["width"] for block in result] == ["33.3333", "33.3333", "33.3333", "100.0000"]


def test_overlapping_blocks_never_share_horizontal_space():
    """Am Handy (375 px) bleiben beide Blöcke antippbar: kein Teil liegt unter dem anderen."""
    first, second = side_by_side([(540, 630), (600, 690)])

    first_right = float(first["left"]) + float(first["width"])
    assert first_right <= float(second["left"])
