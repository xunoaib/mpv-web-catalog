from .metadata import ApiException
from .web import create_app

try:
    app = create_app()
except ApiException as exc:
    print(exc)
    print('Check your environment variables (ie: MPV_MOVIECTL_CACHE_DIR)')
