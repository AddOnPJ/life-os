#!/usr/bin/env python3
"""生活の期限の台帳（domains/life/deadlines.yaml）から、今日の段階を計算する（AI を使わない）。

使い方:
  python scripts/life_deadlines.py [--date YYYY-MM-DD]
出力: domains/life/obs/deadlines.json と、画面用の Markdown（標準出力）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))
DEFAULT = {"注意": -14, "警告": -3, "最優先": 0}
ORDER = {"最優先": 0, "警告": 1, "注意": 2, None: 3}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(JST).date()
    data = yaml.safe_load((ROOT / "domains/life/deadlines.yaml").read_text(encoding="utf-8")) or {}
    out = []
    for d in data.get("deadlines", []) or []:
        if d.get("status") != "open" or not d.get("due"):
            continue
        due = d["due"] if isinstance(d["due"], dt.date) else dt.date.fromisoformat(str(d["due"]))
        diff = (today - due).days
        lv = None
        for name in ("注意", "警告", "最優先"):
            if diff >= int((d.get("levels") or DEFAULT).get(name, 999)):
                lv = name
        out.append({"id": d["id"], "title": d["title"], "due": due.isoformat(), "days": -diff,
                    "category": d.get("category", ""), "level": lv, "note": d.get("note", "")})
    out.sort(key=lambda x: (ORDER[x["level"]], x["due"]))
    p = ROOT / "domains/life/obs/deadlines.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"date": today.isoformat(), "items": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["**生活の期限**"]
    for x in out[:8]:
        when = "今日" if x["days"] == 0 else (f"{-x['days']}日超過" if x["days"] < 0 else f"あと{x['days']}日")
        lines.append(f"- {'【' + x['level'] + '】' if x['level'] else ''}{x['due'][5:].replace('-', '/')} {x['title']}（{when}）")
    print("\n".join(lines) if out else "**生活の期限** なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
