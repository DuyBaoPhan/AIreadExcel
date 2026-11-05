"""Presentation safety and accessibility regressions for the local UI theme."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import ui_theme



class TestUITheme(unittest.TestCase):
    def markup(self, helper, *args):
        with patch.object(ui_theme.st, "markdown") as markdown:
            helper(*args)
        markdown.assert_called_once()
        self.assertTrue(markdown.call_args.kwargs["unsafe_allow_html"])
        return markdown.call_args.args[0]

    def test_static_stylesheet_has_no_remote_resources(self):
        css = self.markup(ui_theme.inject_theme)
        self.assertEqual(css, ui_theme.THEME_CSS + ui_theme.CHAT_CSS)
        for resource in ("@import", "url(", "https://", "http://"):
            self.assertNotIn(resource, css)
        self.assertNotIn("nth-child", css)
        self.assertNotIn("display: none", css)
        self.assertNotIn("visibility: hidden", css)

    def test_theme_accessibility_and_responsive_contract(self):
        css = ui_theme.THEME_CSS
        for rule in ("prefers-reduced-motion: reduce", ":focus-visible", "outline: 3px",
                     "max-width: 700px", "grid-template-columns: 1fr", "button:disabled"):
            self.assertIn(rule, css)
        for widget in ("stChatInput", "stChatMessage", "stFileUploaderDropzone",
                       "stDownloadButton", "stTabs", "stRadio", "stDataFrame", "stExpander"):
            self.assertIn(widget, css)

    def test_dynamic_section_title_is_escaped(self):
        html = self.markup(ui_theme.render_hero, False, '<script>alert("x")</script>')
        self.assertIn('&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;', html)
        self.assertNotIn("<script>", html)
        self.assertIn("LOCAL MODE", html)
        self.assertNotIn(">ONLINE<", html)

    def test_section_intro_escapes_both_strings(self):
        html = self.markup(ui_theme.render_section_intro, '<img src=x onerror="x">', 'a & b <script>')
        self.assertIn('&lt;img src=x onerror=&quot;x&quot;&gt;', html)
        self.assertIn('a &amp; b &lt;script&gt;', html)
        self.assertNotIn('<img', html)

    def test_online_and_each_section_description(self):
        for section, description in ui_theme._SECTION_DESCRIPTIONS.items():
            with self.subTest(section=section):
                html = self.markup(ui_theme.render_hero, True, section)
                if section == "Chatbot":
                    self.assertIn("Excel Assistant", html)
                    self.assertIn("Connected", html)
                    continue
                self.assertIn(">ONLINE<", html)
                self.assertIn(description, html)
                self.assertIn("API đã kết nối", html)
                self.assertNotIn("LOCAL MODE", html)

    def test_empty_state_is_information_not_fake_controls(self):
        html = self.markup(ui_theme.render_empty_chat)
        self.assertIn('xl-welcome', html)
        self.assertIn('x\u00e1c nh\u1eadn', html)
        self.assertNotIn('kh?ng ph?i LLM', html)
        for control in ('<button', 'role="button"', 'onclick=', '<a ', 'tabindex='):
            self.assertNotIn(control, html)

    def test_helpers_compose_without_state_or_navigation(self):
        with patch.object(ui_theme.st, "markdown") as markdown:
            ui_theme.inject_theme()
            ui_theme.render_sidebar_brand()
            ui_theme.render_hero(False, "Chatbot")
            ui_theme.render_section_intro("Báo cáo", "Chọn dữ liệu của bạn.")
            ui_theme.render_empty_chat()
        self.assertEqual(markdown.call_count, 5)
        for call in markdown.call_args_list:
            self.assertTrue(call.kwargs["unsafe_allow_html"])
            self.assertIsInstance(call.args[0], str)

if __name__ == "__main__":
    unittest.main()


