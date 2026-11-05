"""All provider prompts require Vietnamese without corrupting machine identifiers."""
import pytest
from app.services import chat_agent, openai_planner, rag_answer


@pytest.mark.parametrize('module',[chat_agent,openai_planner,rag_answer])
def test_vietnamese_language_policy_in_all_prompts(module):
    assert 'Always write all user-facing prose' in module._PROMPT
    assert 'Vietnamese with correct accents' in module._PROMPT
    assert 'Do not translate' in module._PROMPT
    assert 'Keep JSON field names' in module._PROMPT
