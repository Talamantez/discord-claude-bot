import pytest

pytest_plugins = ['pytest_asyncio']

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as requiring asyncio"
    )