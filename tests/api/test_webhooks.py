import hashlib
import hmac
import json
import pytest

from app.config import settings
from httpx import AsyncClient

# We mock the celery task to avoid actually firing it during HTTP tests
@pytest.fixture(autouse=True)
def mock_analyze_pr_task(mocker):
    # Mock the delay method on the Celery task
    return mocker.patch("app.api.v1.endpoints.webhooks.analyze_pr_task.delay")

def generate_signature(payload: bytes, secret: str) -> str:
    hash_obj = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return f"sha256={hash_obj.hexdigest()}"

@pytest.mark.asyncio
async def test_github_webhook_missing_signature(client: AsyncClient):
    response = await client.post("/api/v1/webhooks/github", json={})
    assert response.status_code == 401
    assert "Missing X-Hub-Signature-256" in response.json()["detail"]

@pytest.mark.asyncio
async def test_github_webhook_invalid_signature(client: AsyncClient):
    payload = b"{}"
    headers = {
        "X-Hub-Signature-256": "sha256=invalid_hash_here"
    }
    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature"

@pytest.mark.asyncio
async def test_github_webhook_missing_github_headers(client: AsyncClient):
    payload = b"{}"
    signature = generate_signature(payload, settings.GITHUB_WEBHOOK_SECRET)
    headers = {
        "X-Hub-Signature-256": signature
    }
    # We are missing X-GitHub-Event and X-GitHub-Delivery
    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 400
    assert "Missing GitHub headers" in response.json()["detail"]

@pytest.mark.asyncio
async def test_github_webhook_ignored_event(client: AsyncClient):
    payload_dict = {"action": "created"}
    payload = json.dumps(payload_dict).encode("utf-8")
    signature = generate_signature(payload, settings.GITHUB_WEBHOOK_SECRET)
    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Event": "issues", # We only process pull_request
        "X-GitHub-Delivery": "guid-1234"
    }
    
    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "ignored"

@pytest.mark.asyncio
async def test_github_webhook_pull_request_opened(client: AsyncClient, mock_analyze_pr_task):
    payload_dict = {
        "action": "opened",
        "pull_request": {
            "html_url": "https://github.com/test/repo/pull/1"
        }
    }
    payload = json.dumps(payload_dict).encode("utf-8")
    signature = generate_signature(payload, settings.GITHUB_WEBHOOK_SECRET)
    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "guid-12345"
    }
    
    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    
    # Ensure the celery task was queued
    mock_analyze_pr_task.assert_called_once()
