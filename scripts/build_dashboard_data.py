#!/usr/bin/env python3
"""全部の画面（スマホ・タブレット・PC のダッシュボード）用のデータを1つの JSON にまとめる（AI を使わない）。

読むもの（どれも life-os の中。secure/ は読まない）:
  status/numbers.json            体と記録の数字（status_numbers.py）
  domains/addon/agent/obs/calc.json   AddOn の目標・期限・実験（addon_agent.py）
  domains/addon/agent/obs/listings.json  PC が取った掲載の要点
  domains/addon/agent/*.yaml / decisions.md
  status/approvals.md, status/pc-sync.json, status/now.md
  docs/backlog.md, docs/automations.md
  domains/addon/agent/runs/ , reviews/system/
出力:
  status/dashboard.json
使い方:
  python scripts/build_dashboard_data.py            # 先に status_numbers.py と addon_agent.py を実行しておく
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))


def rj(p: str) -> dict:
    f = ROOT / p
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def ry(p: str) -> dict:
    f = ROOT / p
    if not f.exists():
        return {}
    return yaml.safe_load(f.read_text(encoding="utf-8")) or {}


def rt(p: str) -> str:
    f = ROOT / p
    return f.read_text(encoding="utf-8") if f.exists() else ""


def checklist(md: str, section: str | None = None) -> list[dict]:
    """「- [ ] 〜」「- [x] 〜」を拾う。section を指定したら、その見出しの下だけ。"""
    if section:
        parts = re.split(r"^## ", md, flags=re.M)
        md = next((p for p in parts if p.startswith(section)), "")
    out = []
    for m in re.finditer(r"^- \[( |x)\] (.+)$", md, re.M):
        out.append({"done": m.group(1) == "x", "text": m.group(2).strip()})
    return out


def backlog(md: str) -> list[dict]:
    items, level = [], ""
    for line in md.splitlines():
        h = re.match(r"^## (.+)", line)
        if h:
            level = h.group(1).strip()
            continue
        m = re.match(r"^- \[ \] (S\d+) (.+)$", line)
        if m and level != "済み":
            items.append({"id": m.group(1), "level": level, "text": m.group(2)})
        d = re.match(r"^- (\d{4}-\d{2}-\d{2}) (.+)$", line)
        if d and level == "済み":
            items.append({"id": "", "level": "済み", "date": d.group(1), "text": d.group(2)})
    return items


def automations(md: str) -> list[dict]:
    rows = []
    sec = md.split("## 自分で送ると動くもの")[0]
    for line in sec.splitlines():
        if not line.startswith("| ") or line.startswith("| 時刻") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4:
            rows.append({"when": cells[0], "name": cells[1], "where": cells[2], "what": cells[3]})
    return rows


def main() -> int:
    now = dt.datetime.now(JST)
    numbers = rj("status/numbers.json")
    calc = rj("domains/addon/agent/obs/calc.json")
    goal = ry("domains/addon/agent/goal.yaml").get("goal", {})
    exps = ry("domains/addon/agent/experiments.yaml").get("experiments", []) or []
    tactics = ry("domains/addon/agent/tactics.yaml").get("tactics", []) or []
    apps = ry("domains/addon/agent/applicants.yaml").get("applicants", []) or []

    # 応募の累計（日ごと）と計画線
    start = dt.date.fromisoformat(str(goal.get("count_from", "2026-11-19")))
    received = sorted(dt.date.fromisoformat(str(a["received"])) for a in apps if a.get("received"))
    cum, series = 0, []
    day = start
    while day <= now.date():
        cum += sum(1 for r in received if r == day)
        series.append({"date": day.isoformat(), "count": cum})
        day += dt.timedelta(days=1)
    plan = [{"date": str(k), "count": int(v)} for k, v in sorted((goal.get("plan") or {}).items(), key=lambda kv: str(kv[0]))]

    runs = sorted((ROOT / "domains/addon/agent/runs").glob("*.md"))
    last_run_text = runs[-1].read_text(encoding="utf-8") if runs else ""
    reviews = sorted((ROOT / "reviews/system").glob("*.md"))

    # YouTube（PC が毎朝取る。7日前の記録と比べる）
    yt = rj("domains/addon/agent/obs/youtube.json")
    if yt:
        obs = ROOT / "domains/addon/agent/obs"
        cur_date = dt.date.fromisoformat(yt["checked_at"][:10])
        prev = None
        for back in range(7, 15):
            f = obs / f"youtube-{(cur_date - dt.timedelta(days=back)).isoformat()}.json"
            if f.exists():
                prev = json.loads(f.read_text(encoding="utf-8")); break
        pv = {v["id"]: v["views"] for v in (prev or {}).get("items", [])}
        for v in yt.get("items", []):
            v["views_7d"] = v["views"] - pv[v["id"]] if v["id"] in pv else None
        yt["subscribers_7d"] = (yt["subscribers"] - prev["subscribers"]) if prev and yt.get("subscribers") is not None and prev.get("subscribers") is not None else None
        yt["views_7d"] = (yt["views"] - prev["views"]) if prev else None
        yt["items"] = yt.get("items", [])[:15]

    data = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "links": {
            "repo": "https://github.com/AddOnPJ/life-os",
            "now": "https://github.com/AddOnPJ/life-os/blob/main/status/now.md",
            "addon": "https://github.com/AddOnPJ/life-os/blob/main/domains/addon/agent/status.md",
            "backlog": "https://github.com/AddOnPJ/life-os/blob/main/docs/backlog.md",
            "automations": "https://github.com/AddOnPJ/life-os/blob/main/docs/automations.md",
            "doc": "https://claude.ai/artifact/Qv563GNdcmyiL5MnNqRL2U",
        },
        "now_md": rt("status/now.md"),
        "body": {
            "through": numbers.get("through"),
            "metrics": numbers.get("metrics", {}),
            "alerts": numbers.get("alerts", []),
            "exercise_days7": numbers.get("exercise_days7"),
            "meal_days7": numbers.get("meal_days7"),
            "daily": [{k: r.get(k) for k in ("date", "sleep_hours", "steps", "active_minutes", "exercise_count", "meals_count")}
                      for r in numbers.get("daily", [])],
        },
        "addon": {
            "goal": calc.get("goal", {}),
            "target": goal.get("target"),
            "deadline": str(goal.get("deadline", "")),
            "series": series,
            "plan": plan,
            "alerts": calc.get("alerts", []),
            "obligations": calc.get("obligations", []),
            "experiments": [{k: e.get(k) for k in ("id", "title", "start", "end", "metric", "adopt_if", "reject_if", "status")} for e in exps],
            "tactics": [{k: t.get(k) for k in ("id", "title", "priority", "status", "owner")} for t in tactics if t.get("status") != "dropped"],
            "decisions": calc.get("decisions_pending", []),
            "listings": rj("domains/addon/agent/obs/listings.json"),
            "last_run": last_run_text[:1200],
        },
        "youtube": yt,
        "approvals": checklist(rt("status/approvals.md"), "待ち"),
        "backlog": backlog(rt("docs/backlog.md")),
        "automations": automations(rt("docs/automations.md")),
        "health_of_system": {
            "pc_sync": rj("status/pc-sync.json"),
            "addon_last_run": calc.get("last_run"),
            "last_review": reviews[-1].stem if reviews else None,
        },
    }
    out = ROOT / "status" / "dashboard.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"status/dashboard.json {out.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
