"""Unit tests for TUI session storage and widgets."""

from __future__ import annotations

import os
import tempfile
import unittest

from swarm.tui.session import Session
from swarm.tui.store import SessionStore


class TestSession(unittest.TestCase):
    """Verify session model and SQLite persistence."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = SessionStore(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_session_title_from_first_message(self):
        s = Session()
        s.add_user_message("What is the capital of France?")
        self.assertEqual(s.title, "What is the capital of France?")

    def test_last_user_query(self):
        s = Session()
        s.add_user_message("First question")
        s.add_orchestrator_message("Answer")
        s.add_user_message("Follow-up")
        self.assertEqual(s.last_user_query(), "Follow-up")

    def test_store_roundtrip(self):
        s = Session()
        s.add_user_message("Query")
        s.add_orchestrator_message("Answer", {"goal": "Query"})
        self.store.save(s)
        loaded = self.store.load(s.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, "Query")
        self.assertEqual(len(loaded.messages), 2)
        self.assertEqual(len(loaded.results), 1)

    def test_list_sessions_order(self):
        s1 = Session()
        s1.add_user_message("One")
        s2 = Session()
        s2.add_user_message("Two")
        self.store.save(s1)
        self.store.save(s2)
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].id, s2.id)

    def test_context_for_followup_empty_without_result(self):
        s = Session()
        s.add_user_message("Query")
        self.assertEqual(s.context_for_followup(), "")


if __name__ == "__main__":
    unittest.main()
