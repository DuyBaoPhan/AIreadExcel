"""Ensure Vietnamese labels survive terminal/file encoding round trips."""
import ast
import re
from pathlib import Path
from unittest.mock import patch
from app import ui_theme


def test_welcome_preserves_vietnamese():
    with patch.object(ui_theme.st,'markdown') as render:
        ui_theme.render_empty_chat()
    html=render.call_args.args[0]
    assert 'B\u1ea1n mu\u1ed1n kh\u00e1m ph\u00e1 \u0111i\u1ec1u g\u00ec h\u00f4m nay?' in html
    assert 'x\u00e1c nh\u1eadn' in html


def test_ui_literals_have_no_replacement_or_embedded_question_marks():
    root=Path(__file__).resolve().parents[1]/'app'
    for name in ['chatbot.py','ui_theme.py']:
        source=(root/name).read_text(encoding='utf-8')
        for node in ast.walk(ast.parse(source)):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                assert '\ufffd' not in node.value, (name,node.lineno)
                assert not re.search(r'\w\?\w|\?{2,}',node.value), (name,node.lineno,node.value)


def test_key_labels_present():
    text=(Path(__file__).resolve().parents[1]/'app/chatbot.py').read_text(encoding='utf-8')
    for label in ['Cu\u1ed9c tr\u00f2 chuy\u1ec7n m\u1edbi','Ngu\u1ed3n b\u1eb1ng ch\u1ee9ng',
                  'Kh\u00e1m ph\u00e1 d\u1eef li\u1ec7u','X\u00e1c nh\u1eadn c\u1eadp nh\u1eadt']:
        assert label in text
