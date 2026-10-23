#!/usr/bin/env python3
"""data/ 以下のデータの整合性をチェックする（標準ライブラリのみ）。

チェック内容:
  1. ID の重複（伏線 F・考察 Q・人物 C・知識表の列 K・人物の掘り下げの列 P・グループ G）
  2. F・Q・K・P・C・G の参照が、実在する ID を指しているか
  3. 脚注の参照と定義が対応しているか
  4. foreshadowing/README.md の一覧表と foreshadowing/0*.md の詳細で、タイトル・状態・重要度が一致しているか
  5. F・Q のタイトルが問いの形で、答えの書き方（「＝」など）が入っていないか（警告のみ。最終確認は目で行う）
  6. Markdown の表で、どの行も列数がそろっているか
  7. 知識表のセルが決められた値だけか。右端が「コナンの把握」の列か。グループ見出しが characters.md の
     グループと同じ順にそろっているか。characters.md の全員が、そのグループの個別の行かまとめ行に
     1 回ずつ、characters.md の順に出てくるか。まとめ行がグループの最後にあるか。
     人物の掘り下げ（profiles/0*.md）の表も同じ規則で見る（記号は同じ。「コナンの把握」の列は無く、まとめ行はすべて `✕`）
  8. File 表記が conventions.md の 3.1 の形か（database にある話は巻・事件名、無い話は掲載号。1 話なら話タイトルも。警告のみ）
  9. 出来事の正本（events/ 以下）の書き方（conventions.md の 11.・events/README.md）。ID の形と重複、
     ファイルとグループ（##）の ID の頭の対応、略号が略号の表にあるか、欄の名前・順番・必須の欄、
     欄の中身が空でないか、写し元の行ごとのコミット（写し元だけは、コミットごとに 2 行以上書ける）、
     区分・時期の値、「出来事」のラベル（知識・関係・伏線・描写・生死）と、その下の項目の書き方。ほかのファイルから参照している出来事の ID（E-…）と、件の中のグループの
     ID（G-…）が実在するかは 2. で見る
  10. 知識表で、knowledge-matrix/README.md の「経路の一覧」の伝える人が `◎`・`〇`・`ー`・`?` の列なのに、
      受け取る人が `✕` になっていて、「経路の例外」にも書いていないセルがないか（警告のみ）

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
G_ID = r"G-[a-z]+(?:-[a-z]+)*"
# 出来事。原作は数字（事件の先頭 File）、劇場版は M、アニオリは A、まじっく快斗・その他は X で始まる（conventions.md の 11.2）
E_ID = r"E-(?:\d+|M\d+|A\d+|[MAX][A-Z]+\d*)-\d{2,3}"
# 日本語の文字は \w に入るので、前後は ASCII だけで区切る（「根拠はE-1106-01」のような書き方も拾う）
E_LOOSE = re.compile(r"(?<![A-Za-z0-9_-])E-[A-Z0-9]+-\d+(?![0-9A-Za-z-])")

CELL_VALUES = {"◎", "〇", "△", "✕", "ー", "?"}
STATUS_VALUES = {"回収済", "部分回収", "未回収", "ミスリード判明"}

# 物語の前提そのものなので、タイトルに含まれていても答えではない表現
TITLE_ALLOWED = ["コナン＝新一"]

# 出来事の正本：ファイルの種類ごとの区分タグと、グループ（##）の ID の頭（E- から連番の前まで）の形
EVENT_KINDS = {
    "manga": ({"[原作]"}, r"\d+"),
    "movies": ({"[劇場版]"}, r"M(?:\d+|[A-Z]+)"),
    "anime": ({"[アニオリ]", "[TVSP]"}, r"A(?:\d+|[A-Z]+\d*)"),
    "magic-kaito": ({"[まじっく快斗]"}, r"XMK\d+"),
    "other": ({"[スピンオフ]"}, r"X(?!MK\d)[A-Z]+\d*"),
}
# 1 件の欄（この順に書く）と、必須の欄
EVENT_FIELDS = ["区分", "出典", "時期", "場面にいた人物", "出来事", "関わる ID", "要確認", "写し元"]
EVENT_REQUIRED = ["区分", "出典", "時期", "出来事", "写し元"]
# 写し元はコミットごとに 1 行なので、2 行以上書いてよい（ほかの欄は 1 回だけ）
EVENT_REPEATABLE = {"写し元"}
EVENT_LABELS = ["知識", "関係", "伏線", "描写", "生死"]
KNOW_HOW = ["見た", "聞いた", "推理した", "疑った", "既知"]
FS_ROLES = ["初出", "経過", "回収"]
LIFE_VALUES = ["死ぬ", "死んだように見せかける"]
# 参照チェックで、出来事の ID が実在しなくてよいファイル（ID の形の例を書いている）
E_REF_EXAMPLES = {"conventions.md", "events/README.md"}


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
    defs = {"F": [], "Q": [], "C": [], "K": [], "P": [], "G": [], "E": []}
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
    for p in sorted((data / "relationships").glob("*.md")):
        # グループ・家族の見出しは「### 名前 `G-…`」。「### 工藤家 × 阿笠博士 `G-…` × `C-…`」のような組の見出しは定義ではない
        text = strip_code(p.read_text(encoding="utf-8"))
        defs["G"] += re.findall(rf"^### [^`×\n]+ `({G_ID})`$", text, flags=re.M)
    for p in event_paths(data):
        text = strip_code(p.read_text(encoding="utf-8"))
        defs["E"] += re.findall(rf"^### ({E_ID}) ", text, flags=re.M)
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
        for m in re.finditer(rf"(?<![\w-]){G_ID}", text):
            if m.group() not in defs["G"]:
                rep.error(rel, f"存在しないグループ {m.group()} を参照している")
        if rel.as_posix() in E_REF_EXAMPLES:
            continue
        for m in E_LOOSE.finditer(text):
            if not re.fullmatch(E_ID, m.group()):
                rep.error(rel, f"「{m.group()}」が出来事の ID の形になっていない（conventions.md の 11.2）")
            elif m.group() not in defs["E"]:
                rep.error(rel, f"存在しない出来事 {m.group()} を参照している")


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
    check_person_tables(data, rep, "knowledge-matrix", conan=True)


def check_profile_cells(data, rep):
    check_person_tables(data, rep, "profiles", conan=False)


def check_person_tables(data, rep, subdir, conan):
    """人物を行にした表（知識表・人物の掘り下げ）の記号・行の並び・まとめ行を見る。

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
                    if conan and (not values or any(v != "✕" for v in body) or values[-1] != "ー"):
                        rep.error(rel, f"{line} 行目: まとめ行は「コナンの把握」を `ー`、ほかの列をすべて `✕` にする")
                    if not conan and (not values or any(v != "✕" for v in body)):
                        rep.error(rel, f"{line} 行目: まとめ行はすべての列を `✕` にする")
                    if pos != sorted(pos):
                        rep.error(rel, f"{line} 行目: まとめ行の名前が characters.md の順になっていない")
                    continue
                if pos and (pos[0] < last or pos != sorted(pos)):
                    rep.error(rel, f"{line} 行目: {ids[0]} の行が characters.md の順になっていない（グループの中の個別の行は characters.md の順に並べる）")
                if pos:
                    last = pos[-1]
                for h, cell in zip(header[1:-1], values):
                    if cell.rstrip("†") not in CELL_VALUES:
                        rep.error(rel, f"{line} 行目 {h}: 値「{cell}」は決められた値ではない")
                # ✕† は根拠（正史外）を残すため「✕ 以外」として扱い、個別の行に置く
                if all(v == "✕" for v in body):
                    who = "「コナンの把握」以外" if conan else "すべての列"
                    rep.error(rel, f"{line} 行目: {who}が `✕`（`†` なし）の人物は、まとめ行に入れる")
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


K_RANGE = re.compile(r"K(\d)-(\d+)(?:〜K\1-(\d+))?")


def expand_columns(text):
    """「K1-1、K2-1〜K2-6」のような列の書き方を、列 ID の集合にする。"""
    cols = set()
    for m in K_RANGE.finditer(text):
        first = int(m.group(2))
        last = int(m.group(3) or first)
        cols.update(f"K{m.group(1)}-{n}" for n in range(first, last + 1))
    return cols


def load_paths(data, rep):
    """knowledge-matrix/README.md の「伝わる経路」から、経路の一覧と例外を読む。"""
    rel = Path("knowledge-matrix/README.md")
    text = (data / rel).read_text(encoding="utf-8")
    m = re.search(r"^### 伝わる経路\n(.*?)(?=^##(?!#) |^### |\Z)", text, flags=re.M | re.S)
    if not m:
        rep.error(rel, "「### 伝わる経路」の節が無い")
        return [], set()
    paths, exceptions, names = [], set(), set()
    for _, rows in iter_tables(m.group(1)):
        header = split_row(rows[0])
        for row in rows[2:]:
            cells = split_row(row)
            if len(cells) != len(header):
                continue  # 列数の誤りは check_tables() が報告する
            if header[:3] == ["経路", "伝える人", "受け取る人"]:
                src, dsts = re.findall(C_ID, cells[1]), re.findall(C_ID, cells[2])
                if len(src) != 1 or not dsts:
                    rep.error(rel, f"経路「{cells[0]}」: 伝える人は 1 人、受け取る人は 1 人以上の人物 ID で書く")
                    continue
                paths.append((cells[0], src[0], dsts))
                names.add(cells[0])
            elif header[:3] == ["受け取る人", "表の列", "経路"]:
                if cells[2] not in names:
                    rep.error(rel, f"経路の例外: 経路「{cells[2]}」は経路の一覧に無い")
                for cid in re.findall(C_ID, cells[0]):
                    exceptions.update((cid, col, cells[2]) for col in expand_columns(cells[1]))
    return paths, exceptions


def check_paths(data, rep):
    paths, exceptions = load_paths(data, rep)
    for p in sorted((data / "knowledge-matrix").glob("0*.md")):
        rel = p.relative_to(data)
        for _, rows in iter_tables(p.read_text(encoding="utf-8")):
            header = split_row(rows[0])
            if header[-1] != "根拠":
                continue
            cols = [h.split()[0] for h in header[1:-2]]  # 「コナンの把握」と根拠を除く
            values = {}
            for row in rows[2:]:
                cells = split_row(row)
                if len(cells) != len(header):
                    continue  # 列数の誤りは check_tables() が報告する
                for cid in re.findall(C_ID, cells[0]):
                    values[cid] = dict(zip(cols, cells[1:-2]))
            for name, src, dsts in paths:
                if src not in values:
                    continue
                for dst in dsts:
                    for col in cols:
                        s, d = values[src][col].rstrip("†"), values.get(dst, {}).get(col, "").rstrip("†")
                        if s in ("◎", "〇", "ー", "?") and d == "✕" and (dst, col, name) not in exceptions:
                            rep.warn(rel, f"{col} {dst} が `✕` だが、経路「{name}」の {src} が `{values[src][col]}`（`?` にするか、README の「経路の例外」に書く）")


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


ELLIPSIS_NG = re.compile(r"…{2,}|・{2,}|･{2,}|\.{3,}")


def check_ellipsis(data, rep):
    # 三点リーダーは「…」1 字（conventions.md の 3.1）。conventions.md は決まりの説明に NG の例を書いているので対象外
    for p in sorted(data.rglob("*.md")):
        if p.name == "conventions.md":
            continue
        text = strip_code(p.read_text(encoding="utf-8"))
        rel = p.relative_to(data)
        for m in ELLIPSIS_NG.finditer(text):
            snippet = text[max(0, m.start() - 10):m.end() + 5].split("\n")[-1]
            rep.warn(rel, f"「{snippet}」の「{m.group()}」は「…」1 字にする（conventions.md の 3.1）")


def load_event_abbrevs(path):
    """events/README.md の略号の表から [(略号の正規表現, events/ からのパス)] を作る。`<…>` は数字として読む。"""
    abbrevs = []
    if not path.exists():
        return abbrevs
    for _, rows in iter_tables(path.read_text(encoding="utf-8")):
        if split_row(rows[0])[0] != "略号":
            continue
        for row in rows[2:]:
            cells = split_row(row)
            parts = re.split(r"<[^>]+>", cells[0].strip("`"))
            abbrevs.append((r"\d+".join(re.escape(x) for x in parts), cells[-1]))
    return abbrevs


def event_paths(data):
    """出来事の正本のファイル（events/ 以下の README.md 以外）。"""
    return sorted(p for p in (data / "events").rglob("*.md") if p.name != "README.md")


def event_kind(ev_rel):
    """events/ からのパスから (種類, そのファイルに置くもの) を返す。決められた名前でなければ (None, None)。

    原作の巻のファイルなら巻の番号、database に無い話（単行本未収録）のファイルなら "unpublished"、
    劇場版なら、そのファイルのグループの ID の頭（"M26"、番外編なら "MLV" など）。
    """
    if m := re.fullmatch(r"01-manga/(\d{3})\.md", ev_rel):
        return "manga", int(m.group(1))
    if ev_rel == "01-manga/unpublished.md":
        return "manga", "unpublished"
    if m := re.fullmatch(r"02-movies/(\d{2})\.md", ev_rel):
        return "movies", f"M{int(m.group(1))}"
    if m := re.fullmatch(r"02-movies/(M[A-Z]+)\.md", ev_rel):
        return "movies", m.group(1)
    return {
        "03-anime-original.md": ("anime", None),
        "04-magic-kaito.md": ("magic-kaito", None),
        "05-other.md": ("other", None),
    }.get(ev_rel, (None, None))


def check_event_group(rel, line, title, prefix, kind, span, ev_rel, abbrevs, rep):
    """グループ（##）の見出しと ID の頭とファイルが合っているかを見て、原作なら File の範囲を返す。"""
    if re.fullmatch(r"[MAX][A-Z]+\d*", prefix):
        if not any(re.fullmatch(pat, prefix) and f == ev_rel for pat, f in abbrevs):
            rep.error(rel, f"{line} 行目: 略号 {prefix} が README の略号の表に無い（ファイル {ev_rel}）")
    # 原作は、見出しの最初の巻でファイルが決まる。database に無い話（単行本未収録）は unpublished.md
    if kind == "manga":
        vol = re.search(r"（(\d+)(?:・\d+)*巻「", title)
        if span == "unpublished":
            if "単行本未収録" not in title:
                rep.error(rel, f"{line} 行目: unpublished.md には、database に無い話（単行本未収録）のグループだけを書く")
        elif not vol:
            rep.error(rel, f"{line} 行目: グループの見出しに巻が無い（database に無い話は 01-manga/unpublished.md に書く）")
        elif int(vol.group(1)) != span:
            rep.error(rel, f"{line} 行目: {vol.group(1)}巻の事件は 01-manga/{int(vol.group(1)):03d}.md に書く")
    # 劇場版は 1 作 1 ファイル。ファイル名は作品の番号（2 桁）か、番外編の略号
    if kind == "movies" and prefix != span:
        rep.error(rel, f"{line} 行目: E-{prefix} は、このファイル（E-{span}）のグループではない")
    # 番号で振るグループは、ID の頭の番号と見出しの番号をそろえる（略号だけのグループは見ない）
    numbered = {
        "manga": (r"(\d+)", r"File (\d+)(?:–(\d+))?"),
        "movies": (r"M(\d+)", r"劇場版第 (\d+) 作"),
        "anime": (r"A(\d+)", r"アニメ第 (\d+)(?:–(\d+))? 話"),
        "magic-kaito": (r"XMK(\d+)", r"(\d+)巻"),
    }
    if kind not in numbered or not (pm := re.fullmatch(numbered[kind][0], prefix)):
        return None
    m = re.search(numbered[kind][1], title)
    if not m:
        rep.error(rel, f"{line} 行目: グループの見出しに番号が無い（{numbered[kind][1]} の形）")
        return None
    if m.group(1) != pm.group(1):
        rep.error(rel, f"{line} 行目: グループの見出しの番号 {m.group(1)} と ID の頭 E-{prefix} が合わない")
    if kind == "manga":
        return int(m.group(1)), int(m.group(2) or m.group(1))
    return None


def check_event_entry(rel, entry, kind, group, rep):
    """1 件（### から次の見出しまで）の欄と「出来事」の書き方を見る。"""
    eid, line = entry["id"], entry["line"]
    tags = EVENT_KINDS[kind][0]
    names = [f[0] for f in entry["fields"]]
    for n, c in Counter(names).items():
        if c > 1 and n not in EVENT_REPEATABLE:
            rep.error(rel, f"{eid}: 欄「{n}」が {c} 回ある")
    for n in EVENT_REQUIRED:
        if n not in names:
            rep.error(rel, f"{eid}: 必須の欄「{n}」が無い")
    order = [EVENT_FIELDS.index(n) for n in names if n in EVENT_FIELDS]
    if order != sorted(order):
        rep.error(rel, f"{eid}: 欄の順番が決まりと違う（{'・'.join(EVENT_FIELDS)} の順）")
    # 「出来事」は次の行から項目を書くので、中身が空でよい。空の欄は、下の値の確かめから外す
    fields = {}
    for f in entry["fields"]:
        if f[0] != "出来事" and not f[2].strip():
            rep.error(rel, f"{f[3]} 行目: {eid} の欄「{f[0]}」が空（必須の欄は中身を書く。ほかの欄は、書くことが無ければ行ごと省く）")
        else:
            fields[f[0]] = f
    if "区分" in fields and fields["区分"][2] not in tags:
        rep.error(rel, f"{fields['区分'][3]} 行目: {eid} の区分「{fields['区分'][2]}」は、このファイルの区分（{'・'.join(sorted(tags))}）ではない")
    if "出典" in fields and kind == "manga" and group:
        nums = [int(x) for m in FILE_REF.finditer(fields["出典"][2]) for x in m.group().replace("File ", "").split("–")]
        if not nums:
            rep.error(rel, f"{fields['出典'][3]} 行目: {eid} の出典に File が無い")
        elif any(not group[0] <= n <= group[1] for n in nums):
            rep.error(rel, f"{fields['出典'][3]} 行目: {eid} の出典の File が、グループの File {group[0]}–{group[1]} の外にある")
    if "時期" in fields:
        when = fields["時期"][2]
        if when != "物語の今" and not re.fullmatch(r"過去：.+", when):
            rep.error(rel, f"{fields['時期'][3]} 行目: {eid} の時期は「物語の今」か「過去：<作中の言い方>」にする")
    if "場面にいた人物" in fields and not re.search(C_ID, fields["場面にいた人物"][2]):
        rep.error(rel, f"{fields['場面にいた人物'][3]} 行目: {eid} の場面にいた人物に人物 ID が無い")
    commits = Counter()
    for _, paren, value, ln in (f for f in entry["fields"] if f[0] == "写し元" and f[2].strip()):
        if re.search(r"\.md\b", value) and not re.fullmatch(r"[0-9a-f]{7,40}", paren or ""):
            rep.error(rel, f"{ln} 行目: {eid} の写し元に、写したときのコミットが無い（「写し元（<コミット>）: …」）")
        commits[paren] += 1
    for c, n in commits.items():
        if n > 1:
            rep.error(rel, f"{eid}: 写し元（{c or 'コミットなし'}）の行が {n} 行ある（同じコミットの写し元は 1 行にまとめる）")
    if "出来事" in fields and not entry["events"]:
        rep.error(rel, f"{eid}: 「出来事」に 1 段目の項目が無い")
    person = rf"[^`]+ `({C_ID})`"
    knower = rf"{person}（(?:[^（）]*。)?(?:{'|'.join(KNOW_HOW)})）"
    formats = {
        "関係": (None, "「<名前> `C-…` × <名前> `C-…` — <どういう関係になったか>」か「<名前> `C-…` — G-… に入る」"),
        "伏線": (rf"{F_ID} — (?:{'|'.join(FS_ROLES)})", f"「F-… — <{'・'.join(FS_ROLES)}>」"),
        "描写": (rf"{person} — .+", "「<名前> `C-…` — <P の ID か文>」"),
        "生死": (rf"{person} — (?:{'|'.join(LIFE_VALUES)})", f"「<名前> `C-…` — <{'・'.join(LIFE_VALUES)}>」"),
    }
    for ev in entry["events"]:
        for label, c in Counter(lab["label"] for lab in ev["labels"]).items():
            if c > 1:
                rep.error(rel, f"{ev['line']} 行目: 1 つの出来事に「{label}」のラベルが {c} 回ある（同じラベルの項目は 1 つのラベルの下にまとめる）")
        for lab in ev["labels"]:
            label, ln = lab["label"], lab["line"]
            if label not in EVENT_LABELS:
                rep.error(rel, f"{ln} 行目: 「出来事」のラベル「{label}」は決められたものではない（{'・'.join(EVENT_LABELS)}）")
                continue
            if not lab["items"]:
                rep.error(rel, f"{ln} 行目: ラベル「{label}」の下に項目が無い")
            for text, c in Counter(it["text"] for it in lab["items"]).items():
                if c > 1:
                    rep.error(rel, f"{ln} 行目: ラベル「{label}」の下に「{text}」が {c} 回ある")
            for it in lab["items"]:
                body, iln = it["text"], it["line"]
                if label == "知識":
                    if re.search(C_ID, body):
                        rep.error(rel, f"{iln} 行目: 「知識」の 3 段目には何を知ったか（K の ID か文）を書き、知った人物は 4 段目に書く")
                    if not it["persons"]:
                        rep.error(rel, f"{iln} 行目: 「知識」の項目の下に、知った人物（4 段目）が無い")
                    for pb, pln in it["persons"]:
                        if not re.fullmatch(knower, pb):
                            rep.error(rel, f"{pln} 行目: 知った人物の行の書き方が違う（「<名前> `C-…`（<知り方>）」。知り方は {'・'.join(KNOW_HOW)}）")
                    for pid, c in Counter(re.findall(C_ID, " ".join(pb for pb, _ in it["persons"]))).items():
                        if c > 1:
                            rep.error(rel, f"{iln} 行目: 「{body}」の下に {pid} が {c} 回ある")
                    continue
                if it["persons"]:
                    rep.error(rel, f"{it['persons'][0][1]} 行目: 4 段目は「知識」の下にだけ書く")
                pattern, hint = formats[label]
                if label == "関係":
                    ids = re.findall(C_ID, body)
                    ok = " — " in body and (len(ids) >= 2 or (ids and re.search(G_ID, body)))
                else:
                    ok = re.fullmatch(pattern, body)
                if not ok:
                    rep.error(rel, f"{iln} 行目: 「{label}」の項目の書き方が違う（{hint}）")


def check_events(data, rep):
    """出来事の正本（events/ 以下）の書き方を見る（conventions.md の 11.・events/README.md）。"""
    ev_dir = data / "events"
    abbrevs = load_event_abbrevs(ev_dir / "README.md")
    for p in event_paths(data):
        rel = p.relative_to(data)
        ev_rel = p.relative_to(ev_dir).as_posix()
        kind, span = event_kind(ev_rel)
        if not kind:
            rep.error(rel, "events/ のファイル名が決められたものではない（events/README.md の「ファイル」の表）")
            continue
        prefix_re = EVENT_KINDS[kind][1]
        group = entry = None  # group: (ID の頭, 原作の File の範囲)
        firsts = []
        in_code = False

        def finish():
            if entry:
                check_event_entry(rel, entry, kind, group[1] if group else None, rep)

        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if line.startswith("## "):
                finish()
                entry = None
                m = re.fullmatch(r"## (.+) `E-([^`]+)`", line)
                if not m or not re.fullmatch(prefix_re, m.group(2)):
                    rep.error(rel, f"{i} 行目: グループの見出しの最後に、このファイルの形の ID の頭（`E-…`）が無い")
                    group = None
                    continue
                rng = check_event_group(rel, i, m.group(1), m.group(2), kind, span, ev_rel, abbrevs, rep)
                group = (m.group(2), rng)
                if rng:
                    if firsts and rng[0] < firsts[-1]:
                        rep.error(rel, f"{i} 行目: グループが File の順になっていない")
                    firsts.append(rng[0])
            elif line.startswith("### "):
                finish()
                m = re.fullmatch(rf"### ({E_ID}) (.+)", line)
                entry = {"id": m.group(1) if m else line[4:], "line": i, "fields": [], "events": []}
                if not m:
                    rep.error(rel, f"{i} 行目: 件の見出しが「### <ID> <何が起きたか>」の形でない")
                    entry = None
                elif not group:
                    rep.error(rel, f"{i} 行目: {entry['id']} がグループ（##）の下に無い")
                else:
                    head = entry["id"][2:entry["id"].rfind("-")]
                    rng = group[1]
                    if not re.fullmatch(prefix_re, head):
                        rep.error(rel, f"{i} 行目: {entry['id']} は、このファイルの ID の形ではない（conventions.md の 11.2）")
                    elif rng and not rng[0] <= int(head) <= rng[1]:
                        rep.error(rel, f"{i} 行目: {entry['id']} の数字が、グループの File {rng[0]}–{rng[1]} の外にある")
                    elif not rng and head != group[0]:
                        rep.error(rel, f"{i} 行目: {entry['id']} の頭が、グループの E-{group[0]} と違う")
            elif entry is not None and line.strip():
                if m := re.fullmatch(r"- ([^:（]+?)(?:（([^）]*)）)?: ?(.*)", line):
                    if m.group(1) not in EVENT_FIELDS:
                        rep.error(rel, f"{i} 行目: 欄「{m.group(1)}」は決められたものではない（{'・'.join(EVENT_FIELDS)}）")
                    entry["fields"].append((m.group(1), m.group(2), m.group(3), i))
                    if m.group(1) == "出来事" and m.group(3):
                        rep.error(rel, f"{i} 行目: 「出来事:」の後ろには何も書かず、次の行から項目を書く")
                elif m := re.fullmatch(r"((?:  )+)- (.+)", line):
                    # 字下げの深さ。1：出来事、2：ラベル（- 知識: など）、3：ラベルの項目、4：知った人物（知識だけ）
                    depth, body = len(m.group(1)) // 2, m.group(2)
                    events = entry["events"]
                    labels = events[-1]["labels"] if events else []
                    items = labels[-1]["items"] if labels else []
                    if not entry["fields"] or entry["fields"][-1][0] != "出来事":
                        rep.error(rel, f"{i} 行目: 字下げした項目は「出来事」の下にだけ書く")
                    elif depth == 1:
                        events.append({"text": body, "line": i, "labels": []})
                    elif depth == 2 and events:
                        if lm := re.fullmatch(r"(\S+?):", body):
                            labels.append({"label": lm.group(1), "line": i, "items": []})
                        else:
                            rep.error(rel, f"{i} 行目: 2 段目はラベルだけの行（「- 知識:」など）にし、中身は次の段に書く")
                    elif depth == 3 and labels:
                        items.append({"text": body, "line": i, "persons": []})
                    elif depth == 4 and items:
                        items[-1]["persons"].append((body, i))
                    else:
                        rep.error(rel, f"{i} 行目: 字下げの深さが合わない（1 段目：出来事、2 段目：ラベル、3 段目：項目、4 段目：知った人物）")
                else:
                    rep.error(rel, f"{i} 行目: 件の中の行が決められた書き方（欄・出来事の項目）になっていない")
        finish()


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
    check_paths(args.data, rep)
    check_file_refs(args.data, rep)
    check_ellipsis(args.data, rep)
    check_events(args.data, rep)

    for line in rep.errors + rep.warnings:
        print(line)
    print(
        f"\n伏線 {len(defs['F'])} 件／考察 {len(defs['Q'])} 件／人物 {len(defs['C'])} 件／"
        f"知識表の列 {len(defs['K'])} 件／人物の掘り下げの列 {len(defs['P'])} 件／出来事 {len(defs['E'])} 件"
        f" — エラー {len(rep.errors)} 件、警告 {len(rep.warnings)} 件"
    )
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
