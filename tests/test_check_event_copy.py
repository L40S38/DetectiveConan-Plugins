"""check_event_copy.py の --cited（脚注 → 件の向き）のテスト（標準ライブラリのみ）。

作り物の小さなデータ（知識表・人物の掘り下げの表を 1 つずつと、件 4 件）を一時ディレクトリに書き、
check_event_copy.DATA を差し替えて check_cited() を走らせる。ほかに、今のデータで --cited が
すべての表を読めること（終了コードが 2 にならないこと）を見る。

使い方: python -m unittest discover -s tests -v
"""
import contextlib
import io
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "detective-conan" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check_event_copy as cec  # noqa: E402

FILES = {
    "knowledge-matrix/01-test.md": """
        # 表1 テスト

        | 列 ID | 列 |
        |---|---|
        | K1-1 | a |
        | K1-2 | b |
        | K1-3 | c |
        | K1-7 | この人物が K1-1〜K1-3 の情報を知っていることを、コナンが把握している |

        | 人物 | K1-1 a | K1-2 b | K1-3 c | K1-7 コナンの把握 | 根拠 |
        |---|---|---|---|---|---|
        | **グループ** |  |  |  |  |  |
        | 甲 `C-ko` | ◎ | 〇 | ◎† | ◎ | [^K1-ko] |
        | 乙 `C-otsu` | ◎ | ? | △ | 〇 | [^K1-shared] |
        | 丙 `C-hei` | ✕ | ◎ | ー | 〇 | [^K1-shared] |
        | 探偵団（丁 `C-tei`・戊 `C-bo`） | ◎ | ◎ | ✕ | 〇 | [^K1-group] |
        | ほかの「グループ」：己 `C-ki` | ✕ | ✕ | ✕ | ー |  |

        [^K1-ko]: K1-1 は E-1-01 による。K1-2 は E-1-01・E-1-02 による（2026-10-28 に、E-9-99 から直した）。K1-3 は、コナンと推理する場面による（例：E-1-02）。K1-1〜K1-3 は A：E-1-03 で、コナンが気づいていることによる。K1-7 は、E-1-01 で気づいているので `◎`。K1-2 は E-5-01 による（括弧の中で。区切らない E-1-04）。

        [^K1-shared]: K1-1・K1-2 は E-1-01・E-1-02 による。K1-3 は E-1-02 による。

        [^K1-group]: K1-1・K1-2 は E-1-04 による。K1-2 は未確認（要確認）：E-1-04 の場にコナンがいたかを確かめていない。K1-1〜K1-3 は E-1-04・E-1-02 による。
        """,
    "knowledge-matrix/README.md": """
        # 人物の表が無いファイル
        """,
    "profiles/01-test.md": """
        # 表1 テスト

        | 列 ID | 列 |
        |---|---|
        | P1-1 | 恋愛 |
        | P1-2 | 家族 |

        | 人物 | P1-1 恋愛 | P1-2 家族 | 根拠 |
        |---|---|---|---|
        | 甲 `C-ko` | ◎ | ? | [^P1-ko] |
        | 乙 `C-otsu` | △ | 〇 | [^P1-otsu] |
        | 丙 `C-hei` | 〇 | ✕ | [^P1-hei] |

        [^P1-ko]: P1-1 は E-1-04 による。P1-2 は E-1-04 による。

        [^P1-otsu]: P1-1 は E-1-01 による。P1-2 は E-1-04 による。

        [^P1-hei]: P1-1 は E-1-04 による。
        """,
    "profiles/02-test.md": """
        # 表2 テスト（無いところが無い表）

        | 列 ID | 列 |
        |---|---|
        | P2-1 | 内面 |

        | 人物 | P2-1 内面 | 根拠 |
        |---|---|---|
        | 甲 `C-ko` | ◎ | [^P2-ko] |

        [^P2-ko]: P2-1 は E-1-04 による。
        """,
    "events/01-manga/001.md": """
        # 1巻

        ## File 1–2（1巻「テスト」）

        `E-1`

        ### E-1-01 一

        - 区分: [原作]
        - 場面にいた人物: 甲 `C-ko`、乙 `C-otsu`
        - 出来事:
          - 一。
            - 知識:
              - K1-1
                - 甲 `C-ko`（見た）
                - 乙 `C-otsu`（見た）
              - なにか（K1-2 の一部）
                - 甲 `C-ko`（聞いた）

        ### E-1-02 二

        - 場面にいた人物: 丙 `C-hei`
        - 出来事:
          - 二。
            - 知識:
              - K1-2
                - 丙 `C-hei`（見た）
              - K1-3
                - 甲 `C-ko`（推理した）

        ### E-1-03 三

        - 場面にいた人物: 甲 `C-ko`
        - 出来事:
          - 三。

        ### E-1-04 四

        - 場面にいた人物: 丁 `C-tei`
        - 出来事:
          - 四。
            - 知識:
              - K1-1
                - 丁 `C-tei`（見た）
                - 戊 `C-bo`（見た）
              - K1-2
                - 丁 `C-tei`（聞いた）
            - 描写:
              - 甲 `C-ko` — P1-1
              - 甲 `C-ko` — P2-1
              - 乙 `C-otsu` — 何か（P1-2 の一部）
        """,
}


def split_parts(output):
    """出力を「無い」の段と「参考」の段に分けて、(無い, 参考) の文字列で返す。"""
    main, ref, part = [], [], None
    for line in output.splitlines():
        if line.startswith("  無い："):
            part = main
        elif line.startswith("  参考"):
            part = ref
        elif part is not None:
            part.append(line)
    return "\n".join(main), "\n".join(ref)


class CitedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        data = Path(cls.tmp.name)
        for rel, text in FILES.items():
            path = data / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
        cls.saved = cec.DATA
        cec.DATA = data

    @classmethod
    def tearDownClass(cls):
        cec.DATA = cls.saved
        cls.tmp.cleanup()

    def cited(self, *paths):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = cec.check_cited(list(paths))
        return status, out.getvalue()

    def test_counts_and_status(self):
        status, out = self.cited("knowledge-matrix/01-test.md")
        self.assertEqual(status, 1)
        # 「K1-7 は…」の文（コナンの把握の列）と、乙・丙のどちらも見ない「K1-3 は E-1-02 による」は数えない
        self.assertIn("  見た文：9（うち「コナンの把握」の理由の文 2）", out)
        self.assertIn("  無い：9", out)
        self.assertRegex(out, r"(?m)^  参考（.*）：4$")

    def test_conan_column_is_not_checked(self):
        _, out = self.cited("knowledge-matrix/01-test.md")
        self.assertNotIn("K1-7", out)

    def test_fixed_history_paren_is_ignored(self):
        _, out = self.cited("knowledge-matrix/01-test.md")
        # E-9-99 は件に無いので、見ていれば「E-9-99：events/ に無い」が出る（見出しの文には出る）
        self.assertNotIn("E-9-99：", out)
        self.assertNotIn("E-9-99 の「知識」", out)
        self.assertIn("      ko の K1-2（〇）：E-1-02 の「知識」に無い（場面にいた人物にもいない）", out)

    def test_other_parens_are_checked_and_not_split(self):
        main, _ = split_parts(self.cited("knowledge-matrix/01-test.md")[1])
        self.assertIn("[^K1-ko]「K1-2 は E-5-01 による（括弧の中で。区切らない E-1-04）」", main)
        self.assertIn("      ko の K1-2（〇）：E-1-04 の「知識」に無い（場面にいた人物にもいない）", main)
        self.assertIn("      E-5-01：events/ に無い", main)
        # 「（例：E-1-02）」も見るが、甲の K1-3 は E-1-02 にあるので出ない
        self.assertNotIn("ko の K1-3（◎†）：E-1-02", main)

    def test_marks_decide_which_cells_are_checked(self):
        _, out = self.cited("knowledge-matrix/01-test.md")
        # 乙の K1-3（△）・丙の K1-3（ー）しか当たらない文は見ない。乙の K1-2（?）・丙の K1-1（✕）も見ない
        self.assertNotIn("「K1-3 は E-1-02 による」", out)
        self.assertNotIn("otsu の K1-2", out)
        self.assertNotIn("hei の K1-1", out)

    def test_two_columns_two_events_are_checked_loosely(self):
        main, _ = split_parts(self.cited("knowledge-matrix/01-test.md")[1])
        lines = main.splitlines()
        # 共有の脚注：乙と丙を、それぞれの記号で見る。どの件にもどれかの列があるかを見る
        self.assertIn("      otsu の K1-1：E-1-02 の「知識」にどれも無い（場面にいた人物にもいない）", lines)
        self.assertIn("      hei の K1-2：E-1-01 の「知識」にどれも無い（場面にいた人物にもいない）", lines)
        # 1 行に何人もいる行：丁と戊の両方を見る。どの列もどれかの件にあるかも見る
        self.assertIn("      tei の K1-1・K1-2：E-1-02 の「知識」にどれも無い（場面にいた人物にもいない）", lines)
        self.assertIn("      bo の K1-2（◎）：E-1-04・E-1-02 のどの「知識」にも無い", lines)
        self.assertNotIn("otsu の K1-1（◎）：E-1-02", main)

    def test_strict_check_for_one_event(self):
        main, _ = split_parts(self.cited("knowledge-matrix/01-test.md")[1])
        self.assertIn("      bo の K1-2（◎）：E-1-04 の「知識」に無い（場面にいた人物にもいない）", main.splitlines())
        self.assertNotIn("tei の K1-1（◎）：E-1-04", main)

    def test_reason_sentences_go_to_reference(self):
        main, ref = split_parts(self.cited("knowledge-matrix/01-test.md")[1])
        for heading in ("[^K1-ko]「K1-1〜K1-3 は A：E-1-03 で、コナンが気づいていることによる」",
                        "[^K1-group]「K1-2 は未確認（要確認）：E-1-04 の場にコナンがいたかを確かめていない」"):
            self.assertIn(heading, ref)
            self.assertNotIn(heading, main)
        # 甲は E-1-03 の場面にいるので、「場面にいた人物にもいない」は添えない
        self.assertIn("      ko の K1-3（◎†）：E-1-03 の「知識」に無い", ref.splitlines())

    def test_profiles_check_description(self):
        status, out = self.cited("profiles/01-test.md")
        self.assertEqual(status, 1)
        self.assertIn("  見た文：4", out)
        self.assertIn("  無い：2", out)
        self.assertNotIn("参考", out)
        lines = out.splitlines()
        # △ も見る。描写は、その場にいなくても書くので「場面にいた人物にもいない」は添えない
        self.assertIn("      otsu の P1-1（△）：E-1-01 の「描写」に無い", lines)
        self.assertIn("      hei の P1-1（〇）：E-1-04 の「描写」に無い", lines)
        self.assertNotIn("ko の P1", out)

    def test_no_warning_means_status_0(self):
        status, out = self.cited("profiles/02-test.md")
        self.assertEqual(status, 0)
        self.assertIn("  見た文：1", out)
        self.assertIn("  無い：0", out)

    def test_unreadable_or_no_table_is_status_2(self):
        status, out = self.cited("knowledge-matrix/README.md")
        self.assertEqual(status, 2)
        self.assertIn("人物の表", out)
        status, out = self.cited("knowledge-matrix/09-none.md")
        self.assertEqual(status, 2)
        self.assertIn("を読めない", out)


class HelperTest(unittest.TestCase):
    def test_split_sentences(self):
        self.assertEqual(cec.split_sentences("a は b（c。d）。e。"), ["a は b（c。d）", "e"])
        self.assertEqual(cec.split_sentences("閉じない（括弧。f"), ["閉じない（括弧", "f"])

    def test_top_parens(self):
        self.assertEqual(cec.top_parens("x（a（b）c）y（d）"), [(1, 8), (9, 12)])

    def test_expand_cols(self):
        self.assertEqual(cec.expand_cols("K1-1〜K1-3・K1-6"), ["K1-1", "K1-2", "K1-3", "K1-6"])
        self.assertEqual(cec.expand_cols("P2-6"), ["P2-6"])


class RealDataTest(unittest.TestCase):
    def test_cited_reads_every_table(self):
        """今のデータで、--cited がすべての表を読めること（読めなければ終了コード 2）。"""
        res = subprocess.run([sys.executable, str(SCRIPTS / "check_event_copy.py"), "--cited"],
                             capture_output=True, cwd=ROOT)
        out = res.stdout.decode("utf-8")
        self.assertIn(res.returncode, (0, 1), out + res.stderr.decode("utf-8", "replace"))
        data = SCRIPTS.parent / "data"
        tables = sorted(p.relative_to(data).as_posix() for d in ("knowledge-matrix", "profiles")
                        for p in (data / d).glob("0*.md"))
        self.assertTrue(tables)
        for rel in tables:
            self.assertRegex(out, rf"(?m)^{re.escape(rel)}（脚注が根拠に挙げた件に")


if __name__ == "__main__":
    unittest.main()
