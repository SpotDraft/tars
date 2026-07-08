"""
Base class for all DB repository tests.

Mirrors SDTestCase in django-rest-api/core/testing.py.

Usage
-----
Inherit from BaseDBRepoTestCase and declare the `db_session` fixture as a
method parameter.  Each test method gets a fresh session with a rolled-back
transaction.                      # run everything
"""

import pytest


@pytest.mark.integration
class BaseDBRepoTestCase:
    pass
