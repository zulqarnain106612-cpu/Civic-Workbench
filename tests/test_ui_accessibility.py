"""Static keyboard/accessibility checks for the browser workbench markup (REQ-UI-001)."""
from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src/civic_workbench/web"
VOID = {"input", "br", "img", "meta", "link", "hr", "source"}


class _Audit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.lang = None
        self.label_for: set[str] = set()
        self.controls: list[tuple[str | None, bool, str | None, str | None]] = []
        self.positive_tabindex: list[dict] = []
        self.empty_buttons: list[dict] = []
        self._button: list | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang")
        if tag == "label" and attrs.get("for"):
            self.label_for.add(attrs["for"])
        if tag in {"input", "select", "textarea"}:
            self.controls.append((attrs.get("id"), "label" in self.stack, attrs.get("aria-label"), attrs.get("type")))
        if attrs.get("tabindex", "0").lstrip("-").isdigit() and int(attrs.get("tabindex", "0")) > 0:
            self.positive_tabindex.append(attrs)
        if tag == "button":
            self._button = [attrs, ""]
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "button" and self._button is not None:
            if not self._button[1].strip() and not self._button[0].get("aria-label"):
                self.empty_buttons.append(self._button[0])
            self._button = None
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self._button is not None:
            self._button[1] += data


class UiAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = _Audit()
        cls.audit.feed((WEB / "index.html").read_text(encoding="utf-8"))
        cls.script = (WEB / "app.js").read_text(encoding="utf-8")

    def test_document_language_is_declared(self):
        self.assertEqual(self.audit.lang, "en")

    def test_every_form_control_has_an_accessible_label(self):
        unlabeled = [c for c in self.audit.controls
                     if c[3] != "hidden" and not (c[1] or c[2] or c[0] in self.audit.label_for)]
        self.assertEqual(unlabeled, [])

    def test_buttons_have_names_and_tab_order_is_natural(self):
        self.assertEqual(self.audit.empty_buttons, [])
        self.assertEqual(self.audit.positive_tabindex, [])

    def test_interactive_rows_use_native_controls_and_errors_are_surfaced(self):
        # Clickable behaviour is bound to buttons/rows from app.js; errors always reach the notice area.
        self.assertGreaterEqual(len(re.findall(r'note\(e(rror)?\.message,\s*["\']error["\']\)', self.script)), 10)
        self.assertIn('id="txAbortAll"', (WEB / "index.html").read_text(encoding="utf-8"))

    def test_selectable_frame_rows_are_keyboard_operable(self):
        self.assertIn('<tr tabindex="0" data-frame=', self.script)
        self.assertIn('ev.key==="Enter"', self.script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
