from unicodedata import normalize
from unittest import TestCase

import sublime

from ..unicode_nfd_highlighter import _changed_line_ranges, _get_nfd_ranges_in_line


class TestTextChangeListener(TestCase):
    def test_changed_line_ranges_1(self) -> None:

        changes: list[sublime.TextChange] = [
            sublime.TextChange(
                pa=sublime.HistoricPosition(pt=1, row=0, col=1, col_utf16=1, col_utf8=1),
                pb=sublime.HistoricPosition(pt=4, row=1, col=1, col_utf16=1, col_utf8=1),
                len_utf16=3,
                len_utf8=3,
                s="!\n@\n#\n$\n%",
            ),
            sublime.TextChange(
                pa=sublime.HistoricPosition(pt=8, row=3, col=1, col_utf16=1, col_utf8=1),
                pb=sublime.HistoricPosition(pt=11, row=4, col=1, col_utf16=1, col_utf8=1),
                len_utf16=3,
                len_utf8=3,
                s="!\n@\n#\n$\n%",
            ),
            sublime.TextChange(
                pa=sublime.HistoricPosition(pt=15, row=6, col=1, col_utf16=1, col_utf8=1),
                pb=sublime.HistoricPosition(pt=18, row=7, col=1, col_utf16=1, col_utf8=1),
                len_utf16=3,
                len_utf8=3,
                s="!\n@\n#\n$\n%",
            ),
        ]

        expected_ranges = [(0, 4), (6, 10), (12, 16)]
        actual_ranges = _changed_line_ranges(changes)
        self.assertEqual(actual_ranges, expected_ranges)

    def test_changed_line_ranges_2(self) -> None:
        changes: list[sublime.TextChange] = [
            sublime.TextChange(
                pa=sublime.HistoricPosition(pt=0, row=0, col=0, col_utf16=0, col_utf8=0),
                pb=sublime.HistoricPosition(pt=1, row=0, col=1, col_utf16=1, col_utf8=1),
                len_utf16=1,
                len_utf8=1,
                s="@\n#\n$",
            ),
            sublime.TextChange(
                pa=sublime.HistoricPosition(pt=2, row=0, col=2, col_utf16=2, col_utf8=2),
                pb=sublime.HistoricPosition(pt=3, row=0, col=3, col_utf16=3, col_utf8=3),
                len_utf16=1,
                len_utf8=1,
                s="@\n#\n$",
            ),
        ]

        expected_ranges = [(0, 4)]
        actual_ranges = _changed_line_ranges(changes)
        self.assertEqual(actual_ranges, expected_ranges)

    def test_get_nfd_ranges_in_line_1(self) -> None:
        nfd_char = normalize("NFD", "ご")
        raw_line = f"abc{nfd_char}def{nfd_char}"

        expected_ranges = [(3, 5), (8, 10)]
        actual_ranges = _get_nfd_ranges_in_line(raw_line)
        self.assertEqual(actual_ranges, expected_ranges)

    def test_get_nfd_ranges_in_line_2(self) -> None:
        nfd_char = normalize("NFD", "じ")
        raw_line = f"{nfd_char}a{nfd_char}a{nfd_char}"

        expected_ranges = [(0, 2), (3, 5), (6, 8)]
        actual_ranges = _get_nfd_ranges_in_line(raw_line)
        self.assertEqual(actual_ranges, expected_ranges)
