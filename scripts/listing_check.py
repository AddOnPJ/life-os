#!/usr/bin/env python3
"""募集掲載の中身を PC から確認する（AI を使わない）。

クラウドからはジモティーの記事ページの古い保存版しか取れないため、
PC（ふつうの家庭のネット回線）から毎朝取りに行き、要点だけを JSON に残す。
本文そのものは保存しない（要点と、本文の指紋＝ハッシュだけ）。

使い方（PC の morning_sync.ps1 から呼ぶ）:
  python scripts/listing_check.py
出力:
  domains/addon/agent/obs/listings.json        いちばん新しい結果（毎回上書き）
  domains/addon/agent/obs/listings-YYYY-MM-DD.json  その日の結果
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "domains" / "addon" / "agent" / "obs"
JST = dt.timezone(dt.timedelta(hours=9))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

PAGES = {
    "jmty": "https://jmty.jp/osaka/com-ban/article-pgt61",
    "ensemblefan": "https://allegro.ensemble.fan/conbrio/gakudan/732",
    "site_recruit": "https://addon-pj.com/recruit/",
}
# 掲載にあってほしい語（なければ「ない」と記録するだけ。判断は AddOn エージェント）
EXPECT = ["ヴァイオリン", "ヴィオラ", "チェロ", "コントラバス", "クラリネット", "オーボエ",
          "ファゴット", "サックス", "フルート", "IXj1YW6BqZw", "SNS"]
AVOID = ["急募", "ボーカル"]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DATE_MD = re.compile(r"(\d{1,2})月(\d{1,2})日")
DATE_SLASH = re.compile(r"(20\d\d)[/年](\d{1,2})[/月](\d{1,2})")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "ja,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        enc = r.headers.get_content_charset() or "utf-8"
    return raw.decode(enc, errors="replace")


def to_text(h: str) -> str:
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", "\n", h)
    t = html.unescape(h)
    t = re.sub(r"[ \t　]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def after(label: str, text: str, n: int = 40) -> str | None:
    i = text.find(label)
    if i < 0:
        return None
    return text[i + len(label): i + len(label) + n].strip()


def summarize(name: str, text: str, today: dt.date) -> dict:
    out: dict = {"ok": True, "chars": len(text),
                 "fingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]}
    for label in ("更新日", "更新", "作成日"):
        v = after(label, text, 30)
        if v:
            m = DATE_SLASH.search(v) or DATE_MD.search(v)
            if m:
                out.setdefault("updated_text", f"{label} {m.group(0)}")
                break
    fav = re.search(r"お気に入り[^\d]{0,10}(\d+)", text)
    if fav:
        out["favorites"] = int(fav.group(1))
    if name == "jmty":
        for g in ("吹奏楽", "その他", "オーケストラ", "クラシック"):
            if f"> {g}" in text or f"\n{g}\n" in text:
                out.setdefault("genre_candidates", []).append(g)
    # 見学日らしい日付（今日より前の日付が残っていないか）
    dates = set()
    body = "\n".join(l for l in text.split("\n") if "更新" not in l and "作成" not in l and "掲載" not in l)
    for m in DATE_MD.finditer(body):
        mo, d = int(m.group(1)), int(m.group(2))
        year = today.year if mo >= today.month - 1 else today.year + 1
        try:
            dates.add(dt.date(year, mo, d))
        except ValueError:
            pass
    near = sorted(x for x in dates if -60 <= (x - today).days <= 180)
    out["dates_found"] = [x.isoformat() for x in near]
    out["past_dates"] = [x.isoformat() for x in near if x < today]
    emails = sorted(set(EMAIL.findall(text)))
    out["emails_in_body"] = len(emails)          # 何件あるかだけ（アドレスは残さない）
    out["has"] = {w: (w in text) for w in EXPECT}
    out["avoid_found"] = [w for w in AVOID if w in text]
    m = re.search(r"(\d{2})歳\s*[〜~～-]\s*(\d{2})歳", text)
    if m:
        out["age_range"] = f"{m.group(1)}-{m.group(2)}"
    return out


def main() -> int:
    now = dt.datetime.now(JST)
    today = now.date()
    result = {"checked_at": now.strftime("%Y-%m-%d %H:%M"), "from": "PC", "pages": {}}
    for name, url in PAGES.items():
        try:
            text = to_text(fetch(url))
            result["pages"][name] = {"url": url, **summarize(name, text, today)}
        except Exception as e:  # 取れなかったことも記録する
            result["pages"][name] = {"url": url, "ok": False, "error": type(e).__name__}
    OUT.mkdir(parents=True, exist_ok=True)
    body = json.dumps(result, ensure_ascii=False, indent=1)
    (OUT / "listings.json").write_text(body, encoding="utf-8")
    (OUT / f"listings-{today.isoformat()}.json").write_text(body, encoding="utf-8")
    for name, p in result["pages"].items():
        print(name, "OK" if p.get("ok") else "失敗", p.get("updated_text", ""), "過去日:", p.get("past_dates", ""),
              "メール:", p.get("emails_in_body", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
