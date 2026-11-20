#!/usr/bin/env python3
"""logs/daily の front matter から、体と記録の数字を集計して Markdown と JSON を出す。

使い方:
  python scripts/status_numbers.py                 # 今日（日本時間）基準
  python scripts/status_numbers.py --date 2026-11-18
  python scripts/status_numbers.py --json status/numbers.json

AI を使わない計算だけのスクリプト。life-status スキルがこの結果をそのまま now.md に貼る。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import statistics
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML が必要です: pip install pyyaml", file=sys.stderr)
    raise

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs" / "daily"
JST = dt.timezone(dt.timedelta(hours=9))

# 通知の基準（変えるときはここと life-status の SKILL.md をそろえる）
SLEEP_SHORT_H = 6.0       # これ未満を「睡眠不足」とする
SLEEP_SHORT_STREAK = 3    # 何日続いたら知らせるか
NO_EXERCISE_STREAK = 4    # 運動の記録がない日が何日続いたら知らせるか
STEPS_DROP_RATIO = 0.7    # 7日平均が28日平均のこの割合を下回ったら知らせる
RESTING_HR_RISE = 5       # 安静時心拍の7日平均が28日平均よりこれ以上高ければ知らせる（bpm）
MIN_DAYS = 3              # 平均を出すのに必要な最低日数


def read_front(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load(days: int, today: dt.date) -> list[dict]:
    rows = []
    for i in range(days):
        d = today - dt.timedelta(days=i)
        p = LOGS / f"{d.isoformat()}.md"
        fm = read_front(p) if p.exists() else {}
        ex = fm.get("exercise") or []
        meals = fm.get("meals") or []
        rows.append({
            "date": d.isoformat(),
            "exists": p.exists(),
            "sleep_hours": num(fm.get("sleep_hours")),
            "steps": num(fm.get("steps")),
            "active_minutes": num(fm.get("active_minutes")),
            "resting_hr": num(fm.get("resting_hr")),
            "hrv_ms": num(fm.get("hrv_ms")),
            "spo2_pct": num(fm.get("spo2_pct")),
            "weight_kg": num(fm.get("weight_kg")),
            "bedtime": fm.get("bedtime"),
            "exercise_count": len(ex) if isinstance(ex, list) else 0,
            "meals_count": len(meals) if isinstance(meals, list) else 0,
        })
    return rows  # 新しい順


def avg(rows, key):
    vals = [r[key] for r in rows if r[key] is not None]
    if len(vals) < MIN_DAYS:
        return None, len(vals)
    return statistics.mean(vals), len(vals)


def streak(rows, cond):
    """新しい日から数えて cond を満たす日が何日続いているか（データのない日で止める）。"""
    n = 0
    for r in rows:
        c = cond(r)
        if c is None:
            break
        if not c:
            break
        n += 1
    return n


def fmt(v, unit="", digits=1):
    if v is None:
        return "—"
    if digits == 0:
        return f"{v:,.0f}{unit}"
    return f"{v:.{digits}f}{unit}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="基準日 YYYY-MM-DD（省略時は日本時間の今日）")
    ap.add_argument("--json", help="JSON の出力先")
    a = ap.parse_args()

    today = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(JST).date()
    # 体の数字は前日までを使う（当日分は朝の時点で揃っていない）
    base = today - dt.timedelta(days=1)
    rows28 = load(28, base)
    rows7 = rows28[:7]

    metrics = {}
    for key, label, unit, digits in [
        ("sleep_hours", "睡眠", "h", 1),
        ("steps", "歩数", "", 0),
        ("active_minutes", "活動時間", "分", 0),
        ("resting_hr", "安静時心拍", "bpm", 0),
        ("hrv_ms", "HRV", "ms", 0),
        ("spo2_pct", "SpO2", "%", 1),
        ("weight_kg", "体重", "kg", 1),
    ]:
        a7, n7 = avg(rows7, key)
        a28, n28 = avg(rows28, key)
        y = rows28[0][key]
        metrics[key] = {"label": label, "unit": unit, "digits": digits,
                        "yesterday": y, "avg7": a7, "n7": n7, "avg28": a28, "n28": n28}

    ex_days7 = sum(1 for r in rows7 if r["exercise_count"] > 0)
    meal_days7 = sum(1 for r in rows7 if r["meals_count"] > 0)
    log_days7 = sum(1 for r in rows7 if r["exists"])

    sleep_short = streak(rows28, lambda r: None if r["sleep_hours"] is None else r["sleep_hours"] < SLEEP_SHORT_H)
    no_ex = streak(rows28, lambda r: None if not r["exists"] else r["exercise_count"] == 0)

    alerts = []
    if sleep_short >= SLEEP_SHORT_STREAK:
        alerts.append(f"睡眠{SLEEP_SHORT_H:g}時間未満が{sleep_short}日続いている")
    if no_ex >= NO_EXERCISE_STREAK:
        alerts.append(f"運動の記録がない日が{no_ex}日続いている")
    s = metrics["steps"]
    if s["avg7"] is not None and s["avg28"] is not None and s["n28"] >= 10 and s["avg7"] < s["avg28"] * STEPS_DROP_RATIO:
        alerts.append(f"歩数の7日平均（{s['avg7']:,.0f}）が28日平均（{s['avg28']:,.0f}）の{STEPS_DROP_RATIO:.0%}未満")

    r = metrics["resting_hr"]
    if r["avg7"] is not None and r["avg28"] is not None and r["n28"] >= 10 and r["avg7"] >= r["avg28"] + RESTING_HR_RISE:
        alerts.append(f"安静時心拍の7日平均（{r['avg7']:.0f}）が28日平均（{r['avg28']:.0f}）より{RESTING_HR_RISE}以上高い")

    # 就寝時刻の7日平均（0時をまたぐので 18時より前は翌日扱い）
    beds = []
    for row in rows7:
        b = row.get("bedtime")
        if isinstance(b, str) and ":" in b:
            h, m_ = b.split(":")[:2]
            v = int(h) * 60 + int(m_)
            beds.append(v + 1440 if v < 18 * 60 else v)
    bedtime_avg7 = None
    if len(beds) >= MIN_DAYS:
        v = round(statistics.mean(beds)) % 1440
        bedtime_avg7 = f"{v // 60}:{v % 60:02d}"

    out = {
        "generated_for": today.isoformat(),
        "through": base.isoformat(),
        "metrics": metrics,
        "exercise_days7": ex_days7,
        "meal_days7": meal_days7,
        "log_days7": log_days7,
        "bedtime_avg7": bedtime_avg7,
        "sleep_short_streak": sleep_short,
        "no_exercise_streak": no_ex,
        "alerts": alerts,
        "daily": list(reversed(rows28)),  # 古い順（グラフ用）
    }

    lines = [f"**体**（{base.month}/{base.day}まで。7日平均と28日平均）", "",
             "| | 昨日 | 7日平均 | 28日平均 |", "|---|---|---|---|"]
    for m in metrics.values():
        if m["yesterday"] is None and m["avg7"] is None and m["avg28"] is None:
            continue   # まだ記録のない項目は表に出さない
        lines.append(f"| {m['label']} | {fmt(m['yesterday'], m['unit'], m['digits'])} | "
                     f"{fmt(m['avg7'], m['unit'], m['digits'])}（{m['n7']}日） | "
                     f"{fmt(m['avg28'], m['unit'], m['digits'])}（{m['n28']}日） |")
    lines += ["",
              f"- 運動した日：直近7日で{ex_days7}日",
              f"- 寝た時刻の平均：直近7日 {bedtime_avg7 or '—'}",
              f"- 食事の記録：直近7日で{meal_days7}日（日次ログがある日 {log_days7}日）"]
    if alerts:
        lines += ["", "注意：" + "／".join(alerts)]
    print("\n".join(lines))

    if a.json:
        p = pathlib.Path(a.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
