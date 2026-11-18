# Google Health（Pixel Watch 4）連携

Google Health API から歩数・睡眠・心拍・運動などを取得し、life-os に入れる。PC 上で動かす（費用なし）。

## 流れ

1. `scripts/google_health/sync.py fetch` が API から取得 → `secure/health/raw/` に生データ保存
2. Claude Code が生データを集計 → 日次ログ（歩数・睡眠時間・運動）と `secure/`（心拍など細かい数値）へ
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
