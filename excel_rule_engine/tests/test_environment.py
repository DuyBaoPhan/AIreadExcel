"""Local dotenv loading does not replace externally supplied secrets."""
from unittest.mock import patch
from app.services.environment import load_environment


def test_loader_uses_repository_root_and_preserves_environment():
    with patch('app.services.environment.load_dotenv', return_value=True) as load:
        assert load_environment() is True
    args, kwargs = load.call_args
    assert args[0].name == '.env'
    assert (args[0].parent / 'streamlit_app.py').is_file()
    assert kwargs == {'override': False}
