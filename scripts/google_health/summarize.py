"""sync.py が保存した Google Health の生データを集計して、日次ログに書く。

使い方（life-os のルートで）:
    python scripts/google_health/summarize.py --days 3
    python scripts/google_health/summarize.py --days 3 --dry-run   # 書かずに内容だけ見る
    python scripts/google_health/summarize.py --backfill           # 保存してある生データ全部から入れ直す

読むもの: secure/health/raw/YYYY-MM-DD/*.json（既定は最新の日付フォルダ。--raw-dir で指定可）
          生データは大きいので Git に入れない（secure/ は .gitignore 済み）。中身の秘密扱いはしない

書くもの: logs/daily/YYYY-MM-DD.md
  front matter: steps, distance_km, calories_total, active_minutes, sleep_hours, nap_minutes,
                bedtime, wake_time, sleep_deep_min, sleep_light_min, sleep_rem_min, sleep_awake_min,
                resting_hr, hrv_ms, spo2_pct, weight_kg, exercise
  本文:「## 運動・体調」の自動ブロック（心拍の幅・睡眠の内訳・昼寝なども）

ルール:
- 2026-11-20 から健康の数字は通常の記録（Yuichi の決定）。以前は心拍などを secure/health/ に分けていた
- 日付は日本時間。睡眠は「起きた日」（睡眠の終了時刻の日付）の記録にする。
- sleep_hours は主睡眠（いちばん長い睡眠）の実睡眠時間。昼寝などは nap_minutes に分ける。
- 既に値がある項目は上書きしない。違っていれば「要確認」に書く。
  ただし前回このスクリプトが書いた値のままなら更新してよい（当日の歩数は日中に増えるため）。
  前回値は secure/health/.summarize_state.json に持つ（PC の中だけの作業用ファイル）。
- sync.py が長い期間を取った日（_meta.json）は、その期間を全部反映する。
- 初めて新しい形で動くとき（state に format 2 が無いとき）は、自動で --backfill と同じ入れ直しをする。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "secure" / "health" / "raw"
STATE_FILE = ROOT / "secure" / "health" / ".summarize_state.json"
DAILY_DIR = ROOT / "logs" / "daily"
TEMPLATE = ROOT / "templates" / "daily.md"

JST = dt.timezone(dt.timedelta(hours=9))
MARK_S = "<!-- google-health:start -->"
MARK_E = "<!-- google-health:end -->"
TAG = "[google-health]"

EXERCISE_JA = {
    "WALKING": "ウォーキング",
    "RUNNING": "ランニング",
    "BIKING": "サイクリング",
    "CYCLING": "サイクリング",
    "SWIMMING": "水泳",
    "HIKING": "ハイキング",
    "WORKOUT": "ワークアウト",
    "YOGA": "ヨガ",
    "ELLIPTICAL": "エリプティカル",
    "WEIGHTLIFTING": "筋トレ",
    "STRENGTH_TRAINING": "筋トレ",
}


# ---------- 読み込み ----------

def pick_raw_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    today = RAW_DIR / dt.datetime.now(JST).date().isoformat()
    if today.exists():
        return today
    dirs = sorted(p for p in RAW_DIR.iterdir() if p.is_dir()) if RAW_DIR.exists() else []
    if not dirs:
        sys.exit(f"{RAW_DIR} に生データがありません。先に sync.py fetch を実行してください。")
    return dirs[-1]


def load(raw: Path, name: str):
    f = raw / f"{name}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def rollup_by_day(raw: Path, dtype: str) -> dict[dt.date, dict]:
    d = load(raw, f"rollup_{dtype}") or {}
    out = {}
    for r in d.get("rollupDataPoints", []):
        c = r["civilStartTime"]["date"]
        out[dt.date(c["year"], c["month"], c["day"])] = r
    return out


def list_points(raw: Path, dtype: str) -> list[dict]:
    d = load(raw, f"list_{dtype}") or {}
    return [p for pg in d.get("pages", []) for p in pg.get("dataPoints", [])]


def date_of(c: dict) -> dt.date:
    return dt.date(c["year"], c["month"], c["day"])


def jst(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST)


def secs(s: str | None) -> int:
    return int(float(s.rstrip("s"))) if s else 0


# ---------- 1日分の集計 ----------

def collect(raw: Path, day: dt.date, cache: dict) -> dict:
    """day の値を { pub: front matter に書く数字, det: 本文の自動ブロックに書く説明 } にまとめる。無い項目は入れない。"""
    pub: dict = {}
    det: dict = {}

    r = cache["steps"].get(day)
    if r:
        pub["steps"] = int(r["steps"]["countSum"])
    r = cache["distance"].get(day)
    if r:
        pub["distance_km"] = round(int(r["distance"]["millimetersSum"]) / 1_000_000, 1)
    r = cache["total-calories"].get(day)
    if r:
        pub["calories_total"] = round(r["totalCalories"]["kcalSum"])
    r = cache["active-minutes"].get(day)
    if r:
        lv = {x["activityLevel"]: int(x["activeMinutesSum"])
              for x in r["activeMinutes"].get("activeMinutesRollupByActivityLevel", [])}
        pub["active_minutes"] = sum(lv.values())
        pub["_active_levels"] = lv
    r = cache["heart-rate"].get(day)
    if r:
        h = r["heartRate"]
        det["心拍(日)"] = (f"平均 {h['beatsPerMinuteAvg']:.0f}／最大 {h['beatsPerMinuteMax']:.0f}／"
                          f"最小 {h['beatsPerMinuteMin']:.0f} bpm")

    # 睡眠: 終了時刻（日本時間）の日付 = 起きた日
    sleeps = []
    for p in cache["sleep"]:
        s = p["sleep"]
        if jst(s["interval"]["endTime"]).date() != day:
            continue
        sm = s.get("summary", {})
        sleeps.append({
            "asleep": int(sm.get("minutesAsleep", 0)),
            "period": int(sm.get("minutesInSleepPeriod", 0)),
            "awake": int(sm.get("minutesAwake", 0)),
            "start": jst(s["interval"]["startTime"]),
            "end": jst(s["interval"]["endTime"]),
            "stages": {x["type"]: int(x["minutes"]) for x in sm.get("stagesSummary", [])},
            "main": s.get("metadata", {}).get("mainSleep", False),
        })
    if sleeps:
        main = max(sleeps, key=lambda x: x["asleep"])
        naps = [s for s in sleeps if s is not main]
        pub["sleep_hours"] = round(main["asleep"] / 60, 1)
        if naps:
            pub["nap_minutes"] = sum(s["asleep"] for s in naps)
        st = main["stages"]
        pub["bedtime"] = f'"{main["start"]:%H:%M}"'
        pub["wake_time"] = f'"{main["end"]:%H:%M}"'
        if st:
            pub["sleep_deep_min"] = st.get("DEEP", 0)
            pub["sleep_light_min"] = st.get("LIGHT", 0)
            pub["sleep_rem_min"] = st.get("REM", 0)
            pub["sleep_awake_min"] = st.get("AWAKE", 0)
        det["睡眠"] = (f"{main['start']:%H:%M}〜{main['end']:%H:%M}／睡眠 {main['asleep']}分・"
                     f"中途覚醒 {main['awake']}分"
                     + (f"／深 {st.get('DEEP', 0)}・浅 {st.get('LIGHT', 0)}・REM {st.get('REM', 0)}・"
                        f"覚醒 {st.get('AWAKE', 0)}（分）" if st else ""))
        for i, n in enumerate(naps, 1):
            det[f"昼寝{i}"] = f"{n['start']:%H:%M}〜{n['end']:%H:%M}／睡眠 {n['asleep']}分"

    # 運動: 開始時刻（日本時間）の日付
    ex = []
    for p in cache["exercise"]:
        e = p["exercise"]
        start = jst(e["interval"]["startTime"])
        if start.date() != day:
            continue
        minutes = max(1, round(secs(e.get("activeDuration")) / 60))
        t = e.get("exerciseType", "UNKNOWN")
        ex.append({"start": start, "type": EXERCISE_JA.get(t, t), "known": t in EXERCISE_JA,
                   "raw": t, "minutes": minutes})
    ex.sort(key=lambda x: x["start"])
    if ex:
        pub["exercise"] = ex

    # 心拍・HRV・SpO2・体重
    for p in cache["daily-resting-heart-rate"]:
        d = p["dailyRestingHeartRate"]
        if date_of(d["date"]) == day and d.get("beatsPerMinute") is not None:
            pub["resting_hr"] = int(round(float(d["beatsPerMinute"])))
    for p in cache["daily-heart-rate-variability"]:
        d = p["dailyHeartRateVariability"]
        if date_of(d["date"]) != day:
            continue
        if d.get("averageHeartRateVariabilityMilliseconds") is not None:
            pub["hrv_ms"] = round(float(d["averageHeartRateVariabilityMilliseconds"]), 1)
        extra = []
        if d.get("deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds") is not None:
            extra.append(f"深い睡眠の RMSSD {d['deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds']} ms")
        if d.get("nonRemHeartRateBeatsPerMinute") is not None:
            extra.append(f"ノンレム心拍 {d['nonRemHeartRateBeatsPerMinute']} bpm")
        if extra:
            det["HRV の内訳"] = "／".join(extra)
    for p in cache["daily-oxygen-saturation"]:
        d = p["dailyOxygenSaturation"]
        if date_of(d["date"]) == day and d.get("averagePercentage") is not None:
            pub["spo2_pct"] = round(float(d["averagePercentage"]), 1)
            if d.get("lowerBoundPercentage") is not None:
                det["SpO2 の幅"] = f"{d.get('lowerBoundPercentage')}〜{d.get('upperBoundPercentage')}%"
    w = [p["weight"] for p in cache["weight"] if date_of(p["weight"]["sampleTime"]["civilTime"]["date"]) == day]
    if w:
        w.sort(key=lambda x: x["sampleTime"]["physicalTime"])
        pub["weight_kg"] = round(w[-1]["weightGrams"] / 1000, 1)
    return {"pub": pub, "det": det}


# ---------- front matter / 本文の編集 ----------

def split_fm(text: str) -> tuple[list[str], list[str]]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return [], lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], lines[i + 1:]
    return [], lines


def fm_find(fm: list[str], key: str) -> tuple[int, int] | None:
    """key の行範囲 [start, end) を返す（リスト形式の続き行を含む）。"""
    for i, ln in enumerate(fm):
        if re.match(rf"^{re.escape(key)}\s*:", ln):
            j = i + 1
            while j < len(fm) and re.match(r"^\s+(-|\S)", fm[j]) and not re.match(r"^\S", fm[j]):
                j += 1
            return i, j
    return None


def fm_scalar(fm: list[str], key: str):
    """既存の値。無い・空なら None。数値は数値で返す。"""
    r = fm_find(fm, key)
    if not r:
        return None
    v = re.sub(r"\s+#.*$", "", fm[r[0]].split(":", 1)[1]).strip()
    if v in ("", "[]", "null", "~"):
        return None
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v


def fm_exercise_total(fm: list[str]) -> int | None:
    r = fm_find(fm, "exercise")
    if not r:
        return None
    block = "\n".join(re.sub(r"\s+#.*$", "", ln) for ln in fm[r[0]:r[1]])
    ms = re.findall(r"minutes\s*:\s*(\d+)", block)
    return sum(int(m) for m in ms) if ms else None


def fm_set(fm: list[str], key: str, value_lines: list[str]) -> None:
    r = fm_find(fm, key)
    if r:
        comment = re.search(r"\s+#.*$", fm[r[0]])
        if len(value_lines) == 1 and comment:
            value_lines = [value_lines[0] + comment.group(0)]
        fm[r[0]:r[1]] = value_lines
    else:
        fm.extend(value_lines)


def fmt_num(v) -> str:
    return f"{v:.1f}" if isinstance(v, float) else str(v)


def same(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) < 0.05
    except (TypeError, ValueError):
        return str(a) == str(b)


def set_section_block(body: list[str], heading: str, block: list[str]) -> list[str]:
    """heading 直下の自動ブロック（MARK_S〜MARK_E）を入れ替える。無ければ作る。"""
    text = "\n".join(body)
    new = "\n".join([MARK_S, *block, MARK_E])
    if MARK_S in text and MARK_E in text:
        text = re.sub(re.escape(MARK_S) + r".*?" + re.escape(MARK_E), lambda _: new, text, flags=re.S)
    elif re.search(rf"^{re.escape(heading)}\s*$", text, flags=re.M):
        text = re.sub(rf"^({re.escape(heading)})\s*$", lambda m: f"{m.group(1)}\n{new}", text, count=1, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\n\n{heading}\n{new}\n"
    text = re.sub(re.escape(MARK_E) + r"\n(?=## )", MARK_E + "\n\n", text)
    return text.split("\n")


def add_confirm(body: list[str], lines: list[str]) -> list[str]:
    """「## 要確認」に行を足す（同じ項目の自動行があれば置き換え）。"""
    if not lines:
        return body
    text = "\n".join(body)
    if not re.search(r"^## 要確認\s*$", text, flags=re.M):
        text = text.rstrip("\n") + "\n\n## 要確認\n"
    for ln in lines:
        key = ln.split(":", 1)[0]
        text = re.sub(rf"^{re.escape(key)}:.*\n?", "", text, flags=re.M)
        text = re.sub(r"^(## 要確認[ \t]*\n)", lambda m: m.group(1) + ln + "\n", text, count=1, flags=re.M)
    return text.split("\n")


# ---------- 日次ログの更新 ----------

def update_daily(day: dt.date, pub: dict, det: dict, state: dict, dry: bool) -> list[str]:
    f = DAILY_DIR / f"{day.isoformat()}.md"
    if f.exists():
        text = f.read_text(encoding="utf-8")
    else:
        text = TEMPLATE.read_text(encoding="utf-8").replace("YYYY-MM-DD", day.isoformat())
    fm, body = split_fm(text)
    if not fm:
        return [f"{f.name}: front matter が読めないためスキップ（要確認）"]
    mem = state.setdefault(day.isoformat(), {})
    report, confirms = [], []

    def put_scalar(key: str, val, label: str):
        cur = fm_scalar(fm, key)
        if cur is None or (key in mem and same(cur, mem[key])):
            if cur is None or not same(cur, val):
                fm_set(fm, key, [f"{key}: {fmt_num(val)}"])
                report.append(f"{key}: {fmt_num(val)}" + ("（更新）" if cur is not None else ""))
            mem[key] = val
        elif not same(cur, val):
            confirms.append(f"- {TAG} {key}: ログ {fmt_num(cur)} / Google Health {fmt_num(val)}（{label}）")
            report.append(f"{key}: 既存 {fmt_num(cur)} ≠ {fmt_num(val)} → 要確認")

    labels = {"steps": "歩数", "distance_km": "距離km", "calories_total": "総消費kcal",
              "active_minutes": "アクティブ分", "sleep_hours": "睡眠時間", "nap_minutes": "昼寝分",
              "bedtime": "就寝", "wake_time": "起床", "sleep_deep_min": "深い睡眠分",
              "sleep_light_min": "浅い睡眠分", "sleep_rem_min": "REM分", "sleep_awake_min": "中途覚醒分",
              "resting_hr": "安静時心拍", "hrv_ms": "HRV", "spo2_pct": "SpO2", "weight_kg": "体重"}
    for key, label in labels.items():
        if key in pub:
            put_scalar(key, pub[key], label)

    ex = pub.get("exercise")
    if ex:
        total = sum(e["minutes"] for e in ex)
        cur_total = fm_exercise_total(fm)
        if cur_total is None or ("exercise_total" in mem and mem["exercise_total"] == cur_total):
            lines = ["exercise:"] + [f"  - {{type: \"{e['type']}\", minutes: {e['minutes']}}}" for e in ex]
            if cur_total != total or fm_find(fm, "exercise") is None:
                fm_set(fm, "exercise", lines)
                report.append(f"exercise: {len(ex)}件 合計{total}分")
            mem["exercise_total"] = total
        elif cur_total != total:
            confirms.append(f"- {TAG} exercise: ログ 合計{cur_total}分 / Google Health 合計{total}分")
            report.append(f"exercise: 既存 {cur_total}分 ≠ {total}分 → 要確認")
        for e in ex:
            if not e["known"]:
                confirms.append(f"- {TAG} 運動の種類 {e['raw']}: 日本語の対応表に無い（{e['start']:%H:%M}）")

    # 「運動・体調」の自動ブロック
    block = []
    if "steps" in pub:
        block.append(f"- 歩数 {pub['steps']:,}" + (f"／距離 {pub['distance_km']} km" if "distance_km" in pub else ""))
    if "calories_total" in pub:
        block.append(f"- 消費カロリー {pub['calories_total']} kcal（1日の総消費。基礎代謝を含み、運動だけの消費ではない）")
    if "active_minutes" in pub:
        lv = pub["_active_levels"]
        block.append(f"- アクティブ {pub['active_minutes']}分（軽 {lv.get('LIGHT', 0)}／中 {lv.get('MODERATE', 0)}／高 {lv.get('VIGOROUS', 0)}）")
    if "sleep_hours" in pub:
        block.append(f"- 睡眠 {pub['sleep_hours']} 時間" + (f"（昼寝 {pub['nap_minutes']}分）" if "nap_minutes" in pub else "")
                     + (f"：{det['睡眠']}" if "睡眠" in det else ""))
    for k in [k for k in det if k.startswith("昼寝")]:
        block.append(f"- {k} {det[k]}")
    if ex:
        block.append("- 運動: " + "、".join(f"{e['start']:%H:%M} {e['type']} {e['minutes']}分" for e in ex))
    hr = []
    if "resting_hr" in pub:
        hr.append(f"安静時心拍 {pub['resting_hr']} bpm")
    if "hrv_ms" in pub:
        hr.append(f"HRV {pub['hrv_ms']} ms")
    if "spo2_pct" in pub:
        hr.append(f"SpO2 {pub['spo2_pct']}%" + (f"（{det['SpO2 の幅']}）" if "SpO2 の幅" in det else ""))
    if hr:
        block.append("- " + "／".join(hr))
    if "HRV の内訳" in det:
        block.append(f"- HRV の内訳: {det['HRV の内訳']}")
    if "心拍(日)" in det:
        block.append(f"- 心拍（1日）: {det['心拍(日)']}")
    if "weight_kg" in pub:
        block.append(f"- 体重 {pub['weight_kg']} kg")
    if block and "steps" in pub:   # rollup が取れていない日（取得日数の外）は既存ブロックを残す
        body = set_section_block(body, "## 運動・体調", block)
    body = add_confirm(body, confirms)

    new_text = "---\n" + "\n".join(fm) + "\n---\n" + "\n".join(body)
    new_text = re.sub(r"\n{3,}", "\n\n", new_text).rstrip("\n") + "\n"
    if not f.exists() or new_text != text:
        if not dry:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(new_text, encoding="utf-8", newline="\n")
        report.insert(0, f"{'作成' if not f.exists() else '更新'}: logs/daily/{f.name}")
    else:
        report.insert(0, f"変更なし: logs/daily/{f.name}")
    return report


# ---------- main ----------

def load_cache(raw: Path) -> dict:
    cache = {t: rollup_by_day(raw, t) for t in ("steps", "distance", "total-calories", "active-minutes", "heart-rate")}
    for t in ("sleep", "exercise", "daily-resting-heart-rate", "daily-heart-rate-variability",
              "daily-oxygen-saturation", "weight"):
        cache[t] = list_points(raw, t)
    return cache


def meta_days(raw: Path, end: dt.date, days: int) -> int:
    """sync.py が取った期間（_meta.json）が days より長ければ、その日数を返す。"""
    m = load(raw, "_meta")
    if m and m.get("start"):
        span = (end - dt.date.fromisoformat(m["start"])).days + 1
        return max(days, span)
    return days


def run(raw: Path, end: dt.date, days: int, state: dict, dry: bool) -> None:
    days = meta_days(raw, end, days)
    print(f"生データ: {raw.relative_to(ROOT) if raw.is_relative_to(ROOT) else raw}（{days}日分）")
    cache = load_cache(raw)
    for n in range(days - 1, -1, -1):
        day = end - dt.timedelta(days=n)
        r = collect(raw, day, cache)
        if not r["pub"]:
            print(f"\n{day}: データなし")
            continue
        print(f"\n{day}")
        for line in update_daily(day, r["pub"], r["det"], state, dry):
            print("  " + line)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Google Health 生データ → 日次ログ")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--raw-dir")
    ap.add_argument("--backfill", action="store_true", help="保存してある生データの日付フォルダを古い順に全部使って入れ直す")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    today = dt.datetime.now(JST).date()
    backfill = args.backfill or state.get("_format") != 2
    if backfill and RAW_DIR.exists() and not args.raw_dir:
        print("入れ直し: 保存してある生データを古い順に全部使う")
        for d in sorted(p for p in RAW_DIR.iterdir() if p.is_dir()):
            try:
                end = dt.date.fromisoformat(d.name)
            except ValueError:
                continue
            run(d, end, 10, state, args.dry_run)
    run(pick_raw_dir(args.raw_dir), today, args.days, state, args.dry_run)

    if not args.dry_run:
        state["_format"] = 2
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
