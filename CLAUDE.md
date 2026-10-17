# このリポジトリで作業するときの約束

- `plugins/detective-conan/data/` のデータを書くときは、必ず `plugins/detective-conan/data/conventions.md` に従う（情報時点・正史区分タグ・出典の書き方・ID 規則・タイトルの書き方・知識表の記号）。
- データの追加・更新の手順は `plugins/detective-conan/skills/update/SKILL.md` に従う。
- 編集するのはこのリポジトリのファイル。`~/.claude/plugins/cache/` にあるインストール済みのコピーは直さない。
- 話数・巻・初登場は `python plugins/detective-conan/scripts/conan_db.py` で引く。database の CSV の `number` 列は公式の File 番号とずれているので、そのまま使わない。
- 確かめられなかった話数や事実は「要確認」と書き、推測で埋めない。Web の要約結果（WebFetch など）は細部を取り違えることがあるので、原文か database で確かめる。
- データや Markdown を変えたら、`npm run fix:md` で書式を直してから `python plugins/detective-conan/scripts/lint_data.py` と `npm run lint:md` を実行し、どちらもエラーを 0 件にする。fix:md は data/ のファイルも書き換えるので、lint_data.py は fix:md の後に実行する。初回は `npm ci`（`npm install` は package-lock.json を書き換えることがあるので使わない）。
- markdownlint のルールの例外は `.markdownlint-cli2.jsonc` に書く。リポジトリ全体の例外は直下のファイル、特定のディレクトリだけの例外はそのディレクトリのファイルに書く。表の桁をそろえる formatter（Prettier など）は、lint_data.py の表の読み取りが壊れるので使わない。
- `plugins/detective-conan/database` は submodule（L40S38/DetectiveConan-Database）。中身を更新したら、submodule 側のコミットと push が必要になる。push はユーザーに確認してから行う。
