"""
pytest configuration for CortexPrime integration tests.
"""
from unittest.mock import patch

import pytest

# Prevent real Azure OpenAI API calls during tests.
# Must start before any module-level AzureOpenAI() instantiations.
patch("openai.AzureOpenAI").start()

# Use asyncio event loop for all async tests in this test suite
pytest_plugins = ["pytest_asyncio"]
