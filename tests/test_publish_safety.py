"""Regression tests for publish target selection and submit verification."""

import json
import os
import sys
import unittest
from unittest.mock import Mock


SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from cdp_publish import CDPError, XHS_NOTE_MANAGER_API_PATH, XiaohongshuPublisher


class PublishTargetTests(unittest.TestCase):
    def setUp(self):
        self.publisher = XiaohongshuPublisher(timing_jitter=0)

    def test_required_prefix_selects_publish_tab(self):
        self.publisher._get_targets = Mock(return_value=[
            {
                "type": "page",
                "url": "https://creator.xiaohongshu.com/new/note-manager",
                "webSocketDebuggerUrl": "ws://manager",
            },
            {
                "type": "page",
                "url": "https://creator.xiaohongshu.com/publish/publish?source=official",
                "webSocketDebuggerUrl": "ws://publish",
            },
        ])

        result = self.publisher._find_or_create_tab(
            target_url_prefix="https://creator.xiaohongshu.com/publish",
            reuse_existing_tab=True,
        )

        self.assertEqual(result, "ws://publish")

    def test_required_prefix_never_falls_back_to_another_tab(self):
        self.publisher._get_targets = Mock(return_value=[
            {
                "type": "page",
                "url": "https://creator.xiaohongshu.com/new/note-manager",
                "webSocketDebuggerUrl": "ws://manager",
            }
        ])

        with self.assertRaisesRegex(CDPError, "No existing browser tab matches"):
            self.publisher._find_or_create_tab(
                target_url_prefix="https://creator.xiaohongshu.com/publish",
                reuse_existing_tab=True,
            )


class PublishClickTests(unittest.TestCase):
    def setUp(self):
        self.publisher = XiaohongshuPublisher(timing_jitter=0)
        self.publisher._sleep = Mock()
        self.publisher._wait_for_publish_button_ready = Mock()
        self.publisher._get_accessible_button_rect = Mock(return_value={
            "backendDOMNodeId": 123,
            "x": 742.5,
            "y": 1055.0,
            "width": 120,
            "height": 40,
        })
        self.publisher._send = Mock(return_value={})
        self.publisher._evaluate = Mock(return_value=False)
        self.publisher._click_mouse = Mock()

    def test_refuses_non_publish_page_before_click(self):
        self.publisher._current_publish_form = Mock(return_value={
            "url": "https://creator.xiaohongshu.com/new/note-manager",
            "title": "目标标题",
            "host": {},
        })

        with self.assertRaisesRegex(CDPError, "outside the creator publish page"):
            self.publisher._click_publish(expected_title="目标标题")

        self.publisher._click_mouse.assert_not_called()

    def test_refuses_wrong_title_before_click(self):
        self.publisher._current_publish_form = Mock(return_value={
            "url": "https://creator.xiaohongshu.com/publish/publish?source=official",
            "title": "另一个标题",
            "host": {"submit-disabled": "false", "submit-loading": "false"},
        })

        with self.assertRaisesRegex(CDPError, "wrong form"):
            self.publisher._click_publish(expected_title="目标标题")

        self.publisher._click_mouse.assert_not_called()

    def test_click_requires_platform_response(self):
        self.publisher._current_publish_form = Mock(return_value={
            "url": "https://creator.xiaohongshu.com/publish/publish?source=official",
            "title": "目标标题",
            "host": {"submit-disabled": "false", "submit-loading": "false"},
        })
        self.publisher._wait_for_publish_response = Mock(
            side_effect=CDPError("no Xiaohongshu note submission response")
        )
        self.publisher.verify_note_submission = Mock(return_value={"found": False})

        with self.assertRaisesRegex(CDPError, "no Xiaohongshu note submission response"):
            self.publisher._click_publish(expected_title="目标标题")

        self.publisher.verify_note_submission.assert_called_once_with(
            title="目标标题",
            timeout_seconds=30.0,
        )
        self.publisher._click_mouse.assert_not_called()

    def test_web_component_dispatches_public_publish_event(self):
        self.publisher._evaluate = Mock(return_value=True)

        mode = self.publisher._activate_publish_button({
            "backendDOMNodeId": 123,
            "x": 742.5,
            "y": 1055.0,
        })

        self.assertEqual(mode, "web_component_publish_event")
        expression = self.publisher._evaluate.call_args.args[0]
        self.assertIn("new CustomEvent('publish'", expression)
        self.assertIn("composed: true", expression)
        self.publisher._send.assert_not_called()
        self.publisher._click_mouse.assert_not_called()

    def test_success_returns_verified_platform_payload(self):
        self.publisher._current_publish_form = Mock(return_value={
            "url": "https://creator.xiaohongshu.com/publish/publish?source=official",
            "title": "目标标题",
            "host": {"submit-disabled": "false", "submit-loading": "false"},
        })
        expected = {
            "status": 200,
            "note_id": "0123456789abcdef01234567",
            "share_link": "https://www.xiaohongshu.com/discovery/item/0123456789abcdef01234567",
        }
        self.publisher._wait_for_publish_response = Mock(return_value=expected)

        result = self.publisher._click_publish(expected_title="目标标题")

        self.assertEqual(result, expected)
        self.publisher._click_mouse.assert_not_called()


class PublishResponseTests(unittest.TestCase):
    def test_accepts_successful_note_response(self):
        publisher = XiaohongshuPublisher(timing_jitter=0)
        messages = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "request-1",
                    "request": {
                        "url": "https://edith.xiaohongshu.com/web_api/sns/v2/note",
                        "method": "POST",
                    },
                },
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "request-1",
                    "response": {
                        "url": "https://edith.xiaohongshu.com/web_api/sns/v2/note",
                        "status": 200,
                    },
                },
            },
        ]
        publisher._receive_cdp_message = Mock(side_effect=messages)
        body = {
            "success": True,
            "result": 0,
            "data": {"id": "0123456789abcdef01234567"},
            "share_link": "https://www.xiaohongshu.com/discovery/item/0123456789abcdef01234567",
        }
        publisher._send = Mock(return_value={"body": json.dumps(body)})

        result = publisher._wait_for_publish_response(timeout_seconds=5)

        self.assertEqual(result["status"], 200)
        self.assertEqual(result["note_id"], "0123456789abcdef01234567")


class NoteManagerRecoveryTests(unittest.TestCase):
    def test_retries_native_manager_list_after_transient_406(self):
        """A transient manager-list error must not be treated as an empty account."""
        publisher = XiaohongshuPublisher(timing_jitter=0)
        publisher._send = Mock(return_value={})
        publisher._sleep = Mock()
        publisher._get_response_body_with_retry = Mock(return_value={
            "body": json.dumps({
                "code": 0,
                "data": {"notes": [{"display_title": "目标标题", "tab_status": 1}]},
            })
        })
        manager_url = (
            "https://creator.xiaohongshu.com"
            f"{XHS_NOTE_MANAGER_API_PATH}?tab=0&page=0"
        )
        publisher._receive_cdp_message = Mock(side_effect=[
            {
                "method": "Network.requestWillBeSent",
                "params": {"requestId": "first", "request": {"url": manager_url}},
            },
            {
                "method": "Network.responseReceived",
                "params": {"requestId": "first", "response": {"status": 406}},
            },
            {
                "method": "Network.requestWillBeSent",
                "params": {"requestId": "second", "request": {"url": manager_url}},
            },
            {
                "method": "Network.responseReceived",
                "params": {"requestId": "second", "response": {"status": 200}},
            },
        ])

        notes = publisher._capture_note_manager_notes(retries=2)

        self.assertEqual(notes, [{"display_title": "目标标题", "tab_status": 1}])
        self.assertEqual(publisher._sleep.call_count, 1)


if __name__ == "__main__":
    unittest.main()
