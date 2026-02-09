"""
Shared Flask extension instances.

Created as a separate module to avoid circular imports when route
blueprints need access to extensions that are initialised in server.py.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Limiter is created without an app; init_app() is called in server.py.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)
