"""Unit tests for src/alerts/services.py — no real AWS calls."""
from unittest.mock import MagicMock, patch

import pytest

import alerts.services as svc


# ---------------------------------------------------------------------------
# DynamoDB item helpers
# ---------------------------------------------------------------------------


def _rule_item(tenant_id="t1", rule_id="rule1", check_id="chk1",
               name="My Rule", webhook_url="https://hook.example.com",
               is_active="true") -> dict:
    return {
        "tenant_id": {"S": tenant_id},
        "rule_id": {"S": rule_id},
        "check_id": {"S": check_id},
        "name": {"S": name},
        "webhook_url": {"S": webhook_url},
        "is_active": {"S": is_active},
        "created_at": {"S": "2024-01-01T00:00:00+00:00"},
        "updated_at": {"S": "2024-01-01T00:00:00+00:00"},
    }


def _event_item(check_id="chk1", event_id="evt1", tenant_id="t1",
                status="down", delivery_status="delivered") -> dict:
    return {
        "check_id": {"S": check_id},
        "event_id": {"S": event_id},
        "tenant_id": {"S": tenant_id},
        "rule_id": {"S": "rule1"},
        "webhook_url": {"S": "https://hook.example.com"},
        "event_type": {"S": status},
        "timestamp": {"S": "2024-01-01T00:00:00Z"},
        "status": {"S": status},
        "previous_status": {"S": "up"},
        "response_time_ms": {"N": "120"},
        "delivery_status": {"S": delivery_status},
        "created_at": {"S": "2024-01-01T00:00:00+00:00"},
    }


# ---------------------------------------------------------------------------
# list_rules_for_check
# ---------------------------------------------------------------------------


def test_list_rules_for_check_returns_rules():
    mock_client = MagicMock()
    mock_client.query.return_value = {"Items": [_rule_item()]}
    with patch.object(svc, "_get_client", return_value=mock_client):
        rules = svc.list_rules_for_check("t1", "chk1")
    assert len(rules) == 1
    assert rules[0]["rule_id"] == "rule1"
    assert rules[0]["check_id"] == "chk1"
    assert rules[0]["webhook_url"] == "https://hook.example.com"


def test_list_rules_for_check_returns_empty_when_none():
    mock_client = MagicMock()
    mock_client.query.return_value = {"Items": []}
    with patch.object(svc, "_get_client", return_value=mock_client):
        rules = svc.list_rules_for_check("t1", "chk1")
    assert rules == []


def test_list_rules_for_check_tenant_isolation():
    """Query includes tenant_id filter to prevent cross-tenant data leakage."""
    mock_client = MagicMock()
    mock_client.query.return_value = {"Items": []}
    with patch.object(svc, "_get_client", return_value=mock_client):
        svc.list_rules_for_check("t1", "chk1")
    call_kwargs = mock_client.query.call_args[1]
    assert "tenant_id" in call_kwargs.get("FilterExpression", "")
    values = call_kwargs.get("ExpressionAttributeValues", {})
    assert any(v.get("S") == "t1" for v in values.values())


def test_list_rules_for_check_queries_by_check_id():
    mock_client = MagicMock()
    mock_client.query.return_value = {"Items": []}
    with patch.object(svc, "_get_client", return_value=mock_client):
        svc.list_rules_for_check("t1", "chk1")
    call_kwargs = mock_client.query.call_args[1]
    values = call_kwargs.get("ExpressionAttributeValues", {})
    assert any(v.get("S") == "chk1" for v in values.values())


# ---------------------------------------------------------------------------
# get_rule
# ---------------------------------------------------------------------------


def test_get_rule_returns_deserialized_rule():
    mock_client = MagicMock()
    mock_client.get_item.return_value = {"Item": _rule_item()}
    with patch.object(svc, "_get_client", return_value=mock_client):
        rule = svc.get_rule("t1", "rule1")
    assert rule is not None
    assert rule["rule_id"] == "rule1"
    assert rule["tenant_id"] == "t1"


def test_get_rule_returns_none_when_not_found():
    mock_client = MagicMock()
    mock_client.get_item.return_value = {}
    with patch.object(svc, "_get_client", return_value=mock_client):
        rule = svc.get_rule("t1", "nonexistent")
    assert rule is None


def test_get_rule_uses_correct_key():
    mock_client = MagicMock()
    mock_client.get_item.return_value = {}
    with patch.object(svc, "_get_client", return_value=mock_client):
        svc.get_rule("t1", "rule1")
    call_kwargs = mock_client.get_item.call_args[1]
    key = call_kwargs["Key"]
    assert key["tenant_id"]["S"] == "t1"
    assert key["rule_id"]["S"] == "rule1"


# ---------------------------------------------------------------------------
# create_rule
# ---------------------------------------------------------------------------


def test_create_rule_puts_item_and_returns_rule():
    mock_client = MagicMock()
    with patch.object(svc, "_get_client", return_value=mock_client):
        rule = svc.create_rule("t1", "chk1", "My Rule", "https://hook.example.com")
    mock_client.put_item.assert_called_once()
    assert rule["tenant_id"] == "t1"
    assert rule["check_id"] == "chk1"
    assert rule["name"] == "My Rule"
    assert rule["webhook_url"] == "https://hook.example.com"
    assert rule["is_active"] == "true"


def test_create_rule_assigns_unique_rule_id():
    mock_client = MagicMock()
    with patch.object(svc, "_get_client", return_value=mock_client):
        rule1 = svc.create_rule("t1", "chk1", "R1", "https://h1.example.com")
        rule2 = svc.create_rule("t1", "chk1", "R2", "https://h2.example.com")
    assert rule1["rule_id"] != rule2["rule_id"]


def test_create_rule_stores_correct_tenant_and_check():
    mock_client = MagicMock()
    with patch.object(svc, "_get_client", return_value=mock_client):
        svc.create_rule("tenant-x", "check-y", "R", "https://h.example.com")
    item = mock_client.put_item.call_args[1]["Item"]
    assert item["tenant_id"]["S"] == "tenant-x"
    assert item["check_id"]["S"] == "check-y"


# ---------------------------------------------------------------------------
# delete_rule
# ---------------------------------------------------------------------------


def test_delete_rule_calls_delete_item():
    mock_client = MagicMock()
    with patch.object(svc, "_get_client", return_value=mock_client):
        svc.delete_rule("t1", "rule1")
    mock_client.delete_item.assert_called_once()


def test_delete_rule_uses_correct_key():
    mock_client = MagicMock()
    with patch.object(svc, "_get_client", return_value=mock_client):
        svc.delete_rule("t1", "rule1")
    call_kwargs = mock_client.delete_item.call_args[1]
    key = call_kwargs["Key"]
    assert key["tenant_id"]["S"] == "t1"
    assert key["rule_id"]["S"] == "rule1"


# ---------------------------------------------------------------------------
# list_events_for_check
# ---------------------------------------------------------------------------


def test_list_events_for_check_returns_events():
    mock_client = MagicMock()
    mock_client.query.return_value = {"Items": [_event_item()]}
    with patch.object(svc, "_get_client", return_value=mock_client):
        events = svc.list_events_for_check("chk1")
    assert len(events) == 1
    assert events[0]["check_id"] == "chk1"
    assert events[0]["delivery_status"] == "delivered"


def test_list_events_for_check_returns_newest_first():
    """Query uses ScanIndexForward=False for descending order."""
    mock_client = MagicMock()
    mock_client.query.return_value = {"Items": []}
    with patch.object(svc, "_get_client", return_value=mock_client):
        svc.list_events_for_check("chk1")
    call_kwargs = mock_client.query.call_args[1]
    assert call_kwargs.get("ScanIndexForward") is False


def test_list_events_for_check_respects_limit():
    mock_client = MagicMock()
    mock_client.query.return_value = {"Items": []}
    with patch.object(svc, "_get_client", return_value=mock_client):
        svc.list_events_for_check("chk1", limit=10)
    call_kwargs = mock_client.query.call_args[1]
    assert call_kwargs.get("Limit") == 10


def test_list_events_for_check_empty_when_none():
    mock_client = MagicMock()
    mock_client.query.return_value = {"Items": []}
    with patch.object(svc, "_get_client", return_value=mock_client):
        assert svc.list_events_for_check("chk1") == []


def test_list_events_deserializes_numeric_fields():
    mock_client = MagicMock()
    item = _event_item()
    item["status_code"] = {"N": "503"}
    mock_client.query.return_value = {"Items": [item]}
    with patch.object(svc, "_get_client", return_value=mock_client):
        events = svc.list_events_for_check("chk1")
    assert events[0]["status_code"] == 503
    assert events[0]["response_time_ms"] == 120
