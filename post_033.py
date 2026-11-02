#!/usr/bin/env python3
# One-shot scheduled X post for ハチミツ (033). Fired by Task Scheduler at 7:00 JST 2026-06-22.
import sys, datetime, traceback
from pathlib import Path
BASE = str(Path(__file__).resolve().parent)
sys.path.insert(0, BASE)
LOG = Path(BASE) / "post_033.log"

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")

try:
    log("start scheduled X post for ハチミツ 033")
    import x_post
    tid = x_post.post_for_video("ハチミツ", "ycWaGXbEoHI", "🍯")
    log(f"SUCCESS tweet id: {tid}")
except Exception as e:
    log("ERROR: " + repr(e))
    log(traceback.format_exc())
    raise
