#!/usr/bin/env bash
# pomo-cmd-wrapper.sh
# Simple, robust executor for lsdx.py (Pomodoro) — runs tools detached, logs output per-tool.
# By: ardx
#
# Usage:
#   ~/bin/pomo-cmd-wrapper.sh nmap -Pn -sV 192.168.56.101
#   ~/bin/pomo-cmd-wrapper.sh gobuster dir -u http://target -w /path/wordlist
#
# Notes:
# - This wrapper runs the command in background and returns immediately.
# - Output and metadata saved to /home/ardx/pomonmap/logs/<tool>/
# - The wrapper records a small header, PID and a completion line in the same logfile.

# CONFIG
BASE_LOGDIR="/home/ardx/pomonmap/logs"
RETENTION_DAYS=30    # optional: cleanup logs older than this (set 0 to disable)
UMASK=077            # ensure logs not world-readable

# safety: ensure we have at least one argument (tool to run)
if [ $# -lt 1 ]; then
  echo "Usage: $0 <tool> [args...]"
  exit 2
fi

# derive tool name (basename of first arg)
tool=$(basename "$1" | tr '[:upper:]' '[:lower:]')

# build directories
mkdir -p "$BASE_LOGDIR/$tool"
chmod 700 "$BASE_LOGDIR" "$BASE_LOGDIR/$tool"
umask $UMASK

# safe filename: timestamp + short sanitized command
TS=$(date +%Y%m%dT%H%M%S)
# join all args into a single short safe string for filename
SAFE_CMD="$(printf "%s " "$@" | tr -s ' ' '_' | tr -cd '[:alnum:]_-.')"
SAFE_CMD="${SAFE_CMD:0:80}"
OUTFILE="$BASE_LOGDIR/$tool/${TS}_${SAFE_CMD}.log"
PIDFILE="$BASE_LOGDIR/$tool/${TS}.pid"

# metadata header
{
  echo "=== POMO-WRAPPER START ==="
  echo "Date: $(date --iso-8601=seconds 2>/dev/null || date)"
  echo "Tool: $tool"
  echo "Cmd: $*"
  echo "CWD: $(pwd)"
  echo "User: $(whoami 2>/dev/null || id)"
  echo "Outfile: $OUTFILE"
  echo "-------------------------"
} > "$OUTFILE" 2>&1

# run command detached but capture exit status and append DONE line when finishes
# We use a background subshell that runs the command with setsid to detach from TTY.
# The subshell appends stdout/stderr to OUTFILE and writes a completion line when done.
(
  # child process; run under its own session so it survives terminal close
  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" >>"$OUTFILE" 2>&1
    rc=$?
  else
    # fallback if setsid not available
    "$@" >>"$OUTFILE" 2>&1
    rc=$?
  fi
  echo "-------------------------" >>"$OUTFILE"
  echo "END: $(date --iso-8601=seconds 2>/dev/null || date)  EXIT:$rc" >>"$OUTFILE"
  echo "=========================" >>"$OUTFILE"
) &

child_pid=$!
# record PID
echo "$child_pid" > "$PIDFILE"
echo "Started PID $child_pid" >> "$OUTFILE"
# print small status to stdout (useful when calling wrapper directly)
echo "Started: $*"
echo "PID: $child_pid"
echo "Log: $OUTFILE"

# optional: cleanup old logs (simple retention)
if [ "$RETENTION_DAYS" -gt 0 ] 2>/dev/null; then
  # run cleanup in background to avoid blocking
  (find "$BASE_LOGDIR" -type f -mtime +"$RETENTION_DAYS" -name '*.log' -print0 2>/dev/null | xargs -0 -r rm -f) &
fi

# done; wrapper exits while child keeps running
exit 0
