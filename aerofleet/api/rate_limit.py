"""Shared slowapi Limiter instance.

Split into its own module so route files can `@limiter.limit(...)` their
endpoints without a circular import with app.py, which registers the
limiter's exception handler and imports every route module.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
