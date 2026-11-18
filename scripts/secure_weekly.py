#!/usr/bin/env python3
"""PC の中だけで動く「詳しい健康とお金」のまとめと画面（AI を使わない）。

読むもの（どれも secure/ の中。GitHub には上がらない）:
  secure/health/YYYY-MM-DD.md   summarize.py が書く Google Health の詳細
  secure/money/YYYY-MM.md       「- YYYY-MM-DD 支出 1200 内容 #分類」の行（あれば）
書くもの（secure/ の中だけ）:
  secure/dashboard.html          PC のブラウザで開く画面（毎朝作り直す）
  secure/weekly/YYYY-Www.md      その週のまとめ
外には何も送らない。印刷するのは「書いた」という1行だけ。
"""
from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEC = ROOT / "secure"
JST = dt.timezone(dt.timedelta(hours=9))
MARK = re.compile(r"<!-- google-health:start -->(.*?)<!-- google-health:end -->", re.S)
NUM = re.compile(r"(-?\d+(?:\.\d+)?)")


def first(v: str, pat: str | None = None) -> float | None:
    if pat:
        m = re.search(pat, v)
        return float(m.group(1)) if m else None
    m = NUM.search(v)
    return float(m.group(1)) if m else None


def health_day(day: dt.date) -> dict:
    f = SEC / "health" / f"{day.isoformat()}.md"
    if not f.exists():
        return {}
    m = MARK.search(f.read_text(encoding="utf-8"))
    if not m:
        return {}
    kv = {}
    for ln in m.group(1).strip().splitlines():
        k, _, v = ln.removeprefix("- ").partition(": ")
        kv[k.strip()] = v.strip()
    r = {"date": day.isoformat()}
    if "安静時心拍" in kv: r["rhr"] = first(kv["安静時心拍"])
    if "HRV" in kv: r["hrv"] = first(kv["HRV"], r"平均\s*(-?\d+(?:\.\d+)?)")
    if "SpO2" in kv: r["spo2"] = first(kv["SpO2"], r"平均\s*(-?\d+(?:\.\d+)?)")
    if "体重" in kv: r["weight"] = first(kv["体重"])
    if "心拍(日)" in kv: r["hr_avg"] = first(kv["心拍(日)"], r"平均\s*(\d+)")
    if "睡眠(主)" in kv:
        s = kv["睡眠(主)"]
        r["sleep_main"] = first(s, r"睡眠\s*(\d+)分")
        r["deep"] = first(s, r"深\s*(\d+)")
        r["rem"] = first(s, r"REM\s*(\d+)")
        r["sleep_window"] = s.split("／")[0]
    naps = [first(v, r"睡眠\s*(\d+)分") for k, v in kv.items() if k.startswith("睡眠(昼寝")]
    naps = [n for n in naps if n]
    r["naps"] = len(naps)
    r["sleep_total"] = (r.get("sleep_main") or 0) + sum(naps) if ("sleep_main" in r or naps) else None
    r["nap_windows"] = [v.split("／")[0] for k, v in kv.items() if k.startswith("睡眠(昼寝")]
    return r


def money_month(ym: str) -> dict:
    f = SEC / "money" / f"{ym}.md"
    out = {"支出": 0, "収入": 0, "分類": {}}
    if not f.exists():
        return {}
    for ln in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- (\d{4}-\d{2}-\d{2})\s+(支出|収入)\s+([\d,]+)\s+(.*?)(?:\s+#(\S+))?$", ln.strip())
        if not m:
            continue
        amt = int(m.group(3).replace(",", ""))
        out[m.group(2)] += amt
        if m.group(2) == "支出":
            c = m.group(5) or "その他"
            out["分類"][c] = out["分類"].get(c, 0) + amt
    return out


def avg(rows, k):
    v = [r[k] for r in rows if r.get(k) is not None]
    return round(statistics.mean(v), 1) if v else None


def spark(rows, k, w=280, h=60, color="#23467e"):
    pts = [(i, r[k]) for i, r in enumerate(rows) if r.get(k) is not None]
    if len(pts) < 2:
        return '<span class="muted">データ不足</span>'
    lo, hi = min(p[1] for p in pts), max(p[1] for p in pts)
    span = (hi - lo) or 1
    n = len(rows) - 1 or 1
    xy = " ".join(f"{4 + i / n * (w - 8):.1f},{h - 6 - (v - lo) / span * (h - 12):.1f}" for i, v in pts)
    lx, ly = xy.split(" ")[-1].split(",")
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}"><polyline fill="none" stroke="{color}" stroke-width="2" points="{xy}"/>'
            f'<circle cx="{lx}" cy="{ly}" r="3" fill="{color}"/><text x="4" y="10" font-size="10" fill="#5d6676">{hi:g}</text>'
            f'<text x="4" y="{h - 1}" font-size="10" fill="#5d6676">{lo:g}</text></svg>')


def main() -> int:
    today = dt.datetime.now(JST).date()
    days = [today - dt.timedelta(days=i) for i in range(28, 0, -1)]
    rows = [health_day(d) or {"date": d.isoformat()} for d in days]
    last7, prev = rows[-7:], rows[:-7]
    metrics = [("sleep_total", "睡眠（主＋昼寝）", "分"), ("sleep_main", "睡眠（主）", "分"), ("deep", "深い睡眠", "分"),
               ("rhr", "安静時心拍", "bpm"), ("hrv", "HRV", "ms"), ("spo2", "SpO2", "%"), ("weight", "体重", "kg")]
    table = []
    for k, label, unit in metrics:
        a7, a21 = avg(last7, k), avg(prev, k)
        diff = round(a7 - a21, 1) if a7 is not None and a21 is not None else None
        table.append((label, unit, a7, a21, diff, spark(rows, k)))
    ym = today.strftime("%Y-%m")
    money = money_month(ym)

    iso = today.isocalendar()
    wk = SEC / "weekly" / f"{iso.year}-W{iso.week:02d}.md"
    wk.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {iso.year}-W{iso.week:02d} 詳しい健康とお金（PC の中だけ）", "", f"作成 {today.isoformat()}", "",
             "| 項目 | 直近7日 | その前の21日 | 差 |", "|---|---|---|---|"]
    for label, unit, a7, a21, diff, _ in table:
        lines.append(f"| {label} | {a7 if a7 is not None else '—'} {unit} | {a21 if a21 is not None else '—'} {unit} | {diff if diff is not None else '—'} |")
    lines += ["", "睡眠の区切り（直近7日。主な睡眠が短い日は、夜の睡眠が分かれて記録されていないか確認）"]
    for r in last7:
        if r.get("sleep_window") or r.get("nap_windows"):
            lines.append(f"- {r['date'][5:]} 主 {r.get('sleep_window', '—')}・{int(r.get('sleep_main') or 0)}分" +
                         (f"／ほか {'、'.join(r['nap_windows'])}" if r.get("nap_windows") else ""))
    if money:
        lines += ["", f"## お金（{ym}）", f"- 支出 {money['支出']:,} 円／収入 {money['収入']:,} 円"]
        lines += [f"- {c} {v:,} 円" for c, v in sorted(money["分類"].items(), key=lambda x: -x[1])]
    lines += ["", "健康については記録と傾向の整理まで。診断はしない。"]
    wk.write_text("\n".join(lines) + "\n", encoding="utf-8")

    esc = html.escape
    trs = "".join(f"<tr><td>{esc(l)}</td><td class=n>{'' if a is None else a} {u}</td><td class=n>{'' if b is None else b} {u}</td>"
                  f"<td class=n>{'' if d is None else ('+' if d > 0 else '') + str(d)}</td><td>{s}</td></tr>" for l, u, a, b, d, s in table)
    sleep_rows = "".join(f"<tr><td>{r['date'][5:]}</td><td>{esc(r.get('sleep_window', '—'))}</td><td class=n>{int(r.get('sleep_main') or 0)}</td>"
                         f"<td>{esc('、'.join(r.get('nap_windows') or []))}</td></tr>" for r in last7)
    money_html = ""
    if money:
        cats = "".join(f"<tr><td>{esc(c)}</td><td class=n>{v:,} 円</td></tr>" for c, v in sorted(money["分類"].items(), key=lambda x: -x[1]))
        money_html = f"<section><h2>お金 {ym}</h2><p>支出 <b>{money['支出']:,}</b> 円／収入 <b>{money['収入']:,}</b> 円</p><table>{cats}</table></section>"
    else:
        money_html = "<section><h2>お金</h2><p class=muted>secure/money/ にまだ記録がありません。スマホから「記録 支出 1200 昼ごはん」と送ると、暗号化して届きます。</p></section>"
    page = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>life-os 詳細（PC の中だけ）</title><style>
:root{{--bg:#f4f5f2;--paper:#fff;--ink:#1d2433;--muted:#5d6676;--line:#dfe2e6;--accent:#23467e}}
@media (prefers-color-scheme:dark){{:root{{--bg:#12161f;--paper:#1a202c;--ink:#e7eaf0;--muted:#9aa3b2;--line:#2c3443;--accent:#8fb0ea}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Zen Kaku Gothic New","Yu Gothic UI","Meiryo",sans-serif;font-size:15px;line-height:1.6}}
main{{max-width:1100px;margin:0 auto;padding:16px;display:grid;gap:16px}}
section{{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow-x:auto}}
h1{{font-size:20px;margin:16px auto 0;max-width:1100px;padding:0 16px}} h2{{font-size:16px;margin:0 0 8px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:middle}}
.n{{font-variant-numeric:tabular-nums;white-space:nowrap}} .muted{{color:var(--muted);font-size:13px}} svg polyline{{stroke:var(--accent)}} svg circle{{fill:var(--accent)}}
</style></head><body><h1>life-os 詳細（PC の中だけ）</h1><main>
<p class=muted>作成 {today.isoformat()}。このファイルは PC の secure/ にだけあり、GitHub やクラウドには送られません。健康は記録と傾向の整理までで、診断はしません。</p>
<section><h2>体（直近7日とその前の21日）</h2><table><tr><th>項目</th><th>直近7日</th><th>その前</th><th>差</th><th>28日</th></tr>{trs}</table></section>
<section><h2>睡眠の区切り（直近7日）</h2><p class=muted>主な睡眠が短い日は、夜の睡眠がいくつかに分かれて「昼寝」として数えられていないか確認してください。</p>
<table><tr><th>日</th><th>主な睡眠</th><th>分</th><th>ほかの睡眠</th></tr>{sleep_rows}</table></section>
{money_html}
<section><h2>恋愛</h2><p class=muted>恋愛の記録は別の非公開リポジトリ love-coach と、Claude の「恋愛コーチ」プロジェクトにあります。</p></section>
</main></body></html>"""
    (SEC / "dashboard.html").write_text(page, encoding="utf-8")
    print("secure/dashboard.html と secure/weekly を更新しました")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("secure_weekly.py 失敗:", type(e).__name__)
        sys.exit(1)
