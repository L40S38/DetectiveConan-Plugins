---
name: update
description: 名探偵コナン調査プラグインのデータ（伏線リスト・考察項目リスト・人物索引・知識表・編纂室データベース）を、新しい話・単行本・劇場版の情報やユーザーの指摘に合わせて更新するときに使う。「最新話を反映して」「File 1168 の内容でデータを更新して」「109巻が出たので database を更新して」「表3 の世良の欄を直して」「この伏線は回収済みにして」のような依頼で使う。質問に答えるだけの用途は research スキルを使う。
---

# 名探偵コナン データ更新

`data/` 以下のデータを、`data/conventions.md` の約束事を守って書き換える。最後に `lint_data.py` を通し、何を変えたかを表で示す。

## Step 0: 編集する場所を確かめる

- 編集するのは **ソースリポジトリ**（DetectiveConan-Plugins）で、インストール済みプラグインのキャッシュ（`~/.claude/plugins/cache/...`）ではない。キャッシュを直しても、次の更新で消える。
- カレントディレクトリに `.claude-plugin/marketplace.json` があり、`"name": "detective-conan-plugins"` になっているか確かめる。無ければ、ソースリポジトリのパスをユーザーに聞く。
- 以降のパスは、ソースリポジトリの `plugins/detective-conan/` からの相対パスで書く。

## Step 1: 何を反映するかを決め、情報を集める

1. 反映する範囲をユーザーと確かめる（例：「File 1168」「109巻」「劇場版第 30 作」「表3 の世良」）。
2. 単行本が出たときは、database を最新にする。

   ```
   cd plugins/detective-conan/database
   python ConanData.py
   python Case.py && python FileTitle.py && python GuestCharacter.py && python MainCharacter.py && python Place.py
   cd ..
   python scripts/conan_db.py latest
   python scripts/conan_db.py anomalies
   ```

   `anomalies` で新しい欠け・重複が出たら、報告に含める。submodule に差分が出たら、コミットと push が必要なことをユーザーに伝える（勝手に push しない）。
3. `data/sources.md` の信頼度の順に情報を集める。単行本未収録の話は、D の速報系 2 サイト以上で一致したものだけを使う。WebFetch の要約は細部を取り違えることがあるので、話数と人物名は原文か database で確かめる。

## Step 2: 伏線リスト（data/foreshadowing.md）

- 新しい謎を見つけたら、分類ごとに次の番号で項目を立てる。ID は再利用しない。
- **タイトルは謎の形**で書き、答えも、ほかの謎の答えになる名前も入れない（`conventions.md` の 5.）。
- 冒頭の一覧表と詳細の両方に書く（ID・タイトル・状態・重要度・初出・回収）。
- 回収されたら「状態」を変え、「回収」欄に話数と答えを書く。答えを書くのは「回収」欄だけ。
- 途中の進展は「経過」欄に時系列で足す。

## Step 3: 考察項目リスト（data/open-questions.md）

- 新しい事実を「確定している事実」に話数つきで足す。新しい説には `[ファン説]` を付け、根拠と反証を書く。
- 解明された項目は消さずに、末尾の「解明済み」セクションへ移し、どの話で解明されたかを書く。
- 新しい大きな問いが生まれたら、次の番号で項目を立てる（タイトルの書き方は伏線と同じ）。

## Step 4: 知識表（data/knowledge-matrix/）

- 値が変わったセルを直し、脚注に根拠の話数を書く。記号と段階値の意味は `knowledge-matrix/README.md`。
- 新しい人物が秘密に関わってきたら、該当する表に行を足す（人物 ID は `characters.md` に先に作る）。
- `?` のセルを確かめられたら、記号に置き換えて根拠を書く。
- `knowledge-matrix/README.md` と `conventions.md` の「情報時点」を更新する。

## Step 5: 人物索引（data/characters.md）

- 新しい人物はカードを足し、別名があれば「(a) 別名 → 人物 ID」にも足す。初登場は `python scripts/conan_db.py char <名前>` で引く。原作より先に劇場版・アニメなどで出ていたら「／先行：」を付ける。
- 所属・生死・役割が変わったら書き換え、根拠の話数を付ける。
- 新しい劇場版が公開されたら、「(c) 劇場版への登場」に行を足す。

## Step 6: 参考サイト（data/sources.md）

新しく使ったサイトは、URL が開けることを確かめてから、信頼度を付けて足す。「最終確認日」を更新する。

## Step 7: チェックする

```
python scripts/lint_data.py
```

エラーが 0 件になるまで直す。警告（タイトルの書き方）は、答えが入っていないことを目で確かめる。

## Step 8: 変更をまとめて示す

```markdown
# データ更新：File 1168 まで

| ファイル | ID・場所 | 変更 | 根拠 |
|---|---|---|---|
| foreshadowing.md | F-RUM-009 | 経過を追加 | 原作 File 1168 [原作] |
| knowledge-matrix/03-akai-family.md | 世良真純 K3-2 | △ → ● | 原作 File 1168 |

- lint：エラー 0 件、警告 0 件
- 要確認のまま残したもの：…
- database：更新あり／なし（submodule のコミットと push が必要）
```

コミットはユーザーから頼まれたときだけ行う。
