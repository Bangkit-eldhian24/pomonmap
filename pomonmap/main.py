#!/usr/bin/env python3
"""
pomo_clock.py - TTY-clock style Pomodoro in terminal (curses)

Usage examples:
  python3 pomo_clock.py                    # default 25m focus, 5m break
  python3 pomo_clock.py 50                 # focus 50 minutes, break default
  python3 pomo_clock.py 50 10              # focus 50 minutes, break 10 minutes
  python3 pomo_clock.py 1:30 0:10          # focus 1 hour 30 minutes, break 10 minutes
  python3 pomo_clock.py -c "nmap -Pn target"  # run command at focus start
  python3 pomo_clock.py "nmap -Pn target"     # also works: auto-detects command and uses defaults

By : ardx
"""

import curses
import time
import sys
import os
import csv
import shlex
import subprocess
from datetime import datetime
from threading import Thread
import argparse
import re
import signal

# ---------- Helper: duration parsing ----------
def parse_duration_to_seconds(s):
    """
    Parse duration string to seconds.
    Accepts:
      - "25" -> 25 minutes
      - "10m", "10min", "10 minutes"
      - "2h", "2hours"
      - "1:30" -> 1 hour 30 minutes
    Raises ValueError on invalid format.
    """
    if s is None:
        raise ValueError("No duration provided")
    s = str(s).strip().lower()
    # H:M pattern (hours:minutes)
    if ":" in s:
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid H:M format: {s}")
        h = int(parts[0]) if parts[0] else 0
        m = int(parts[1]) if parts[1] else 0
        return (h * 60 + m) * 60
    # numeric only -> minutes
    if re.fullmatch(r"\d+", s):
        return int(s) * 60
    # minutes suffix
    if re.fullmatch(r"\d+\s*(m|min|mins|minutes)$", s):
        n = int(re.findall(r"\d+", s)[0])
        return n * 60
    # hours suffix
    if re.fullmatch(r"\d+\s*(h|hr|hour|hours)$", s):
        n = int(re.findall(r"\d+", s)[0])
        return n * 3600
    # also accept forms like "10 min" or "2 hours" with space
    m_match = re.match(r"^(\d+)\s*(m|min|mins|minutes)$", s)
    if m_match:
        return int(m_match.group(1)) * 60
    h_match = re.match(r"^(\d+)\s*(h|hr|hour|hours)$", s)
    if h_match:
        return int(h_match.group(1)) * 3600
    raise ValueError(f"Unrecognized duration format: {s}")

# ---------- Defaults and arg parsing ----------
DEFAULT_FOCUS_MIN = 25
DEFAULT_BREAK_MIN = 5

HELP_DESCRIPTION = (
    "TTY-clock style Pomodoro (terminal/curses).\n\n"
    "Keterangan pembuatan:\n"
    "  Program ini dibuat untuk membantu sesi Pomodoro di terminal.\n"
    "  By : ardx\n\n"
    "Format durasi yang diterima:\n"
    "  - integer (menit): 25\n"
    "  - suffix menit: 10m, 10min, 10 minutes\n"
    "  - suffix jam: 2h, 2hours\n"
    "  - H:M: 1:30 (1 jam 30 menit)\n\n"
    "Contoh penggunaan singkat:\n"
    "  python3 pomo_clock.py\n"
    "  python3 pomo_clock.py 50 10\n"
    "  python3 pomo_clock.py -c \"nmap -Pn target\"\n"
    "  python3 pomo_clock.py \"nmap -Pn target\"  # auto-detect command\n"
)

parser = argparse.ArgumentParser(
    prog="pomo_clock.py",
    description=HELP_DESCRIPTION,
    formatter_class=argparse.RawTextHelpFormatter,
    add_help=True
)
# positional duration arguments (optional)
parser.add_argument("focus", nargs="?", default=str(DEFAULT_FOCUS_MIN),
                    help="Focus duration (minutes/hours/H:M). Examples: 25 50m 2h 1:30")
parser.add_argument("break_d", nargs="?", default=str(DEFAULT_BREAK_MIN),
                    help="Break duration (minutes/hours/H:M). Examples: 5 10m 0:10")

# explicit command flag (prefer this for clarity)
parser.add_argument("-c", "--cmd", nargs=argparse.REMAINDER,
                    help="Optional command to run at focus start (wrap in quotes). Prefer -c for commands.")

args = parser.parse_args()

# reconstruct raw positional arguments (excluding script name and any option tokens)
raw_positional = []
# sys.argv[1:] contains everything; we want to include everything user provided as positionals or leftovers
if len(sys.argv) > 1:
    raw_positional = sys.argv[1:]

# Determine CMD and durations resiliently:
CMD = None
focus_sec = None
break_sec = None

# If user used -c/--cmd explicitly, use that (join remainder)
if args.cmd:
    CMD = " ".join(args.cmd).strip() if args.cmd else None

# Try to parse focus; if fails and no explicit CMD, then treat all raw args as CMD and use defaults
try:
    focus_sec = parse_duration_to_seconds(args.focus)
    # focus parsed OK; now try break
    try:
        break_sec = parse_duration_to_seconds(args.break_d)
    except ValueError:
        # break invalid. If user didn't supply explicit -c, treat remaining raw args (after first) as CMD.
        if not CMD:
            # If user passed something like: python3 script.py 25 "nmap -Pn ..." then args.focus parsed and args.break_d is the command.
            # reconstruct probable CMD from raw_positional excluding the first (focus)
            if raw_positional:
                probable_cmd_parts = raw_positional[1:]
                if probable_cmd_parts:
                    CMD = " ".join(probable_cmd_parts).strip()
                    break_sec = parse_duration_to_seconds(str(DEFAULT_BREAK_MIN))
                else:
                    # fallback to default break
                    break_sec = parse_duration_to_seconds(str(DEFAULT_BREAK_MIN))
            else:
                break_sec = parse_duration_to_seconds(str(DEFAULT_BREAK_MIN))
        else:
            # explicit CMD provided but break parsing failed -> fallback to default break
            break_sec = parse_duration_to_seconds(str(DEFAULT_BREAK_MIN))
except ValueError:
    # focus parsing failed -> treat all raw args as CMD (if any), and use defaults
    if raw_positional:
        CMD = " ".join(raw_positional).strip()
    focus_sec = parse_duration_to_seconds(str(DEFAULT_FOCUS_MIN))
    break_sec = parse_duration_to_seconds(str(DEFAULT_BREAK_MIN))

# final fallback sanity
if focus_sec is None:
    focus_sec = parse_duration_to_seconds(str(DEFAULT_FOCUS_MIN))
if break_sec is None:
    break_sec = parse_duration_to_seconds(str(DEFAULT_BREAK_MIN))

# Now CMD may be None or a string; log / use as needed
LOGFILE = "/home/{USERNAME}/pomonmap/logs/pomo_clock_log.csv"

# ---------- Big digits (tty-clock like) ----------
DIGITS = {
    "0": [" █████ ",
          "██   ██",
          "██  ███",
          "██ █ ██",
          "███  ██",
          "██   ██",
          " █████ "],
    "1": ["  ██   ",
          " ███   ",
          "  ██   ",
          "  ██   ",
          "  ██   ",
          "  ██   ",
          "██████ "],
    "2": [" █████ ",
          "██   ██",
          "    ██ ",
          "  ███  ",
          " ██    ",
          "██     ",
          "██████ "],
    "3": [" █████ ",
          "██   ██",
          "    ██ ",
          "  ███  ",
          "    ██ ",
          "██   ██",
          " █████ "],
    "4": ["   ███ ",
          "  █ ██ ",
          " █  ██ ",
          "██   ██",
          "██████ ",
          "    ██ ",
          "    ██ "],
    "5": ["██████ ",
          "██     ",
          "█████  ",
          "     ██",
          "     ██",
          "██   ██",
          " █████ "],
    "6": [" █████ ",
          "██   ██",
          "██     ",
          "█████  ",
          "██   ██",
          "██   ██",
          " █████ "],
    "7": ["██████ ",
          "     ██",
          "    ██ ",
          "   ██  ",
          "  ██   ",
          "  ██   ",
          "  ██   "],
    "8": [" █████ ",
          "██   ██",
          "██   ██",
          " █████ ",
          "██   ██",
          "██   ██",
          " █████ "],
    "9": [" █████ ",
          "██   ██",
          "██   ██",
          " █████ ",
          "    ██ ",
          "██   ██",
          " █████ "],
    ":": ["   ",
          " ░ ",
          "   ",
          "   ",
          " ░ ",
          "   ",
          "   "]
}

# ---------- Utilities ----------
def timestamp():
    return datetime.now().isoformat()

def log_event(kind, detail=""):
    try:
        with open(LOGFILE, "a", newline="") as f:
            w = csv.writer(f)
            w.writerow([timestamp(), kind, detail])
    except Exception:
        pass

def notify(title, body):
    try:
        subprocess.run(["notify-send", title, body], check=False)
    except Exception:
        print("\a", end="", flush=True)

def run_detached(cmd):
    """
    Jalankan CMD secara detached non-interaktif.
    Output disimpan ke ~/.pomo_cmd_outputs/<timestamp>_<safe>.log
    """
    if not cmd:
        return
    try:
        out_dir = "/home/{USERNAME}/pomonmap/logs"
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        safe_name = re.sub(r"[^\w\-_.]", "_", cmd)[:60]
        out_path = os.path.join(out_dir, f"{ts}_{safe_name}.log")

        # gunakan shell=True agar pengguna bisa pakai pipes/redirects ketika memanggil lewat -c or positional command
        # WARNING: shell=True -> jangan masukkan input dari sumber tak tepercaya
        with open(out_path, "wb") as f:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=f,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None
            )
        log_event("CMD_RUN_DETACHED", f"{cmd} -> {out_path}")
    except Exception as e:
        log_event("CMD_ERROR", str(e))

# ---------- Curses drawing ----------
def draw_big_time(stdscr, mmss_str, top, left):
    rows = 7
    for r in range(rows):
        x = left
        for ch in mmss_str:
            pattern = DIGITS.get(ch, ["   "]*rows)
            try:
                stdscr.addstr(top + r, x, pattern[r])
            except curses.error:
                pass
            x += len(pattern[r]) + 1

def draw_progress_bar(stdscr, y, left, width, pct):
    filled = int(pct * width + 0.000001)
    bar = "[" + "#" * filled + "-" * (width - filled) + "]"
    try:
        stdscr.addstr(y, left, bar)
    except curses.error:
        pass

def format_mmss(seconds):
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"

# ---------- Main loop ----------
def pomodoro_loop(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    height, width = stdscr.getmaxyx()

    has_colors = False
    try:
        if curses.has_colors():
            curses.start_color()
            try:
                curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
            except Exception:
                curses.init_pair(1, curses.COLOR_RED, 0)
            has_colors = True
    except Exception:
        has_colors = False

    mode = "FOCUS"
    remaining = focus_sec
    paused = False
    session_count = 0
    last_tick = time.time()
    skip_session = False

    log_event("APP_START", f"focus={focus_sec}s break={break_sec}s cmd={'yes' if CMD else 'no'}")

    while True:
        now = time.time()
        if not paused and (now - last_tick) >= 1.0:
            last_tick = now
            remaining -= 1
            if remaining < 0:
                if mode == "FOCUS":
                    log_event("FOCUS_END", f"{focus_sec}s")
                    notify("Pomodoro", "Focus finished — time for a break")
                    mode = "BREAK"
                    remaining = break_sec
                else:
                    log_event("BREAK_END", f"{break_sec}s")
                    session_count += 1
                    notify("Pomodoro", "Break finished — start next focus")
                    mode = "FOCUS"
                    remaining = focus_sec
                    if CMD:
                        Thread(target=run_detached, args=(CMD,), daemon=True).start()
                        log_event("CMD_RUN", CMD)

        try:
            ch = stdscr.getch()
            if ch != -1:
                if ch in (ord('q'), 27):
                    log_event("APP_QUIT", f"sessions={session_count}")
                    break
                elif ch == ord(' '):
                    paused = not paused
                    log_event("PAUSE" if paused else "RESUME", f"mode={mode} rem={remaining}s")
                elif ch == ord('n'):
                    log_event("SKIP", f"mode={mode} rem={remaining}s")
                    skip_session = True
                elif ch == ord('r'):
                    mode = "FOCUS"
                    remaining = focus_sec
                    paused = False
                    log_event("RESET", "")
        except Exception:
            pass

        if skip_session:
            skip_session = False
            if mode == "FOCUS":
                log_event("FOCUS_END_SKIPPED", "")
                notify("Pomodoro", "Focus skipped — going to break")
                mode = "BREAK"
                remaining = break_sec
            else:
                log_event("BREAK_END_SKIPPED", "")
                session_count += 1
                notify("Pomodoro", "Break skipped — going to focus")
                mode = "FOCUS"
                remaining = focus_sec
                if CMD:
                    Thread(target=run_detached, args=(CMD,), daemon=True).start()
                    log_event("CMD_RUN", CMD)

        stdscr.erase()
        height, width = stdscr.getmaxyx()

        author_label = "By : ardx"
        try:
            if has_colors:
                stdscr.addstr(0, 1, author_label[:max(0, width-2)], curses.color_pair(1) | curses.A_BOLD)
            else:
                stdscr.addstr(0, 1, author_label[:max(0, width-2)])
        except curses.error:
            pass

        title = f"pomodoro tty-clock style — mode: {mode}  sessions: {session_count}  (space pause/resume, n skip, r reset, q quit)"
        try:
            stdscr.addstr(1, 1, title[:width-2])
        except curses.error:
            pass

        mmss = format_mmss(max(0, remaining))
        mmss_str = mmss[0] + mmss[1] + ":" + mmss[3] + mmss[4]
        big_left = max(0, (width - (len(DIGITS["0"][0]) * 5 + 4)) // 2)
        big_top = max(3, (height - 10) // 2)
        draw_big_time(stdscr, mmss_str, big_top, big_left)

        total = focus_sec if mode == "FOCUS" else break_sec
        pct = (total - remaining) / total if total > 0 else 1.0
        bar_width = min(width - 10, 60)
        draw_progress_bar(stdscr, big_top + 8, big_left, bar_width, pct)

        status_left = 2
        try:
            stdscr.addstr(big_top + 10, status_left, f"Mode: {mode}   Remaining: {mmss}   Paused: {'YES' if paused else 'NO'}")
            stdscr.addstr(big_top + 11, status_left, f"Focus: {focus_sec//60}m  Break: {break_sec//60}m  CMD: {CMD or 'None'}")
            stdscr.addstr(big_top + 12, status_left, f"Log: {LOGFILE}")
        except curses.error:
            pass

        stdscr.refresh()
        time.sleep(0.05)

def main():
    try:
        curses.wrapper(pomodoro_loop)
    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
