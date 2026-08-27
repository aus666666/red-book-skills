"""Regression tests for indeterminate topic-selection timeout recovery."""

import os
import sys
import unittest
from unittest.mock import Mock, patch


SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from cdp_publish import CDPError  # noqa: E402
from publish_pipeline import _select_topics  # noqa: E402


class TopicTimeoutRecoveryTests(unittest.TestCase):
    def make_publisher(self, topic_states, title="目标标题"):
        publisher = Mock()
        publisher.command_timeout_seconds = 15.0
        publisher._evaluate = Mock(
            side_effect=[
                CDPError(
                    "Timed out waiting for CDP response to Runtime.evaluate after 30.0s."
                ),
                *topic_states,
            ]
        )
        publisher._current_publish_form = Mock(return_value={"title": title})
        return publisher

    @patch("publish_pipeline.time.sleep", return_value=None)
    def test_timeout_continues_when_native_anchor_was_committed(self, _sleep):
        publisher = self.make_publisher([
            {"topics": ["AI技术前沿"], "suggestions": []}
        ])

        _select_topics(
            publisher,
            ["#AI技术前沿"],
            expected_title="目标标题",
            timing_jitter=0,
        )

        publisher.disconnect.assert_called_once()
        publisher.connect.assert_called_once_with(
            target_url_prefix="https://creator.xiaohongshu.com/publish",
            reuse_existing_tab=True,
        )
        self.assertEqual(publisher.command_timeout_seconds, 15.0)

    @patch("publish_pipeline.time.sleep", return_value=None)
    def test_timeout_stops_when_native_anchor_is_absent(self, _sleep):
        publisher = self.make_publisher([
            {"topics": ["AIAgent"], "suggestions": []}
        ])

        with self.assertRaisesRegex(CDPError, "was not recovered"):
            _select_topics(
                publisher,
                ["#AI技术前沿"],
                expected_title="目标标题",
                timing_jitter=0,
            )

        self.assertEqual(publisher.command_timeout_seconds, 15.0)

    @patch("publish_pipeline.time.sleep", return_value=None)
    def test_timeout_refuses_wrong_preserved_form(self, _sleep):
        publisher = self.make_publisher(
            [{"topics": ["AI技术前沿"], "suggestions": []}],
            title="另一个标题",
        )

        with self.assertRaisesRegex(CDPError, "wrong form"):
            _select_topics(
                publisher,
                ["#AI技术前沿"],
                expected_title="目标标题",
                timing_jitter=0,
            )

    @patch("publish_pipeline.time.sleep", return_value=None)
    def test_exact_pending_suggestion_is_committed_with_native_enter(self, _sleep):
        pending = {"topics": [], "suggestions": ["#AI技术前沿"]}
        committed = {"topics": ["AI技术前沿"], "suggestions": []}
        publisher = self.make_publisher([pending, pending, committed])

        _select_topics(
            publisher,
            ["#AI技术前沿"],
            expected_title="目标标题",
            timing_jitter=0,
        )

        self.assertEqual(publisher._send.call_count, 2)
        self.assertEqual(
            publisher._send.call_args_list[0].args[0],
            "Input.dispatchKeyEvent",
        )

    @patch("publish_pipeline.time.sleep", return_value=None)
    def test_async_commit_after_focus_skips_native_enter(self, _sleep):
        pending = {"topics": [], "suggestions": ["#AI技术前沿"]}
        committed = {"topics": ["AI技术前沿"], "suggestions": []}
        publisher = self.make_publisher([pending, committed])

        _select_topics(
            publisher,
            ["#AI技术前沿"],
            expected_title="目标标题",
            timing_jitter=0,
        )

        publisher._send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
