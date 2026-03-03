import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_graph, get_workspace_manager
from src.core.config import settings

# Mock out the singletons so tests are fast and isolated
mock_workspace_manager = MagicMock()
mock_workspace_manager.identify_repository.return_value = "owner/repo"

mock_graph = MagicMock()
# Graph stream yields an iterator of dicts representing the node states
mock_graph.stream.return_value = iter([{"FINISH": {"status": "success"}}])


# Override dependencies for the test client
app = create_app()
app.dependency_overrides[get_workspace_manager] = lambda: mock_workspace_manager
app.dependency_overrides[get_graph] = lambda: mock_graph

client = TestClient(app)


def generate_signature(payload: dict, secret: str) -> str:
    """Helper to generate a valid HMAC signature for a payload."""
    payload_bytes = json.dumps(payload).encode("utf-8")
    hash_obj = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256)
    return f"sha256={hash_obj.hexdigest()}"


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Ensure the webhook secret is set for tests without mutating global state."""
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "test_secret_123")


def test_health_check():
    """Verify the health endpoint works."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "agentic-engineering-api",
        "workspace_ready": False,
    }


def test_webhook_missing_signature():
    """Expect 403 when the signature header is missing."""
    payload = {"action": "opened"}
    response = client.post("/webhooks/github", json=payload)
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid signature"}


def test_webhook_invalid_signature():
    """Expect 403 when the signature header is wrong."""
    payload = {"action": "opened"}
    headers = {"X-Hub-Signature-256": "sha256=invalid_hash_data"}
    response = client.post("/webhooks/github", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid signature"}


def test_webhook_ignored_event():
    """Expect 'ignored' status when the GitHub event is not 'issues'."""
    payload = {"action": "opened"}
    payload_body = json.dumps(payload).encode("utf-8")
    hash_obj = hmac.new(b"test_secret_123", payload_body, hashlib.sha256)
    signature = f"sha256={hash_obj.hexdigest()}"
    headers = {"X-Hub-Signature-256": signature, "X-GitHub-Event": "push"}

    response = client.post("/webhooks/github", content=payload_body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_webhook_ignored_action():
    """Expect 'ignored' status when the issues action is not handled."""
    payload = {"action": "closed", "issue": {"number": 1}}
    payload_body = json.dumps(payload).encode("utf-8")
    hash_obj = hmac.new(b"test_secret_123", payload_body, hashlib.sha256)
    signature = f"sha256={hash_obj.hexdigest()}"
    headers = {"X-Hub-Signature-256": signature, "X-GitHub-Event": "issues"}

    response = client.post("/webhooks/github", content=payload_body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


@patch("src.api.webhooks.post_issue_comment", new_callable=AsyncMock)
def test_webhook_valid_issue(mock_post_comment):
    """Expect successful execution loop for a valid issue creation."""
    payload = {
        "action": "opened",
        "issue": {
            "number": 42,
            "title": "Fix the login bug",
            "body": "Users cannot log in.",
            "labels": [{"name": "bug"}],
        },
        "repository": {"full_name": "owner/test-repo"},
        "sender": {"login": "testuser"},
    }
    payload_body = json.dumps(payload).encode("utf-8")
    hash_obj = hmac.new(b"test_secret_123", payload_body, hashlib.sha256)
    signature = f"sha256={hash_obj.hexdigest()}"
    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Event": "issues",
        "Content-Type": "application/json",
    }

    response = client.post("/webhooks/github", content=payload_body, headers=headers)

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert "thread_id" in res_data

    # Verify our mock dependencies were called
    mock_workspace_manager.identify_repository.assert_called_once()
    mock_graph.stream.assert_called_once()

    # Verify the callback was triggered
    mock_post_comment.assert_called_once()
    args, kwargs = mock_post_comment.call_args
    assert args[0] == "owner/test-repo"  # repo
    assert args[1] == 42  # issue_number
    assert "Agentic Execution Completed" in args[2]  # body
