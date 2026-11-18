# 自動で動いているもの一覧

増やす・止める・時刻を変えるときは、このファイルも直す。最終確認：2026-11-18

## 毎日

| 時刻 | 名前 | どこで動く | やること | 結果の置き場所 |
|---|---|---|---|---|
| 6:00 | AddOn広報リサーチ | Grok Bot（ルーティン） | X の公開情報から募集・集客の材料と投稿の下書き。投稿・いいね・DM はしない | Grok Bot のチャット |
| 6:30 | life-os-google-health | PC（タスク スケジューラ） | Pixel Watch のデータを取得し、日次ログに歩数・睡眠などを書く | `logs/daily/`（詳細は `secure/health/`） |
| 6:23 | AddOn エージェント | Claude 定期実行（クラウド） | 募集・本番・発信の点検と判断。応募への返信の下書き、期限の段階分け、打ち手の準備。月曜は3つの立場のAIで検討会。通知は最優先のときだけ（ふだんは 6:47 のブリーフにまとめる） | `domains/addon/agent/status.md`、`status/approvals.md` |
| 6:47 | life-os 朝のブリーフ | Claude 定期実行（クラウド） | カレンダー・Gmail・記録から今日のブリーフ、続けて現状まとめ。応募メールには返信の下書き（送らない） | `logs/daily/今日.md`、`status/now.md`、通知 |


## 毎週

| 時刻 | 名前 | どこで動く | やること | 結果の置き場所 |
|---|---|---|---|---|
| 土曜 20:13 | life-os 仕組みの点検 | Claude 定期実行（クラウド） | 各仕事が動いたか、うるさい・足りない・壊れているところを見つけ、直せるものは直す。大きな変更はブランチを作って承認待ちへ | `reviews/system/`、`docs/backlog.md`、通知 |
| 日曜 20:47 | life-os 週次振り返り | Claude 定期実行（クラウド） | 1週間の数字・AddOn・来週の山場とフォーカス候補 | `reviews/weekly/`、通知 |

## 自分で送ると動くもの

| 送り方 | どこ | やること |
|---|---|---|
| 「記録 ◯◯」、食事の写真 | スマホの Claude Code（life-os） | inbox に保存（quick-log） |
| 「恋愛記録 苗字」＋【記録】 | スマホの Claude Code（**love-coach** リポジトリを開く） | love-coach の `profiles/苗字/記録.md` に追記 |
| 「A1 OK」「A1,A3 OK」「A1 なし」 | スマホの Claude Code（life-os） | 承認待ちを実行・取り下げ（approve） |
| 「D1 外す」など | スマホの Claude Code（life-os） | AddOn の決めてほしいことを決定として反映（approve） |
| 「改善 ◯◯」 | スマホの Claude Code（life-os） | 改善の一覧（docs/backlog.md）に足す |
| 「grok」＋Grok の結果を貼る | スマホの Claude Code（life-os） | inbox に保存。AddOn エージェントが翌朝読む |
| LINE のトーク履歴を添付 | Claude アプリの「恋愛コーチ」プロジェクト | 相手の気持ちの読み取りと次の一手 |
| 「secure を処理して」 | PC の Claude Code | 暗号化メモを復号して secure/ に整理（secure-log） |

## life-os 以外で動いている定期実行（参考）

| 時刻 | 名前 |
|---|---|
| 6:46・21:46 | 金のなる木 |
| 8:33・21:33 | 競馬研究の一歩 |
| 毎月1日 | Mac ストレージ月次点検 |

## 止めたもの

- 2026-11-18 削除：毎朝のブリーフィング（5:50）、AddOn 募集チェック（7:00）、AddOn AI強化策チーム 朝会議（6:47）。朝のブリーフと重複していたため。募集チェックの点検項目は `domains/addon/agent-notes.md` に移した
