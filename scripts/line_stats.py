"""LINE の「トーク履歴を送信／トークを保存」で書き出した .txt から、やりとりの傾向を数字で出す。

使い方（PC で。ファイルは secure/ の中に置く）:
    python scripts/line_stats.py secure/love/<苗字>/line/2026-11-18.txt --me 辻祐一
    python scripts/line_stats.py <file> --me 辻祐一 --days 60

出力は Markdown（自分／相手 の表記。名前は出さない）。secure の外に書き出さないこと。
対応形式：スマホ版（日付行 + 「時刻<TAB>名前<TAB>本文」）と PC 版（「時刻 名前 本文」）。形式が合わない場合はエラー行数を表示する。
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

DATE_RE = re.compile(r"^(\d{4})[/.](\d{1,2})[/.](\d{1,2})")
MSG_TAB = re.compile(r"^(午前|午後)?\s*(\d{1,2}):(\d{2})\t([^\t]+)\t?(.*)$")
MSG_SP = re.compile(r"^(\d{1,2}):(\d{2}) (\S+) (.*)$")
NEW_TALK_GAP = dt.timedelta(hours=6)
SPECIAL = ("[スタンプ]", "[写真]", "[動画]", "[ファイル]", "[ボイスメッセージ]", "[アルバム]", "☎")


def parse(path: Path):
    msgs, day, bad = [], None, 0
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    for raw in lines:
        line = raw.rstrip("\r")
        if not line.strip() or line.startswith("[LINE]") or line.startswith("保存日時"):
            continue
        m = DATE_RE.match(line)
        if m and not MSG_TAB.match(line):
            day = dt.date(int(m[1]), int(m[2]), int(m[3]))
            continue
        m = MSG_TAB.match(line)
        if m and day:
            h = int(m[2]) % 12 + (12 if m[1] == "午後" else 0) if m[1] else int(m[2])
            msgs.append({"t": dt.datetime.combine(day, dt.time(h, int(m[3]))), "who": m[4].strip(), "text": m[5].strip().strip('"')})
            continue
        m = MSG_SP.match(line)
        if m and day:
            msgs.append({"t": dt.datetime.combine(day, dt.time(int(m[1]), int(m[2]))), "who": m[3], "text": m[4]})
            continue
        if msgs:
            msgs[-1]["text"] += "\n" + line.strip().strip('"')
        else:
            bad += 1
    return msgs, bad


def summarize(msgs, me):
    out = {}
    for side in ("me", "them"):
        mine = [x for x in msgs if (x["who"] == me) == (side == "me")]
        texts = [x["text"] for x in mine if not x["text"].startswith(SPECIAL)]
        out[side] = {
            "count": len(mine),
            "avg_len": round(statistics.mean(len(t) for t in texts), 1) if texts else 0,
            "questions": sum(1 for t in texts if "?" in t or "？" in t),
            "stickers": sum(1 for x in mine if x["text"].startswith("[スタンプ]")),
            "photos": sum(1 for x in mine if x["text"].startswith(("[写真]", "[動画]"))),
            "exclaim": sum(1 for t in texts if "!" in t or "！" in t),
        }
    starts = Counter()
    replies = {"me": [], "them": []}
    prev = None
    for x in msgs:
        side = "me" if x["who"] == me else "them"
        if prev is None or x["t"] - prev["t"] >= NEW_TALK_GAP:
            starts[side] += 1
        elif (prev["who"] == me) != (side == "me"):
            replies[side].append((x["t"] - prev["t"]).total_seconds() / 60)
        prev = x
    for side in ("me", "them"):
        r = replies[side]
        out[side]["reply_median_min"] = round(statistics.median(r)) if r else None
        out[side]["starts"] = starts[side]
    hours = Counter(x["t"].hour for x in msgs if x["who"] != me)
    out["them_active_hours"] = [h for h, _ in hours.most_common(3)]
    return out


def table(title, s):
    q = lambda d: f"{d['questions']}（{round(100 * d['questions'] / d['count']) if d['count'] else 0}%）"
    r = lambda d: "—" if d["reply_median_min"] is None else f"{d['reply_median_min']}分"
    rows = [
        ("メッセージ数", s["me"]["count"], s["them"]["count"]),
        ("会話を始めた回数（6時間以上空いたあと）", s["me"]["starts"], s["them"]["starts"]),
        ("返信までの時間（中央値）", r(s["me"]), r(s["them"])),
        ("1通の平均文字数", s["me"]["avg_len"], s["them"]["avg_len"]),
        ("質問を含む通数", q(s["me"]), q(s["them"])),
        ("「！」を含む通数", s["me"]["exclaim"], s["them"]["exclaim"]),
        ("スタンプ", s["me"]["stickers"], s["them"]["stickers"]),
        ("写真・動画", s["me"]["photos"], s["them"]["photos"]),
    ]
    lines = [f"### {title}", "| | 自分 | 相手 |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    if s["them_active_hours"]:
        lines.append(f"\n相手が送ることが多い時間帯：{', '.join(f'{h}時台' for h in s['them_active_hours'])}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--me", required=True, help="LINE 上の自分の表示名")
    p.add_argument("--days", type=int, default=30, help="直近と比べる期間（日）")
    a = p.parse_args()
    msgs, bad = parse(Path(a.file))
    if not msgs:
        sys.exit(f"メッセージを読み取れませんでした（読めない行 {bad}）。形式を確認してください。")
    names = Counter(x["who"] for x in msgs)
    if a.me not in names:
        sys.exit(f"--me の名前が見つかりません。候補: {', '.join(names)}")
    end = msgs[-1]["t"]
    recent = [x for x in msgs if x["t"] > end - dt.timedelta(days=a.days)]
    before = [x for x in msgs if end - dt.timedelta(days=2 * a.days) < x["t"] <= end - dt.timedelta(days=a.days)]
    print(f"## LINE の傾向（{msgs[0]['t']:%Y-%m-%d} 〜 {end:%Y-%m-%d}、{len(msgs)}通）\n")
    print(table("全期間", summarize(msgs, a.me)))
    if recent:
        print("\n" + table(f"直近{a.days}日", summarize(recent, a.me)))
    if before:
        print("\n" + table(f"その前の{a.days}日", summarize(before, a.me)))
    if bad:
        print(f"\n（読めなかった行：{bad}）")


if __name__ == "__main__":
    main()
