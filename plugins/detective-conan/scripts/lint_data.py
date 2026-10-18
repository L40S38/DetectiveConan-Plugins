#!/usr/bin/env python3
"""data/ 以下のデータの整合性をチェックする（標準ライブラリのみ）。

チェック内容:
  1. ID の重複（伏線 F・考察 Q・人物 C・知識表の列 K・人物の掘り下げの列 P）
  2. F・Q・K・P・C の参照が、実在する ID を指しているか
  3. 脚注の参照と定義が対応しているか
  4. foreshadowing/README.md の一覧表と foreshadowing/0*.md の詳細で、タイトル・状態・重要度が一致しているか
  5. F・Q のタイトルが問いの形で、答えの書き方（「＝」など）が入っていないか（警告のみ。最終確認は目で行う）
  6. Markdown の表で、どの行も列数がそろっているか
  7. 知識表のセルが決められた値だけか。右端が「コナンの把握」の列か。グループ見出しが characters.md の
     グループと同じ順にそろっているか。characters.md の全員が、そのグループの個別の行かまとめ行に
     1 回ずつ、characters.md の順に出てくるか。まとめ行がグループの最後にあるか。
     人物の掘り下げ（profiles/0*.md）の表も同じ規則で見る（「コナンの把握」の列は無く、まとめ行はすべて `0`）
  8. File 表記が conventions.md の 3.1 の形か（database にある話は巻・事件名、無い話は掲載号。1 話なら話タイトルも。警告のみ）

使い方:
    python lint_data.py [--data PATH]

エラーが 1 件でもあれば終了コード 1 を返す。警告だけなら 0。
"""
import argparse
import io
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data"

F_ID = r"F-[A-Z]+-\d{3}"
Q_ID = r"Q-\d{3}"
K_ID = r"K\d-\d+"
P_ID = r"P\d-\d+"
C_ID = r"C-[a-z]+(?:-[a-z]+)*"

CELL_VALUES = {"◎", "〇", "△", "✕", "ー", "?"}
PROFILE_VALUES = {"3", "2", "1", "0", "ー", "?"}
STATUS_VALUES = {"回収済", "部分回収", "未回収", "ミスリード判明"}

# 物語の前提そのものなので、タイトルに含まれていても答えではない表現
TITLE_ALLOWED = ["コナン＝新一"]


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, path, msg):
        self.errors.append(f"[ERROR] {path}: {msg}")

    def warn(self, path, msg):
        self.warnings.append(f"[WARN]  {path}: {msg}")


def split_row(line):
    """Markdown の表の 1 行をセルに分ける（前後の | を除く）。"""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip() for c in body.split("|")]


def iter_tables(text):
    """(開始行番号, 行のリスト) を表ごとに返す。コードブロックの中は無視する。"""
    table, start, in_code = [], None, False
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code and line.strip().startswith("|"):
            if not table:
                start = i
            table.append(line)
        else:
            if table:
                yield start, table
            table = []
    if table:
        yield start, table


def strip_code(text):
    """コードブロック（書式の例）を参照チェックの対象から外す。"""
    return re.sub(r"```.*?```", "", text, flags=re.S)


def collect_definitions(data, rep):
    defs = {"F": [], "Q": [], "C": [], "K": [], "P": []}
    for p in sorted((data / "foreshadowing").glob("0*.md")):
        text = strip_code(p.read_text(encoding="utf-8"))
        defs["F"] += re.findall(rf"^### ({F_ID}) ", text, flags=re.M)
    oq = (data / "open-questions.md").read_text(encoding="utf-8")
    defs["Q"] = re.findall(rf"^### ({Q_ID}) ", oq, flags=re.M)
    ch = (data / "characters.md").read_text(encoding="utf-8")
    defs["C"] = re.findall(rf"^#### ({C_ID}) ", strip_code(ch), flags=re.M)
    for p in sorted((data / "knowledge-matrix").glob("0*.md")):
        text = p.read_text(encoding="utf-8")
        defs["K"] += re.findall(rf"^\| ({K_ID}) \|", text, flags=re.M)
    for p in sorted((data / "profiles").glob("0*.md")):
        text = p.read_text(encoding="utf-8")
        defs["P"] += re.findall(rf"^\| ({P_ID}) \|", text, flags=re.M)
    for kind, ids in defs.items():
        for i, n in Counter(ids).items():
            if n > 1:
                rep.error("data", f"{kind} の ID {i} が {n} 回定義されている")
    return {k: set(v) for k, v in defs.items()}


def check_references(data, defs, rep):
    tables = {int(k[1]) for k in defs["K"]}
    for p in sorted(data.rglob("*.md")):
        text = strip_code(p.read_text(encoding="utf-8"))
        rel = p.relative_to(data)
        for m in re.finditer(F_ID, text):
            if m.group() not in defs["F"]:
                rep.error(rel, f"存在しない伏線 {m.group()} を参照している")
        for m in re.finditer(Q_ID, text):
            if m.group() not in defs["Q"]:
                rep.error(rel, f"存在しない考察 {m.group()} を参照している")
        for m in re.finditer(rf"(?<![\w^]){K_ID}", text):
            if m.group() not in defs["K"]:
                rep.error(rel, f"存在しない知識表の列 {m.group()} を参照している")
        for m in re.finditer(r"(?<![\w^\-])K(\d)(?![\d-])", text):
            if int(m.group(1)) not in tables:
                rep.error(rel, f"存在しない知識表 K{m.group(1)} を参照している")
        for m in re.finditer(rf"(?<![\w^]){P_ID}", text):
            if m.group() not in defs["P"]:
                rep.error(rel, f"存在しない人物の掘り下げの列 {m.group()} を参照している")
        for m in re.finditer(rf"(?<![\w-]){C_ID}", text):
            if m.group() not in defs["C"]:
                rep.error(rel, f"存在しない人物 {m.group()} を参照している")


def check_footnotes(data, rep):
    for p in sorted(data.rglob("*.md")):
        # インラインコード（`[^K1-mori-ran]` のような書式の例）は脚注として扱わない
        text = re.sub(r"`[^`]*`", "", strip_code(p.read_text(encoding="utf-8")))
        rel = p.relative_to(data)
        defined = re.findall(r"^\[\^([^\]]+)\]:", text, flags=re.M)
        refs = re.findall(r"\[\^([^\]]+)\](?!:)", text)
        for d, n in Counter(defined).items():
            if n > 1:
                rep.error(rel, f"脚注 [^{d}] が {n} 回定義されている")
        for r in set(refs) - set(defined):
            rep.error(rel, f"脚注 [^{r}] の定義がない")
        for d in set(defined) - set(refs):
            rep.error(rel, f"脚注 [^{d}] がどこからも参照されていない")


def check_tables(data, rep):
    for p in sorted(data.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(data)
        for start, rows in iter_tables(text):
            width = len(split_row(rows[0]))
            for offset, row in enumerate(rows):
                n = len(split_row(row))
                if n != width:
                    rep.error(rel, f"{start + offset} 行目: 表の列数が {n}（見出しは {width}）")


def check_foreshadowing(data, rep):
    """伏線データは data/foreshadowing/README.md（一覧表）と
    data/foreshadowing/0*.md（分類ごとの詳細）に分かれている。両者の整合性を見る。"""
    fs_dir = data / "foreshadowing"
    index_rel = Path("foreshadowing") / "README.md"
    text = (fs_dir / "README.md").read_text(encoding="utf-8")
    index = {}
    for _, rows in iter_tables(text):
        header = split_row(rows[0])
        if header[:4] == ["ID", "タイトル", "状態", "重要度"]:
            for row in rows[2:]:
                cells = split_row(row)
                # 1 セル目は "[F-ORG-001](01-org.md#F-ORG-001)" の形なので ID を取り出す
                m = re.search(rf"({F_ID})", cells[0])
                if m:
                    index[m.group(1)] = (cells[1], cells[2], cells[3])

    details = {}
    detail_file = {}
    for p in sorted(fs_dir.glob("0*.md")):
        rel = Path("foreshadowing") / p.name
        body = strip_code(p.read_text(encoding="utf-8"))
        for m in re.finditer(rf"^### ({F_ID}) (.+)$", body, flags=re.M):
            block = body[m.end():].split("\n### ", 1)[0]
            status = re.search(r"^- 状態: (.+)$", block, flags=re.M)
            weight = re.search(r"^- 重要度: (.+)$", block, flags=re.M)
            fid = m.group(1)
            if fid in details:
                rep.error(rel, f"{fid} が複数ファイルに定義されている（{detail_file[fid]} と重複）")
            details[fid] = (
                m.group(2).strip(),
                status.group(1).strip() if status else None,
                weight.group(1).strip() if weight else None,
            )
            detail_file[fid] = rel

    for fid in sorted(set(index) | set(details)):
        if fid not in index:
            rep.error(index_rel, f"{fid} が一覧表に無い")
            continue
        if fid not in details:
            rep.error(index_rel, f"{fid} の詳細が無い")
            continue
        rel = detail_file[fid]
        (it, ist, iw), (dt, dst, dw) = index[fid], details[fid]
        if it != dt:
            rep.error(rel, f"{fid} のタイトルが一覧表と詳細で違う（{it} / {dt}）")
        if ist != dst:
            rep.error(rel, f"{fid} の状態が一覧表と詳細で違う（{ist} / {dst}）")
        if iw != dw:
            rep.error(rel, f"{fid} の重要度が一覧表と詳細で違う（{iw} / {dw}）")
        if dst not in STATUS_VALUES:
            rep.error(rel, f"{fid} の状態「{dst}」は決められた値ではない")
    return details


def check_titles(data, fs_details, rep):
    titles = {fid: t for fid, (t, _, _) in fs_details.items()}
    oq = (data / "open-questions.md").read_text(encoding="utf-8")
    for m in re.finditer(rf"^### ({Q_ID}) (.+)$", oq, flags=re.M):
        titles[m.group(1)] = m.group(2).strip()
    for tid, title in titles.items():
        t = title
        for ok in TITLE_ALLOWED:
            t = t.replace(ok, "")
        if "＝" in t or "=" in t:
            rep.warn("titles", f"{tid}「{title}」に「＝」がある。答えを書いていないか確認する")
        if not re.search(r"(か|？|\?)(（[^）]*）)?(\s*`\[[^\]]+\]`)?$", title):
            rep.warn("titles", f"{tid}「{title}」が問いの形で終わっていない。答えを書いていないか確認する")


def load_character_groups(data):
    """characters.md の (b) 人物カードから {人物 ID: グループ名} を作る。"""
    text = strip_code((data / "characters.md").read_text(encoding="utf-8"))
    body = text.split("## (b) 人物カード", 1)[1].split("\n## ", 1)[0]
    groups, group = {}, None
    for line in body.splitlines():
        if m := re.match(r"^### (.+)$", line):
            group = m.group(1).strip()
        elif m := re.match(rf"^#### ({C_ID}) ", line):
            groups[m.group(1)] = group
    return groups


def check_knowledge_cells(data, rep):
    check_person_tables(data, rep, "knowledge-matrix", CELL_VALUES, blank="✕", conan=True)


def check_profile_cells(data, rep):
    check_person_tables(data, rep, "profiles", PROFILE_VALUES, blank="0", conan=False)


def check_person_tables(data, rep, subdir, cell_values, blank, conan):
    """人物を行にした表（知識表・人物の掘り下げ）の値・行の並び・まとめ行を見る。

    blank はまとめ行に入れる人物の値（知識表は `✕`、人物の掘り下げは `0`）。
    conan が真なら、根拠の左に「コナンの把握」の列がある表として見る。
    """
    groups = load_character_groups(data)
    order = {cid: i for i, cid in enumerate(groups)}
    group_order = list(dict.fromkeys(groups.values()))
    for p in sorted((data / subdir).glob("0*.md")):
        rel = p.relative_to(data)
        text = p.read_text(encoding="utf-8")
        for start, rows in iter_tables(text):
            header = split_row(rows[0])
            if header[-1] != "根拠":
                continue
            if conan and "コナンの把握" not in header[-2]:
                rep.error(rel, f"{start} 行目: 根拠の左の列が「コナンの把握」になっていない")
            seen, group, headings = Counter(), None, []
            last, summary_line = -1, None
            for offset, row in enumerate(rows[2:], 2):
                line = start + offset
                cells = split_row(row)
                values = cells[1:-1]
                body = values[:-1] if conan else values  # 「コナンの把握」以外の列
                m = re.fullmatch(r"\*\*(.+)\*\*", cells[0])
                if m and not any(cells[1:]):
                    group = m.group(1)  # グループ見出しの行
                    headings.append(group)
                    last, summary_line = -1, None
                    continue
                if summary_line:
                    rep.error(rel, f"{line} 行目: まとめ行（{summary_line} 行目）の後に行がある（まとめ行はグループの最後に置く）")
                ids = re.findall(C_ID, cells[0])
                if not ids:
                    rep.error(rel, f"{line} 行目: 人物 ID が無い（{cells[0]}）")
                seen.update(ids)
                for cid in ids:
                    if cid in groups and groups[cid] != group:
                        rep.error(rel, f"{line} 行目: {cid} は characters.md では「{groups[cid]}」のグループ")
                pos = [order[cid] for cid in ids if cid in order]
                if cells[0].startswith("ほかの"):
                    # グループ内の残り全員をまとめた行
                    summary_line = line
                    if not cells[0].startswith(f"ほかの「{group}」："):
                        rep.error(rel, f"{line} 行目: まとめ行は「ほかの「{group}」：」で始める")
                    if conan and (not values or any(v != blank for v in body) or values[-1] != "ー"):
                        rep.error(rel, f"{line} 行目: まとめ行は「コナンの把握」を `ー`、ほかの列をすべて `{blank}` にする")
                    if not conan and (not values or any(v != blank for v in body)):
                        rep.error(rel, f"{line} 行目: まとめ行はすべての列を `{blank}` にする")
                    if pos != sorted(pos):
                        rep.error(rel, f"{line} 行目: まとめ行の名前が characters.md の順になっていない")
                    continue
                if pos and (pos[0] < last or pos != sorted(pos)):
                    rep.error(rel, f"{line} 行目: {ids[0]} の行が characters.md の順になっていない（グループの中の個別の行は characters.md の順に並べる）")
                if pos:
                    last = pos[-1]
                for h, cell in zip(header[1:-1], values):
                    if cell.rstrip("†") not in cell_values:
                        rep.error(rel, f"{line} 行目 {h}: 値「{cell}」は決められた値ではない")
                # ✕† や 0† は根拠（正史外）を残すため「まとめ行の値以外」として扱い、個別の行に置く
                if all(v == blank for v in body):
                    who = "「コナンの把握」以外" if conan else "すべての列"
                    rep.error(rel, f"{line} 行目: {who}が `{blank}`（`†` なし）の人物は、まとめ行に入れる")
            if headings != group_order:
                missing = [g for g in group_order if g not in headings]
                extra = [h for h in headings if h not in group_order]
                if missing:
                    rep.error(rel, f"{start} 行目の表: グループ見出しが無い（{'、'.join(missing)}）")
                if extra:
                    rep.error(rel, f"{start} 行目の表: characters.md に無いグループ見出しがある（{'、'.join(extra)}）")
                if not missing and not extra:
                    rep.error(rel, f"{start} 行目の表: グループ見出しの順番が characters.md と違う（または重複している）")
            for cid in groups:
                if not seen[cid]:
                    rep.error(rel, f"{cid} がどの行にも無い（個別の行かまとめ行に入れる）")
            for cid, n in seen.items():
                if n > 1:
                    rep.error(rel, f"{cid} が {n} 行に出てくる")


FILE_REF = re.compile(r"File (\d+)(–\d+)?")
FILE_WHERE = r"（(?:\d+(?:・\d+)*巻「[^「」\n]+」|単行本未収録／サンデー[^）\n]+)）"
# 単行本未収録の範囲は「File 1163「題」〜File 1166「題」（単行本未収録／…）」と書くので、題の後に「〜File」が続く形も認める
FILE_SINGLE_OK = re.compile(r"「[^「」\n]+」(?:" + FILE_WHERE + r"|〜File )")
FILE_RANGE_OK = re.compile(FILE_WHERE)


def check_file_refs(data, rep):
    # conventions.md は書式の説明、sources.md は検索語の例なので対象外
    for p in sorted(data.rglob("*.md")):
        if p.name in ("conventions.md", "sources.md"):
            continue
        text = strip_code(p.read_text(encoding="utf-8"))
        rel = p.relative_to(data)
        for m in FILE_REF.finditer(text):
            ok = FILE_RANGE_OK if m.group(2) else FILE_SINGLE_OK
            if not ok.match(text, m.end()):
                snippet = text[m.start():m.end() + 20].split("\n")[0]
                rep.warn(rel, f"「{snippet}」が File の書き方になっていない（database にある話は巻・事件名、無い話は掲載号。1 話なら話タイトルも。conventions.md の 3.1）")


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()

    rep = Report()
    defs = collect_definitions(args.data, rep)
    check_references(args.data, defs, rep)
    check_footnotes(args.data, rep)
    check_tables(args.data, rep)
    fs_details = check_foreshadowing(args.data, rep)
    check_titles(args.data, fs_details, rep)
    check_knowledge_cells(args.data, rep)
    check_profile_cells(args.data, rep)
    check_file_refs(args.data, rep)

    for line in rep.errors + rep.warnings:
        print(line)
    print(
        f"\n伏線 {len(defs['F'])} 件／考察 {len(defs['Q'])} 件／人物 {len(defs['C'])} 件／"
        f"知識表の列 {len(defs['K'])} 件／人物の掘り下げの列 {len(defs['P'])} 件 — エラー {len(rep.errors)} 件、警告 {len(rep.warnings)} 件"
    )
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
