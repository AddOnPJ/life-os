"""機微情報（健康の詳細・恋愛・お金）をスマホ（クラウド）から安全に送るための暗号化ツール。

仕組み（age 公開鍵暗号）:
- 公開鍵 keys/age-public.txt はリポジトリに置く。クラウドの Claude Code はこれで「暗号化だけ」できる
- 秘密鍵 secure/keys/age-identity.txt は PC の中だけ（.gitignore 済み）。復号は PC でしかできない
- クラウドは secure-inbox/*.age（暗号文）だけをコミットする。中身は GitHub でもクラウドでも読めない

使い方:
    pip install pyrage
    python scripts/secure_note.py keygen                       # PC で1回だけ
    python scripts/secure_note.py encrypt --kind love --text "..."   # クラウド/PC どちらでも
    python scripts/secure_note.py decrypt                      # PC だけ。secure/inbox/ に平文で展開
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "keys" / "age-public.txt"
IDENTITY = ROOT / "secure" / "keys" / "age-identity.txt"
OUTBOX = ROOT / "secure-inbox"
PLAIN = ROOT / "secure" / "inbox"
KINDS = {"love", "money", "health", "other"}
JST = dt.timezone(dt.timedelta(hours=9))


def need_pyrage():
    try:
        import pyrage  # noqa: F401
        from pyrage import x25519  # noqa: F401
    except ImportError:
        sys.exit("pyrage がありません。`pip install pyrage` を実行してください。")


def keygen(_):
    need_pyrage()
    from pyrage import x25519
    if IDENTITY.exists():
        sys.exit(f"秘密鍵はすでにあります: {IDENTITY}（上書きしません）")
    ident = x25519.Identity.generate()
    IDENTITY.parent.mkdir(parents=True, exist_ok=True)
    IDENTITY.write_text(str(ident) + "\n", encoding="utf-8")
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.write_text(str(ident.to_public()) + "\n", encoding="utf-8")
    print("秘密鍵:", IDENTITY, "（PC の外に出さない。別の安全な場所にもバックアップする）")
    print("公開鍵:", PUBLIC, "（コミットしてよい）")


def encrypt(args):
    need_pyrage()
    import pyrage
    from pyrage import x25519
    if not PUBLIC.exists():
        sys.exit("公開鍵 keys/age-public.txt がありません。PC で `keygen` を実行してください。")
    if args.kind not in KINDS:
        sys.exit(f"--kind は {sorted(KINDS)} のどれか")
    text = args.text if args.text is not None else sys.stdin.read()
    if not text.strip():
        sys.exit("本文が空です")
    recipient = x25519.Recipient.from_str(PUBLIC.read_text(encoding="utf-8").strip())
    now = dt.datetime.now(JST)
    body = f"---\nkind: {args.kind}\nlogged_at: {now.isoformat(timespec='minutes')}\n---\n\n{text.strip()}\n"
    OUTBOX.mkdir(exist_ok=True)
    out = OUTBOX / f"{now:%Y-%m-%d-%H%M%S}-{args.kind}.age"
    out.write_bytes(pyrage.encrypt(body.encode("utf-8"), [recipient]))
    print(out.relative_to(ROOT))


def decrypt(_):
    need_pyrage()
    import pyrage
    from pyrage import x25519
    if not IDENTITY.exists():
        sys.exit("秘密鍵がありません。この PC で `keygen` したか確認してください。")
    ident = x25519.Identity.from_str(IDENTITY.read_text(encoding="utf-8").strip())
    PLAIN.mkdir(parents=True, exist_ok=True)
    files = sorted(OUTBOX.glob("*.age"))
    for f in files:
        plain = pyrage.decrypt(f.read_bytes(), [ident])
        dest = PLAIN / (f.stem + ".md")
        dest.write_bytes(plain)
        f.unlink()
        print("展開:", dest.relative_to(ROOT))
    if not files:
        print("暗号化メモはありません")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(required=True)
    sub.add_parser("keygen").set_defaults(func=keygen)
    e = sub.add_parser("encrypt")
    e.add_argument("--kind", required=True)
    e.add_argument("--text")
    e.set_defaults(func=encrypt)
    sub.add_parser("decrypt").set_defaults(func=decrypt)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
