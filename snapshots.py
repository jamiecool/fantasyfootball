"""Find the newest dated snapshot of a live feed.

Live feeds are written as `<stem>__YYYY-MM-DD.<ext>` rather than to a fixed
filename. Two people fetching on different days then produce different files
instead of conflicting edits to one, and we accumulate a record of how the market
moved through preseason -- which we badly wish we had for Underdog, whose edge
currently rests on judgement precisely because nobody kept the daily snapshots.

Undated legacy files are still found, so nothing breaks on an old checkout.
"""
import glob
import os
import time


def snapshot_path(directory, stem, ext):
    """Where today's fetch should be written."""
    return os.path.join(directory, f"{stem}__{time.strftime('%Y-%m-%d')}.{ext}")


def latest_snapshot(directory, stem, ext):
    """Newest dated snapshot, or the undated legacy file, or None."""
    dated = sorted(glob.glob(os.path.join(directory, f"{stem}__*.{ext}")))
    if dated:
        return dated[-1]
    legacy = os.path.join(directory, f"{stem}.{ext}")
    return legacy if os.path.exists(legacy) else None


def snapshot_date(path):
    """The date baked into a snapshot filename, or '' if it is a legacy file."""
    base = os.path.basename(path or "")
    return base.split("__")[1].rsplit(".", 1)[0] if "__" in base else ""
