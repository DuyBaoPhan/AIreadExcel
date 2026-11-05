"""Friendly confirmation preview retains exact values and explicit action controls."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from app.ui.source_update_ui import format_value


@pytest.mark.parametrize('value,expected', [(42000000,'42.000.000'),(50000000,'50.000.000'),
    ('0012','0012'),(None,'(Trống)'),(True,'True'),(12.25,'12,25'),(-0.25,'-0,25'),(-1234.25,'-1.234,25'),('a<b>','a<b>')])
def test_value_format(value,expected):
    assert format_value(value)==expected


def test_preview_is_readable_without_json():
    script = """
from app.ui.source_update_ui import render_update_preview
render_update_preview({'source':'Employees_IT.xlsx','key_column':'name',
    'key_value':'Example employee','column':'salary','old_value':42000000,'new_value':50000000})
"""
    app=AppTest.from_string(script).run()
    assert not app.exception
    assert not app.get('json')
    text=[item.value for item in app.text]
    assert '42.000.000' in text and '50.000.000' in text
    assert any('Example employee' in value for value in text)
    assert app.warning


def test_chat_retains_confirmation_endpoints():
    source=(Path(__file__).resolve().parents[1]/'app/ui/chatbot.py').read_text(encoding='utf-8')
    assert 'render_update_preview(pending_update["preview"])' in source
    for endpoint in ['/api/chat/update/confirm','/api/chat/update/cancel']:
        assert endpoint in source
