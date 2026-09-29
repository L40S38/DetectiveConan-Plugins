# このリポジトリで作業するときの約束

- `plugins/detective-conan/data/` のデータを書くときは、必ず `plugins/detective-conan/data/conventions.md` に従う（情報時点・正史区分タグ・出典の書き方・ID 規則・タイトルの書き方・知識表の記号）。
- データの追加・更新の手順は `plugins/detective-conan/skills/update/SKILL.md` に従う。
- 編集するのはこのリポジトリのファイル。`~/.claude/plugins/cache/` にあるインストール済みのコピーは直さない。
- 話数・巻・初登場は `python plugins/detective-conan/scripts/conan_db.py` で引く。database の CSV の `number` 列は公式の File 番号とずれているので、そのまま使わない。
- 確かめられなかった話数や事実は「要確認」と書き、推測で埋めない。Web の要約結果（WebFetch など）は細部を取り違えることがあるので、原文か database で確かめる。
- データを変えたら `python plugins/detective-conan/scripts/lint_data.py` を実行し、エラーを 0 件にする。
- `plugins/detective-conan/database` は submodule（L40S38/DetectiveConan-Database）。中身を更新したら、submodule 側のコミットと push が必要になる。push はユーザーに確認してから行う。
