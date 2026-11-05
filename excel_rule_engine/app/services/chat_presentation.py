"""Keep technical metric notes out of chat, preserving actionable warnings."""
import re


def visible_chat_warnings(warnings):
    technical = re.compile(r'^.+: (?:sum cong gia tri cua .+, khong phai dem so dong\.|count chi dem gia tri khong rong cua .+, khong phai tong hay so dong\.|rows dem so dong, khong phai tong gia tri\.)$')
    return [warning for warning in warnings if not isinstance(warning, str) or not technical.fullmatch(warning)]
