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
from datetime import datetime

# ─── Constants ───────────────────────────────────────────────────────

TYPE_FILTERS = ["all", "Decision", "Learning", "Context"]
SORT_MODES = ["importance", "recency", "accessed"]
LOAD_LIMIT = 2000

# Stats panel (bottom of the left pane). Rows needed for a useful render:
# divider + memories + up to 4 type rows + 2 importance + accesses ≈ 9.
# Only shown when the list pane can spare at least this many rows for it.
STATS_MIN_H = 9
STATS_MAX_H = 11

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
    """Format an ISO timestamp as 'YYYY-MM-DD HH:MM' in the LOCAL timezone.

    Stored timestamps are UTC (…+00:00). We parse and convert to the machine's
    local zone so times read naturally. Falls back to a plain string trim if the
    value can't be parsed (never raises — this feeds the render loop).
    """
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(str(s))
        # Naive timestamps (no offset) are assumed local already; aware ones
        # are converted from their zone (UTC) to local.
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(s).replace("T", " ")[:16]


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
        self.show_stats = True
        self.show_dashboard = False  # right-pane charts dashboard (toggle: S)
        self.stats = compute_stats(all_mems)
        self.access = access_buckets(all_mems)  # (hot, warm, cold)
        self.created_src = all_mems  # list to bucket at draw time (width-dependent)
        self.recompute_view()

    def recompute_view(self):
        v = self.all_mems
        if self.type_filter != "all":
            v = [m for m in v if m.get("experience_type") == self.type_filter]
        if self.search:
            v = [m for m in v if matches(m, self.search)]
        if self.sort_mode == "importance":
            v = sorted(v, key=lambda m: _imp(m), reverse=True)
        elif self.sort_mode == "accessed":
            v = sorted(v, key=lambda m: _acc(m), reverse=True)
        else:  # recency
            v = sorted(
                v,
                key=lambda m: (m.get("last_accessed") or m.get("created_at") or ""),
                reverse=True,
            )
        self.view = v
        self.sel = clamp(self.sel, 0, max(0, len(v) - 1))
        self.detail_scroll = 0
        # Stats follow the current view when a filter/search narrows it, so the
        # panel/dashboard is a live readout of what's on screen; otherwise the
        # whole set. The created histogram is bucketed at draw time (its bucket
        # count depends on pane width), so we only stash the source list here.
        filtering = bool(self.search) or self.type_filter != "all"
        src = self.view if filtering else self.all_mems
        self.stats = compute_stats(src)
        self.access = access_buckets(src)
        self.created_src = src

    def current(self):
        if self.view and 0 <= self.sel < len(self.view):
            return self.view[self.sel]
        return None


def _imp(m):
    try:
        return float(m.get("importance") or 0)
    except (TypeError, ValueError):
        return 0.0


def _acc(m):
    try:
        return int(m.get("access_count") or 0)
    except (TypeError, ValueError):
        return 0


def compute_stats(mems):
    """Aggregate a memory list into display stats (pure, no curses).

    Returns a dict:
      total          — count
      types          — OrderedDict type→count (Decision/Learning/Context/Other)
      importance     — dict with high/mid/low counts and mean
      total_accesses — sum of access_count
      flags          — dict failure/anomaly/compressed counts
    """
    total = len(mems)
    types = {"Decision": 0, "Learning": 0, "Context": 0, "Other": 0}
    high = mid = low = 0
    imp_sum = 0.0
    accesses = 0
    failure = anomaly = compressed = 0
    for m in mems:
        t = m.get("experience_type")
        types[t if t in types else "Other"] += 1
        imp = _imp(m)
        imp_sum += imp
        if imp >= 0.8:
            high += 1
        elif imp >= 0.5:
            mid += 1
        else:
            low += 1
        accesses += _acc(m)
        if m.get("is_failure"):
            failure += 1
        if m.get("is_anomaly"):
            anomaly += 1
        if m.get("compressed"):
            compressed += 1
    return {
        "total": total,
        "types": types,
        "importance": {
            "high": high, "mid": mid, "low": low,
            "mean": (imp_sum / total) if total else 0.0,
        },
        "total_accesses": accesses,
        "flags": {"failure": failure, "anomaly": anomaly, "compressed": compressed},
    }


def _mini_bar(count, total, width):
    """Proportional block bar for `count` out of `total` over `width` cells."""
    if width <= 0:
        return ""
    frac = (count / total) if total else 0.0
    filled = int(round(frac * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def apportion(counts, width):
    """Split `width` cells among `counts` proportionally, summing to exactly
    `width` (largest-remainder / Hamilton method).

    `counts` is a list of ints. Returns a list of ints the same length, each
    >= 0, summing to `width`. Non-zero counts get at least 1 cell so a
    present-but-tiny slice never vanishes — as long as the number of non-zero
    slices fits in `width` (else the min-1 bump is trimmed from the largest).
    Returns all-zero when total or width is 0.
    """
    total = sum(counts)
    if total <= 0 or width <= 0:
        return [0] * len(counts)
    exact = [c / total * width for c in counts]
    floors = [int(x) for x in exact]
    # Guarantee a visible cell for any non-zero slice when there's room.
    nonzero = sum(1 for c in counts if c > 0)
    if nonzero <= width:
        for i, c in enumerate(counts):
            if c > 0 and floors[i] == 0:
                floors[i] = 1
    remainder = width - sum(floors)
    if remainder > 0:
        # Hand out the leftover cells to the largest fractional parts.
        order = sorted(range(len(counts)), key=lambda i: exact[i] - floors[i], reverse=True)
        for i in order[:remainder]:
            floors[i] += 1
    elif remainder < 0:
        # The min-1 bump over-allocated; trim from the largest slices (keep >=1).
        order = sorted(range(len(counts)), key=lambda i: floors[i], reverse=True)
        k = 0
        while remainder < 0 and k < len(order):
            i = order[k]
            if floors[i] > 1:
                floors[i] -= 1
                remainder += 1
            else:
                k += 1
    return floors


def access_buckets(mems):
    """Split memories into (hot, warm, cold) by access_count: 3+, 1–2, 0."""
    hot = warm = cold = 0
    for m in mems:
        a = _acc(m)
        if a >= 3:
            hot += 1
        elif a >= 1:
            warm += 1
        else:
            cold += 1
    return hot, warm, cold


def created_series(mems, n):
    """Bucket memories into `n` equal-duration buckets over their created_at span.

    Returns (buckets, lo, hi) where buckets is a length-`n` list of counts, and
    lo/hi are the earliest/latest local datetimes (or None when no valid dates).
    Timestamps are parsed as UTC-aware and converted to local, consistent with
    short_ts. Unparseable/missing created_at values are skipped.
    """
    if n <= 0:
        return [], None, None
    dts = []
    for m in mems:
        s = m.get("created_at")
        if not s:
            continue
        try:
            dts.append(datetime.fromisoformat(str(s)).astimezone())
        except (ValueError, TypeError):
            continue
    buckets = [0] * n
    if not dts:
        return buckets, None, None
    lo, hi = min(dts), max(dts)
    span = (hi - lo).total_seconds()
    for d in dts:
        if span <= 0:
            idx = 0
        else:
            idx = min(n - 1, int((d - lo).total_seconds() / span * n))
        buckets[idx] += 1
    return buckets, lo, hi


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

    # ── Split the left column: list on top, stats panel on the bottom. ──
    # Only carve out stats when the panel is toggled on AND the list keeps a
    # workable minimum of rows; otherwise the list takes the whole column. The
    # bottom-left panel is redundant while the dashboard fills the right pane,
    # so it's suppressed then (the list gets the whole column).
    stats_h = 0
    if b.show_stats and not b.show_dashboard and b.view:
        want = min(STATS_MAX_H, STATS_MIN_H + len(
            [1 for c in b.stats["types"].values() if c]
        ))
        if body_h - want >= 6:  # keep the list usable
            stats_h = want
    list_h = body_h - stats_h
    stats_top = body_top + list_h

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
    _ensure_visible(b, list_h)
    if not b.view:
        msg = "No memories"
        hint = "(filter/search active — press t/s/Esc, or r to reload)" if (
            b.search or b.type_filter != "all"
        ) else "(press r to reload, q to quit)"
        cy = body_top + list_h // 2
        safe_addstr(stdscr, cy, max(0, (list_w - display_width(msg)) // 2), msg, _cp(CP_DIM))
        safe_addstr(stdscr, cy + 1, 1, truncate_to_width(hint, list_w - 2), _cp(CP_DIM))
    else:
        for i in range(list_h):
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

    # ── Stats panel (bottom of the left column) ──
    if stats_h >= STATS_MIN_H:
        _draw_stats(stdscr, b, stats_top, stats_h, list_w)

    # ── Divider ── (full height of the body, spans list + stats)
    for i in range(body_h):
        try:
            stdscr.addch(body_top + i, list_w, curses.ACS_VLINE, _cp(CP_DIM))
        except curses.error:
            pass

    # ── Right pane ── charts dashboard (S) or the selected memory's detail.
    if detail_w > 4:
        if b.show_dashboard:
            _draw_dashboard(stdscr, b, body_top, body_h, detail_x, detail_w)
        else:
            _draw_detail(stdscr, b, body_top, body_h, detail_x, detail_w)

    # ── Footer ──
    if b.status:
        foot = " " + b.status + " "
    else:
        dash = "S detail" if b.show_dashboard else "S dash"
        foot = (
            " jk move   Enter read   / search   "
            "t type   s sort   {}   r reload   q quit ".format(dash)
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


_TYPE_CP = {
    "Decision": CP_DECISION,
    "Learning": CP_LEARNING,
    "Context": CP_CONTEXT,
    "Other": CP_DIM,
}


def _draw_stats(stdscr, b, top, height, w):
    """Render the stats panel in the bottom of the left pane.

    `top` is the first row, `height` the number of rows available, `w` the pane
    width. Content is drawn best-effort and clipped to `height`; the caller
    guarantees height >= _STATS_MIN_H before calling.
    """
    s = b.stats
    total = s["total"]
    label_attr = _cp(CP_LABEL) | curses.A_BOLD
    dim = _cp(CP_DIM)

    # Section divider with a title, so the split from the list is obvious.
    title = " STATS "
    bar = "─" * max(0, (w - display_width(title)) // 2)
    safe_addstr(stdscr, top, 0, bar, dim)
    safe_addstr(stdscr, top, len(bar), title, _cp(CP_ACCENT) | curses.A_BOLD)
    safe_addstr(stdscr, top, len(bar) + display_width(title),
                "─" * max(0, w - len(bar) - display_width(title)), dim)

    rows = []  # (segments) where segments is list of (text, attr)
    scope = "view" if (b.search or b.type_filter != "all") else "total"
    rows.append([("Memories  ", label_attr), ("{} ({})".format(total, scope), _cp(CP_TITLE))])

    # Type distribution with proportional bars.
    bar_w = max(4, min(12, w - 22))
    for t, c in s["types"].items():
        if c == 0:
            continue
        rows.append([
            ("{:<9}".format(t[:9]), _cp(_TYPE_CP.get(t, CP_DIM)) | curses.A_BOLD),
            (" " + _mini_bar(c, total, bar_w), _cp(CP_BAR)),
            (" {:>4}".format(c), _cp(CP_TITLE)),
        ])

    imp = s["importance"]
    rows.append([("Importance", label_attr)])
    rows.append([
        ("  ⭐{}  🔥{}  ·{}".format(imp["high"], imp["mid"], imp["low"]), _cp(CP_TITLE)),
        ("  μ{:.2f}".format(imp["mean"]), dim),
    ])

    rows.append([("Accesses  ", label_attr), ("{} total".format(s["total_accesses"]), _cp(CP_TITLE))])

    fl = s["flags"]
    if fl["failure"] or fl["anomaly"]:
        rows.append([
            ("Flags     ", label_attr),
            ("⚑{} failure  ⚑{} anomaly".format(fl["failure"], fl["anomaly"]),
             _cp(CP_FLAG) | curses.A_BOLD),
        ])

    for i, segs in enumerate(rows):
        y = top + 1 + i
        if y >= top + height:
            break
        x = 0
        for text, attr in segs:
            safe_addstr(stdscr, y, x, text, attr)
            x += display_width(text)


def _draw_stacked_bar(stdscr, y, x, width, segments):
    """Draw a single-row multi-color stacked bar.

    `segments` is a list of (count, color_pair). Cell widths are apportioned so
    they sum to exactly `width` (largest-remainder); each segment is a separate
    `safe_addstr` (one attr per call) drawn at an advancing x. Any leftover from
    an all-zero bar is filled with `░` in the dim color.
    """
    if width <= 0:
        return
    cells = apportion([max(0, c) for c, _ in segments], width)
    cx = x
    drawn = 0
    for (_, cp), n in zip(segments, cells):
        if n <= 0:
            continue
        safe_addstr(stdscr, y, cx, "█" * n, _cp(cp))
        cx += n
        drawn += n
    if drawn < width:
        safe_addstr(stdscr, y, cx, "░" * (width - drawn), _cp(CP_DIM))


def _sparkline(buckets):
    """Map a list of counts to a sparkline string using ▁▂▃▄▅▆▇█.

    Heights are relative to the tallest bucket; an empty bucket renders as a
    space so gaps in time read as gaps in the chart.
    """
    blocks = "▁▂▃▄▅▆▇█"
    peak = max(buckets) if buckets else 0
    if peak <= 0:
        return " " * len(buckets)
    out = []
    for b_ in buckets:
        if b_ <= 0:
            out.append(" ")
        else:
            out.append(blocks[min(len(blocks) - 1, int((b_ / peak) * (len(blocks) - 1)))])
    return "".join(out)


def _draw_dashboard(stdscr, b, top, height, x, w):
    """Charts dashboard for the right pane (replaces the memory detail view).

    Four sections top→bottom: importance (stacked bar), flags (three bars),
    access activity (stacked bar), and a created-over-time sparkline. Sections
    are drawn until vertical space runs out (bottom-up clip), matching the
    file's clip-don't-crash style.
    """
    s = b.stats
    total = s["total"]
    label_attr = _cp(CP_LABEL) | curses.A_BOLD
    dim = _cp(CP_DIM)
    inner_w = max(4, w - 1)
    bar_w = max(6, min(inner_w, w - 14))  # leave room for a label + count
    y = top
    bottom = top + height

    def title(text):
        nonlocal y
        if y >= bottom:
            return False
        safe_addstr(stdscr, y, x, text, _cp(CP_ACCENT) | curses.A_BOLD)
        y += 1
        return True

    def row(segs):
        nonlocal y
        if y >= bottom:
            return False
        cx = x
        for text, attr in segs:
            safe_addstr(stdscr, y, cx, text, attr)
            cx += display_width(text)
        y += 1
        return True

    def blank():
        nonlocal y
        y += 1

    scope = "view" if (b.search or b.type_filter != "all") else "all"
    safe_addstr(stdscr, y, x, "DASHBOARD", _cp(CP_HEADER) | curses.A_BOLD)
    safe_addstr(stdscr, y, x + 10, "· {} mem ({})".format(total, scope), dim)
    y += 1
    safe_addstr(stdscr, y, x, "─" * inner_w, dim)
    y += 1

    # ── Importance ── high / mid / low partition the whole set.
    imp = s["importance"]
    if title("IMPORTANCE"):
        if y < bottom:
            _draw_stacked_bar(stdscr, y, x, bar_w, [
                (imp["high"], CP_ACCENT), (imp["mid"], CP_BAR), (imp["low"], CP_DIM)
            ])
            y += 1
        row([
            ("⭐{}  ".format(imp["high"]), _cp(CP_ACCENT)),
            ("🔥{}  ".format(imp["mid"]), _cp(CP_BAR)),
            ("·{}".format(imp["low"]), dim),
            ("   μ{:.2f}".format(imp["mean"]), _cp(CP_TITLE)),
        ])
    blank()

    # ── Flags ── overlapping sets, so one independent bar each.
    fl = s["flags"]
    if title("FLAGS"):
        fbar = max(6, min(inner_w, w - 16))
        for name, cp in (("failure", CP_FLAG), ("anomaly", CP_ACCENT), ("compressed", CP_CONTEXT)):
            c = fl[name]
            row([
                ("{:<11}".format(name), _cp(cp) | curses.A_BOLD),
                (_mini_bar(c, total, fbar), _cp(cp)),
                (" {:>4}".format(c), _cp(CP_TITLE)),
            ])
    blank()

    # ── Access activity ── hot / warm / cold partition the whole set.
    hot, warm, cold = b.access
    if title("ACCESS"):
        if y < bottom:
            _draw_stacked_bar(stdscr, y, x, bar_w, [
                (hot, CP_BAR), (warm, CP_ACCENT), (cold, CP_DIM)
            ])
            y += 1
        row([
            ("hot {}  ".format(hot), _cp(CP_BAR)),
            ("warm {}  ".format(warm), _cp(CP_ACCENT)),
            ("cold {}".format(cold), dim),
        ])
    blank()

    # ── Created over time ── equal-width buckets across the full span.
    if title("CREATED"):
        chart_w = max(1, inner_w)
        buckets, lo, hi = created_series(b.created_src, chart_w)
        if lo is None:
            row([("no dates", dim)])
        else:
            spark = _sparkline(buckets)
            row([(spark, _cp(CP_BAR))])
            peak = max(buckets) if buckets else 0
            axis = "{} → {}   peak {}".format(
                lo.strftime("%m-%d"), hi.strftime("%m-%d"), peak
            )
            row([(truncate_to_width(axis, inner_w), dim)])


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
    elif ch == ord("S"):
        b.show_dashboard = not b.show_dashboard
        b.status = "dashboard {}".format("on" if b.show_dashboard else "off")
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
