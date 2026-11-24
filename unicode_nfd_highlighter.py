import difflib
import logging
import sys
import unicodedata

import sublime
import sublime_plugin

logger = logging.getLogger("UnicodeNfdHighlighter")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(name)s][%(asctime)s][%(levelname)-8s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False

# https://www.sublimetext.com/docs/api_environments.html
# Since build 4050 plugins may also be run using Python 3.8.
# Starting in build 4205 this has been replaced with Python 3.14.

REGION_KEY = "unicode_nfd_check_regions"
MAX_FILE_SIZE = 10 * 1024 * 1024
VIEW_STATUS_KEY = "unicode_nfd_check_view_status"


def _changed_line_ranges(changes: list[sublime.TextChange]) -> list[tuple[int, int]]:
    line_ranges: list[tuple[int, int]] = []
    row_offset = 0

    for change in changes:
        start_row = change.a.row + row_offset
        added_newlines = change.str.count("\n")
        end_row = start_row + added_newlines
        line_ranges.append((start_row, end_row))

        row_offset += added_newlines - (change.b.row - change.a.row)

    merged_ranges: list[tuple[int, int]] = []
    for start, end in line_ranges:
        if len(merged_ranges) == 0:
            merged_ranges.append((start, end))
            continue

        last_merged_start, last_merged_end = merged_ranges[-1]
        if start > last_merged_end + 1:
            merged_ranges.append((start, end))
            continue

        merged_ranges[-1] = (last_merged_start, max(last_merged_end, end))

    return merged_ranges


def _get_nfd_ranges_in_line(raw_line: str) -> list[tuple[int, int]]:

    nfc_line = unicodedata.normalize("NFC", raw_line)
    if raw_line == nfc_line:
        return []

    nfd_ranges: list[tuple[int, int]] = []

    matcher = difflib.SequenceMatcher(None, raw_line, nfc_line, autojunk=False)

    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag == "replace":
            nfd_ranges.append((i1, i2))

    return nfd_ranges


class UnicodeNfdHighlighterListener(sublime_plugin.TextChangeListener):
    def on_text_changed_async(self, changes: list[sublime.TextChange]) -> None:
        view = self.buffer.primary_view()
        if not view.is_valid():
            logger.warning("View is not valid, skipping processing.")
            return

        target_change_count = view.change_count()

        sorted_changes = sorted(changes, key=lambda c: (c.a.row, c.a.col))
        changed_line_ranges = _changed_line_ranges(sorted_changes)

        if view.size() > MAX_FILE_SIZE:
            return

        new_regions: list[sublime.Region] = []
        changed_rows: list[int] = []

        for start_row, end_row in changed_line_ranges:
            for row in range(start_row, end_row + 1):
                # Refresh every edited row so stale highlights are cleared when NFD text is removed.
                changed_rows.append(row)
                line_text = view.substr(view.line(view.text_point(row=row, col=0)))
                nfd_column_ranges = _get_nfd_ranges_in_line(line_text)
                if len(nfd_column_ranges) == 0:
                    continue
                new_regions.extend(
                    sublime.Region(view.text_point(row=row, col=start_col), view.text_point(row=row, col=end_col))
                    for start_col, end_col in nfd_column_ranges
                )

        current_change_count = view.change_count()
        if current_change_count != target_change_count:
            logger.warning(
                "View change count changed during processing (target: %d, current: %d). Skipping highlight update.",
                target_change_count,
                current_change_count,
            )
            return

        self._highlight_nfd_in_view(new_regions=new_regions, changed_rows=changed_rows)

    def on_revert_async(self) -> None:
        pass

    def on_reload_async(self) -> None:
        pass

    def _highlight_nfd_in_view(self, *, new_regions: list[sublime.Region], changed_rows: list[int]) -> None:

        for view in self.buffer.views():
            if not view.is_valid():
                logger.warning("View is not valid, skipping processing.")
                continue

            old_regions = view.get_regions(REGION_KEY)

            kept_regions: list[sublime.Region] = []
            for _region in old_regions:
                start_row, _ = view.rowcol(_region.begin())
                end_row, _ = view.rowcol(_region.end())
                if any(row in changed_rows for row in range(start_row, end_row + 1)):
                    continue
                kept_regions.append(_region)

            view.add_regions(
                key=REGION_KEY,
                regions=kept_regions + new_regions,
                scope="region.redish",
                flags=sublime.DRAW_NO_FILL,
            )


class SpellCheckViewListener(sublime_plugin.ViewEventListener):
    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return True

    def on_load_async(self) -> None:
        file_size = self.view.size()

        if file_size > MAX_FILE_SIZE:
            msg = "UnicodeNfdHighlighter skipped: File too large."
            show_toast(self.view, msg)

            self.view.set_status(VIEW_STATUS_KEY, "UnicodeNfdHighlighter: Skipped (File too large)")
            return

        self.view.erase_status(VIEW_STATUS_KEY)
        self.check_and_highlight()

    def check_and_highlight(self) -> None:
        view = self.view
        full_region = sublime.Region(0, view.size())

        new_regions: list[sublime.Region] = []
        for row, line_region in enumerate(view.lines(full_region)):
            line_text = view.substr(line_region)
            nfd_column_ranges = _get_nfd_ranges_in_line(line_text)
            if len(nfd_column_ranges) == 0:
                continue
            new_regions.extend(
                sublime.Region(view.text_point(row=row, col=start_col), view.text_point(row=row, col=end_col))
                for start_col, end_col in nfd_column_ranges
            )

        buffer = self.view.buffer()
        if not buffer:
            return

        for view in buffer.views():
            view.add_regions(
                key=REGION_KEY,
                regions=new_regions,
                scope="region.redish",
                flags=sublime.DRAW_NO_FILL,
            )


def show_toast(view: sublime.View, message: str) -> None:
    if not view.is_valid():
        return
    bg_color = "var(--orangish)"
    html = f"""
    <body id="spell-toast">
        <style>
            body {{
                background-color: {bg_color};
                color: #ffffff;
                padding: 6px 12px;
                border-radius: 4px;
                font-family: system;
                font-size: 12px;
                font-weight: bold;
            }}
        </style>
        <div>{message}</div>
    </body>
    """

    view.show_popup(
        html,
        flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
        location=-1,
        max_width=500,
    )
    sublime.set_timeout(lambda: view.hide_popup(), 3000)
