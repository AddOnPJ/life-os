# health

体調・通院・薬・検査結果の記録（2026-11-20 から通常の記録。以前は secure/ に分けていた）。

- 毎日の体の数字（睡眠・心拍・HRV・SpO2・体重・歩数・運動）は `logs/daily/` の front matter に Pixel Watch から自動で入る
- `log.md` … 体調・通院・薬・検査結果。1行1件、新しいものを上に：`- YYYY-MM-DD 内容`（Yuichi の言葉のまま）
- アドバイスの手順は `.claude/skills/health-coach/SKILL.md`
- 他人の健康の話は書かない
