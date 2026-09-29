#!/usr/bin/env python3
"""名探偵コナン編纂室データ（database submodule の CSV）を引くための小さな検索ツール。

database の Volume-Index-Case-Title.csv の `number` 列は取得した行の通し番号で、
公式の File 番号とはずれることがある（欠けている話・重複している話があるため）。
このツールは「巻」と「巻内の話番号（index）」から公式の File 番号を計算し直して使う。

使い方:
    python conan_db.py file 1103          # 公式 File 1103 の巻・事件名・話タイトル
    python conan_db.py case 17年前         # 事件名で検索（公式 File 範囲つき）
    python conan_db.py char 若狭留美       # 人物の初登場（事件の先頭 File）と登場事件数
    python conan_db.py vol 104            # 巻の収録話一覧
    python conan_db.py latest             # database に入っている最新の話
    python conan_db.py anomalies          # 欠けている話・重複している話の一覧

オプション:
    --db PATH   dataset_csv ディレクトリ（既定: このスクリプトの ../database/dataset_csv）
"""
import argparse
import csv
import io
import re
import sys
from collections import OrderedDict
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "database" / "dataset_csv"


def normalize_title(title):
    """括弧の種類や記号の違いを無視して話タイトルを比べるための正規化。"""
    return re.sub(r"[「」『』（）()\[\]［］【】・…！!？?\s　]", "", title)


def load_files(db):
    """公式 File 番号を振り直した話の一覧と、欠け・重複の情報を返す。"""
    path = db / "Volume-Index-Case-Title.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_volume = OrderedDict()
    for r in rows:
        by_volume.setdefault(int(r["volume"]), []).append(r)

    files = []
    anomalies = []
    offset = 0
    for volume in sorted(by_volume):
        vrows = sorted(by_volume[volume], key=lambda r: int(r["number"]))
        position = 0
        prev_title = None
        positions = []
        for r in vrows:
            idx = int(r["index"])
            norm = normalize_title(r["title"])
            if norm == prev_title:
                # 同じ話が 2 つの事件にまたがって載っている
                anomalies.append(f"{volume}巻: 話 {position} が 2 事件に重複（{r['title']}）")
                pos = position
            else:
                pos = max(idx, position + 1)
                if pos != idx:
                    anomalies.append(
                        f"{volume}巻: index {idx} を {pos} とみなした（{r['case']} {r['title']}）"
                    )
            positions.append(pos)
            position = pos
            prev_title = norm
            files.append({
                "file": offset + pos,
                "volume": volume,
                "index": pos,
                "case": r["case"],
                "title": r["title"],
                "db_number": int(r["number"]),
            })
        count = max(positions)
        missing = sorted(set(range(1, count + 1)) - set(positions))
        if missing:
            anomalies.append(
                f"{volume}巻: 巻内の話 {missing}（公式 File {[offset + m for m in missing]}）が database に無い"
            )
        offset += count
    return files, anomalies


def case_ranges(files):
    ranges = OrderedDict()
    for f in files:
        r = ranges.setdefault(f["case"], {"first": f["file"], "last": f["file"], "volumes": []})
        r["first"] = min(r["first"], f["file"])
        r["last"] = max(r["last"], f["file"])
        if f["volume"] not in r["volumes"]:
            r["volumes"].append(f["volume"])
    return ranges


def load_characters(db):
    chars = []
    with (db / "Title-MainCharacter.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            chars.append((r["mchara"], r["case"], "メイン"))
    with (db / "Title-GuestCharacter.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            chars.append((r["gchara"], r["title"], "ゲスト"))
    return chars


def fmt_file(f):
    return f"File {f['file']}（{f['volume']}巻 {f['index']}話目）{f['case']} {f['title']}"


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["file", "case", "char", "vol", "latest", "anomalies"])
    parser.add_argument("query", nargs="?")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if not (args.db / "Volume-Index-Case-Title.csv").exists():
        print(f"database が見つからない: {args.db}")
        print("submodule を取得していない場合は `git submodule update --init` を実行するか、"
              "名探偵コナン編纂室 https://websunday.net/conandb/ を直接見る。")
        return 2

    files, anomalies = load_files(args.db)

    if args.command == "file":
        n = int(args.query)
        hits = [f for f in files if f["file"] == n]
        if not hits:
            print(f"File {n} は database に無い（最新は File {files[-1]['file']}、または欠けている話）")
        for f in hits:
            print(fmt_file(f))
    elif args.command == "case":
        for name, r in case_ranges(files).items():
            if args.query in name:
                vols = "・".join(str(v) for v in r["volumes"])
                print(f"File {r['first']}–{r['last']}（{vols}巻）{name}")
    elif args.command == "vol":
        for f in files:
            if f["volume"] == int(args.query):
                print(fmt_file(f))
    elif args.command == "latest":
        print(fmt_file(files[-1]))
    elif args.command == "anomalies":
        print("\n".join(anomalies) if anomalies else "異常なし")
    elif args.command == "char":
        ranges = case_ranges(files)
        found = OrderedDict()
        for name, case, role in load_characters(args.db):
            if args.query in name and case in ranges:
                found.setdefault(name, []).append((ranges[case]["first"], case, role))
        if not found:
            print(f"「{args.query}」は database の登場人物に無い")
        for name, apps in found.items():
            apps.sort()
            first = apps[0]
            vol = next(f["volume"] for f in files if f["file"] == first[0])
            print(f"{name}: 初登場 File {first[0]}（{vol}巻）{first[1]}［{first[2]}］／登場事件 {len(apps)} 件")
            print("  ※ 事件の先頭 File。事件の途中の話や回想で初めて出た場合も事件の先頭が出る")
    return 0


if __name__ == "__main__":
    sys.exit(main())
