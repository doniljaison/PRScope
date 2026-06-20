"""
conftest.py — Shared pytest fixtures.

Fixtures defined here are available to ALL test files automatically.
No import needed — pytest discovers them by convention.

Day 1: Empty (just the file needs to exist).
Day 3+: Add DB session fixture, async test client fixture, etc.
"""

# Future fixtures will go here, for example:
#
# import pytest
# from httpx import AsyncClient, ASGITransport
# from app.main import app
#
# @pytest.fixture
# async def client():
#     async with AsyncClient(
#         transport=ASGITransport(app=app), base_url="http://test"
#     ) as ac:
#         yield ac
