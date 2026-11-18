#!/usr/bin/env python3
"""AddOn エージェントの計算部分（AI を使わない）。

domains/addon/agent/ の YAML を読み、目標の進み具合・期限の段階・実験の状態・
決めてほしいこと・エージェント自身の稼働を計算して、Markdown と JSON を出す。

使い方:
  python scripts/addon_agent.py                       # 今日（日本時間）基準で表示
  python scripts/addon_agent.py --date 2026-12-14
  python scripts/addon_agent.py --json domains/addon/agent/obs/calc.json

判断の基準（段階の日数・計画線）は YAML とこのファイルの定数にある。AI はこの結果を書き換えない。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
AG = ROOT / "domains" / "addon" / "agent"
JST = dt.timezone(dt.timedelta(hours=9))

DEFAULT_LEVELS = {"注意": -3, "警告": 0, "最優先": 2}
LEVEL_ORDER = {"最優先": 0, "警告": 1, "注意": 2}
REPLY_LEVELS = [(72, "最優先"), (48, "警告"), (24, "注意")]   # 応募への未返信（時間）
STALE_RUN_HOURS = 26                                          # エージェントが止まったとみなす時間


def load(name: str) -> dict:
    p = AG / name
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def d(v) -> dt.date | None:
    if v in (None, ""):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def level_for(days_from_due: int, levels: dict) -> str | None:
    """期限との差（今日−期限、正は超過）から段階を返す。"""
    hit = None
    for name in ("注意", "警告", "最優先"):
        if name in levels and days_from_due >= int(levels[name]):
            hit = name
    return hit


def plan_needed(plan: dict, today: dt.date) -> tuple[int, dt.date | None, int | None]:
    """今日時点で達しているべき累計（直前の計画日の値）と、次の計画日・その値。"""
    pts = sorted((d(k), int(v)) for k, v in plan.items())
    need = 0
    nxt, nxt_v = None, None
    for day, v in pts:
        if day <= today:
            need = v
        elif nxt is None:
            nxt, nxt_v = day, v
    return need, nxt, nxt_v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--json")
    a = ap.parse_args()
    now = dt.datetime.now(JST)
    today = dt.date.fromisoformat(a.date) if a.date else now.date()

    goal = load("goal.yaml").get("goal", {})
    apps = load("applicants.yaml").get("applicants", []) or []
    obls = load("obligations.yaml").get("obligations", []) or []
    exps = load("experiments.yaml").get("experiments", []) or []
    tacs = load("tactics.yaml").get("tactics", []) or []
    alerts: list[dict] = []

    # --- 目標 ---
    start = d(goal.get("count_from"))
    deadline = d(goal.get("deadline"))
    target = int(goal.get("target", 0))
    counted = [x for x in apps if d(x.get("received")) and (start is None or d(x.get("received")) >= start)]
    total = len(counted)
    need, nxt, nxt_v = plan_needed(goal.get("plan", {}), today)
    gap = total - need
    days_left = (deadline - today).days if deadline else None
    remain = max(target - total, 0)
    pace = round(remain / max(days_left, 1) * 30, 2) if days_left is not None else None
    last28 = sum(1 for x in counted if (today - d(x["received"])).days < 28)
    by_source: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    by_part: dict[str, int] = {}
    for x in counted:
        by_source[x.get("source", "不明")] = by_source.get(x.get("source", "不明"), 0) + 1
        by_stage[x.get("stage", "不明")] = by_stage.get(x.get("stage", "不明"), 0) + 1
        by_part[x.get("part", "不明")] = by_part.get(x.get("part", "不明"), 0) + 1
    joined = sum(1 for x in counted if x.get("stage") == "入団")

    if gap <= -2 or (start and (today - start).days >= 28 and last28 == 0):
        alerts.append({"level": "警告", "text": f"応募が計画より遅れている（累計{total}件／計画{need}件、直近28日{last28}件）→ 打ち手を追加する"})
    elif gap == -1:
        alerts.append({"level": "注意", "text": f"応募が計画より1件遅れ（累計{total}件／計画{need}件）"})
    if deadline and today.month == 3 and today.year == deadline.year and gap <= -2:
        alerts[-1]["level"] = "最優先"

    # --- 応募への返信 ---
    for x in counted:
        if x.get("stage") == "問い合わせ" and not x.get("replied"):
            rec = d(x.get("received"))
            hours = (today - rec).days * 24 if rec else 0
            for h, lv in REPLY_LEVELS:
                if hours >= h:
                    alerts.append({"level": lv, "text": f"応募 {x.get('initial','?')}（{x.get('part','?')}）に未返信 {hours // 24}日目", "id": x.get("id")})
                    break
        if x.get("stage") == "見学済み":
            vd = d(x.get("visit"))
            if vd and (today - vd).days >= 3:
                alerts.append({"level": "最優先", "text": f"{x.get('initial','?')}（{x.get('part','?')}）の見学から{(today - vd).days}日、入団の連絡がまだ", "id": x.get("id")})

    # --- 期限の台帳 ---
    obl_out = []
    for o in obls:
        if o.get("status") != "open":
            continue
        due = d(o.get("due"))
        if not due:
            continue
        diff = (today - due).days
        lv = level_for(diff, o.get("levels") or DEFAULT_LEVELS)
        item = {"id": o["id"], "title": o["title"], "due": due.isoformat(), "days": -diff, "owner": o.get("owner", ""), "level": lv}
        obl_out.append(item)
        if lv:
            when = f"期限 {due.month}/{due.day}" + ("（今日）" if diff == 0 else f"（{diff}日超過）" if diff > 0 else f"（あと{-diff}日）")
            alerts.append({"level": lv, "text": f"{o['title']}　{when}", "id": o["id"]})
    obl_out.sort(key=lambda x: x["due"])

    # --- 実験 ---
    exp_out = []
    for e in exps:
        if e.get("status") not in ("running", "planned", "extended"):
            continue
        end = d(e.get("end"))
        days = (end - today).days if end else None
        exp_out.append({"id": e["id"], "title": e["title"], "end": end.isoformat() if end else None, "days_left": days, "status": e.get("status")})
        if days is not None and days <= 0 and e.get("status") == "running":
            alerts.append({"level": "警告", "text": f"実験 {e['id']} の判定日（{end.month}/{end.day}）。判定案を承認待ちに出す", "id": e["id"]})
        if "要確認" in str(e.get("start", "")) or e.get("start") is None:
            alerts.append({"level": "注意", "text": f"実験 {e['id']} の開始日が未確定", "id": e["id"]})

    # --- 決めてほしいこと ---
    dec_path = AG / "decisions.md"
    pending = []
    if dec_path.exists():
        txt = dec_path.read_text(encoding="utf-8")
        sec = txt.split("## 未決", 1)[-1].split("## 決定済み", 1)[0]
        pending = [m.group(1).strip() for m in re.finditer(r"^- \[ \] (.+)$", sec, re.M)]

    # --- 打ち手 ---
    todo = sorted([t for t in tacs if t.get("status") == "todo"], key=lambda t: t.get("priority", 9))
    waiting = [t for t in tacs if t.get("status") == "waiting_decision"]

    # --- エージェントの稼働 ---
    runs = sorted((AG / "runs").glob("*.md"))
    last_run = runs[-1].stem if runs else None
    if last_run:
        lr = d(last_run)
        if lr and (today - lr).days * 24 > STALE_RUN_HOURS:
            alerts.append({"level": "警告", "text": f"AddOn エージェントの最後の実行が {lr.month}/{lr.day}。止まっている可能性"})

    alerts.sort(key=lambda x: LEVEL_ORDER.get(x["level"], 9))
    out = {
        "date": today.isoformat(),
        "goal": {"total": total, "target": target, "plan_now": need, "gap": gap, "next_plan": nxt.isoformat() if nxt else None,
                 "next_plan_value": nxt_v, "days_left": days_left, "needed_per_month": pace, "last28": last28,
                 "joined": joined, "by_source": by_source, "by_stage": by_stage, "by_part": by_part},
        "alerts": alerts,
        "obligations": obl_out,
        "experiments": exp_out,
        "decisions_pending": pending,
        "tactics_next": [{"id": t["id"], "title": t["title"]} for t in todo[:3]],
        "tactics_waiting": [{"id": t["id"], "title": t["title"]} for t in waiting],
        "last_run": last_run,
    }

    # --- Markdown ---
    L = [f"**目標** 3月末までに応募{target}件：いま {total}件（計画 {need}件"
         + (f"、次は {nxt.month}/{nxt.day} までに {nxt_v}件" if nxt else "") + f"）。残り{days_left}日、必要ペース 月{pace}件"]
    if counted:
        L.append("- 経路：" + "、".join(f"{k}{v}" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1]))
                 + "／段階：" + "、".join(f"{k}{v}" for k, v in by_stage.items()))
    if alerts:
        L += ["", "**今やること**"]
        for x in alerts[:8]:
            L.append(f"- 【{x['level']}】{x['text']}")
    soon = [o for o in obl_out if o["days"] is not None and 0 < o["days"] <= 14 and not o["level"]]
    if soon:
        L += ["", "**2週間以内の期限**"]
        for o in soon[:6]:
            L.append(f"- {o['due'][5:].replace('-', '/')} {o['title']}（{o['owner']}）")
    if pending:
        L += ["", f"**決めてほしいこと**（{len(pending)}件）"]
        for p in pending[:5]:
            L.append(f"- {p}")
    if exp_out:
        L += ["", "**実験**"]
        for e in exp_out:
            L.append(f"- {e['id']} {e['title']}（判定 {e['end'][5:].replace('-', '/') if e['end'] else '未定'}、あと{e['days_left']}日）")
    print("\n".join(L))

    if a.json:
        p = pathlib.Path(a.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
