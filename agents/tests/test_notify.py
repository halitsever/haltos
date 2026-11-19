import unittest

from haltos_agents.claude import Session
from haltos_agents.notify import Notice, NotifyPolicy, gvariant_str, notify_argv, parse_action, parse_notify_id


def s(name, state="", status=""):
    return Session(name, f"sid-{name}", name, "/w", "background", state, status, 0.0, True)


class NotifyTest(unittest.TestCase):
    def test_first_observation_is_silent(self):
        p = NotifyPolicy()
        self.assertEqual(p.observe([s("a", "blocked"), s("b", "blocked")], 0, None), [])

    def test_becoming_blocked_notifies(self):
        p = NotifyPolicy()
        p.observe([s("a", "working", "busy")], 0, None)
        notices = p.observe([s("a", "blocked", "waiting")], 5, None)
        self.assertEqual([(n.key, n.title, n.body) for n in notices], [("a", "a is waiting", "It needs your answer.")])

    def test_staying_blocked_notifies_once(self):
        p = NotifyPolicy()
        p.observe([s("a", "working")], 0, None)
        p.observe([s("a", "blocked")], 5, None)
        self.assertEqual(p.observe([s("a", "blocked")], 10, None), [])

    def test_short_work_then_done_is_silent(self):
        p = NotifyPolicy()
        p.observe([s("a", "working", "busy")], 0, None)
        self.assertEqual(p.observe([s("a", "done", "idle")], 59, None), [])

    def test_long_work_then_done_notifies_minutes(self):
        p = NotifyPolicy()
        p.observe([s("a", "done", "idle")], 0, None)
        p.observe([s("a", "working", "busy")], 10, None)
        notices = p.observe([s("a", "done", "idle")], 190, None)
        self.assertEqual([(n.title, n.body) for n in notices], [("a is done", "It ran for 3 min.")])

    def test_minutes_never_below_one(self):
        p = NotifyPolicy(min_busy=10)
        p.observe([s("a", "working")], 0, None)
        self.assertEqual(p.observe([s("a", "done")], 20, None)[0].body, "It ran for 1 min.")

    def test_focused_agent_is_silent(self):
        p = NotifyPolicy()
        p.observe([s("a", "working")], 0, None)
        self.assertEqual(p.observe([s("a", "blocked")], 5, "a"), [])

    def test_new_session_appearing_blocked_notifies(self):
        p = NotifyPolicy()
        p.observe([], 0, None)
        self.assertEqual(len(p.observe([s("n", "blocked")], 3, None)), 1)

    def test_vanished_session_is_forgotten(self):
        p = NotifyPolicy()
        p.observe([s("a", "blocked")], 0, None)
        p.observe([], 1, None)
        self.assertEqual(len(p.observe([s("a", "blocked")], 2, None)), 1)


class DbusTest(unittest.TestCase):
    def test_gvariant_str_escapes_quotes_and_backslashes(self):
        self.assertEqual(gvariant_str("kahvefalin'in \\ yolu"), "'kahvefalin\\'in \\\\ yolu'")

    def test_notify_argv(self):
        argv = notify_argv(Notice("k", "seo-fix is done", "It ran for 3 min."))
        self.assertEqual(argv[:8], ["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                                    "--object-path", "/org/freedesktop/Notifications",
                                    "--method"])
        self.assertEqual(argv[9:], ["'HaltOS Agents'", "0", "'haltos-agents'", "'seo-fix is done'", "'It ran for 3 min.'",
                                    "['default', 'Open', 'open', 'Open']", "{'desktop-entry': <'haltos-agents'>}", "int32 -1"])

    def test_parse_notify_id(self):
        self.assertEqual(parse_notify_id("(uint32 7,)\n"), 7)
        self.assertIsNone(parse_notify_id("Error: GDBus.Error"))

    def test_parse_action(self):
        line = "/org/freedesktop/Notifications: org.freedesktop.Notifications.ActionInvoked (uint32 12, 'open')"
        self.assertEqual(parse_action(line), (12, "open"))
        self.assertIsNone(parse_action("/org/freedesktop/Notifications: org.freedesktop.Notifications.NotificationClosed (uint32 12, uint32 2)"))


class BodyClickTest(unittest.TestCase):
    def test_body_click_counts_as_open(self):
        self.assertIn("'default', 'Open'", notify_argv(Notice("k", "t", "b"))[14])
        line = "/org/freedesktop/Notifications: org.freedesktop.Notifications.ActionInvoked (uint32 3, 'default')"
        self.assertEqual(parse_action(line), (3, "open"))

if __name__ == "__main__":
    unittest.main()
