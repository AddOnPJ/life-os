#!/usr/bin/env python3
"""AddOn の YouTube チャンネルの数字を取る（YouTube Data API v3、AI を使わない）。

鍵は環境変数 YOUTUBE_API_KEY か、リポジトリ直下の .env（`YOUTUBE_API_KEY=...`）から読む。.env はコミットしない。
1回の実行で使う枠は 3〜5 ユニット（無料枠は 1日 10,000）。

出力:
  domains/addon/agent/obs/youtube.json            いちばん新しい結果
  domains/addon/agent/obs/youtube-YYYY-MM-DD.json その日の結果（前の週と比べるのに使う）
使い方:
  python scripts/youtube_stats.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "domains" / "addon" / "agent" / "obs"
JST = dt.timezone(dt.timedelta(hours=9))
HANDLE = "addonensemble"
API = "https://www.googleapis.com/youtube/v3/"


def api_key() -> str | None:
    k = os.environ.get("YOUTUBE_API_KEY")
    if k:
        return k.strip()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("YOUTUBE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def get(path: str, key: str, **params) -> dict:
    params["key"] = key
    url = API + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    key = api_key()
    if not key:
        print("YOUTUBE_API_KEY がないので取得しません（.env に書くと動きます）")
        return 0
    now = dt.datetime.now(JST)
    ch = get("channels", key, part="statistics,contentDetails,snippet", forHandle=HANDLE)
    if not ch.get("items"):
        print("チャンネルが見つかりません")
        return 1
    c = ch["items"][0]
    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
        if token:
            params["pageToken"] = token
        pl = get("playlistItems", key, **params)
        ids += [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
        token = pl.get("nextPageToken")
        if not token or len(ids) >= 200:
            break
    videos = []
    for i in range(0, len(ids), 50):
        vs = get("videos", key, part="statistics,snippet", id=",".join(ids[i:i + 50]))
        for v in vs.get("items", []):
            s = v.get("statistics", {})
            videos.append({
                "id": v["id"],
                "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"][:10],
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)) if "likeCount" in s else None,
                "comments": int(s.get("commentCount", 0)) if "commentCount" in s else None,
            })
    videos.sort(key=lambda v: -v["views"])
    st = c["statistics"]
    out = {
        "checked_at": now.strftime("%Y-%m-%d %H:%M"),
        "channel": c["snippet"]["title"],
        "subscribers": int(st.get("subscriberCount", 0)) if not st.get("hiddenSubscriberCount") else None,
        "views": int(st.get("viewCount", 0)),
        "videos": int(st.get("videoCount", 0)),
        "items": videos,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    body = json.dumps(out, ensure_ascii=False, indent=1)
    (OUT / "youtube.json").write_text(body, encoding="utf-8")
    (OUT / f"youtube-{now.date().isoformat()}.json").write_text(body, encoding="utf-8")
    print(f"YouTube: 登録者 {out['subscribers']} / 再生 {out['views']} / 動画 {out['videos']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 取得失敗で朝の同期を止めない
        print("youtube_stats.py 失敗:", type(e).__name__, e)
        sys.exit(1)
