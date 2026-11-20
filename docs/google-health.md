# Google Health（Pixel Watch 4）連携

Google Health API から歩数・睡眠・心拍・運動などを取得し、life-os に入れる。PC 上で動かす（費用なし）。

## 流れ

1. `scripts/google_health/sync.py fetch` が API から取得 → `secure/health/raw/` に生データ保存
2. `summarize.py` が生データを集計 → 日次ログの front matter と「運動・体調」へ（歩数・睡眠・就寝/起床・睡眠の内訳・安静時心拍・HRV・SpO2・体重・運動）。2026-11-20 から健康の数字は通常の記録。生データは大きいので `secure/health/raw/` に置いたまま GitHub には上げない
3. Windows のタスクスケジューラで毎朝実行

## 1. Google Cloud の準備（PC のブラウザで1回だけ）

1. Google Cloud コンソールでプロジェクトを作る（例: `life-os`）
2. 「API とサービス」→「ライブラリ」で **Google Health API** を有効化
3. 「OAuth 同意画面」（Google Auth Platform）
   - ユーザーの種類: **外部**、公開ステータス: **テスト**
   - 「テストユーザー」に Pixel Watch で使っている Google アカウントを追加
4. 「認証情報」→「OAuth クライアント ID を作成」
   - 種類: **ウェブアプリケーション**
   - 承認済みのリダイレクト URI: `https://www.google.com`
5. JSON をダウンロードし、`secure/google_health/client_secret.json` として保存
   （`secure/` は .gitignore 済み。GitHub には上がらない）

## 2. 初回認証

```
cd $HOME\claude-work\life-os
python scripts/google_health/sync.py auth
```

表示された URL を開いて許可 → 移動先 `https://www.google.com/?code=...` の URL を貼り付け。

## 3. 取得テスト

```
python scripts/google_health/sync.py fetch --days 3
```

`OK` / `NG` が種別ごとに出る。NG があれば `secure/health/raw/<今日>/_errors.json` を Claude Code に読ませて直す。

## 4. Claude Code に頼むこと（プロンプト）

```
scripts/google_health/sync.py fetch --days 3 を実行し、結果を確認してください。
- NG があれば _errors.json を読み、Google Health API の公式リファレンス
  （https://developers.google.com/health/reference/rest）を確認して sync.py を修正
- 全部 OK になったら、secure/health/raw/ の実データの形を見て
  scripts/google_health/summarize.py を作る:
  - 歩数・距離・消費カロリー・睡眠時間・運動（種類と時間）は logs/daily/YYYY-MM-DD.md の
    front matter（steps, sleep_hours, exercise など）と「運動・体調」セクションへ
  - 心拍・HRV・SpO2・体重などの細かい数値は secure/health/YYYY-MM-DD.md へ
  - 既にある値は上書きせず、違っていれば「要確認」に書く
- 最後に、毎朝 6:30 に fetch → summarize を実行する Windows タスクスケジューラの登録手順を出す
  （登録は私の確認後）
```

## 注意（要確認）

- 公開ステータスが「テスト」の OAuth アプリは、リフレッシュトークンが約7日で切れる
  （Google の OAuth の仕様）。切れたら `auth` をやり直す。週1回の手間が気になる場合は別の方法を検討する
- API スコープは「制限付き」。テストユーザー本人のデータを読むだけなら審査なしで使える想定だが、実際に通るかは初回認証で確認
- `sync.py` の CivilDateTime の形と、一覧取得の filter 書式は未確認（v1 は filter なし）


## 7日で認証が切れないようにする（2026-11-19 追記）
「テスト中」のアプリでは、テストユーザーの認証は同意から7日で切れ、更新用トークンも無効になる（Google Cloud のヘルプ）。毎週やり直さずに済むよう、一度だけ次をする。
1. PC かスマホのブラウザで Google Cloud コンソール → 健康データ用のプロジェクト → 「Google Auth Platform」（または「OAuth 同意画面」）→「対象」
2. 公開ステータスの「アプリを公開」→「本番環境」に変える（Google の審査は申請しなくてよい。自分だけが使うので、未確認アプリの注意画面が出るだけ）
3. PC の PowerShell で `cd C:\Users\ytytc\claude-work\life-os` → `python scripts/google_health/sync.py auth`。ブラウザで「このアプリは Google で確認されていません」と出たら「詳細」→「（安全ではないページ）に移動」で進めて許可
4. 翌朝 6:10 の同期が動けば完了（司令室の「仕組み」に PC の同期の時刻が出る）

## YouTube の数字を毎朝取る（S16、2026-11-19 追記）
1. Google Cloud コンソール（健康データと同じプロジェクトでよい）→「API とサービス」→「ライブラリ」→「YouTube Data API v3」→ 有効にする
2. 「認証情報」→「認証情報を作成」→「API キー」。できたキーの「キーを制限」で、API の制限を「YouTube Data API v3」だけにする
3. PC の `C:\Users\ytytc\claude-work\life-os\.env` に1行足す（ファイルがなければメモ帳で作る）：`YOUTUBE_API_KEY=作ったキー`
4. 翌朝の同期から、司令室の「YouTube」に登録者数と曲ごとの再生数が出る（使う枠は1日 5 ユニット程度。無料枠は 10,000）

## 取りこぼしを埋める（2026-11-20 追記）
- `sync.py fetch` は前回うまく取れた日（`secure/health/.sync_state.json`）から今日までをまとめて取る。PC が何日か止まっていても、次に動いたときに埋まる（最大90日）
- 初めてこの形で動くときは35日分さかのぼる（28日平均がすぐ出るように）
- 心拍などの「1回で14日まで」の種別は区切って取りつなぐ。睡眠などの1件ずつの種別は、期間の最初の日より古いデータが出るまでページをめくる
- 取った期間は生データのフォルダの `_meta.json` に残り、`summarize.py` がその期間を日次ログに反映する
- 認証が生きているかだけ確かめる：`python scripts/google_health/sync.py check`
