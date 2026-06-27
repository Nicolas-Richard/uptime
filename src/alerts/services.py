"""DynamoDB service layer for alert rules and alert events."""
import uuid
from datetime import datetime, timezone

import boto3
from django.conf import settings


def _get_client():
    kwargs = {"region_name": settings.AWS_REGION}
    if settings.DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
    return boto3.client("dynamodb", **kwargs)


# ---------------------------------------------------------------------------
# Alert rules
# ---------------------------------------------------------------------------


def list_rules_for_check(tenant_id: str, check_id: str) -> list[dict]:
    """Return all alert rules for a check, regardless of active state."""
    client = _get_client()
    resp = client.query(
        TableName="alert_rules",
        IndexName="check_id-index",
        KeyConditionExpression="check_id = :cid",
        FilterExpression="tenant_id = :tid",
        ExpressionAttributeValues={
            ":cid": {"S": check_id},
            ":tid": {"S": tenant_id},
        },
    )
    rules = []
    for item in resp.get("Items", []):
        rules.append(_deserialize_rule(item))
    return rules


def get_rule(tenant_id: str, rule_id: str) -> dict | None:
    """Return a single alert rule by tenant + rule_id, or None."""
    client = _get_client()
    resp = client.get_item(
        TableName="alert_rules",
        Key={"tenant_id": {"S": tenant_id}, "rule_id": {"S": rule_id}},
    )
    item = resp.get("Item")
    return _deserialize_rule(item) if item else None


def create_rule(tenant_id: str, check_id: str, name: str, webhook_url: str) -> dict:
    """Create an alert rule and return the new item."""
    client = _get_client()
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "tenant_id": {"S": tenant_id},
        "rule_id": {"S": str(uuid.uuid4())},
        "check_id": {"S": check_id},
        "name": {"S": name},
        "webhook_url": {"S": webhook_url},
        "is_active": {"S": "true"},
        "created_at": {"S": now},
        "updated_at": {"S": now},
    }
    client.put_item(TableName="alert_rules", Item=item)
    return _deserialize_rule(item)


def delete_rule(tenant_id: str, rule_id: str) -> None:
    """Delete an alert rule."""
    client = _get_client()
    client.delete_item(
        TableName="alert_rules",
        Key={"tenant_id": {"S": tenant_id}, "rule_id": {"S": rule_id}},
    )


def _deserialize_rule(item: dict) -> dict:
    return {
        "tenant_id": item["tenant_id"]["S"],
        "rule_id": item["rule_id"]["S"],
        "check_id": item["check_id"]["S"],
        "name": item.get("name", {}).get("S", ""),
        "webhook_url": item.get("webhook_url", {}).get("S", ""),
        "is_active": item.get("is_active", {}).get("S", "true"),
        "created_at": item.get("created_at", {}).get("S", ""),
    }


# ---------------------------------------------------------------------------
# Alert events
# ---------------------------------------------------------------------------


def list_events_for_check(check_id: str, limit: int = 50) -> list[dict]:
    """Return recent alert events for a check, newest first."""
    client = _get_client()
    resp = client.query(
        TableName="alert_events",
        KeyConditionExpression="check_id = :cid",
        ExpressionAttributeValues={":cid": {"S": check_id}},
        ScanIndexForward=False,
        Limit=limit,
    )
    return [_deserialize_event(item) for item in resp.get("Items", [])]


def _deserialize_event(item: dict) -> dict:
    return {
        "check_id": item["check_id"]["S"],
        "event_id": item["event_id"]["S"],
        "tenant_id": item.get("tenant_id", {}).get("S", ""),
        "rule_id": item.get("rule_id", {}).get("S", ""),
        "webhook_url": item.get("webhook_url", {}).get("S", ""),
        "event_type": item.get("event_type", {}).get("S", ""),
        "timestamp": item.get("timestamp", {}).get("S", ""),
        "status": item.get("status", {}).get("S", ""),
        "previous_status": item.get("previous_status", {}).get("S", ""),
        "status_code": (
            int(item["status_code"]["N"])
            if "status_code" in item and "N" in item.get("status_code", {})
            else None
        ),
        "response_time_ms": (
            int(item["response_time_ms"]["N"])
            if "response_time_ms" in item and "N" in item.get("response_time_ms", {})
            else 0
        ),
        "error_message": item.get("error_message", {}).get("S", ""),
        "delivery_status": item.get("delivery_status", {}).get("S", ""),
        "delivered_at": item.get("delivered_at", {}).get("S", ""),
        "created_at": item.get("created_at", {}).get("S", ""),
    }
