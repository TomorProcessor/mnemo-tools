#!/usr/bin/env python3
"""Memory browser — full-screen curses TUI for browsing wt-memory CONTENTS.

Unlike memory_tui.py (a metrics/analytics dashboard), this is a content browser:
a two-pane view where the left pane lists memories and the right pane shows the
full detail of the selected one. Supports live search, type filtering, and sort.

Pure Python stdlib (curses + json + subprocess + textwrap) — zero dependencies.

Invocation (from cmd_ui in lib/memory/ui.sh):
    memory_browser.py <repo_root> <project_or_empty>

Data is loaded by shelling out to `wt-memory [--project P] list --limit N` so we
inherit its health check, per-project RocksDB lock, auto-migrate, banner
suppression, and graceful `[]` fallback — the browser never opens the store
directly.
"""

import curses
import json
import os
import shutil
import subprocess
import sys
import textwrap
import unicodedata

# ─── Constants ───────────────────────────────────────────────────────

TYPE_FILTERS = ["all", "Decision", "Learning", "Context"]
SORT_MODES = ["importance", "recency"]
LOAD_LIMIT = 2000

# Color pair ids
CP_HEADER = 1
CP_SELECTED = 2
CP_DECISION = 3
CP_LEARNING = 4
CP_CONTEXT = 5
CP_DIM = 6
CP_FLAG = 7
CP_ACCENT = 8
CP_BAR = 9
CP_LABEL = 10
CP_TITLE = 11


# ─── Data layer ──────────────────────────────────────────────────────


def load_memories(project, limit=LOAD_LIMIT):
    """Shell out to `wt-memory list --json` and return a list of memory dicts.

    Returns [] on any failure (matches the CLI's graceful-degradation contract).
    """
    exe = shutil.which("wt-memory") or os.path.expanduser("~/.local/bin/wt-memory")
    cmd = [exe]
    if project:
        cmd += ["--project", project]
    cmd += ["list", "--limit", str(limit)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


# ─── Pure helpers (no curses) ────────────────────────────────────────


def display_width(s):
    """Visible cell width of a string, accounting for wide/emoji glyphs."""
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        ea = unicodedata.east_asian_width(ch)
        w += 2 if ea in ("W", "F") else 1
    return w


def truncate_to_width(s, max_w):
    """Truncate s so its display width is <= max_w (no ellipsis, exact fit)."""
    if max_w <= 0:
        return ""
    out = []
    w = 0
    for ch in s:
        cw = 0 if unicodedata.combining(ch) else (
            2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        )
        if w + cw > max_w:
            break
        out.append(ch)
        w += cw
    return "".join(out)


def clamp(v, lo, hi):
    return max(lo, min(v, hi))


def importance_icon(imp):
    """Emoji indicator by importance. ⭐ high, 🔥 mid, blank low."""
    try:
        imp = float(imp)
    except (TypeError, ValueError):
        imp = 0.0
    if imp >= 0.8:
        return "⭐"
    if imp >= 0.5:
        return "🔥"
    return "  "  # two spaces: same display width as an emoji, keeps columns aligned


def importance_bar(imp, width=10):
    """A block-character importance meter: ▓▓▓▓░░░░░░ 0.42"""
    try:
        imp = float(imp)
    except (TypeError, ValueError):
        imp = 0.0
    imp = max(0.0, min(1.0, imp))
    filled = int(round(imp * width))
    return "{}{} {:.2f}".format("█" * filled, "░" * (width - filled), imp)


def first_line(content):
    for ln in (content or "").splitlines():
        ln = ln.strip()
        if ln:
            return ln
    return "(empty)"


def matches(mem, q):
    """Case-insensitive substring match over content + tags."""
    if not q:
        return True
    q = q.lower()
    if q in (mem.get("content") or "").lower():
        return True
    return any(q in (t or "").lower() for t in (mem.get("tags") or []))


def short_ts(s):
    """Trim an ISO timestamp to 'YYYY-MM-DD HH:MM' for display."""
    if not s:
        return "—"
    s = str(s).replace("T", " ")
    return s[:16]


# ─── Application state ────────────────────────────────────────────────


class Browser:
    def __init__(self, all_mems, project):
        self.all_mems = all_mems
        self.view = []
        self.sel = 0
        self.list_top = 0
        self.search = ""
        self.search_active = False
        self.type_filter = "all"
        self.sort_mode = "importance"
        self.detail_scroll = 0
        self.focus = "list"  # "list" | "detail"
        self.mode = "browse"  # "browse" | "reader"
        self.reader_scroll = 0
        self.project = project
        self.status = ""
        self.recompute_view()

    def recompute_view(self):
        v = self.all_mems
        if self.type_filter != "all":
            v = [m for m in v if m.get("experience_type") == self.type_filter]
        if self.search:
            v = [m for m in v if matches(m, self.search)]
        if self.sort_mode == "importance":
            v = sorted(v, key=lambda m: _imp(m), reverse=True)
        else:
            v = sorted(
                v,
                key=lambda m: (m.get("last_accessed") or m.get("created_at") or ""),
                reverse=True,
            )
        self.view = v
        self.sel = clamp(self.sel, 0, max(0, len(v) - 1))
        self.detail_scroll = 0

    def current(self):
        if self.view and 0 <= self.sel < len(self.view):
            return self.view[self.sel]
        return None


def _imp(m):
    try:
        return float(m.get("importance") or 0)
    except (TypeError, ValueError):
        return 0.0


# ─── Rendering ───────────────────────────────────────────────────────


def safe_addstr(win, y, x, s, attr=0):
    """Width-safe addstr: clip to the row and swallow curses errors.

    curses raises on writing at/over the last column or the bottom-right cell;
    we clip defensively and ignore the residual edge error.
    """
    if y < 0 or x < 0:
        return
    H, W = win.getmaxyx()
    if y >= H:
        return
    avail = W - x - 1  # never touch the very last column
    if avail <= 0:
        return
    s = truncate_to_width(s, avail)
    try:
        win.addstr(y, x, s, attr)
    except curses.error:
        pass


def _type_attr(etype):
    return {
        "Decision": _cp(CP_DECISION),
        "Learning": _cp(CP_LEARNING),
        "Context": _cp(CP_CONTEXT),
    }.get(etype, 0)


def _cp(pair):
    return curses.color_pair(pair) if curses.has_colors() else 0


def draw(stdscr, b):
    stdscr.erase()
    H, W = stdscr.getmaxyx()

    if H < 4 or W < 24:
        safe_addstr(stdscr, 0, 0, "Terminal too small — resize (need >= 24x4)")
        stdscr.noutrefresh()
        curses.doupdate()
        return

    if b.mode == "reader":
        _draw_reader(stdscr, b, H, W)
        stdscr.noutrefresh()
        curses.doupdate()
        return

    header_row = 0
    search_row = 1 if b.search_active else -1
    body_top = 1 + (1 if b.search_active else 0)
    footer_row = H - 1
    body_h = footer_row - body_top
    list_w = max(28, W * 2 // 5)
    detail_x = list_w + 1
    detail_w = W - detail_x

    # ── Header ── (solid bar; brand + scope on the left, filters on the right)
    scope = b.project if b.project else "(all)"
    hdr_attr = _cp(CP_HEADER) | curses.A_BOLD
    # paint the whole bar first
    safe_addstr(stdscr, header_row, 0, " " * (W - 1), hdr_attr)
    left = "  wt-memory  ·  {}  ·  {} mem".format(scope, len(b.view))
    right = "type:{}   sort:{}  ".format(b.type_filter, b.sort_mode)
    safe_addstr(stdscr, header_row, 0, left, hdr_attr)
    rx = W - 1 - display_width(right)
    if rx > display_width(left) + 2:
        safe_addstr(stdscr, header_row, rx, right, hdr_attr)

    # ── Search row ──
    if b.search_active:
        safe_addstr(stdscr, search_row, 0, "/" + b.search + "▏", curses.A_BOLD)

    # ── List pane ──
    _ensure_visible(b, body_h)
    if not b.view:
        msg = "No memories"
        hint = "(filter/search active — press t/s/Esc, or r to reload)" if (
            b.search or b.type_filter != "all"
        ) else "(press r to reload, q to quit)"
        cy = body_top + body_h // 2
        safe_addstr(stdscr, cy, max(0, (list_w - display_width(msg)) // 2), msg, _cp(CP_DIM))
        safe_addstr(stdscr, cy + 1, 1, truncate_to_width(hint, list_w - 2), _cp(CP_DIM))
    else:
        for i in range(body_h):
            idx = b.list_top + i
            if idx >= len(b.view):
                break
            m = b.view[idx]
            y = body_top + i
            selected = idx == b.sel
            icon = importance_icon(m.get("importance"))
            idp = (m.get("id") or "")[:6]
            badge = (m.get("experience_type") or "?")[:1].upper()  # D / L / C
            title = first_line(m.get("content"))
            # layout: " D 00524c ⭐ title…"  (badge + id + icon + title)
            prefix = " {} {} {} ".format(badge, idp, icon)
            avail = list_w - display_width(prefix) - 1
            line = prefix + truncate_to_width(title, max(0, avail))
            if display_width(line) < list_w:
                line = line + " " * (list_w - display_width(line))
            if selected:
                attr = _cp(CP_SELECTED) | curses.A_BOLD if curses.has_colors() else curses.A_REVERSE
                safe_addstr(stdscr, y, 0, line, attr)
            else:
                # paint base line, then recolor the type badge
                safe_addstr(stdscr, y, 0, line, _cp(CP_TITLE))
                safe_addstr(stdscr, y, 1, badge, _type_attr(m.get("experience_type")) | curses.A_BOLD)

    # ── Divider ──
    for i in range(body_h):
        try:
            stdscr.addch(body_top + i, list_w, curses.ACS_VLINE, _cp(CP_DIM))
        except curses.error:
            pass

    # ── Detail pane ──
    if detail_w > 4:
        _draw_detail(stdscr, b, body_top, body_h, detail_x, detail_w)

    # ── Footer ──
    if b.status:
        foot = " " + b.status + " "
    else:
        foot = (
            " jk move   Enter read   / search   "
            "t type   s sort   r reload   q quit "
        )
    safe_addstr(stdscr, footer_row, 0, foot, _cp(CP_DIM))

    stdscr.noutrefresh()
    curses.doupdate()


def _draw_detail(stdscr, b, top, body_h, x, w):
    m = b.current()
    if not m:
        return
    lines = []  # (text, attr)

    etype = m.get("experience_type") or "—"
    lines.append(("Type:        " + etype, _type_attr(etype) | curses.A_BOLD))

    imp = _imp(m)
    lines.append(("Importance:  " + importance_bar(imp), _cp(CP_BAR)))

    tags = ", ".join(m.get("tags") or []) or "—"
    for j, wl in enumerate(textwrap.wrap("Tags:        " + tags, w - 1) or ["Tags:        —"]):
        lines.append((wl, _cp(CP_DIM) if j else _cp(CP_LABEL)))

    lines.append(("Created:     " + short_ts(m.get("created_at")), _cp(CP_DIM)))
    lines.append((
        "Accessed:    {}  (×{})".format(short_ts(m.get("last_accessed")), m.get("access_count", 0)),
        _cp(CP_DIM),
    ))

    flags = []
    if m.get("is_failure"):
        flags.append("failure")
    if m.get("is_anomaly"):
        flags.append("anomaly")
    if m.get("compressed"):
        flags.append("compressed")
    if flags:
        lines.append(("Flags:       " + " / ".join(flags), _cp(CP_FLAG) | curses.A_BOLD))

    lines.append(("─" * (w - 1), _cp(CP_DIM)))

    meta_rows = len(lines)  # header lines that always show

    content_lines = []
    content = m.get("content") or ""
    for para in content.splitlines() or [""]:
        if not para.strip():
            content_lines.append(("", 0))
            continue
        for wl in textwrap.wrap(para, w - 1, break_long_words=True, break_on_hyphens=False):
            content_lines.append((wl, _cp(CP_TITLE)))

    # The preview pane shows meta + as much content as fits. If content
    # overflows, the last row becomes a call-to-action to open the reader —
    # no dead scroll markers (full text lives in the reader, via Enter).
    avail = body_h - meta_rows
    total_content = len(content_lines)
    if avail >= 1 and total_content > avail:
        shown = content_lines[: avail - 1]
        more = total_content - len(shown)
        lines.extend(shown)
        lines.append(("↵ Enter — read full ({} more lines)".format(more),
                      _cp(CP_ACCENT) | curses.A_BOLD))
    else:
        lines.extend(content_lines)

    for i, (text, attr) in enumerate(lines[:body_h]):
        safe_addstr(stdscr, top + i, x, text, attr)


def _draw_reader(stdscr, b, H, W):
    """Full-screen, full-width reader for a single memory's entire content."""
    m = b.current()
    if not m:
        b.mode = "browse"
        return

    inner_w = W - 4  # 2-space margin each side
    cx = 2  # content left margin

    # ── Title bar (row 0) ──
    etype = m.get("experience_type") or "—"
    idp = (m.get("id") or "")[:8]
    title = first_line(m.get("content"))
    bar_attr = _cp(CP_HEADER) | curses.A_BOLD
    safe_addstr(stdscr, 0, 0, " " * (W - 1), bar_attr)
    safe_addstr(stdscr, 0, 1, " {}  {} ".format(importance_icon(m.get("importance")).strip() or "·", title), bar_attr)

    # ── Meta line (row 1) ──
    tags = ", ".join(m.get("tags") or []) or "—"
    meta = "{} · {} · ×{} · {}".format(
        etype, idp, m.get("access_count", 0), short_ts(m.get("created_at"))
    )
    safe_addstr(stdscr, 1, cx, truncate_to_width(meta, inner_w), _type_attr(etype) | curses.A_BOLD)
    safe_addstr(stdscr, 2, cx, truncate_to_width("tags: " + tags, inner_w), _cp(CP_DIM))
    safe_addstr(stdscr, 3, cx, truncate_to_width(importance_bar(_imp(m), 20), inner_w), _cp(CP_BAR))

    # ── Separator (row 4) ──
    safe_addstr(stdscr, 4, 0, "─" * (W - 1), _cp(CP_DIM))

    # ── Content (rows 5 .. H-2), scrollable ──
    content_top = 5
    content_h = (H - 1) - content_top  # leave row H-1 for footer
    if content_h < 1:
        content_h = 1

    body = []
    for para in (m.get("content") or "").splitlines() or [""]:
        if not para.strip():
            body.append("")
            continue
        for wl in textwrap.wrap(para, inner_w, break_long_words=True, break_on_hyphens=False):
            body.append(wl)

    total = len(body)
    max_scroll = max(0, total - content_h)
    b.reader_scroll = clamp(b.reader_scroll, 0, max_scroll)
    window = body[b.reader_scroll: b.reader_scroll + content_h]
    for i, ln in enumerate(window):
        safe_addstr(stdscr, content_top + i, cx, ln, _cp(CP_TITLE))

    # ── Footer with scroll position ──
    if total > content_h:
        pct = int(100 * b.reader_scroll / max_scroll) if max_scroll else 100
        pos = " {}–{} of {} lines · {}% ".format(
            b.reader_scroll + 1, min(b.reader_scroll + content_h, total), total, pct
        )
    else:
        pos = " {} lines ".format(total)
    foot = " jk/↑↓ scroll   Space/PgDn page   g/G top/bottom   Esc/← back   q quit  " + pos
    safe_addstr(stdscr, H - 1, 0, foot, _cp(CP_DIM))

    if b.reader_scroll > 0:
        safe_addstr(stdscr, content_top, W - 3, "▲", _cp(CP_ACCENT))
    if b.reader_scroll < max_scroll:
        safe_addstr(stdscr, H - 2, W - 3, "▼", _cp(CP_ACCENT))


def _ensure_visible(b, body_h):
    if body_h <= 0:
        return
    if b.sel < b.list_top:
        b.list_top = b.sel
    elif b.sel >= b.list_top + body_h:
        b.list_top = b.sel - body_h + 1
    b.list_top = max(0, b.list_top)


# ─── Key handling ────────────────────────────────────────────────────


def handle_search_key(b, ch):
    if ch in (27,):  # Esc — cancel search
        b.search = ""
        b.search_active = False
        b.recompute_view()
    elif ch in (10, 13, curses.KEY_ENTER):  # commit, keep filter
        b.search_active = False
        b.focus = "list"
    elif ch in (curses.KEY_BACKSPACE, 127, 8):
        b.search = b.search[:-1]
        b.recompute_view()
    elif ch == 21:  # Ctrl-U clear
        b.search = ""
        b.recompute_view()
    elif 32 <= ch <= 126:
        b.search += chr(ch)
        b.recompute_view()


def _open_reader(b):
    if b.current():
        b.mode = "reader"
        b.reader_scroll = 0


def handle_reader_key(b, ch, content_h):
    """Keys while in full-screen reader. Return False to quit."""
    if ch in (ord("q"), ord("Q")):
        return False
    if ch in (27, ord("h"), curses.KEY_LEFT):  # Esc / ← / h — back to browse
        b.mode = "browse"
    elif ch in (ord("j"), curses.KEY_DOWN):
        b.reader_scroll += 1
    elif ch in (ord("k"), curses.KEY_UP):
        b.reader_scroll = max(0, b.reader_scroll - 1)
    elif ch in (curses.KEY_NPAGE, ord(" ")):
        b.reader_scroll += max(1, content_h - 1)
    elif ch == curses.KEY_PPAGE:
        b.reader_scroll = max(0, b.reader_scroll - max(1, content_h - 1))
    elif ch == ord("g"):
        b.reader_scroll = 0
    elif ch == ord("G"):
        b.reader_scroll = 10 ** 9  # clamped in draw
    elif ch in (ord("J"), ord("n")):  # next memory without leaving reader
        b.sel = clamp(b.sel + 1, 0, max(0, len(b.view) - 1))
        b.reader_scroll = 0
    elif ch in (ord("K"), ord("p")):  # previous memory
        b.sel = clamp(b.sel - 1, 0, max(0, len(b.view) - 1))
        b.reader_scroll = 0
    return True


def handle_nav_key(b, ch, body_h):
    """Keys while browsing the list. Return False to quit, True to keep going."""
    b.status = ""
    if ch in (ord("q"), ord("Q")):
        return False
    if ch == ord("/"):
        b.search_active = True
    elif ch in (ord("j"), curses.KEY_DOWN):
        b.sel = clamp(b.sel + 1, 0, max(0, len(b.view) - 1))
    elif ch in (ord("k"), curses.KEY_UP):
        b.sel = clamp(b.sel - 1, 0, max(0, len(b.view) - 1))
    elif ch == curses.KEY_NPAGE:
        b.sel = clamp(b.sel + body_h, 0, max(0, len(b.view) - 1))
    elif ch == curses.KEY_PPAGE:
        b.sel = clamp(b.sel - body_h, 0, max(0, len(b.view) - 1))
    elif ch == ord("g"):
        b.sel = 0
    elif ch == ord("G"):
        b.sel = max(0, len(b.view) - 1)
    elif ch in (ord("l"), curses.KEY_RIGHT, 10, 13, curses.KEY_ENTER):
        _open_reader(b)
    elif ch == ord("t"):
        i = TYPE_FILTERS.index(b.type_filter)
        b.type_filter = TYPE_FILTERS[(i + 1) % len(TYPE_FILTERS)]
        b.recompute_view()
    elif ch == ord("s"):
        i = SORT_MODES.index(b.sort_mode)
        b.sort_mode = SORT_MODES[(i + 1) % len(SORT_MODES)]
        b.recompute_view()
    elif ch in (ord("r"), ord("R")):
        b.all_mems = load_memories(b.project)
        b.recompute_view()
        b.status = "reloaded — {} memories".format(len(b.all_mems))
    return True


# ─── Main ────────────────────────────────────────────────────────────


def _bright(color):
    """Bright variant of a base ANSI color when the terminal supports >8 colors."""
    try:
        if curses.COLORS >= 16:
            return color + 8
    except Exception:
        pass
    return color


# Custom color slots (used only when the terminal can redefine colors).
_C_SLATE = 16     # fixed dark-slate background
_C_SLATE2 = 17    # slightly lighter slate (selection / header field)
_C_FG = 18        # soft off-white foreground
_C_MUTED = 19     # muted grey for dim text


def _setup_palette():
    """Return (BG, header_bg, sel_bg, fg, muted) color numbers for a FIXED
    dark-slate theme, independent of the user's terminal light/dark setting.

    Three tiers:
      * can_change_color  → define exact slate RGB (best).
      * COLORS >= 256     → use xterm grayscale/slate indices.
      * otherwise (8/16)  → plain black bg, white fg (still fixed, not default).
    """
    try:
        colors = curses.COLORS
    except Exception:
        colors = 8

    if curses.can_change_color() and colors >= 20:
        # RGB on a 0–1000 scale. Dark slate ≈ #1e2430.
        curses.init_color(_C_SLATE, 117, 141, 188)   # ~#1e2430
        curses.init_color(_C_SLATE2, 200, 235, 305)  # ~#33506e lighter slate
        curses.init_color(_C_FG, 850, 870, 900)      # soft off-white
        curses.init_color(_C_MUTED, 470, 520, 600)   # muted blue-grey
        return _C_SLATE, _C_SLATE2, _C_FG, _C_MUTED
    if colors >= 256:
        # xterm-256 indices: 234 dark slate, 237 lighter, 252 light grey, 245 grey
        return 234, 237, 252, 245
    # basic terminal: fixed black bg, white fg
    return curses.COLOR_BLACK, curses.COLOR_BLUE, curses.COLOR_WHITE, curses.COLOR_WHITE


def _init_colors():
    if not curses.has_colors():
        return None
    curses.start_color()

    BG, BG2, FG, MUTED = _setup_palette()
    B = _bright

    # Chrome bars: dark text on a bright cyan field (reads on any bg)
    curses.init_pair(CP_HEADER, curses.COLOR_BLACK, B(curses.COLOR_CYAN))
    # Selected row: bright field so the selection always pops off the slate
    curses.init_pair(CP_SELECTED, curses.COLOR_BLACK, B(curses.COLOR_CYAN))
    # Type accents on the fixed bg
    curses.init_pair(CP_DECISION, B(curses.COLOR_MAGENTA), BG)
    curses.init_pair(CP_LEARNING, B(curses.COLOR_GREEN), BG)
    curses.init_pair(CP_CONTEXT, B(curses.COLOR_CYAN), BG)
    # Chrome on the fixed bg
    curses.init_pair(CP_DIM, MUTED, BG)
    curses.init_pair(CP_FLAG, B(curses.COLOR_RED), BG)
    curses.init_pair(CP_ACCENT, B(curses.COLOR_YELLOW), BG)
    curses.init_pair(CP_BAR, B(curses.COLOR_GREEN), BG)
    curses.init_pair(CP_LABEL, B(curses.COLOR_CYAN), BG)
    curses.init_pair(CP_TITLE, FG, BG)                       # default text on slate
    return BG, FG


def main(stdscr, project):
    curses.curs_set(0)
    stdscr.keypad(True)
    pal = _init_colors()
    if pal is not None:
        # Paint the ENTIRE screen (incl. unwritten cells) with the fixed slate bg
        # so the terminal's own light/dark theme never shows through.
        stdscr.bkgd(" ", _cp(CP_TITLE))

    b = Browser(load_memories(project), project)

    while True:
        H, W = stdscr.getmaxyx()
        body_h = max(1, (H - 1) - (1 + (1 if b.search_active else 0)))
        content_h = max(1, (H - 1) - 5)  # reader content rows (rows 5..H-2)
        draw(stdscr, b)
        ch = stdscr.getch()
        if ch == curses.KEY_RESIZE:
            continue
        if b.mode == "reader":
            if not handle_reader_key(b, ch, content_h):
                break
        elif b.search_active:
            handle_search_key(b, ch)
        else:
            if not handle_nav_key(b, ch, body_h):
                break


if __name__ == "__main__":
    # argv: [script, repo_root, project_or_empty]
    proj = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else ""
    curses.wrapper(main, proj)
