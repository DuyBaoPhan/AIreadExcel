"""Public API capability checks; never terminate or replace an unknown server."""
import requests

REQUIRED_REPORT_ROUTES = ('/api/report/preview', '/api/report/confirm', '/api/report/auto', '/api/chat', '/api/chat/update/confirm')


def check_report_api(base_url='http://127.0.0.1:8000'):
    """Return compatibility and a diagnostic using documented OpenAPI only."""
    try:
        response = requests.get(base_url.rstrip('/') + '/openapi.json', timeout=3)
        response.raise_for_status()
        document = response.json()
        paths = document.get('paths', {})
        if not isinstance(paths, dict):
            return False, 'Backend OpenAPI paths khong hop le'
        missing = [route for route in REQUIRED_REPORT_ROUTES
                   if not isinstance(paths.get(route), dict) or 'post' not in paths[route]]
        if missing:
            return False, 'Backend thieu API: ' + ', '.join(missing)
        return True, ''
    except (requests.RequestException, ValueError, AttributeError, TypeError) as exc:
        return False, 'Khong kiem tra duoc backend: ' + str(exc)
