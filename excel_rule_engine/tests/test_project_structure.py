"""Regression checks for package relocation and stable entrypoints."""
import ast
from pathlib import Path
from unittest.mock import patch

from app.paths import APP_DIR, DATABASE_PATH, ENGINE_DIR, PROJECTS_DIR, REPOSITORY_ROOT, UI_DIR


def test_runtime_data_paths_are_unchanged():
    assert ENGINE_DIR == REPOSITORY_ROOT / "excel_rule_engine"
    assert PROJECTS_DIR == ENGINE_DIR / "projects"
    assert DATABASE_PATH == ENGINE_DIR / "excel_rule_engine.db"
    assert (PROJECTS_DIR / "demo_project/input/Sales_Data.xlsx").is_file()
    assert UI_DIR == APP_DIR / "ui"


def test_all_application_imports_resolve_to_canonical_packages():
    # Resolve names without importing Streamlit pages or starting model downloads.
    from importlib.util import find_spec
    for source in [*APP_DIR.rglob("*.py"), * (REPOSITORY_ROOT / "scripts").glob("*.py")]:
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
                assert find_spec(node.module) is not None, (source, node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("app."):
                        assert find_spec(alias.name) is not None, (source, alias.name)


def test_runtime_services_share_stable_paths(monkeypatch, tmp_path):
    from app.services.sources import file_manager
    from app.database import db
    from app.services.runtime import environment
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(file_manager, "_PROJECTS_ROOT", None)
    monkeypatch.setattr(db, "_DB_PATH", None)
    assert file_manager.get_projects_root() == PROJECTS_DIR
    assert db.get_db_path() == DATABASE_PATH
    with patch.object(environment, "load_dotenv", return_value=False) as load:
        environment.load_environment()
    load.assert_called_once_with(REPOSITORY_ROOT / ".env", override=False)


def test_root_launcher_uses_explicit_engine_file(monkeypatch):
    monkeypatch.chdir(REPOSITORY_ROOT)
    with patch("runpy.run_path") as launch:
        # Execute the source directly so the runpy mock only intercepts delegation.
        path = REPOSITORY_ROOT / "main.py"
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), {"__file__": str(path), "__name__": "__main__"})
    launch.assert_called_once_with(str(ENGINE_DIR / "main.py"), run_name="__main__")


def test_cloud_and_local_launchers_target_existing_ui():
    assert (UI_DIR / "chatbot.py").is_file()
    cloud = (REPOSITORY_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    local = (ENGINE_DIR / "main.py").read_text(encoding="utf-8")
    for source in (cloud, local):
        assert '"app" / "ui" / "chatbot.py"' in source
    assert {p.name for p in (APP_DIR / "services").glob("*.py")} == {"__init__.py"}


def test_launcher_sample_generators_exist():
    from scripts import create_sample_data
    tree = ast.parse((ENGINE_DIR / "main.py").read_text(encoding="utf-8"))
    names = [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
             and isinstance(node.value, ast.Name) and node.value.id == "sample_gen"
             and node.attr.startswith("create_")]
    assert len(names) == 5
    assert all(callable(getattr(create_sample_data, name)) for name in names)


def test_fresh_workspace_bootstrap_uses_relocated_generators(monkeypatch):
    import importlib.util
    import os
    from scripts import create_sample_data
    path = ENGINE_DIR / "main.py"
    spec = importlib.util.spec_from_file_location("migration_launcher", path)
    launcher = importlib.util.module_from_spec(spec)
    cwd = Path.cwd()
    original_output = create_sample_data.OUTPUT_DIR
    try:
        spec.loader.exec_module(launcher)
        marker = PROJECTS_DIR / "demo_project/input/Employees_IT.xlsx"
        original_exists = Path.exists
        monkeypatch.setattr(Path, "exists", lambda p: False if p == marker else original_exists(p))
        names = ["create_employees_it", "create_employees_business", "create_employees_operations",
                 "create_sales_data", "create_root_and_update_files"]
        from contextlib import ExitStack
        with ExitStack() as stack:
            calls = [stack.enter_context(patch.object(create_sample_data, name)) for name in names]
            socket = stack.enter_context(patch("socket.socket"))
            socket.return_value.__enter__.return_value.connect_ex.return_value = 1
            stack.enter_context(patch("app.database.db.init_db"))
            process = stack.enter_context(patch("subprocess.Popen"))
            stack.enter_context(patch("time.sleep"))
            stack.enter_context(patch("uvicorn.run", side_effect=KeyboardInterrupt))
            launcher.main()
            for call in calls:
                call.assert_called_once_with()
            process.return_value.terminate.assert_called_once_with()
    finally:
        os.chdir(cwd)
        create_sample_data.OUTPUT_DIR = original_output
