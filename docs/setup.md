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

## 3. 機微メモ用の鍵を作る（スマホから恋愛・お金・健康の詳細を記録するため）

```
pip install pyrage
python scripts/secure_note.py keygen
git add keys/age-public.txt
git commit -m "機微メモ用の公開鍵"
git push
```

- 秘密鍵 `secure/keys/age-identity.txt` は PC の中だけ。USB メモリやパスワード管理アプリなど、別の安全な場所にもコピーしておく（なくすと過去の暗号メモが読めなくなる）
- 以後、スマホから送った機微メモは暗号文で `secure-inbox/` に届き、PC で「secure を処理して」と頼むと `secure/` に展開される

## 4.（任意）secure/ ごと暗号化して GitHub に置く

いまは `secure/` の中身は .gitignore で GitHub に上がらないようにしてある。
暗号化してから GitHub に載せたい場合は git-crypt を使う:

1. git-crypt をインストール（Windows では WSL か配布バイナリ。要確認）
2. `git-crypt init`
3. `.gitattributes` に `secure/** filter=git-crypt diff=git-crypt` を追加
4. 鍵を `git-crypt export-key <リポジトリ外の安全な場所>` で書き出して保管
5. `.gitignore` から secure の行を外してコミット

※ 実行前に Claude Code に手順を確認させること。
