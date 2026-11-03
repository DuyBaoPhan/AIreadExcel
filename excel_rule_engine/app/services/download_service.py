"""Fetch output files server-side so browsers never need the private API URL."""
from urllib.parse import quote

import requests

EXCEL_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def fetch_output_file(api_base: str, project: str, filename: str) -> bytes:
    """Use the existing download endpoint, preserving its access/path checks."""
    url = f"{api_base.rstrip('/')}/api/download/{quote(project, safe='')}/{quote(filename, safe='')}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content
