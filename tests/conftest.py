"""Test setup: use a temporary SQLite file so tests never touch your real farm.db."""
import os
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name.replace(os.sep, '/')}"
