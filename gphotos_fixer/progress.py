"""
progress.py
-----------
A tiny, dependency-free progress bar with a size-based ETA.

Behaviour
~~~~~~~~~
* Interactive terminal, per-file output off (--quiet):
      redraws a single line in place.
* Anything else (per-file output on, or stderr is piped / redirected to a log):
      prints a plain status line every few seconds instead, so it never
      garbles the per-file lines or fills a log file with control characters.

The bar is written to stderr, so it never ends up in redirected stdout.
Use Progress.write() for any other output while a bar is active -- it clears
the bar line first, so the text is not printed on top of it.
"""

import shutil
import sys
import time


def fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


class Progress:
    """
    Progress tracker for a run over *total_files* files / *total_bytes* bytes.

    Call advance(nbytes) once per processed file and close() (or use it as a
    context manager) when done. ETA is computed from bytes, not file count,
    because a 2 GB video and a 200 KB photo are very different amounts of work.
    """

    _BAR_WIDTH = 24

    def __init__(
        self,
        total_files: int,
        total_bytes: int,
        *,
        enabled: bool = True,
        verbose: bool = False,
        stream=None,
    ) -> None:
        self.total_files = total_files
        self.total_bytes = total_bytes
        self.done_files = 0
        self.done_bytes = 0

        self._stream = stream if stream is not None else sys.stderr
        self.enabled = enabled and total_files > 0
        # Redraw one line in place only on a real terminal with no per-file
        # output competing for the same screen.
        isatty = getattr(self._stream, "isatty", lambda: False)()
        self._inplace = isatty and not verbose
        self._interval = 0.2 if self._inplace else 15.0

        self._start = time.monotonic()
        self._last_draw = 0.0
        self._last_t = self._start
        self._last_bytes = 0
        self._rate: float | None = None  # smoothed bytes/second
        self._drawn_len = 0              # width of the bar currently on screen

    # ── public API ────────────────────────────────────────────────────────────

    def advance(self, nbytes: int = 0) -> None:
        """Record one finished file of *nbytes* bytes."""
        self.done_files += 1
        self.done_bytes += max(nbytes, 0)
        if not self.enabled:
            return
        now = time.monotonic()
        if now - self._last_draw >= self._interval:
            self._draw(now)

    def write(self, message: str = "") -> None:
        """Print *message* without corrupting the bar line."""
        self._clear()
        print(message, flush=True)

    def close(self) -> None:
        """Draw the final state and move to a fresh line."""
        if not self.enabled:
            return
        self._draw(time.monotonic(), final=True)
        if self._inplace:
            self._stream.write("\n")
            self._stream.flush()
        self.enabled = False

    def __enter__(self) -> "Progress":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── internals ─────────────────────────────────────────────────────────────

    def _fraction(self) -> float:
        if self.total_bytes > 0:
            return min(self.done_bytes / self.total_bytes, 1.0)
        return min(self.done_files / self.total_files, 1.0)

    def _update_rate(self, now: float) -> None:
        dt = now - self._last_t
        if dt <= 0:
            return
        instant = (self.done_bytes - self._last_bytes) / dt
        # Exponential smoothing: reacts to speed changes (photos vs. videos)
        # without the ETA jumping around on every redraw.
        self._rate = instant if self._rate is None else 0.3 * instant + 0.7 * self._rate
        self._last_t = now
        self._last_bytes = self.done_bytes

    def _eta(self, now: float) -> str:
        if now - self._start < 3 or not self._rate or self._rate <= 0:
            return "ETA …"
        if self.total_bytes > 0:
            remaining = max(self.total_bytes - self.done_bytes, 0)
            return "ETA " + fmt_duration(remaining / self._rate)
        return "ETA …"

    def _line(self, now: float, bar_width: int) -> str:
        frac = self._fraction()
        filled = int(bar_width * frac)
        bar = "█" * filled + "░" * (bar_width - filled)
        parts = [
            (f"[{bar}] " if bar_width else "") + f"{frac * 100:5.1f}%",
            f"{self.done_files:,}/{self.total_files:,} files",
        ]
        if self.total_bytes > 0:
            parts.append(f"{fmt_bytes(self.done_bytes)}/{fmt_bytes(self.total_bytes)}")
        if self._rate:
            parts.append(f"{fmt_bytes(self._rate)}/s")
        parts.append(self._eta(now))
        return "  ".join(parts)

    def _draw(self, now: float, final: bool = False) -> None:
        self._update_rate(now)
        self._last_draw = now
        if self._inplace:
            # A line wider than the terminal wraps, and then "\r" can no longer
            # redraw it in place -- so shrink the bar (then truncate) to fit.
            width = shutil.get_terminal_size((80, 24)).columns - 1
            for bar_width in range(self._BAR_WIDTH, -1, -4):
                line = self._line(now, bar_width)
                if len(line) <= width:
                    break
            line = line[:width]
        else:
            line = self._line(now, self._BAR_WIDTH)
        if final and self.done_files >= self.total_files:
            elapsed = fmt_duration(now - self._start)
            line = line.rsplit("  ", 1)[0] + f"  took {elapsed}"
        if self._inplace:
            # Pad with spaces so a shorter line fully covers the previous one
            # (portable; no ANSI escape codes needed).
            pad = max(self._drawn_len - len(line), 0)
            self._stream.write("\r" + line + " " * pad)
            self._stream.flush()
            self._drawn_len = len(line)
        else:
            self._stream.write(line + "\n")
            self._stream.flush()

    def _clear(self) -> None:
        if self._inplace and self._drawn_len:
            self._stream.write("\r" + " " * self._drawn_len + "\r")
            self._stream.flush()
            self._drawn_len = 0
