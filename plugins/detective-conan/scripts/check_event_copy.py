#!/usr/bin/env python3
"""出来事の正本（data/events/）の件が、写し元の文をそのまま写しているかを確かめる（標準ライブラリのみ）。

今のデータ（data/ 以下）や database のあらすじから写した件を確かめるためのもの。おもに、今のデータの脚注・経緯から
件を登録し直す作業で使う。git の履歴を読むので、ソースリポジトリでだけ動く。Web の出典から書いた件は確かめられない。

各件の「写し元（<コミット>）」に書いたファイルを、そのコミットの時点で読み（git show）、
「出来事」の 1 段目と「要確認」の文が、写し元にそのまま含まれているかを「。」で区切った 1 文ずつ調べる。
写し元の行は、コミットごとに 2 行以上書ける。行ごとに、その行のコミットで読む。
含まれていない文は、写し元でいちばん近い文と、どこが違うかを表示する（[-写し元にだけある部分-]・{+正本にだけある部分+}）。
言い換えたこと自体は誤りではないが、違いはユーザーに見せる（events/README.md の「書くときの確かめ方」）。
「知識」「描写」「伏線」に書いた K・P・F の ID が、写し元に出てくるかも調べる（「知識」「描写」は、まずその人物の脚注を探す）。

写し元の場所の書き方（events/README.md の「写し元の書き方」）:
    knowledge-matrix/04-haneda-case.md `[^K4-kudo-shinichi]`   … その脚注の行
    relationships/friends-and-rivals.md「羽田浩司 × 浅香（若狭留美）」 … その見出しの節（次の同じ深さ以上の見出しまで）
    profiles/timeline.md                                          … 場所を書かなければファイル全体
    database/dataset_csv/Number-Title-Explain.csv「<事件名>」      … その事件のあらすじ（submodule の今の中身）

--removed は逆の向きを調べる。ほかのファイルの根拠を出来事の ID に置き換えたあとで、<コミット>（置き換える前）の
時点と今のファイルを比べ、消えた行の文が、今のファイルに残っているか、どれかの件（見出し・出典・「出来事」の
1 段目・要確認）にそのままあるか（一致）、近い文があるか（違いあり）、どちらでもないか（見つからない）を出す。
脚注の行は、今の同じ脚注とも比べる。

--cited は脚注 → 件の向きを調べる（git は使わず、今のファイルを読む）。知識表・人物の掘り下げの表で、脚注の文のうち
その表の列 ID で始まるもの（「K1-4・K1-5 は E-429-03 による」。範囲「K1-1〜K1-3」と列挙を読む）に出てくる件に、
その脚注の行の人物（脚注を共有する行・1 行に何人もいる行は全員）の知識（人物の掘り下げでは描写）があるかを見る。
見るのは、知識表では `◎`・`〇`、人物の掘り下げでは `◎`・`〇`・`△` のセル（`†` 付きを含む）だけ。「コナンの把握」の
列と、「直した」を含む括弧（直した履歴）の中の件は見ない。2 列以上・2 件以上を 1 文で書いたものは、どの件にも
どれかの列があるか、どの列もどれかの件にあるかだけを見る。「コナンの把握」の理由の文（「K1-3 は A：…」）から
出たものは、参考の段に出す。知識表では、件の「場面にいた人物」にいない人に、そのことを添える。

使い方:
    python check_event_copy.py E-1106-01 [E-… …]
    python check_event_copy.py --all
    python check_event_copy.py --removed <コミット> knowledge-matrix/04-haneda-case.md [<data からのパス> …]
    python check_event_copy.py --cited [knowledge-matrix/01-conan-shinichi.md …]

写しにすべて一致すれば（--removed では、消えた文がすべて件にそのままあれば。--cited では、脚注が根拠に挙げた件に
知識・描写がすべてあれば。参考の段は数えない）終了コード 0、違いのある文（--removed では、違いあり・見つからない文。
--cited では、無いところ）があれば 1、件や写し元（--cited では表）が読めなければ 2 を返す。
"""
import argparse
import csv
import difflib
import io
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
DATA = PLUGIN / "data"
E_ID = r"E-(?:\d+|M\d+|A\d+|[MAX][A-Z]+\d*)-\d{2,3}"
SOURCE_ITEM = re.compile(r"((?:database/)?[A-Za-z0-9_./-]+\.(?:md|csv))\s*(?:`\[\^([^\]`]+)\]`|「([^」]+)」)?")
ID_IN_SUB = {"知識": r"K\d-\d+", "描写": r"P\d-\d+", "伏線": r"F-[A-Z]+-\d{3}"}
COL_RANGE = re.compile(r"([KP]\d)-(\d+)(?:〜\1-(\d+))?")


def load_entries():
    """events/0*.md から {ID: 件} を作る。件は見出し・出典・場面にいた人物・1 段目の文・ラベルの項目・要確認・写し元を持つ。

    写し元は、行ごとに (コミット, 場所の並び) にする（写し元の行は、コミットごとに 2 行以上書ける）。
    """
    entries = {}
    for p in sorted(x for x in (DATA / "events").rglob("*.md") if x.name != "README.md"):
        entry = label = item = None
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                m = re.fullmatch(rf"### ({E_ID}) (.+)", line)
                label = item = None
                entry = {"file": p.relative_to(DATA / "events").as_posix(), "title": m.group(2) if m else "", "origin": "",
                         "present": "", "events": [], "subs": [], "note": "", "sources": []} if m else None
                if m:
                    entries[m.group(1)] = entry
            elif entry is None:
                continue
            elif m := re.fullmatch(r"  - (.+)", line):
                entry["events"].append(m.group(1))
            elif m := re.fullmatch(r"    - (\S+?):", line):
                label = m.group(1)
            elif m := re.fullmatch(r"      - (.+)", line):
                item = m.group(1)
                if label != "知識":
                    entry["subs"].append((label, item))
            elif m := re.fullmatch(r"        - (.+)", line):
                # 知識：3 段目（何を知ったか）と 4 段目（誰が）を 1 つにして調べる
                entry["subs"].append((label, f"{m.group(1)} {item}"))
            elif m := re.fullmatch(r"- 出典: (.+)", line):
                entry["origin"] = m.group(1)
            elif m := re.fullmatch(r"- 場面にいた人物: (.+)", line):
                entry["present"] = m.group(1)
            elif m := re.fullmatch(r"- 要確認: (.+)", line):
                entry["note"] = m.group(1)
            elif m := re.fullmatch(r"- 写し元(?:（([^）]*)）)?: (.+)", line):
                entry["sources"].append((m.group(1), m.group(2)))
    return entries


def git_show(commit, path):
    """リポジトリの <commit> 時点の data/<path> を読む。"""
    top = subprocess.run(["git", "-C", str(DATA), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
    rel = (DATA / path).resolve().relative_to(Path(top).resolve()).as_posix()
    res = subprocess.run(["git", "-C", top, "show", f"{commit}:{rel}"],
                         capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise OSError(res.stderr.strip())
    return res.stdout


def read_source(commit, path, footnote, heading):
    """写し元の 1 か所を読み、(表示名, 文字列) を返す。"""
    name = path + (f" [^{footnote}]" if footnote else f"「{heading}」" if heading else "")
    if path.startswith("database/"):
        if not heading:
            raise OSError("database のファイルには「事件名」を付ける")
        with (PLUGIN / path).open(encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("title") == heading]
        if not rows:
            raise OSError(f"{path} に「{heading}」の行が無い")
        return name, "\n".join(r["explain"] for r in rows)
    if not commit:
        raise OSError("写し元にコミットが書かれていない")
    text = git_show(commit, path)
    lines = text.splitlines()
    if footnote:
        hit = [ln for ln in lines if ln.startswith(f"[^{footnote}]:")]
        if not hit:
            raise OSError(f"{path} に脚注 [^{footnote}] が無い（{commit} の時点）")
        return name, hit[0]
    if heading:
        starts = [i for i, ln in enumerate(lines) if re.match(r"#{1,6} ", ln) and heading in ln]
        if not starts:
            raise OSError(f"{path} に「{heading}」を含む見出しが無い（{commit} の時点）")
        if len(starts) > 1:
            print(f"    注意：{path} に「{heading}」を含む見出しが {len(starts)} つある。最初のものを読む")
        start = starts[0]
        level = len(lines[start]) - len(lines[start].lstrip("#"))
        end = next((i for i in range(start + 1, len(lines))
                    if re.match(r"#{1,%d} " % level, lines[i])), len(lines))
        return name, "\n".join(lines[start:end])
    return name, text


def sentences(text):
    """「。」で区切る（区切りの「。」は落とす）。空の文は除く。"""
    return [s.strip() for s in re.split(r"。", text) if s.strip()]


def show_diff(src, dst):
    """src（写し元）を dst（正本）に変える違いを、[-…-]{+…+} で 1 行にして返す。"""
    out = []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, src, dst, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(src[a1:a2])
        if op in ("delete", "replace"):
            out.append(f"[-{src[a1:a2]}-]")
        if op in ("insert", "replace"):
            out.append(f"{{+{dst[b1:b2]}+}}")
    return "".join(out)


def closest(sentence, sources):
    """写し元の文で、sentence にいちばん近いものを (一致の割合, 写し元の名前, 文) で返す。

    近さは、sentence のうち写し元の文と一致する文字の割合で測る（長い文の一部を写したときも、その文を選べるように）。
    1 文で 8 割以上一致するものが無いときだけ、隣り合う 2 文をつないだものも候補にする。
    いちばん高い割合から 10 ポイント以内の候補のうち、いちばん短い（余分な部分の少ない）文を選ぶ。
    """
    def score(cands):
        out = []
        for name, cand in cands:
            sm = difflib.SequenceMatcher(None, cand, sentence, autojunk=False)
            out.append((sum(b.size for b in sm.get_matching_blocks()) / len(sentence), name, cand))
        return out

    split = [(name, sentences(text)) for name, text in sources]
    scored = score((name, s) for name, sents in split for s in sents)
    if not scored or max(s[0] for s in scored) < 0.8:
        scored += score((name, "。".join(sents[i:i + 2])) for name, sents in split for i in range(len(sents) - 1))
    if not scored:
        return 0.0, None, None
    top = max(s[0] for s in scored)
    return min((s for s in scored if s[0] >= top - 0.1), key=lambda s: len(s[2]))


def check(eid, entry):
    print(f"{eid}（events/{entry['file']}）")
    sources = []
    items = [(commit, *item) for commit, text in entry["sources"] for item in SOURCE_ITEM.findall(text)]
    if not items:
        print("  写し元：data/ のファイルや database の場所が書かれていない（新しい話などで出典から書いた件なら、目で確かめる）")
        return 2
    for commit, path, footnote, heading in items:
        try:
            sources.append(read_source(commit, path, footnote, heading))
            print(f"  写し元：{sources[-1][0]}（{'submodule' if path.startswith('database/') else commit}）を読んだ")
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"  写し元：{path} を読めない — {e}")
            return 2
    status = 0
    targets = [(f"出来事 {i}", t) for i, t in enumerate(entry["events"], 1)]
    if entry["note"]:
        targets.append(("要確認", entry["note"]))
    for label, text in targets:
        print(f"  {label}")
        for s in sentences(text):
            hit = next((name for name, src in sources if s in src), None)
            if hit:
                print(f"    一致　　：「{s}」 — {hit}")
                continue
            status = 1
            ratio, name, cand = closest(s, sources)
            print(f"    違いあり：「{s}」")
            if cand:
                print(f"      いちばん近い写し元：{name}（正本の文の {ratio:.0%} が一致）")
                print(f"      違い：{show_diff(cand, s)}")
            else:
                print("      近い文が写し元に無い")
    for label, body in entry["subs"]:
        if label not in ID_IN_SUB:
            continue
        person = re.search(r"`C-([a-z-]+)`", body)
        for i in re.findall(ID_IN_SUB[label], body):
            where = [name for name, src in sources if re.search(rf"(?<![\w-]){re.escape(i)}(?![\d-])", src)]
            who = f"{label}（{person.group(1)}）の {i}" if person else f"{label} の {i}"
            # 知識表・人物の掘り下げの脚注は 1 人 1 つ（[^K4-akai-shuichi] など）なので、まず本人の脚注を探す
            own = f"[^{i.split('-')[0]}-{person.group(1)}]" if person and label in ("知識", "描写") else None
            if own and any(own in name for name in where):
                print(f"  {who}：本人の脚注に出てくる — {next(n for n in where if own in n)}")
            elif where:
                note = f"（本人の脚注 {own} ではない。共有の脚注なら問題ない）" if own else ""
                print(f"  {who}：写し元に出てくる — {where[0]}{note}")
            else:
                status = 1
                print(f"  {who}：写し元に出てこない（ラベルの下には、写し元が根拠にしているものだけを書く）")
    return status


def event_texts(entries):
    """件の見出し・出典・「出来事」の 1 段目・要確認を、(場所の名前, 文字列) の並びにする。"""
    out = []
    for eid, e in entries.items():
        out += [(f"{eid} 見出し", e["title"]), (f"{eid} 出典", e["origin"])]
        out += [(f"{eid} 出来事 {i}", t) for i, t in enumerate(e["events"], 1)]
        if e["note"]:
            out.append((f"{eid} 要確認", e["note"]))
    return [(name, text) for name, text in out if text]


def trim_paren(s):
    """「。」で区切ったために文の端に残った、対になっていない括弧（「（要確認：…。…）」の「（」「）」）を外す。"""
    if s.endswith("）") and s.count("）") > s.count("（"):
        s = s[:-1]
    if s.startswith("（") and s.count("（") > s.count("）"):
        s = s[1:]
    return s


def changed_lines(commit, path):
    """<commit> の時点の data/<path> にあって、今のファイルの同じ場所に無い行を [(場所, 行の中身, 今の同じ場所の中身)] で返す。

    脚注の行（[^…]:）は脚注 ID を場所にし、今の同じ脚注と比べる。ほかの行（relationships の経緯の項目など）は、
    その上の見出し（### 以下の深さ。「### 羽田浩司 × 浅香… > 経緯」）を場所にし、今の同じ節で書き換わった行と比べる。
    行は (場所, 行) の組で比べる。同じ行がほかの節にもある（relationships の 2 つのペアの経緯に同じ項目がある
    など）ので、ファイル全体で比べると、片方の節だけで消した行を見逃す。見出しを変えた節の行は、すべて消えた行になる。
    """
    def sections(lines):
        """[(場所, 行)]。脚注の行は脚注 ID、ほかの行は上の見出しを場所にする。"""
        out, stack = [], {}
        for ln in lines:
            if m := re.match(r"(#{1,6}) (.+)", ln):
                level = len(m.group(1))
                stack = {lv: t for lv, t in stack.items() if lv < level}
                stack[level] = m.group(2).strip()
            elif m := re.match(r"\[\^([^\]]+)\]:", ln):
                out.append((f"[^{m.group(1)}]", ln[m.end():].strip(), ln))
            elif ln.strip():
                deep = [t for lv, t in sorted(stack.items()) if lv >= 3] or [t for _, t in sorted(stack.items())[-1:]]
                out.append((f"「{' > '.join(deep) or 'ファイルの頭'}」", re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", ln), ln))
        return out

    old = sections(git_show(commit, path).splitlines())
    new = sections((DATA / path).read_text(encoding="utf-8").splitlines())
    old_set, new_set = {(place, ln) for place, _, ln in old}, {(place, ln) for place, _, ln in new}
    # 今のファイルで、その場所に書き換わった（commit の時点の同じ場所に無かった）行。脚注は今の同じ脚注そのもの
    current = {}
    for place, body, ln in new:
        if place.startswith("[^"):
            current[place] = body
        elif (place, ln) not in old_set:
            current[place] = "\n".join(filter(None, [current.get(place), body]))
    return [(place, body, current.get(place, "")) for place, body, ln in old if (place, ln) not in new_set]


def check_removed(commit, paths):
    """<commit> の時点から今までに消えた文が、どれかの件か、今のファイルにあるかを調べる。

    根拠を出来事の ID に置き換えたときに、消した文の中身が正本に移っているかを確かめるためのもの。
    1 文ずつ、今のファイルに残っていれば数えるだけにし、残っていなければ、件（見出し・出典・出来事の 1 段目・
    要確認）にそのままあるか（一致）、近い文があるか（違いあり）、どちらでもないか（見つからない）を出す。
    """
    texts = event_texts(load_entries())
    status = 0
    for path in paths:
        try:
            units = changed_lines(commit, path)
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"{path} を読めない — {e}")
            status = 2
            continue
        print(f"{path}（{commit} の時点と今の比較）")
        if not units:
            print("  消えた行は無い")
        for place, body, current in units:
            sents = [trim_paren(s) for s in sentences(body)]
            # 今の同じ場所とだけ比べる（同じ言い回しがほかの脚注・項目にもあるので、ファイル全体では比べない）。
            # ほかの場所へ移した文は「見つからない」になるので、目で確かめる
            gone = [s for s in sents if s not in current]
            where = "今の同じ脚注" if place.startswith("[^") else "今の同じ節"
            print(f"  {place}：{len(sents)} 文のうち、{where}に残っている文 {len(sents) - len(gone)}")
            cands = texts + ([(f"今の {place}", current)] if current else [])
            for s in gone:
                hit = next((name for name, t in texts if s in t), None)
                if hit:
                    print(f"    一致　　　　：「{s}」 — {hit}")
                    continue
                status = max(status, 1)
                ratio, name, cand = closest(s, cands)
                if cand and ratio >= 0.5:
                    print(f"    違いあり　　：「{s}」")
                    print(f"      いちばん近い文：{name}（消えた文の {ratio:.0%} が一致）")
                    print(f"      違い：{show_diff(s, cand)}")
                else:
                    print(f"    見つからない：「{s}」")
                    if cand:
                        print(f"      いちばん近い文：{name}（消えた文の {ratio:.0%} が一致）")
        print()
    return status


def load_table(path):
    """知識表・人物の掘り下げの表（data/<path>）を読み、(列 ID の並び, コナンの把握の列 ID, 行, 脚注) を返す。

    行は {脚注 ID: [(人物 ID, {列 ID: 記号})]}、脚注は {脚注 ID: 本文}。1 本の脚注を何行かで共有しているときも、
    1 行に何人もいるとき（少年探偵団など）も、全員を並べる。コナンの把握の列は、列の定義の表で「コナンが把握」を
    含む行から読む（表ごとに番号が違う。人物の掘り下げには無いので None）。
    """
    cols, conan, rows, notes = [], None, {}, {}
    for line in (DATA / path).read_text(encoding="utf-8").splitlines():
        if m := re.match(r"\[\^([^\]]+)\]: (.+)", line):
            notes[m.group(1)] = m.group(2)
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip()[1:-1].split("|")]
        if len(cells) == 2 and re.fullmatch(r"K\d-\d+", cells[0]) and "コナンが把握" in cells[1]:
            conan = cells[0]
        elif cells[0] == "人物":
            cols = [c.split()[0] for c in cells[1:-1]]
        elif cols and (m := re.fullmatch(r"\[\^([^\]]+)\]", cells[-1])):
            for cid in re.findall(r"`(C-[a-z-]+)`", cells[0]):
                rows.setdefault(m.group(1), []).append((cid, dict(zip(cols, cells[1:-1]))))
    return cols, conan, rows, notes


def top_parens(text):
    """いちばん外側の括弧（（…））の (始め, 終わり) を並べて返す。閉じていない括弧は数えない。"""
    spans, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == "（":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "）" and depth:
            depth -= 1
            if depth == 0:
                spans.append((start, i + 1))
    return spans


def split_sentences(text):
    """「。」で区切る（区切りの「。」は落とす）。括弧（（…））の中の「。」では区切らない。空の文は除く。"""
    spans = top_parens(text)
    out, start = [], 0
    for i, ch in enumerate(text):
        if ch == "。" and not any(a < i < b for a, b in spans):
            out.append(text[start:i])
            start = i + 1
    out.append(text[start:])
    return [s.strip() for s in out if s.strip()]


def expand_cols(spec):
    """「K1-1〜K1-3・K1-6」のような列の書き方を、["K1-1", "K1-2", "K1-3", "K1-6"] にする。"""
    return [f"{m.group(1)}-{n}" for m in COL_RANGE.finditer(spec)
            for n in range(int(m.group(2)), int(m.group(3) or m.group(2)) + 1)]


def check_cited(paths):
    """脚注が根拠に挙げた件に、その脚注の行の人物の知識（人物の掘り下げでは描写）があるかを調べる。

    脚注の文のうち、その表の列 ID で始まるもの（「K1-4・K1-5 は E-429-03 による」）だけを見る。見るのは、
    知識表では `◎`・`〇`、人物の掘り下げでは `◎`・`〇`・`△` のセル（`†` 付きを含む）だけ。「コナンの把握」の列と、
    「直した」を含む括弧（直した履歴）の中の件は見ない。2 列以上・2 件以上を 1 文で書いたものは、どの列がどの件かが
    わからないので、どの件にもどれかの列があるか、どの列もどれかの件にあるかだけを見る。
    「コナンの把握」の理由の文（「K1-3 は A：…」）から出たものは参考の段に出し、終了コードに数えない。
    知識表では、件の「場面にいた人物」にいない人に、そのことを添える（人の話から推した根拠なら、知識が無くてよい）。
    """
    entries = load_entries()
    have = {}  # 件 ID → {(人物 ID, 列 ID)}。知識は 4 段目の人、描写は 3 段目の人
    for eid, e in entries.items():
        for label, body in e["subs"]:
            if label in ("知識", "描写") and (who := re.search(r"`(C-[a-z-]+)`", body)):
                have.setdefault(eid, set()).update((who.group(1), i) for i in re.findall(ID_IN_SUB[label], body))
    status = 0
    for path in paths:
        try:
            cols, conan, rows, notes = load_table(path)
        except OSError as e:
            print(f"{path} を読めない — {e}")
            status = 2
            continue
        if not cols:
            print(f"{path}：人物の表（| 人物 | … | 根拠 |）が無い")
            status = 2
            continue
        table = cols[0].rsplit("-", 1)[0]  # K1・P1 など
        label = "知識" if table.startswith("K") else "描写"
        marks = ("◎", "〇") if label == "知識" else ("◎", "〇", "△")

        def absent(cid, eid):
            """知識表で、件の「場面にいた人物」にその人がいなければ、そのことを添える（描写は、その場にいなくても書く）。"""
            present = entries[eid]["present"]
            return "（場面にいた人物にもいない）" if label == "知識" and present and f"`{cid}`" not in present else ""

        found = {"本文": [], "参考": []}
        n_sent = n_ref = 0
        for fid, body in notes.items():
            for s in split_sentences(body):
                m = re.match(rf"({table}-\d+(?:[・〜]{table}-\d+)*) は(.*)", s)
                if not m or fid not in rows:
                    continue
                ks = [k for k in expand_cols(m.group(1)) if k in cols and k != conan]
                rest = m.group(2)
                for a, b in reversed(top_parens(rest)):
                    if "直した" in rest[a:b]:
                        rest = rest[:a] + rest[b:]
                eids = list(dict.fromkeys(re.findall(E_ID, rest)))
                if not ks or not eids:
                    continue
                ref = bool(conan) and bool(re.match(r"\s*(?:[A-D]|未確認)(?:（[^）]*）)?：", m.group(2)))
                cited = [e for e in eids if e in entries]
                strict = len(ks) == 1 or len(eids) == 1
                msgs, checked = [], False
                for cid, cells in rows[fid]:
                    use = [k for k in ks if cells.get(k, "").rstrip("†") in marks]
                    if not use:
                        continue
                    checked = True
                    who = cid[2:]
                    if strict:
                        msgs += [f"{who} の {k}（{cells[k]}）：{e} の「{label}」に無い{absent(cid, e)}"
                                 for k in use for e in cited if (cid, k) not in have.get(e, ())]
                    else:
                        msgs += [f"{who} の {'・'.join(use)}：{e} の「{label}」にどれも無い{absent(cid, e)}"
                                 for e in cited if not any((cid, k) in have.get(e, ()) for k in use)]
                        msgs += [f"{who} の {k}（{cells[k]}）：{'・'.join(cited)} のどの「{label}」にも無い"
                                 for k in use if cited and not any((cid, k) in have.get(e, ()) for e in cited)]
                if not checked:
                    continue
                n_sent += 1
                n_ref += ref
                msgs += [f"{e}：events/ に無い" for e in eids if e not in entries]
                if msgs:
                    found["参考" if ref else "本文"].append((fid, s, msgs))
        print(f"{path}（脚注が根拠に挙げた件に、その行の人物の{label}があるか）")
        print(f"  見た文：{n_sent}" + (f"（うち「コナンの把握」の理由の文 {n_ref}）" if conan else ""))
        parts = [("本文", "無い")]
        if conan:
            parts.append(("参考", "参考（「コナンの把握」の理由の文から出たもの。コナンが気づく・思い出すだけの場面なら、知識が無くてよい）"))
        for part, title in parts:
            print(f"  {title}：{sum(len(msgs) for _, _, msgs in found[part])}")
            for fid, s, msgs in found[part]:
                print(f"    [^{fid}]「{s}」")
                for msg in msgs:
                    print(f"      {msg}")
        print()
        if found["本文"]:
            status = max(status, 1)
    return status


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")  # argparse のエラー
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="確かめる件の ID（E-1106-01 など）")
    parser.add_argument("--all", action="store_true", help="すべての件を確かめる")
    parser.add_argument("--removed", nargs="+", metavar=("COMMIT", "PATH"),
                        help="COMMIT の時点から今までに PATH（data/ からのパス）で消えた文が、件か今のファイルにあるかを調べる")
    parser.add_argument("--cited", nargs="*", metavar="PATH",
                        help="PATH（data/ からのパス。書かなければ knowledge-matrix/0*.md と profiles/0*.md のすべて）の"
                             "脚注が根拠に挙げた件に、その行の人物の知識（描写）があるかを調べる")
    args = parser.parse_args()

    if args.removed:
        if len(args.removed) < 2:
            parser.error("--removed にはコミットと、data/ からのパスを 1 つ以上書く")
        return check_removed(args.removed[0], args.removed[1:])
    if args.cited is not None:
        return check_cited(args.cited or [p.relative_to(DATA).as_posix() for d in ("knowledge-matrix", "profiles")
                                          for p in sorted((DATA / d).glob("0*.md"))])
    entries = load_entries()
    ids = list(entries) if args.all else args.ids
    if not ids:
        parser.print_help()
        return 2
    status = 0
    for eid in ids:
        if eid not in entries:
            print(f"{eid}：events/ に無い")
            status = 2
            continue
        status = max(status, check(eid, entries[eid]))
        print()
    return status


if __name__ == "__main__":
    sys.exit(main())
