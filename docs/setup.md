# セットアップ手順

## 1. GitHub に登録する（PC で1回だけ）

PowerShell で:

```
cd $HOME\claude-work\life-os
git init -b main
git add .
git commit -m "life-os 初期構成"
gh repo create AddOnPJ/life-os --private --source=. --push
```

`gh` が入っていない／ログインしていない場合:
1. GitHub で空の private リポジトリ `life-os` を作る（README などは付けない）
2. 次を実行
```
git remote add origin https://github.com/AddOnPJ/life-os.git
git push -u origin main
```

## 2. Claude Code を起動

```
cd $HOME\claude-work\life-os
claude
```

## 3. secure/ の暗号化（健康・恋愛・お金を記録し始める前に）

いまは `secure/` の中身は .gitignore で GitHub に上がらないようにしてある。
暗号化してから GitHub に載せたい場合は git-crypt を使う:

1. git-crypt をインストール（Windows では WSL か配布バイナリ。要確認）
2. `git-crypt init`
3. `.gitattributes` に `secure/** filter=git-crypt diff=git-crypt` を追加
4. 鍵を `git-crypt export-key <リポジトリ外の安全な場所>` で書き出して保管
5. `.gitignore` から secure の行を外してコミット

※ 実行前に Claude Code に手順を確認させること。
