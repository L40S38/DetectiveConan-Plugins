#!/usr/bin/env python3
"""data/ 以下のデータの整合性をチェックする（標準ライブラリのみ）。

チェック内容:
  1. ID の重複（伏線 F・考察 Q・人物 C・知識表の列 K）
  2. F・Q・K・C の参照が、実在する ID を指しているか
  3. 脚注の参照と定義が対応しているか
  4. foreshadowing/README.md の一覧表と foreshadowing/0*.md の詳細で、タイトル・状態・重要度が一致しているか
  5. F・Q のタイトルが問いの形で、答えの書き方（「＝」など）が入っていないか（警告のみ。最終確認は目で行う）
  6. Markdown の表で、どの行も列数がそろっているか
  7. 知識表のセルが決められた値だけか

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
C_ID = r"C-[a-z]+(?:-[a-z]+)*"

BINARY_VALUES = {"●", "◐", "△", "✕", "ー", "?"}
LEVEL_VALUES = {"1", "2", "3", "4", "ー", "?"}
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
    defs = {"F": [], "Q": [], "C": [], "K": []}
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


def check_knowledge_cells(data, rep):
    for p in sorted((data / "knowledge-matrix").glob("0*.md")):
        rel = p.relative_to(data)
        text = p.read_text(encoding="utf-8")
        for start, rows in iter_tables(text):
            header = split_row(rows[0])
            if header[-1] != "根拠":
                continue
            kinds = ["level" if "接近度" in h else "binary" for h in header[1:-1]]
            for offset, row in enumerate(rows[2:], 2):
                cells = split_row(row)
                if cells[0].startswith("**") and not any(cells[1:]):
                    continue  # グループ見出しの行
                if not re.search(C_ID, cells[0]):
                    rep.error(rel, f"{start + offset} 行目: 人物 ID が無い（{cells[0]}）")
                for kind, h, cell in zip(kinds, header[1:-1], cells[1:-1]):
                    value = cell.rstrip("†")
                    allowed = LEVEL_VALUES if kind == "level" else BINARY_VALUES
                    if value not in allowed:
                        rep.error(rel, f"{start + offset} 行目 {h}: 値「{cell}」は決められた値ではない")


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

    for line in rep.errors + rep.warnings:
        print(line)
    print(
        f"\n伏線 {len(defs['F'])} 件／考察 {len(defs['Q'])} 件／人物 {len(defs['C'])} 件／"
        f"知識表の列 {len(defs['K'])} 件 — エラー {len(rep.errors)} 件、警告 {len(rep.warnings)} 件"
    )
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
