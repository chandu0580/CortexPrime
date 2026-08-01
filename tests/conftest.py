"""
pytest configuration for CortexPrime integration tests.
"""
import os
from unittest.mock import patch

import pytest

# Must be set before any module imports that validate JWT_SECRET_KEY
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-for-pytest-suite-do-not-use-in-prod")
os.environ.setdefault("AUTH_DISABLED", "false")

# Prevent real Azure OpenAI API calls during tests.
# Must start before any module-level AzureOpenAI() instantiations.
patch("openai.AzureOpenAI").start()

# Use asyncio event loop for all async tests in this test suite
pytest_plugins = ["pytest_asyncio"]
