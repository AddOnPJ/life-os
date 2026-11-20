# life-os — Claude Code 向けルール

辻 祐一（Yuichi）の個人用ライフマネジメント基盤。このリポジトリがすべての記録の唯一の正本。

## 目的
スケジュール・食事・運動・AddOnアンサンブル運営・人間関係などを、
複数のAI（Claude Code / Antigravity / Cursor / Grok Bot）から扱える形で管理する。

## フォルダ
- `inbox/` … スマホなどからの雑な入力。処理済みは `inbox/done/` へ移す
- `logs/daily/` … 日次ログ `YYYY-MM-DD.md`
- `domains/schedule/` … 予定の振り返り（予定そのものの正本は Google カレンダー）
- `domains/food/` … 食事記録・好み・レシピ
- `domains/fitness/` … 運動・睡眠・体重など
- `domains/health/` … 体調・通院・薬・検査結果（2026-11-20 から通常の記録）
- `domains/addon/` … AddOn アンサンブル運営
- `domains/people/` … 人間関係（本人に見られても困らない範囲だけ）
- `secure/` … PC の中だけに置くもの（Google Health の元データ。お金の記録は停止中）。GitHub に上げない
- 恋愛 … 別の非公開リポジトリ `AddOnPJ/love-coach` が正本（Yuichi が決めた例外）。life-os には書かない
- `secure-inbox/` … スマホ・クラウドから送った機微メモの暗号文（`.age`）。公開鍵 `keys/age-public.txt` で暗号化、PC の秘密鍵で復号（`scripts/secure_note.py`）
- `reviews/weekly/` … 週次振り返り
- `status/` … 生活全体の現状まとめ（`now.md`、毎朝自動）と承認待ち（`approvals.md`）
- `templates/` … 日次ログなどのひな形
- `scripts/` … 集計・同期スクリプト
- `.claude/skills/` … 定型作業のスキル

## 書き方
- 本文は Markdown、日付・タグ・数値は YAML front matter に書く
- ファイル名の日付は `YYYY-MM-DD` 形式（日本時間）
- 確認できない情報は推測で埋めず「要確認」と書く
- Yuichi が書いた文章は言い回しを直さない。直すのは誤字・事実誤り・リンク切れなど壊れている箇所だけ
- 装飾的な言葉や励ましの文は足さない

## 機微情報
- 健康の情報（体の数字・体調・通院・薬・検査結果）は通常の記録として扱う（2026-11-20 Yuichi が決定）。数字は日次ログ、体調などは `domains/health/`
- お金の記録は当面扱わない（2026-11-20 停止）。相談には答えるが、金額や口座のことは記録しない
- `secure/` 配下の内容を、要約も含めてほかのフォルダや外部サービスに書き出さない
- 恋愛の内容は `AddOnPJ/love-coach` に書く（life-os の日次ログには何も書かない）
- 他人（恋愛の相手を含む）の連絡先・住所・本人が人に話していないこと、他人の健康の話は記録しない。恋愛の相手は苗字だけで書く
- 健康については記録と傾向の整理、生活の工夫の提案まで。診断や治療の判断はしない（手順は `.claude/skills/health-coach/`）

## 進め方
- 作業前に計画を出し、Yuichi の確認を取ってから実行する
- ファイル削除は確認を取ってから
- API キー・トークンはコミットしない（`.env` は .gitignore 済み）
- API を使う機能は、Claude Max の API 特典（月100ドル）と Google Cloud 特典（月40ドル）の範囲内に収める
