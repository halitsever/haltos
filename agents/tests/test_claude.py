import subprocess
import unittest

from haltos_agents.claude import (
    ClaudeError,
    clean_env,
    group_for,
    list_sessions,
    parse_agents,
    remove,
    resume_argv,
    start_argv,
)

BG = '{"pid":2495068,"id":"e9f3ca06","cwd":"/home/u","kind":"background","startedAt":1794845326807,"sessionId":"e9f3-1","name":"seo-fix","status":"waiting","state":"blocked"}'
BG_DEAD = '{"id":"a53483f5","cwd":"/home/u","kind":"background","startedAt":1794845326807,"sessionId":"a534-1","name":"old","state":"done"}'
IA = '{"pid":4634,"cwd":"/home/u","kind":"interactive","startedAt":1794912111186,"sessionId":"64f5-1","name":"halit-b9","status":"idle"}'


def done(stdout="", code=0, stderr=""):
    return lambda *a, **k: subprocess.CompletedProcess(a, code, stdout, stderr)


class SessionTest(unittest.TestCase):
    def test_background_session(self):
        s = parse_agents(f"[{BG}]")[0]
        self.assertEqual((s.key, s.state, s.status, s.attachable), ("e9f3ca06", "blocked", "waiting", True))
        self.assertEqual(s.session_id, "e9f3-1")
        self.assertAlmostEqual(s.started_at, 1794845326.807)
        self.assertEqual(s.group, "need")

    def test_background_session_without_process(self):
        s = parse_agents(f"[{BG_DEAD}]")[0]
        self.assertEqual((s.status, s.group, s.attachable), ("", "done", True))

    def test_interactive_session_uses_status_and_pid(self):
        s = parse_agents(f"[{IA}]")[0]
        self.assertEqual((s.key, s.state, s.status, s.attachable), ("pid:4634", "", "idle", False))
        self.assertEqual(s.group, "done")

    def test_groups(self):
        cases = {
            ("blocked", ""): "need",
            ("working", ""): "work",
            ("done", ""): "done",
            ("", "waiting"): "need",
            ("", "busy"): "work",
            ("", "idle"): "done",
            ("done", "waiting"): "need",
            ("blocked", "busy"): "work",
            ("weird", ""): "work",
        }
        for (state, status), group in cases.items():
            self.assertEqual(group_for(state, status), group, (state, status))

    def test_bad_json_raises(self):
        with self.assertRaises(ClaudeError):
            parse_agents("Update available\n[")

    def test_non_list_json_raises(self):
        with self.assertRaises(ClaudeError):
            parse_agents('{"error": "x"}')

    def test_entry_without_session_id_is_skipped(self):
        self.assertEqual(parse_agents('[{"pid": 1}]'), [])


class CliTest(unittest.TestCase):
    def test_list_sessions_parses_output(self):
        self.assertEqual(list_sessions(run=done(f"[{IA}]"))[0].name, "halit-b9")

    def test_missing_binary_raises(self):
        def run(*a, **k):
            raise FileNotFoundError("claude")

        with self.assertRaises(ClaudeError):
            list_sessions(run=run)

    def test_nonzero_exit_raises_with_stderr(self):
        with self.assertRaisesRegex(ClaudeError, "boom"):
            list_sessions(run=done("", 1, "boom"))

    def test_list_sessions_runs_with_clean_env(self):
        seen = {}

        def run(argv, **k):
            seen.update(argv=argv, env=k["env"])
            return subprocess.CompletedProcess(argv, 0, "[]", "")

        list_sessions(run=run)
        self.assertEqual(seen["argv"], ["claude", "agents", "--json"])
        self.assertFalse(any(k.startswith("CLAUDE_CODE") for k in seen["env"]))

    def test_remove_reports_refusal(self):
        self.assertTrue(remove("abc", run=done("removed abc")))
        self.assertFalse(remove("abc", run=done("", 1, "not safe")))

    def test_clean_env_drops_claude_markers(self):
        env = clean_env(
            {
                "HOME": "/h",
                "CLAUDECODE": "1",
                "CLAUDE_CODE_CHILD_SESSION": "x",
                "CLAUDE_PID": "9",
                "CLAUDEGRID_PANE": "2",
                "CLAUDE_CONFIG_DIR": "/c",
            }
        )
        self.assertEqual(env, {"HOME": "/h", "CLAUDE_CONFIG_DIR": "/c"})

    def test_start_argv(self):
        self.assertEqual(
            start_argv("seo-fix", "fix meta", "opus", True),
            ["claude", "--bg", "--permission-mode", "auto", "--name", "seo-fix", "--model", "opus", "-w", "seo-fix", "fix meta"],
        )
        self.assertEqual(start_argv("x", "p", None, False), ["claude", "--bg", "--permission-mode", "auto", "--name", "x", "p"])

    def test_resume_argv(self):
        self.assertEqual(resume_argv("abc"), ["claude", "--bg", "--resume", "abc"])


if __name__ == "__main__":
    unittest.main()
