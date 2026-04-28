"""DynamoDB service layer for checks (CRUD)."""
import uuid
from datetime import datetime, timezone

import boto3
from django.conf import settings


def _get_table():
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=settings.DYNAMODB_ENDPOINT_URL,
        region_name=settings.AWS_REGION,
    )
    return dynamodb.Table("checks")


def list_checks(tenant_id: str) -> list[dict]:
    """Return all checks for a tenant."""
    table = _get_table()
    resp = table.query(
        KeyConditionExpression="tenant_id = :tid",
        ExpressionAttributeValues={":tid": tenant_id},
    )
    return resp.get("Items", [])


def get_check(tenant_id: str, check_id: str) -> dict | None:
    """Return a single check, or None if not found."""
    table = _get_table()
    resp = table.get_item(Key={"tenant_id": tenant_id, "check_id": check_id})
    return resp.get("Item")


def create_check(
    tenant_id: str,
    name: str,
    url: str,
    timeout_seconds: int = 30,
) -> dict:
    """Create a new check and return the item."""
    table = _get_table()
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "tenant_id": tenant_id,
        "check_id": str(uuid.uuid4()),
        "name": name,
        "url": url,
        "timeout_seconds": timeout_seconds,
        "is_active": "true",
        "created_at": now,
        "updated_at": now,
    }
    table.put_item(Item=item)
    return item


def update_check(tenant_id: str, check_id: str, **kwargs) -> dict | None:
    """Update attributes on an existing check. Returns updated item or None."""
    if not kwargs:
        return get_check(tenant_id, check_id)

    kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()

    update_parts = []
    attr_names = {}
    attr_values = {}
    for i, (key, value) in enumerate(kwargs.items()):
        placeholder_name = f"#k{i}"
        placeholder_value = f":v{i}"
        update_parts.append(f"{placeholder_name} = {placeholder_value}")
        attr_names[placeholder_name] = key
        attr_values[placeholder_value] = value

    table = _get_table()
    resp = table.update_item(
        Key={"tenant_id": tenant_id, "check_id": check_id},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
        ReturnValues="ALL_NEW",
    )
    return resp.get("Attributes")


def delete_check(tenant_id: str, check_id: str) -> None:
    """Delete a check."""
    table = _get_table()
    table.delete_item(Key={"tenant_id": tenant_id, "check_id": check_id})
