"""Unit tests for lambda_handler/alert_handler.py — no real network or DDB calls."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from lambda_handler.alert_handler import (
    _build_webhook_payload,
    _deliver_webhooks_async,
    _get_alert_rules,
    _parse_new_image,
    _post_webhook,
    _process_record,
    _update_check_current_status,
    handler,
)


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------


def _stream_record(
    check_id="chk1",
    tenant_id="t1",
    status="down",
    timestamp="2024-01-01T00:00:00Z",
    status_code=503,
    response_time_ms=120,
    event_name="MODIFY",
) -> dict:
    return {
        "eventName": event_name,
        "dynamodb": {
            "NewImage": {
                "check_id": {"S": check_id},
                "tenant_id": {"S": tenant_id},
                "status": {"S": status},
                "timestamp": {"S": timestamp},
                "status_code": {"N": str(status_code)},
                "response_time_ms": {"N": str(response_time_ms)},
            }
        },
    }


def _check_item(check_id="chk1", tenant_id="t1", current_status="up",
                name="My Check", url="https://example.com") -> dict:
    return {
        "Item": {
            "check_id": {"S": check_id},
            "tenant_id": {"S": tenant_id},
            "current_status": {"S": current_status},
            "name": {"S": name},
            "url": {"S": url},
        }
    }


def _rule_item(check_id="chk1", tenant_id="t1", rule_id="rule1",
               webhook_url="https://hook.example.com", on_recovery="true") -> dict:
    """DynamoDB-format rule item (as returned by ddb.query)."""
    return {
        "tenant_id": {"S": tenant_id},
        "rule_id": {"S": rule_id},
        "check_id": {"S": check_id},
        "webhook_url": {"S": webhook_url},
        "name": {"S": "My Rule"},
        "is_active": {"S": "true"},
        "on_recovery": {"S": on_recovery},
    }


def _plain_rule(check_id="chk1", tenant_id="t1", rule_id="rule1",
                webhook_url="https://hook.example.com", on_recovery="true") -> dict:
    """Deserialized rule dict (as returned by _get_alert_rules)."""
    return {
        "tenant_id": tenant_id,
        "rule_id": rule_id,
        "check_id": check_id,
        "webhook_url": webhook_url,
        "name": "My Rule",
        "on_recovery": on_recovery,
    }


def _result_dict(check_id="chk1", tenant_id="t1", status="down") -> dict:
    return {
        "check_id": check_id,
        "tenant_id": tenant_id,
        "status": status,
        "timestamp": "2024-01-01T00:00:00Z",
        "status_code": 503,
        "response_time_ms": 120,
        "error_message": None,
    }


def _ddb_mock(check_item, rules_items, conditional_update_succeeds=True):
    ddb = MagicMock()
    ddb.get_item.return_value = check_item
    ddb.query.return_value = {"Items": rules_items}
    if not conditional_update_succeeds:
        error = {"Error": {"Code": "ConditionalCheckFailedException"}}
        ddb.update_item.side_effect = ClientError(error, "UpdateItem")
    return ddb


# ---------------------------------------------------------------------------
# _parse_new_image
# ---------------------------------------------------------------------------


def test_parse_new_image_valid():
    result = _parse_new_image(_stream_record())
    assert result["check_id"] == "chk1"
    assert result["tenant_id"] == "t1"
    assert result["status"] == "down"
    assert result["status_code"] == 503
    assert result["response_time_ms"] == 120


def test_parse_new_image_no_new_image():
    assert _parse_new_image({"dynamodb": {}}) is None


def test_parse_new_image_missing_check_id():
    record = _stream_record()
    del record["dynamodb"]["NewImage"]["check_id"]
    assert _parse_new_image(record) is None


def test_parse_new_image_no_status_code_defaults_to_none():
    record = _stream_record()
    del record["dynamodb"]["NewImage"]["status_code"]
    result = _parse_new_image(record)
    assert result["status_code"] is None


def test_parse_new_image_no_response_time_defaults_to_zero():
    record = _stream_record()
    del record["dynamodb"]["NewImage"]["response_time_ms"]
    result = _parse_new_image(record)
    assert result["response_time_ms"] == 0


# ---------------------------------------------------------------------------
# _build_webhook_payload
# ---------------------------------------------------------------------------


def test_build_webhook_payload_shape():
    check = {"check_id": "chk1", "name": "My Check", "url": "https://example.com"}
    result = _result_dict()
    payload = _build_webhook_payload("down", check, result, "up")

    assert payload["event_type"] == "down"
    assert payload["check_id"] == "chk1"
    assert payload["check_name"] == "My Check"
    assert payload["url"] == "https://example.com"
    assert payload["status"] == "down"
    assert payload["previous_status"] == "up"
    assert payload["status_code"] == 503
    assert payload["response_time_ms"] == 120
    assert "timestamp" in payload
    assert "error_message" in payload


# ---------------------------------------------------------------------------
# _update_check_current_status
# ---------------------------------------------------------------------------


def test_update_check_current_status_success_returns_true():
    ddb = MagicMock()
    assert _update_check_current_status(ddb, "t1", "chk1", "down", "up") is True
    ddb.update_item.assert_called_once()


def test_update_check_current_status_conditional_fail_returns_false():
    ddb = MagicMock()
    error = {"Error": {"Code": "ConditionalCheckFailedException"}}
    ddb.update_item.side_effect = ClientError(error, "UpdateItem")
    assert _update_check_current_status(ddb, "t1", "chk1", "down", "up") is False


def test_update_check_current_status_other_client_error_raises():
    ddb = MagicMock()
    error = {"Error": {"Code": "ProvisionedThroughputExceededException"}}
    ddb.update_item.side_effect = ClientError(error, "UpdateItem")
    with pytest.raises(ClientError):
        _update_check_current_status(ddb, "t1", "chk1", "down", "up")


def test_update_check_current_status_none_old_uses_attribute_not_exists():
    ddb = MagicMock()
    _update_check_current_status(ddb, "t1", "chk1", "down", None)
    call_kwargs = ddb.update_item.call_args[1]
    assert "attribute_not_exists" in call_kwargs["ConditionExpression"]


# ---------------------------------------------------------------------------
# _get_alert_rules
# ---------------------------------------------------------------------------


def test_get_alert_rules_returns_on_recovery_field():
    ddb = MagicMock()
    ddb.query.return_value = {"Items": [_rule_item(on_recovery="false")]}
    rules = _get_alert_rules(ddb, "chk1")
    assert len(rules) == 1
    assert rules[0]["on_recovery"] == "false"


def test_get_alert_rules_defaults_on_recovery_to_true():
    ddb = MagicMock()
    item = _rule_item()
    del item["on_recovery"]
    ddb.query.return_value = {"Items": [item]}
    rules = _get_alert_rules(ddb, "chk1")
    assert rules[0]["on_recovery"] == "true"


def test_get_alert_rules_empty_when_no_items():
    ddb = MagicMock()
    ddb.query.return_value = {"Items": []}
    assert _get_alert_rules(ddb, "chk1") == []


# ---------------------------------------------------------------------------
# _post_webhook
# ---------------------------------------------------------------------------


async def test_post_webhook_2xx_returns_true():
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp

    assert await _post_webhook(mock_session, "https://hook.example.com", {}) is True


async def test_post_webhook_5xx_returns_false():
    mock_resp = MagicMock()
    mock_resp.status = 500
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp

    assert await _post_webhook(mock_session, "https://hook.example.com", {}) is False


async def test_post_webhook_exception_returns_false_without_raising():
    mock_session = MagicMock()
    mock_session.post.side_effect = Exception("Network error")
    assert await _post_webhook(mock_session, "https://hook.example.com", {}) is False


# ---------------------------------------------------------------------------
# _deliver_webhooks_async
# ---------------------------------------------------------------------------


def _mock_aiohttp_session():
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False
    return session


async def test_deliver_webhooks_logs_delivered_event_on_success():
    ddb = MagicMock()
    rules = [_plain_rule()]
    result = _result_dict()

    with patch("lambda_handler.alert_handler._post_webhook", new=AsyncMock(return_value=True)):
        with patch("lambda_handler.alert_handler.aiohttp.ClientSession",
                   return_value=_mock_aiohttp_session()):
            await _deliver_webhooks_async(rules, {"event": 1}, result, "up", ddb)

    ddb.put_item.assert_called_once()
    item = ddb.put_item.call_args[1]["Item"]
    assert item["delivery_status"]["S"] == "delivered"
    assert "delivered_at" in item
    assert item["check_id"]["S"] == "chk1"


async def test_deliver_webhooks_logs_failed_event_on_webhook_error():
    ddb = MagicMock()
    rules = [_plain_rule()]
    result = _result_dict()

    with patch("lambda_handler.alert_handler._post_webhook", new=AsyncMock(return_value=False)):
        with patch("lambda_handler.alert_handler.aiohttp.ClientSession",
                   return_value=_mock_aiohttp_session()):
            await _deliver_webhooks_async(rules, {"event": 1}, result, "up", ddb)

    ddb.put_item.assert_called_once()
    item = ddb.put_item.call_args[1]["Item"]
    assert item["delivery_status"]["S"] == "failed"
    assert "delivered_at" not in item


async def test_deliver_webhooks_fires_one_event_per_rule():
    ddb = MagicMock()
    rules = [_plain_rule(rule_id="r1"), _plain_rule(rule_id="r2")]
    result = _result_dict()

    with patch("lambda_handler.alert_handler._post_webhook", new=AsyncMock(return_value=True)):
        with patch("lambda_handler.alert_handler.aiohttp.ClientSession",
                   return_value=_mock_aiohttp_session()):
            await _deliver_webhooks_async(rules, {}, result, "up", ddb)

    assert ddb.put_item.call_count == 2


# ---------------------------------------------------------------------------
# _process_record — status transition detection
# ---------------------------------------------------------------------------


def _run_and_close(coro):
    """Side effect for patching asyncio.run: close the coroutine to prevent ResourceWarning."""
    coro.close()


def test_process_record_same_status_does_not_fire_webhook():
    ddb = _ddb_mock(_check_item(current_status="down"), [_rule_item()])
    record = _stream_record(status="down")

    with patch("lambda_handler.alert_handler.asyncio.run") as mock_run:
        _process_record(ddb, record)
        mock_run.assert_not_called()


def test_process_record_up_to_down_fires_webhook():
    ddb = _ddb_mock(_check_item(current_status="up"), [_rule_item()])
    record = _stream_record(status="down")

    with patch("lambda_handler.alert_handler.asyncio.run", side_effect=_run_and_close) as mock_run:
        _process_record(ddb, record)
        mock_run.assert_called_once()


def test_process_record_down_to_up_fires_webhook_when_on_recovery_true():
    ddb = _ddb_mock(_check_item(current_status="down"), [_rule_item(on_recovery="true")])
    record = _stream_record(status="up")

    with patch("lambda_handler.alert_handler.asyncio.run", side_effect=_run_and_close) as mock_run:
        _process_record(ddb, record)
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# _process_record — on_recovery=false skips recovery webhook
# ---------------------------------------------------------------------------


def test_process_record_on_recovery_false_skips_up_event():
    ddb = _ddb_mock(_check_item(current_status="down"), [_rule_item(on_recovery="false")])
    record = _stream_record(status="up")

    with patch("lambda_handler.alert_handler.asyncio.run") as mock_run:
        _process_record(ddb, record)
        mock_run.assert_not_called()


def test_process_record_on_recovery_false_does_not_affect_down_event():
    """on_recovery=false only suppresses recovery (up) events, not down events."""
    ddb = _ddb_mock(_check_item(current_status="up"), [_rule_item(on_recovery="false")])
    record = _stream_record(status="down")

    with patch("lambda_handler.alert_handler.asyncio.run", side_effect=_run_and_close) as mock_run:
        _process_record(ddb, record)
        mock_run.assert_called_once()


def test_process_record_mixed_rules_partial_recovery_suppression():
    """One rule with on_recovery=true, one with false — only the true rule fires."""
    rules_items = [
        _rule_item(rule_id="r1", on_recovery="true"),
        _rule_item(rule_id="r2", on_recovery="false"),
    ]
    ddb = _ddb_mock(_check_item(current_status="down"), rules_items)
    record = _stream_record(status="up")

    captured_rules = []

    def capture_run(coro):
        import asyncio as real_asyncio
        rules_arg = coro.cr_frame.f_locals.get("rules", [])
        captured_rules.extend(rules_arg)
        coro.close()

    with patch("lambda_handler.alert_handler.asyncio.run", side_effect=capture_run):
        _process_record(ddb, record)

    assert len(captured_rules) == 1
    assert captured_rules[0]["rule_id"] == "r1"


# ---------------------------------------------------------------------------
# _process_record — idempotency
# ---------------------------------------------------------------------------


def test_process_record_idempotency_guard_prevents_duplicate_webhook():
    ddb = _ddb_mock(
        _check_item(current_status="up"),
        [_rule_item()],
        conditional_update_succeeds=False,
    )
    record = _stream_record(status="down")

    with patch("lambda_handler.alert_handler.asyncio.run") as mock_run:
        _process_record(ddb, record)
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# _process_record — edge cases
# ---------------------------------------------------------------------------


def test_process_record_ignores_remove_events():
    ddb = MagicMock()
    _process_record(ddb, _stream_record(event_name="REMOVE"))
    ddb.get_item.assert_not_called()


def test_process_record_returns_early_when_check_not_found():
    ddb = MagicMock()
    ddb.get_item.return_value = {}
    with patch("lambda_handler.alert_handler.asyncio.run") as mock_run:
        _process_record(ddb, _stream_record(status="down"))
        mock_run.assert_not_called()


def test_process_record_returns_early_when_no_rules():
    ddb = _ddb_mock(_check_item(current_status="up"), [])
    with patch("lambda_handler.alert_handler.asyncio.run") as mock_run:
        _process_record(ddb, _stream_record(status="down"))
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# handler (entry point)
# ---------------------------------------------------------------------------


def test_handler_returns_200_and_processed_count():
    event = {"Records": [_stream_record()]}
    with patch("lambda_handler.alert_handler._get_dynamodb_client") as mock_client:
        ddb = MagicMock()
        ddb.get_item.return_value = {}
        mock_client.return_value = ddb
        result = handler(event, {})
    assert result["statusCode"] == 200
    assert result["processed"] == 1


def test_handler_does_not_raise_on_record_exception():
    event = {"Records": [_stream_record(), _stream_record()]}
    with patch("lambda_handler.alert_handler._get_dynamodb_client") as mock_client:
        ddb = MagicMock()
        ddb.get_item.side_effect = Exception("DDB error")
        mock_client.return_value = ddb
        result = handler(event, {})
    assert result["statusCode"] == 200
    assert result["processed"] == 2


def test_handler_empty_records():
    result = handler({"Records": []}, {})
    assert result["statusCode"] == 200
    assert result["processed"] == 0
