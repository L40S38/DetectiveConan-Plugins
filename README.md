# DetectiveConan-Plugins

『名探偵コナン』を調査・考察するための Claude Code プラグイン。

- 参考サイトを信頼度つきでまとめた一覧
- 主な伏線リストと、未解明の謎の考察項目リスト（出典の話数と正史区分つき）
- 各キャラクターが物語の根幹となる秘密をどこまで知っているかの表（テーマ別に 7 表）
- 作中の出来事に ID を振ってまとめた正本（その場にいた人物、誰が何を知ったか）
- 名探偵コナン編纂室のデータ（[L40S38/DetectiveConan-Database](https://github.com/L40S38/DetectiveConan-Database)、submodule）を使った話数・巻・初登場の検索

> **ネタバレ注意**：データは原作の最新話（単行本未収録分を含む）と劇場版の内容を含む。

## 導入

```text
# リポジトリを取得（submodule も一緒に）
git clone --recurse-submodules <このリポジトリの URL>

# Claude Code でマーケットプレイスとして登録し、プラグインを入れる
/plugin marketplace add <クローンしたディレクトリのパス>
/plugin install detective-conan@detective-conan-plugins
```

submodule を取得し忘れたときは `git submodule update --init` を実行する。

## 使い方

| スキル | 呼び出し | 用途 |
|---|---|---|
| research | `/detective-conan:research` | 調査・考察・質問への回答。データは書き換えない |
| update | `/detective-conan:update` | 新しい話・単行本・劇場版の反映、データの修正 |

スラッシュコマンドを使わなくても、「コナンの正体を知っているのは誰？」「ラムの伏線を時系列で」「最新話を反映して」のように頼めば自動で呼ばれる。

## 構成

```text
.claude-plugin/marketplace.json       マーケットプレイスの定義
.github/workflows/lint.yml            CI（markdownlint・lint_data.py・スクリプトのテスト）
.markdownlint-cli2.jsonc              Markdown の lint 設定
package.json                          markdownlint-cli2（npm run lint:md / fix:md）。Node 26 以上
.npmrc                                Node の版が足りないときに npm ci を止める
tests/test_check_event_copy.py        check_event_copy.py の --cited のテスト（python -m unittest discover -s tests）
plugins/detective-conan/
├── .claude-plugin/plugin.json
├── data/
│   ├── conventions.md                記法の約束事（情報時点・正史区分タグ・ID・記号）
│   ├── sources.md                    参考サイト
│   ├── characters.md                 人物索引（別名の逆引き・人物カード・劇場版への登場）
│   ├── foreshadowing/                伏線リスト（README.md が一覧、F-分類ごとにファイル）
│   ├── open-questions.md             考察項目リスト
│   ├── knowledge-matrix/             誰が何を知っているか（表1〜8）
│   ├── profiles/                     作品が人物をどこまで描いたか（私生活・過去・内面・素性）
│   └── events/                       出来事の正本（作中の場面に ID を振った一覧）
├── database/                         submodule: L40S38/DetectiveConan-Database
├── scripts/
│   ├── conan_db.py                   編纂室データの検索（公式 File 番号に直して引く）
│   ├── lint_data.py                  データの整合性チェック
│   └── check_event_copy.py           出来事の正本の件が写し元を写しているかの確かめ
└── skills/
    ├── research/SKILL.md
    └── update/SKILL.md
```

## データを更新する

1. このリポジトリで Claude Code を開き、update スキルに頼む（例：「File 1168 を反映して」）。インストール済みプラグインのキャッシュではなく、このリポジトリのファイルを直すこと。
2. `npm run fix:md` で Markdown の書式を直す（初回だけ先に `npm ci`。markdownlint-cli2 を使う。設定は `.markdownlint-cli2.jsonc`）。
3. `python plugins/detective-conan/scripts/lint_data.py` と `npm run lint:md` で、どちらもエラーが 0 件になることを確かめる。fix:md は data/ のファイルも書き換えるので、2. の後に実行する。2. で直る書式が残っていないかと 3. のチェックは、main への push と PR のたびに GitHub Actions（`.github/workflows/lint.yml`）でも確かめる。
4. コミットしたら、`/plugin marketplace update detective-conan-plugins` でインストール済みのプラグインに反映する。

### database について

- 単行本が出たら、`plugins/detective-conan/database` で `python ConanData.py` などを実行して取り直す（手順は update スキルの Step 1）。
- database の CSV の `number` 列は、取得した行の通し番号で、公式の File 番号とずれている（巻の中で話が欠けていたり重複していたりするため）。`scripts/conan_db.py` は巻と巻内の話番号から公式の File 番号を計算し直して使う。`python scripts/conan_db.py anomalies` で欠け・重複の一覧が出る。

## 著作権

作品の著作権は青山剛昌／小学館ほか権利者に帰属する。このリポジトリは作品を調べるための索引と考察メモで、作品の本文や画像は含まない。
