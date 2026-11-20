---
name: secure-log
description: PC で、暗号化された機微メモ（恋愛・お金・健康の詳細）を復号して secure/ に整理し、傾向を分析する。「secure を処理して」「恋愛の振り返り」「お金のまとめ」「◯◯さんとのこと整理して」と言われたときに使う。PC でのみ使える。
---

# 機微情報の記録と分析（PC 専用）

> 2026-11-20 から、健康は通常の記録（`domains/health/`・日次ログ、手順は health-coach）、お金の記録は停止中。
> このスキルを使うのは、`secure-inbox/` に以前の暗号メモ（`.age`）が残っているときだけ。health の古いメモは `domains/health/log.md` に移してよい。

`secure/` は GitHub に上がらない（.gitignore 済み）。ここに書いた内容は、要約も含めて secure の外や外部サービスに出さない。

## 0. 前提
- この PC に秘密鍵 `secure/keys/age-identity.txt` があること。なければ `python scripts/secure_note.py keygen`（初回のみ）
- クラウド（スマホの Claude Code、定期実行）ではこのスキルは使わない

## 1. 取り込み
1. `python scripts/secure_note.py decrypt` → `secure/inbox/*.md` に平文が出る。消えた `.age` は `git rm` してコミットする（中身は secure に移っている）
2. `secure/inbox/` の各メモを `kind` で振り分けて追記し、処理したメモは `secure/inbox/done/` に移す

| kind | 保存先 |
|---|---|
| love | life-os には置かない。`AddOnPJ/love-coach` の `secure/love/profiles/苗字/記録.md` の先頭に追記（PC に clone がなければ Yuichi に伝える） |
| money | `secure/money/YYYY-MM.md` |
| health | `secure/health/YYYY-MM-DD.md` |
| other | `secure/notes/YYYY-MM-DD.md` |

## 2. 恋愛

恋愛の正本は非公開リポジトリ `AddOnPJ/love-coach`（運用ルールはそのリポジトリの `secure/love/README.md`）。以下は記録の書き方の参考。

記録のルール
- 相手は**苗字だけ**。下の名前・連絡先・住所・勤務先・SNS アカウント・家族の情報は書かない
- 相手が他の人に話していない秘密は書かない
- それ以外の出来事・会話の話題・Yuichi の気持ちは、分析に使うので Yuichi の言葉のまま残す

相手メモ.md の形
```
---
name: 苗字
first_met: YYYY-MM-DD   # わかれば
status: 知り合い / 気になる / やりとり中 / デート中 / 付き合っている / 終わった
---
## 出来事（新しい順）
- YYYY-MM-DD 会った・連絡・話題・相手の反応・自分の気持ち（Yuichi の言葉のまま）

## 相手が好きなこと・話して盛り上がったこと
## 次にしたいこと（Yuichi が書く）
```

LINE の読み取りや返信の相談は `love-coach` スキルを使う。

分析（頼まれたとき、または月1回）
- 連絡や会う頻度の推移、盛り上がった話題、Yuichi の気持ちの変化を、記録の件数つきで示す
- 次の一手は**提案**として出す。相手をコントロールする・操作する類の助言はしない。相手の気持ちを断定しない（「記録からは◯◯が多い」の言い方にとどめる）

## 3. お金（secure/money/YYYY-MM.md）

記録のルール
- 口座番号・カード番号・暗証番号・ログイン情報は絶対に書かない（「楽天カード」程度の名前まで）
- 1行1件：`- YYYY-MM-DD 支出/収入 金額 内容 #分類`（分類：食費・交通・AddOn・サブスク・機材・交際・その他）

分析（月末、または頼まれたとき）
- 分類ごとの合計、前月比、AddOn に使った額、サブスクの合計
- 気になる増減を3つまで。投資や借入の判断は助言しない（事実の整理まで）

## 4. 健康（secure/health/）
- 症状・通院・薬・検査値・血圧など。記録と推移の整理まで。診断や治療の判断はしない
- 気になる値が続く場合は「受診を検討してください」と1行添える

## 5. 終わり
- `git status` で `secure/` が含まれていないことを確認してからコミットする（コミットするのは `.age` の削除だけ）
- 報告は「取り込んだ件数・保存先」だけ。内容を会話に長く書き出さない
