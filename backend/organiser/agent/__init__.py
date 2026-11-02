"""Mistral assistant for the house log.

Rules in ``rules.py`` decide when it runs. Within a run, Mistral reads the log
through ``functions.py`` and can only propose. Nick's Apply tap is the only write.
Keep this module light: ``python -m organiser.agent`` imports it without a database.
"""
