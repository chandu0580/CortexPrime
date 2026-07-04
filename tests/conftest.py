"""
pytest configuration for CortexPrime integration tests.
"""
import pytest

# Use asyncio event loop for all async tests in this test suite
pytest_plugins = ["pytest_asyncio"]
