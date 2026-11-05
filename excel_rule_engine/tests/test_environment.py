"""Local dotenv loading does not replace externally supplied secrets."""
from unittest.mock import patch
from app.services.runtime.environment import load_environment


def test_loader_uses_repository_root_and_preserves_environment():
    with patch('app.services.runtime.environment.load_dotenv', return_value=True) as load:
        assert load_environment() is True
    args, kwargs = load.call_args
    assert args[0].name == '.env'
    assert (args[0].parent / 'streamlit_app.py').is_file()
    assert kwargs == {'override': False}


def test_no_local_env_does_not_import_dotenv(tmp_path):
    import builtins
    from app.services.runtime.environment import load_dotenv
    original=builtins.__import__
    def checked(name,*args,**kwargs):
        if name=='dotenv':raise AssertionError('Cloud without .env must not import dotenv')
        return original(name,*args,**kwargs)
    with patch('builtins.__import__',side_effect=checked):
        assert load_dotenv(tmp_path/'missing.env') is False


def test_local_env_without_dependency_has_install_instruction(tmp_path):
    import builtins
    import pytest
    from app.services.runtime.environment import load_dotenv
    path=tmp_path/'.env';path.write_text('EXAMPLE=local')
    original=builtins.__import__
    def missing(name,*args,**kwargs):
        if name=='dotenv':raise ModuleNotFoundError("No module named 'dotenv'",name='dotenv')
        return original(name,*args,**kwargs)
    with patch('builtins.__import__',side_effect=missing),pytest.raises(RuntimeError,match='requirements.txt'):
        load_dotenv(path)
