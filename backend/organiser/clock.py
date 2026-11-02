"""The house clock for new code.

Call ``clock.current_time()`` through the module, not a copied name, so a
test can freeze time by patching ``organiser.clock.current_time`` once.
``routes/system.py`` still has its own copy; the foundation change folds it in.
"""

from datetime import datetime

from organiser.config import get_settings
from organiser.timeutil import house_now


def current_time() -> datetime:
    return house_now(get_settings().house_timezone)
