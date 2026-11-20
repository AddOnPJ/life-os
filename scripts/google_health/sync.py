"""Google Health API から Pixel Watch / Google Health のデータを取得して life-os に保存する（v1）。

使い方（life-os のルートで）:
    python scripts/google_health/sync.py auth          # 初回と、トークンが切れたとき
    python scripts/google_health/sync.py fetch --days 3
    python scripts/google_health/sync.py check          # トークンが生きているかだけ確かめる

取りこぼしの埋め方（2026-11-20〜）:
- 前回うまく取れた日を secure/health/.sync_state.json に残し、次の fetch はその日から今日までを取る
  （--days より長ければそちらを優先）。初めてのときは FIRST_DAYS 日分さかのぼる
- dailyRollUp は種別ごとに1回で取れる日数に上限があるので、長い期間は区切って取りつなぐ
- 1件ずつの種別は、取りたい期間の最初の日より古いデータが出るまでページをめくる（上限 LIST_PAGE_CAP）
- 取った期間は生データのフォルダの _meta.json に書き、summarize.py がその期間を日次ログに反映する

保存先（すべて secure/ 配下＝GitHub に上がらない）:
    secure/google_health/client_secret.json   … Google Cloud で作った OAuth クライアント
    secure/google_health/token.json           … 取得したトークン
    secure/health/raw/YYYY-MM-DD/<type>.json  … 取得した生データ

v1 は「取得して生データを保存する」まで。日次ログへの集計は、実データの形を見てから
Claude Code で scripts/google_health/summarize.py を作る（docs/google-health.md 参照）。

API の仕様で未確認の点（要確認）:
- CivilDateTime の JSON 形（ここでは {"date": {...}, "time": {...}} と仮定）
- dataPoints.list の filter 書式（データ種別ごとに違う可能性。v1 は filter なしで最新ページだけ取る）
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CRED_DIR = ROOT / "secure" / "google_health"
CLIENT_FILE = CRED_DIR / "client_secret.json"
TOKEN_FILE = CRED_DIR / "token.json"
RAW_DIR = ROOT / "secure" / "health" / "raw"
STATE_FILE = ROOT / "secure" / "health" / ".sync_state.json"
FIRST_DAYS = 35        # 初回にさかのぼる日数（28日平均がすぐ出るように）
MAX_BACK_DAYS = 90     # 1回でさかのぼる最大日数

API = "https://health.googleapis.com/v4"
REDIRECT_URI = "https://www.google.com"
SCOPE_PREFIX = "https://www.googleapis.com/auth/googlehealth."
SCOPES = [
    SCOPE_PREFIX + "activity_and_fitness.readonly",
    SCOPE_PREFIX + "health_metrics_and_measurements.readonly",
    SCOPE_PREFIX + "sleep.readonly",
]

# dailyRollUp が使える種別（日ごとの合計など）。heart-rate などは最大14日。
ROLLUP_TYPES = {
    "steps": 90,
    "distance": 90,
    "total-calories": 14,
    "active-minutes": 14,
    "heart-rate": 14,
}
# 1件ずつのデータとして取る種別
LIST_TYPES = [
    "sleep",
    "exercise",
    "daily-resting-heart-rate",
    "daily-heart-rate-variability",
    "daily-oxygen-saturation",
    "weight",
]
LIST_MAX_PAGES = 2       # 短い期間（3日以内）のとき
LIST_PAGE_CAP = 40       # 長い期間のときの上限

JST = dt.timezone(dt.timedelta(hours=9))


def load_client() -> dict:
    if not CLIENT_FILE.exists():
        sys.exit(f"{CLIENT_FILE} がありません。docs/google-health.md の手順で作成してください。")
    data = json.loads(CLIENT_FILE.read_text(encoding="utf-8"))
    return data.get("web") or data.get("installed") or data


def http(method: str, url: str, *, data: bytes | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {url}\n{body}") from None


def cmd_auth(_: argparse.Namespace) -> None:
    client = load_client()
    params = {
        "client_id": client["client_id"],
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "scope": " ".join(SCOPES),
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    print("1. 次の URL をブラウザで開き、Google アカウントで許可してください。")
    print("   「このアプリは確認されていません」と出たら「続行」を選びます。\n")
    print(url + "\n")
    print("2. 許可後 https://www.google.com/?code=... に移動します。")
    pasted = input("   そのアドレスバーの URL 全体（または code= の値）を貼り付けて Enter: ").strip()
    if "code=" in pasted:
        pasted = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)["code"][0]
    body = urllib.parse.urlencode({
        "code": pasted,
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    token = http("POST", "https://oauth2.googleapis.com/token", data=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    save_token(token)
    print("トークンを保存しました:", TOKEN_FILE)


def save_token(token: dict) -> None:
    CRED_DIR.mkdir(parents=True, exist_ok=True)
    old = json.loads(TOKEN_FILE.read_text(encoding="utf-8")) if TOKEN_FILE.exists() else {}
    if "refresh_token" not in token and "refresh_token" in old:
        token["refresh_token"] = old["refresh_token"]
    token["saved_at"] = dt.datetime.now(JST).isoformat()
    TOKEN_FILE.write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding="utf-8")


def access_token() -> str:
    if not TOKEN_FILE.exists():
        sys.exit("トークンがありません。先に `python scripts/google_health/sync.py auth` を実行してください。")
    client = load_client()
    token = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    body = urllib.parse.urlencode({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": token["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    try:
        new = http("POST", "https://oauth2.googleapis.com/token", data=body,
                   headers={"Content-Type": "application/x-www-form-urlencoded"})
    except RuntimeError as e:
        sys.exit(f"トークンの更新に失敗しました。`auth` をやり直してください。\n{e}")
    save_token({**token, **new})
    return new["access_token"]


def civil(d: dt.date) -> dict:
    # 要確認: CivilDateTime の形
    return {"date": {"year": d.year, "month": d.month, "day": d.day},
            "time": {"hours": 0, "minutes": 0, "seconds": 0}}


def save_raw(day: dt.date, name: str, data: dict) -> Path:
    out = RAW_DIR / day.isoformat() / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def point_date(p: dict) -> dt.date | None:
    """1件のデータの日付（日本時間）。形がわからなければ None。"""
    if not p:
        return None
    v = next(iter(p.values())) if len(p) == 1 else p
    if not isinstance(v, dict):
        return None
    try:
        if "interval" in v:
            t = v["interval"].get("endTime") or v["interval"].get("startTime")
            return dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(JST).date()
        if "date" in v and isinstance(v["date"], dict):
            c = v["date"]
            return dt.date(c["year"], c["month"], c["day"])
        if "sampleTime" in v:
            c = v["sampleTime"]["civilTime"]["date"]
            return dt.date(c["year"], c["month"], c["day"])
    except (KeyError, TypeError, ValueError):
        return None
    return None


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}


def fetch_days(today: dt.date, asked: int) -> int:
    last = load_state().get("last_ok")
    if not last:
        return max(asked, FIRST_DAYS)
    gap = (today - dt.date.fromisoformat(last)).days + 2   # 前回の日も取り直す（途中までだったため）
    return min(max(asked, gap), MAX_BACK_DAYS)


def cmd_check(_: argparse.Namespace) -> None:
    access_token()
    tok = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    print("トークンは有効です。保存:", tok.get("saved_at", "不明"))


def cmd_fetch(args: argparse.Namespace) -> None:
    tok = access_token()
    auth = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
    today = dt.datetime.now(JST).date()
    days = fetch_days(today, args.days)
    start = today - dt.timedelta(days=days - 1)
    print(f"期間: {start} 〜 {today}（{days}日）")
    errors = []

    for dtype, max_days in ROLLUP_TYPES.items():
        points, s0 = [], start
        try:
            while s0 <= today:
                e0 = min(today, s0 + dt.timedelta(days=max_days - 1))
                body = {"range": {"start": civil(s0), "end": civil(e0 + dt.timedelta(days=1))},
                        "windowSizeDays": 1}
                url = f"{API}/users/me/dataTypes/{dtype}/dataPoints:dailyRollUp"
                res = http("POST", url, data=json.dumps(body).encode(),
                           headers={**auth, "Content-Type": "application/json"})
                points += res.get("rollupDataPoints", [])
                s0 = e0 + dt.timedelta(days=1)
            print("OK  ", save_raw(today, f"rollup_{dtype}", {"rollupDataPoints": points}))
        except RuntimeError as e:
            errors.append(str(e))
            print("NG  ", dtype)

    cap = LIST_MAX_PAGES if days <= 3 else LIST_PAGE_CAP
    for dtype in LIST_TYPES:
        pages, token = [], None
        try:
            for _ in range(cap):
                q = {"pageToken": token} if token else {}
                url = f"{API}/users/me/dataTypes/{dtype}/dataPoints"
                if q:
                    url += "?" + urllib.parse.urlencode(q)
                res = http("GET", url, headers=auth)
                pages.append(res)
                token = res.get("nextPageToken")
                if not token:
                    break
                ds = [d for d in (point_date(p) for p in res.get("dataPoints", [])) if d]
                if ds and min(ds) < start:   # 取りたい期間より古いところまで来た
                    break
            print("OK  ", save_raw(today, f"list_{dtype}", {"pages": pages}))
        except RuntimeError as e:
            errors.append(str(e))
            print("NG  ", dtype)

    save_raw(today, "_meta", {"start": start.isoformat(), "end": today.isoformat(),
                              "fetched_at": dt.datetime.now(JST).isoformat()})
    if errors:
        log = save_raw(today, "_errors", {"errors": errors})
        print(f"\n失敗 {len(errors)} 件。内容: {log}")
        sys.exit(1)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_ok": today.isoformat()}, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Google Health API → life-os")
    sub = p.add_subparsers(required=True)
    sub.add_parser("auth").set_defaults(func=cmd_auth)
    sub.add_parser("check").set_defaults(func=cmd_check)
    f = sub.add_parser("fetch")
    f.add_argument("--days", type=int, default=3)
    f.set_defaults(func=cmd_fetch)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
