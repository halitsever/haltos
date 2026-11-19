import json
import tempfile
import unittest
from pathlib import Path

from haltos_agents.transcript import find_transcript, pending_question, read_feed


def user(text, **extra):
    return {"type": "user", "message": {"role": "user", "content": text}, **extra}


def text(t, **extra):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}, **extra}


def tool(name, tid, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def result(tid):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": "ok"}]}}


ASK = {
    "questions": [
        {
            "question": "Merge edeyim mi?",
            "header": "Merge",
            "multiSelect": False,
            "options": [{"label": "Evet"}, {"label": "Hayır"}, {"label": "Sonra"}],
        }
    ]
}


class TranscriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def write(self, rows, name="t.jsonl", tail=""):
        p = self.tmp / name
        p.write_text("".join(json.dumps(r) + "\n" for r in rows) + tail)
        return p

    def test_feed_kinds_and_order(self):
        p = self.write([user("build it"), text("Building now."), tool("Bash", "t1", command="npm run build"), result("t1")])
        items = read_feed(p)
        self.assertEqual([i.kind for i in items], ["prompt", "text", "tool"])
        self.assertEqual(items[0].text, "build it")
        self.assertEqual(items[2].text, "Bash: npm run build")

    def test_feed_skips_meta_sidechain_thinking_and_tags(self):
        rows = [
            user("hidden meta", isMeta=True),
            text("hidden side", isSidechain=True),
            {"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "SECRET-THINKING"}]}},
            user("<local-command-stdout>x</local-command-stdout>"),
            {"type": "api-request", "x": 1},
            user("visible"),
        ]
        self.assertEqual([i.text for i in read_feed(self.write(rows))], ["visible"])

    def test_tool_summary_uses_file_path_and_is_truncated(self):
        p = self.write([tool("Edit", "t1", file_path="/a/b.py"), tool("Bash", "t2", command="x" * 300)])
        items = read_feed(p)
        self.assertEqual(items[0].text, "Edit: /a/b.py")
        self.assertLessEqual(len(items[1].text), 80)

    def test_half_written_last_line_is_ignored(self):
        p = self.write([user("one"), text("two")], tail='{"type": "assistant", "mess')
        self.assertEqual(len(read_feed(p)), 2)

    def test_large_file_reads_tail_only(self):
        p = self.write([user("x" * 1000) for _ in range(5000)] + [user("LAST")])
        self.assertEqual([i.text for i in read_feed(p, limit=1)], ["LAST"])
        self.assertLessEqual(len(read_feed(p, tail_bytes=10_000)), 10)

    def test_limit_keeps_newest(self):
        p = self.write([user(str(i)) for i in range(10)])
        self.assertEqual([i.text for i in read_feed(p, limit=3)], ["7", "8", "9"])

    def test_pending_ask_user_question(self):
        q = pending_question(self.write([user("go"), tool("AskUserQuestion", "q1", **ASK)]), waiting=True)
        self.assertEqual(q.text, "Merge edeyim mi?")
        self.assertEqual(q.options, [("Evet", b"1"), ("Hayır", b"2"), ("Sonra", b"3")])

    def test_ask_with_several_questions_has_no_quick_answers(self):
        two = {"questions": ASK["questions"] * 2}
        q = pending_question(self.write([tool("AskUserQuestion", "q1", **two)]), waiting=True)
        self.assertEqual((q.text, q.options), ("Merge edeyim mi?", []))

    def test_answered_question_is_not_pending(self):
        self.assertIsNone(pending_question(self.write([tool("AskUserQuestion", "q1", **ASK), result("q1")]), waiting=True))

    def test_pending_permission_needs_waiting_status(self):
        p = self.write([tool("Bash", "t1", command="rm -rf build")])
        q = pending_question(p, waiting=True)
        self.assertEqual(q.text, "Bash: rm -rf build")
        self.assertEqual(q.options, [("İzin ver", b"1"), ("Reddet", b"\x1b")])
        self.assertIsNone(pending_question(p, waiting=False))

    def test_find_transcript_globs_by_session_id(self):
        d = self.tmp / "-home-u--cache"
        d.mkdir()
        (d / "abc-1.jsonl").write_text("")
        self.assertEqual(find_transcript("abc-1", self.tmp), d / "abc-1.jsonl")
        self.assertIsNone(find_transcript("nope", self.tmp))

    def test_missing_file_gives_empty_feed(self):
        self.assertEqual(read_feed(self.tmp / "gone.jsonl"), [])
        self.assertIsNone(pending_question(self.tmp / "gone.jsonl", waiting=True))


if __name__ == "__main__":
    unittest.main()
