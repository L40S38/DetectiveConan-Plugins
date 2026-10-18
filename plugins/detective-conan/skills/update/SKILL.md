---
name: update
description: 名探偵コナン調査プラグインのデータ（伏線リスト・考察項目リスト・人物索引・知識表・人物の掘り下げ・編纂室データベース）を、新しい話・単行本・劇場版の情報やユーザーの指摘に合わせて更新するときに使う。「最新話を反映して」「File 1168 の内容でデータを更新して」「109巻が出たので database を更新して」「表3 の世良の欄を直して」「この伏線は回収済みにして」のような依頼で使う。質問に答えるだけの用途は research スキルを使う。
---

# 名探偵コナン データ更新

`data/` 以下のデータを、`data/conventions.md` の約束事を守って書き換える。最後に `lint_data.py` と markdownlint を通し、何を変えたかを表で示す。

## Step 0: 編集する場所を確かめる

- 編集するのは **ソースリポジトリ**（DetectiveConan-Plugins）で、インストール済みプラグインのキャッシュ（`~/.claude/plugins/cache/...`）ではない。キャッシュを直しても、次の更新で消える。
- カレントディレクトリに `.claude-plugin/marketplace.json` があり、`"name": "detective-conan-plugins"` になっているか確かめる。無ければ、ソースリポジトリのパスをユーザーに聞く。
- 以降のパスは、ソースリポジトリの `plugins/detective-conan/` からの相対パスで書く。

## Step 1: 何を反映するかを決め、情報を集める

1. 反映する範囲をユーザーと確かめる（例：「File 1168」「109巻」「劇場版第 30 作」「表3 の世良」）。
2. 単行本が出たときは、database を最新にする。

   ```sh
   cd plugins/detective-conan/database
   python ConanData.py
   python Case.py && python FileTitle.py && python GuestCharacter.py && python MainCharacter.py && python Place.py
   cd ..
   python scripts/conan_db.py latest
   python scripts/conan_db.py anomalies
   ```

   `anomalies` で新しい欠け・重複が出たら、報告に含める。submodule に差分が出たら、コミットと push が必要なことをユーザーに伝える（勝手に push しない）。
   database を更新したら、`単行本未収録` の形で書いていた File（`grep -rn 単行本未収録 data/`）のうち、`conan_db.py file` で引けるようになったものを、`conventions.md` の 3.1「database に入っている話」の形に直す。
   database の更新で、事件名や話タイトルが変わることがある（単行本の収録時に改題されるなど）。更新の前後で `database/dataset_csv/Volume-Index-Case-Title.csv` を見比べ（submodule の中で `git diff` する）、名前が変わった事件・話があったら、`data/` 以下で古い名前を使っている箇所（`grep -rn "古い名前" data/`）をすべて新しい名前に直す。直した事件名は Step 8 の報告に含める。`lint_data.py` は File 表記の形しか見ず、名前が database と合っているかは見ないので、この確認は省かない。
3. `data/sources.md` の信頼度の順に情報を集める。単行本未収録の話は、D の速報系 2 サイト以上で一致したものだけを使う。WebFetch の要約は細部を取り違えることがあるので、話数と人物名は原文か database で確かめる。

## Step 2: 伏線リスト（data/foreshadowing/）

`data/foreshadowing/README.md` が一覧表、分類ごとの詳細は `data/foreshadowing/01-org.md`〜`09-rel.md`（分類と番号の対応は README.md の「ファイル一覧」を見る）。

- 新しい謎を見つけたら、分類ごとに次の番号で項目を立てる。ID は再利用しない。
- **タイトルは謎の形**で書き、答えも、ほかの謎の答えになる名前も入れない（`conventions.md` の 5.）。
- `README.md` の一覧表と、対応する分類ファイルの詳細の両方に書く（ID・タイトル・状態・重要度・初出・回収）。
  - 詳細の項目には、見出しの前に `<a id="F-XXX-NNN"></a>` を置く。アンカー・見出し・箇条書きのあいだは空行を 1 行ずつあける（既存項目にならう。空行が無いと markdownlint のエラーになる）。README.md の一覧表からはこのアンカーへリンクする（`ファイル名#F-XXX-NNN`）。
  - 「関連」欄で人物・知識表に触れるときは、`characters.md#C-xxx`／`../knowledge-matrix/0N-〜.md` へのリンクにする（既存項目の書き方にならう）。
- 回収されたら「状態」を変え、「回収」欄に話数と答えを書く。答えを書くのは「回収」欄だけ。
- 途中の進展は「経過」欄に時系列で足す。

## Step 3: 考察項目リスト（data/open-questions.md）

- 新しい事実を「確定している事実」に話数つきで足す。新しい説には `[ファン説]` を付け、根拠と反証を書く。
- 解明された項目は消さずに、末尾の「解明済み」セクションへ移し、どの話で解明されたかを書く。
- 新しい大きな問いが生まれたら、次の番号で項目を立てる（タイトルの書き方は伏線と同じ）。

## Step 4: 人物索引（data/characters.md）

- 新しい人物はカードを足し、別名があれば「(a) 別名 → 人物 ID」にも足す。初登場は `python scripts/conan_db.py char <名前>` で引く。原作より先に劇場版・アニメなどで出ていたら「／先行：」を付ける。
- 所属・生死・役割が変わったら書き換え、根拠の話数を付ける。
- 新しい劇場版が公開されたら、「(c) 劇場版への登場」に行を足す。
- 人物やグループ（`###`）を足したとき、人物を別のグループへ移したときは、Step 5 で知識表と人物の掘り下げにも反映する。

## Step 5: 知識表と人物の掘り下げ（data/knowledge-matrix/・data/profiles/）

記号と「コナンの把握」の列の意味、行の選び方（グループ分け・並び順・個別の行とまとめ行の基準と書式）は `data/knowledge-matrix/README.md` に書いてある。行の置き方はこの README に従う。

- 値が変わったセルを直し、脚注に根拠の話数を書く。`?` のセルを確かめられたら、記号に置き換えて根拠を書く。
- 値が変わって、個別の行とまとめ行のどちらに入るかが変わったら、行を移す（位置と書式は README の「行の選び方」）。
  - まとめ行（`ほかの「<グループ名>」：…` の行）の人物に、「コナンの把握」以外で `✕` 以外の値（`?`・`✕†` を含む）が付いたら、まとめ行から名前と ID を消して個別の行を作る。まとめ行に誰も残らなくなったら、まとめ行ごと消す。
  - 個別の行が「コナンの把握」以外すべて `✕`（`†` なし）になったら、その行を消してまとめ行に名前と ID を入れ、ほかの行で使っていない脚注も消す。まとめ行が無ければ作る。
- Step 4 で人物を足したら、すべての表（`data/knowledge-matrix/0*.md`）にその人物を入れる。確かめていない人物の扱い（その表のテーマに関わる場面が無ければまとめ行）も README の「行の選び方」に書いてある。
- Step 4 でグループを足したら、すべての表に見出し行を足す。人物を別のグループへ移したら、すべての表で、その人物の行（またはまとめ行の名前）を新しいグループへ移す。
- `data/knowledge-matrix/README.md` と `conventions.md` の「情報時点」を更新する。
- 足し忘れ・重複・並び順・グループの食い違いは、Step 7 の `lint_data.py` がエラーにする。
- 人物の掘り下げ（`data/profiles/0*.md`）も、行の置き方は知識表と同じ（記号も同じ。「コナンの把握」の列は無く、まとめ行に入れるのは、すべての列が `✕` の人物）。人物やグループを足したら、こちらの表にも入れる。値と過去の区分は `data/profiles/README.md` を見る。

## Step 6: 参考サイト（data/sources.md）

新しく使ったサイトは、URL が開けることを確かめてから、信頼度を付けて足す。「最終確認日」を更新する。

## Step 7: チェックする

```sh
npm run fix:md    # Markdown の書式を自動で直す（初回だけ先に npm ci）
python scripts/lint_data.py
npm run lint:md
```

fix:md は data/ のファイルも書き換えるので、lint_data.py はその後に実行する。lint_data.py と lint:md のどちらもエラーが 0 件になるまで直す。lint_data.py の警告（タイトルの書き方）は、答えが入っていないことを目で確かめる。markdownlint の設定はリポジトリ直下の `.markdownlint-cli2.jsonc` にある（`data/foreshadowing/`・`data/relationships/` には、そのディレクトリだけの例外を書いた同名のファイルがある）。

## Step 8: 変更をまとめて示す

```markdown
# データ更新：File 1168 まで

| ファイル | ID・場所 | 変更 | 根拠 |
|---|---|---|---|
| foreshadowing/02-rum.md | F-RUM-009 | 経過を追加 | 原作 File 1168 [原作] |
| knowledge-matrix/03-akai-family.md | 世良真純 K3-2 | △ → ◎ | 原作 File 1168 |

- lint：lint_data.py エラー 0 件・警告 0 件／markdownlint エラー 0 件
- 要確認のまま残したもの：…
- database：更新あり／なし（submodule のコミットと push が必要）
- database で名前が変わった事件・話：なし／「旧名」→「新名」（data/ の該当箇所を直した）
```

コミットはユーザーから頼まれたときだけ行う。
