import unittest

from haltos_agents.claude import Session
from haltos_agents.notify import NotifyPolicy


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
        self.assertEqual([(n.key, n.title, n.body) for n in notices], [("a", "a seni bekliyor", "Cevabını bekliyor.")])

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
        self.assertEqual([(n.title, n.body) for n in notices], [("a bitti", "3 dk çalıştı.")])

    def test_minutes_never_below_one(self):
        p = NotifyPolicy(min_busy=10)
        p.observe([s("a", "working")], 0, None)
        self.assertEqual(p.observe([s("a", "done")], 20, None)[0].body, "1 dk çalıştı.")

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


if __name__ == "__main__":
    unittest.main()
