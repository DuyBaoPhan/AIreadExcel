from app.services.chat_presentation import visible_chat_warnings


def test_hide_metric_notes_preserve_real_warnings():
    warnings=['total_revenue: sum cong gia tri cua revenue, khong phai dem so dong.',
              'n: count chi dem gia tri khong rong cua name, khong phai tong hay so dong.',
              'n: rows dem so dong, khong phai tong gia tri.',
              'No rows match the report filters','Source could not be read']
    assert visible_chat_warnings(warnings)==warnings[3:]


def test_filter_details_not_rendered_in_message():
    import ast
    from pathlib import Path
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import Mock
    path=Path(__file__).resolve().parents[1]/'app/chatbot.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_message')
    ui=SimpleNamespace(chat_message=lambda *a,**k:nullcontext(),markdown=Mock(),warning=Mock(),json=Mock())
    ns={'st':ui}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
    ns['render_message']({'role':'assistant','content':'Done','metadata':{
        'applied_filters':[{'column':'month'}], 'warnings':[
            'total: sum cong gia tri cua revenue, khong phai dem so dong.', 'Important warning']}})
    ui.json.assert_not_called()
    ui.warning.assert_called_once_with('Important warning')
