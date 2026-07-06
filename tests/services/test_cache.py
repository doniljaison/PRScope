"""
test_cache.py — Tests for the Redis cache-aside service.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.cache import cache_get, cache_set, cache_delete, cache_exists


@pytest.fixture
def mock_redis():
    """Mock the internal Redis client used by the cache module."""
    mock = AsyncMock()
    with patch("app.services.cache._get_redis", return_value=mock):
        yield mock


@pytest.mark.asyncio
async def test_cache_get_miss(mock_redis):
    """Cache miss returns None."""
    mock_redis.get.return_value = None

    result = await cache_get("nonexistent")

    assert result is None
    mock_redis.get.assert_called_once_with("prscope:nonexistent")


@pytest.mark.asyncio
async def test_cache_get_hit(mock_redis):
    """Cache hit returns deserialized JSON."""
    mock_redis.get.return_value = '{"name": "test", "count": 42}'

    result = await cache_get("mykey")

    assert result == {"name": "test", "count": 42}


@pytest.mark.asyncio
async def test_cache_get_error_returns_none(mock_redis):
    """If Redis fails, cache_get returns None instead of crashing."""
    mock_redis.get.side_effect = ConnectionError("Redis down")

    result = await cache_get("somekey")

    assert result is None


@pytest.mark.asyncio
async def test_cache_set_success(mock_redis):
    """cache_set stores JSON with TTL."""
    mock_redis.set.return_value = True

    result = await cache_set("mykey", {"data": [1, 2, 3]}, ttl_seconds=60)

    assert result is True
    mock_redis.set.assert_called_once_with(
        "prscope:mykey", '{"data": [1, 2, 3]}', ex=60
    )


@pytest.mark.asyncio
async def test_cache_set_default_ttl(mock_redis):
    """cache_set uses 300s default TTL."""
    mock_redis.set.return_value = True

    await cache_set("mykey", "simple_value")

    mock_redis.set.assert_called_once_with(
        "prscope:mykey", '"simple_value"', ex=300
    )


@pytest.mark.asyncio
async def test_cache_set_error_returns_false(mock_redis):
    """If Redis fails, cache_set returns False instead of crashing."""
    mock_redis.set.side_effect = ConnectionError("Redis down")

    result = await cache_set("mykey", "value")

    assert result is False


@pytest.mark.asyncio
async def test_cache_delete_success(mock_redis):
    """cache_delete removes the key."""
    mock_redis.delete.return_value = 1

    result = await cache_delete("mykey")

    assert result is True
    mock_redis.delete.assert_called_once_with("prscope:mykey")


@pytest.mark.asyncio
async def test_cache_delete_nonexistent(mock_redis):
    """Deleting a nonexistent key returns False."""
    mock_redis.delete.return_value = 0

    result = await cache_delete("nonexistent")

    assert result is False


@pytest.mark.asyncio
async def test_cache_exists_true(mock_redis):
    """cache_exists returns True when key exists."""
    mock_redis.exists.return_value = 1

    result = await cache_exists("mykey")

    assert result is True


@pytest.mark.asyncio
async def test_cache_exists_false(mock_redis):
    """cache_exists returns False when key doesn't exist."""
    mock_redis.exists.return_value = 0

    result = await cache_exists("mykey")

    assert result is False
