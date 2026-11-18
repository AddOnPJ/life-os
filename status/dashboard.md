# スマホで見る画面（Claude Docs「life-os いまの状態」）

- 画面：https://claude.ai/artifact/Qv563GNdcmyiL5MnNqRL2U （Claude アプリで開く）
- doc id：c1ab20ab-a64a-4a26-b4a8-71824ae40821
- 本文の node id：efe4e378-74d8（engine: prose）
- 毎朝 6:47 の定期実行が、life-status スキルの「5. 画面を更新する」で丸ごと書き直す。人が書き込んだ内容やコメントは残らない

## 書き直し方（定期実行向け）
1. Claude Docs のツールを読み込む（`ToolSearch` で `Claude_Docs`）。初めてなら `guide(items=["topic.index"])`
2. 本文の目次を読む：`read(ref={"object":"node","id":"efe4e378-74d8"}, engine="prose", container={"kind":"project","id":"c1ab20ab-a64a-4a26-b4a8-71824ae40821"}, payload={"kind":"view","outline":true})`
3. 1回の `update` で、見出し1（タイトル）以外のすべての最上位ブロックを `delete`（`"ifRev"` に読んだ rev）、続けてタイトルの後ろに `insert`（`"side":"after"`）で新しい本文の markdown を入れる
4. 本文の形：日付の行 → 「今日やること」→「AddOn」→「承認待ちと決めてほしいこと」→「体」→「予定」→「仕組み」（リンク4つ）。中身は status/now.md と domains/addon/agent/status.md から。恋愛・お金・健康の詳細は書かない
5. 失敗しても now.md の更新は止めない。失敗したことをブリーフの要確認に1行

## 3. PC の中だけの詳細画面
- `C:\Users\ytytc\claude-work\life-os\secure\dashboard.html`（ブラウザで開いてブックマーク）
- 詳しい健康（安静時心拍・HRV・SpO2・体重・睡眠の区切り）とお金。毎朝の PC の同期で作り直す（scripts/secure_weekly.py）。GitHub・クラウドには出ない
- 司令室（artifact）の最新版：version 1795016669-8f1a 以降。ページを変えたら `python scripts/build_dashboard_page.py` → publish_files（slug 303a0b74-ec11-4e0c-962a-958db0b70a88）
