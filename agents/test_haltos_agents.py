import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import haltos_agents as ha


class IsGridTest(unittest.TestCase):
    def test_a_claudegrid_konsole_window_is_a_grid(self):
        self.assertTrue(ha.is_grid("konsole", "▦ halit — Konsole"))

    def test_other_konsole_windows_are_not(self):
        self.assertFalse(ha.is_grid("konsole", "~ : bash — Konsole"))

    def test_a_konsole_started_by_claudegrid_stays_a_grid_whatever_its_title(self):
        args = ["konsole", "--separate", "--nofork", "--profile", "/run/user/1000/claudegrid-1000/ab12.profile"]
        self.assertTrue(ha.is_grid("konsole", "~ : bash — Konsole", args))
        self.assertFalse(ha.is_grid("konsole", "~ : bash — Konsole", ["/usr/bin/konsole"]))

    def test_other_apps_named_like_a_grid_are_not(self):
        self.assertFalse(ha.is_grid("google-chrome", "▦ claudegrid"))


class ProcessTest(unittest.TestCase):
    def test_descendants_reach_grandchildren_only_under_the_root(self):
        parent_of = {10: 1, 11: 10, 12: 11, 20: 1, 21: 20}
        self.assertEqual(ha.descendants(10, parent_of), {11, 12})

    def test_parents_reads_names_with_spaces_and_parentheses(self):
        with tempfile.TemporaryDirectory() as proc:
            os.makedirs(os.path.join(proc, "42"))
            with open(os.path.join(proc, "42", "stat"), "w") as f:
                f.write("42 (we (ird) name) S 7 42 42 0")
            os.makedirs(os.path.join(proc, "self"))
            self.assertEqual(ha.parents(proc), {42: 7})

    def test_running_sessions_come_in_start_order_and_skip_pids_without_a_session(self):
        with tempfile.TemporaryDirectory() as d:
            for pid, sid, started in ((5, "b", 200), (6, "a", 100)):
                with open(os.path.join(d, f"{pid}.json"), "w") as f:
                    json.dump({"sessionId": sid, "cwd": "/w", "name": f"n{sid}", "startedAt": started}, f)
            got = ha.running_sessions([5, 6, 7], d)
        self.assertEqual([s["id"] for s in got], ["a", "b"])
        self.assertEqual(got[0], {"id": "a", "cwd": "/w", "name": "na"})


def s(sid, cwd="/home/u/app"):
    return {"id": sid, "cwd": cwd, "name": ""}


USED = lambda sid: True  # noqa: E731


class RememberTest(unittest.TestCase):
    def test_a_new_grid_goes_first(self):
        grids = ha.remember([{"saved": 1, "sessions": [s("old")]}], [s("a"), s("b")], 5, USED)
        self.assertEqual([[x["id"] for x in g["sessions"]] for g in grids], [["a", "b"], ["old"]])

    def test_a_grid_sharing_a_session_is_replaced_by_what_runs_now(self):
        grids = ha.remember([{"saved": 1, "sessions": [s("a"), s("b")]}], [s("b"), s("c")], 5, USED)
        self.assertEqual(grids, [{"saved": 5, "sessions": [s("b"), s("c")]}])

    def test_a_grid_nobody_wrote_in_is_not_saved(self):
        grids = [{"saved": 1, "sessions": [s("a")]}]
        self.assertIs(ha.remember(grids, [s("x"), s("y")], 5, lambda sid: False), grids)
        self.assertIs(ha.remember(grids, [], 5, USED), grids)

    def test_reopening_a_grid_with_an_unused_pane_does_not_grow_it(self):
        grids = [{"saved": 1, "sessions": [s("used"), s("empty1")]}]
        # The empty pane comes back as a fresh session with a new id.
        grids = ha.remember(grids, [s("used"), s("empty2")], 5, lambda sid: sid == "used")
        self.assertEqual([x["id"] for x in grids[0]["sessions"]], ["used", "empty2"])
        self.assertEqual(len(grids), 1)

    def test_only_the_newest_grids_are_kept(self):
        grids = []
        for i in range(ha.KEEP + 3):
            grids = ha.remember(grids, [s(str(i))], i, USED)
        self.assertEqual(len(grids), ha.KEEP)
        self.assertEqual(grids[0]["sessions"][0]["id"], str(ha.KEEP + 2))


class SettleTest(unittest.TestCase):
    def test_a_grid_is_saved_once_the_same_sessions_are_seen_twice(self):
        first = ha.settle({}, {1: [s("a"), s("b")]})
        self.assertEqual(first, [])
        self.assertEqual(ha.settle({1: [s("a"), s("b")]}, {1: [s("a"), s("b")]}), [[s("a"), s("b")]])

    def test_a_grid_caught_while_closing_is_not_saved_short(self):
        # Konsole is closing: one pane already died, then the whole window goes.
        self.assertEqual(ha.settle({1: [s("a"), s("b")]}, {1: [s("a")]}), [])
        self.assertEqual(ha.settle({1: [s("a")]}, {}), [])


class StoreTest(unittest.TestCase):
    def test_saved_grids_load_back_and_junk_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x", "grids.json")
            self.assertEqual(ha.load_grids(path), [])
            ha.save_grids([{"saved": 1, "sessions": [s("a")]}, {"saved": 2, "sessions": []}], path)
            self.assertEqual([g["sessions"][0]["id"] for g in ha.load_grids(path)], ["a"])
            with open(path, "w") as f:
                f.write("{broken")
            self.assertEqual(ha.load_grids(path), [])

    def test_entries_with_missing_or_wrong_fields_are_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "grids.json")
            with open(path, "w") as f:
                json.dump([
                    {"saved": 1, "sessions": [{"id": "ok", "cwd": "/w", "name": "n"}]},
                    {"saved": 2, "sessions": [{"id": "no-cwd"}]},
                    {"saved": "x", "sessions": [{"id": "a", "cwd": "/w"}]},
                    {"sessions": [{"id": 5, "cwd": "/w"}]},
                    "junk",
                    {"saved": 3, "sessions": [{"id": "b", "cwd": "/w"}, {"cwd": "/w"}]},
                ], f)
            grids = ha.load_grids(path)
        self.assertEqual([[x["id"] for x in g["sessions"]] for g in grids], [["ok"], ["b"]])
        self.assertEqual(grids[1]["sessions"][0]["name"], "")
        ha.label(grids[1], 10)


class ResumeTest(unittest.TestCase):
    def test_each_session_resumes_in_its_own_folder(self):
        grid = {"saved": 1, "sessions": [{"id": "a", "cwd": "/w/one", "name": "one-1"}, s("b", "/w/two")]}
        config = ha.resume_config(grid, transcript=lambda sid: sid == "a", is_dir=lambda d: True)
        self.assertEqual(config, {"panes": [
            {"dir": "/w/one", "name": "one-1", "args": ["--resume", "a"]},
            {"dir": "/w/two"},
        ]})

    def test_a_pane_whose_folder_is_gone_is_left_out(self):
        grid = {"saved": 1, "sessions": [s("a", "/w/gone"), s("b", "/w/here")]}
        config = ha.resume_config(grid, transcript=lambda sid: True, is_dir=lambda d: d == "/w/here")
        self.assertEqual(config, {"panes": [{"dir": "/w/here", "args": ["--resume", "b"]}]})

    def test_a_session_already_running_is_not_opened_twice(self):
        grid = {"saved": 1, "sessions": [s("a", "/w/one"), s("b", "/w/two")]}
        config = ha.resume_config(grid, transcript=lambda sid: True, running={"a"}, is_dir=lambda d: True)
        self.assertEqual(config, {"panes": [{"dir": "/w/two", "args": ["--resume", "b"]}]})

    def test_live_sessions_skip_files_of_processes_that_ended(self):
        with tempfile.TemporaryDirectory() as d:
            for pid, sid in ((os.getpid(), "alive"), (2 ** 22 + 7, "gone")):
                with open(os.path.join(d, f"{pid}.json"), "w") as f:
                    json.dump({"pid": pid, "sessionId": sid}, f)
            with open(os.path.join(d, "junk.json"), "w") as f:
                f.write("{")
            self.assertEqual(ha.live_sessions(d), {"alive"})

    def test_has_transcript_finds_the_session_in_any_project(self):
        with tempfile.TemporaryDirectory() as claude:
            os.makedirs(os.path.join(claude, "projects", "-home-u-app"))
            open(os.path.join(claude, "projects", "-home-u-app", "abc.jsonl"), "w").close()
            self.assertTrue(ha.has_transcript("abc", claude))
            self.assertFalse(ha.has_transcript("xyz", claude))


class EnvTest(unittest.TestCase):
    def test_claude_session_markers_are_dropped_but_the_config_dir_stays(self):
        env = {"PATH": "/bin", "CLAUDECODE": "1", "CLAUDE_CODE_CHILD_SESSION": "1", "CLAUDE_CONFIG_DIR": "/c"}
        self.assertEqual(ha.clean_env(env), {"PATH": "/bin", "CLAUDE_CONFIG_DIR": "/c"})


class LabelTest(unittest.TestCase):
    def test_label_counts_agents_and_names_folders_once(self):
        grid = {"saved": 0, "sessions": [s("a", "/w/app"), s("b", "/w/app"), s("c", "/w/site")]}
        self.assertEqual(ha.label(grid, 7200), "3 agents · app, site · 2h ago")

    def test_label_shortens_many_folders(self):
        grid = {"saved": 0, "sessions": [s(str(i), f"/w/p{i}") for i in range(5)]}
        self.assertEqual(ha.label(grid, 30), "5 agents · p0, p1, p2 +2 · just now")

    def test_ago(self):
        self.assertEqual([ha.ago(x) for x in (5, 90, 5400, 200000)], ["just now", "1m ago", "1h ago", "2d ago"])


def zombies() -> list[int]:
    found = []
    for name in os.listdir("/proc"):
        if name.isdigit():
            try:
                stat = open(f"/proc/{name}/stat").read().rsplit(")", 1)[1].split()
            except OSError:
                continue
            if stat[0] == "Z" and int(stat[1]) == os.getpid():
                found.append(int(name))
    return found


class LaunchTest(unittest.TestCase):
    def test_a_finished_claudegrid_is_reaped_and_leaves_no_zombie(self):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "claudegrid")
            with open(fake, "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(fake, 0o755)
            with mock.patch.dict(os.environ, {"PATH": d + os.pathsep + os.environ["PATH"]}), \
                    mock.patch.object(ha, "STATE", d):
                ha.launch_grid()
                ha.launch_grid({"saved": 0, "sessions": [s("a")]})
                time.sleep(1.0)
                self.assertEqual(zombies(), [])

    def test_a_claudegrid_that_fails_is_reported(self):
        failed = []
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "claudegrid")
            with open(fake, "w") as f:
                f.write("#!/bin/sh\nexit 3\n")
            os.chmod(fake, 0o755)
            with mock.patch.dict(os.environ, {"PATH": d + os.pathsep + os.environ["PATH"]}):
                self.assertTrue(ha.launch_grid(on_fail=failed.append))
                time.sleep(1.0)
        self.assertEqual(failed, [3])

    def test_a_missing_claudegrid_does_not_raise(self):
        with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}):
            self.assertFalse(ha.launch_grid())


@unittest.skipUnless(os.environ.get("DISPLAY"), "needs an X display")
class X11Test(unittest.TestCase):
    def test_a_window_that_vanished_reads_as_empty_instead_of_killing_the_tray(self):
        code = ("import haltos_agents as ha; x = ha.X11(); "
                "print(repr(x.text(0x7ffffff, '_NET_WM_NAME')), x.wm_class(0x7ffffff) == '', x.pid(0x7ffffff))")
        run = subprocess.run([sys.executable, "-c", code], cwd=os.path.dirname(os.path.abspath(__file__)),
                             capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "'' True 0")


if __name__ == "__main__":
    unittest.main()
