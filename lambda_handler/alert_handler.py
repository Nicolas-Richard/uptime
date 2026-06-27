"""Alert Lambda handler: triggered by DynamoDB Streams on the results table.

Detects up/down status transitions and fires webhook POSTs for matching alert
rules. Events are logged to the alert_events table.

Infra note: the following are managed in Terraform and out of scope here:
  - DynamoDB Streams on the results table (StreamSpecification + event source mapping)
  - Lambda function definition and deployment
  - IAM role with permissions:
      dynamodb:GetShardIterator, GetRecords, DescribeStream, ListStreams (results)
      dynamodb:GetItem (checks)
      dynamodb:Query (alert_rules via check_id-index GSI)
      dynamodb:PutItem (alert_events)
      dynamodb:UpdateItem (checks, for current_status tracking)
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

import aiohttp
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _get_dynamodb_client():
    """Create a boto3 DynamoDB client, using local endpoint if configured."""
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    kwargs = {"region_name": os.environ.get("AWS_REGION", "us-east-1")}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
        kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID", "local")
        kwargs["aws_secret_access_key"] = os.environ.get(
            "AWS_SECRET_ACCESS_KEY", "local"
        )
    return boto3.client("dynamodb", **kwargs)


def _parse_new_image(record: dict) -> dict | None:
    """Extract and normalize the NewImage from a DynamoDB Streams record."""
    new_image = record.get("dynamodb", {}).get("NewImage")
    if not new_image:
        return None
    check_id = new_image.get("check_id", {}).get("S")
    tenant_id = new_image.get("tenant_id", {}).get("S")
    status = new_image.get("status", {}).get("S")
    if not check_id or not tenant_id or not status:
        return None
    return {
        "check_id": check_id,
        "tenant_id": tenant_id,
        "timestamp": new_image.get("timestamp", {}).get("S", ""),
        "status": status,
        "status_code": (
            int(new_image["status_code"]["N"])
            if "status_code" in new_image and "N" in new_image.get("status_code", {})
            else None
        ),
        "response_time_ms": (
            int(new_image["response_time_ms"]["N"])
            if "response_time_ms" in new_image
            and "N" in new_image.get("response_time_ms", {})
            else 0
        ),
        "error_message": new_image.get("error_message", {}).get("S"),
    }


def _get_check_state(ddb, tenant_id: str, check_id: str) -> dict | None:
    """Return check metadata and current tracked status from the checks table."""
    resp = ddb.get_item(
        TableName="checks",
        Key={
            "tenant_id": {"S": tenant_id},
            "check_id": {"S": check_id},
        },
    )
    item = resp.get("Item")
    if not item:
        return None
    return {
        "check_id": item["check_id"]["S"],
        "name": item.get("name", {}).get("S", ""),
        "url": item.get("url", {}).get("S", ""),
        "current_status": item.get("current_status", {}).get("S"),
    }


def _update_check_current_status(
    ddb, tenant_id: str, check_id: str, new_status: str, expected_old_status: str | None
) -> bool:
    """Conditionally update current_status on the checks table for idempotency.

    Uses a conditional expression so that concurrent executions for the same
    check do not double-fire alerts. Returns True if the update succeeded.
    """
    try:
        if expected_old_status is None:
            ddb.update_item(
                TableName="checks",
                Key={"tenant_id": {"S": tenant_id}, "check_id": {"S": check_id}},
                UpdateExpression="SET current_status = :new_status",
                ConditionExpression="attribute_not_exists(current_status)",
                ExpressionAttributeValues={":new_status": {"S": new_status}},
            )
        else:
            ddb.update_item(
                TableName="checks",
                Key={"tenant_id": {"S": tenant_id}, "check_id": {"S": check_id}},
                UpdateExpression="SET current_status = :new_status",
                ConditionExpression="current_status = :old_status",
                ExpressionAttributeValues={
                    ":new_status": {"S": new_status},
                    ":old_status": {"S": expected_old_status},
                },
            )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def _get_alert_rules(ddb, check_id: str) -> list[dict]:
    """Return all active alert rules for a check via the check_id-index GSI."""
    resp = ddb.query(
        TableName="alert_rules",
        IndexName="check_id-index",
        KeyConditionExpression="check_id = :cid",
        FilterExpression="is_active = :active",
        ExpressionAttributeValues={
            ":cid": {"S": check_id},
            ":active": {"S": "true"},
        },
    )
    rules = []
    for item in resp.get("Items", []):
        rules.append(
            {
                "tenant_id": item["tenant_id"]["S"],
                "rule_id": item["rule_id"]["S"],
                "check_id": item["check_id"]["S"],
                "webhook_url": item.get("webhook_url", {}).get("S", ""),
                "name": item.get("name", {}).get("S", ""),
            }
        )
    return rules


def _write_alert_event(
    ddb,
    *,
    check_id: str,
    event_id: str,
    tenant_id: str,
    rule_id: str,
    webhook_url: str,
    event_type: str,
    result: dict,
    previous_status: str | None,
    delivery_status: str,
    delivered_at: str | None,
) -> None:
    """Persist an alert delivery event to the alert_events table."""
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "check_id": {"S": check_id},
        "event_id": {"S": event_id},
        "tenant_id": {"S": tenant_id},
        "rule_id": {"S": rule_id},
        "webhook_url": {"S": webhook_url},
        "event_type": {"S": event_type},
        "timestamp": {"S": result["timestamp"] or now},
        "status": {"S": result["status"]},
        "previous_status": {"S": previous_status or "unknown"},
        "response_time_ms": {"N": str(result["response_time_ms"])},
        "delivery_status": {"S": delivery_status},
        "created_at": {"S": now},
    }
    if result["status_code"] is not None:
        item["status_code"] = {"N": str(result["status_code"])}
    if result["error_message"]:
        item["error_message"] = {"S": result["error_message"]}
    if delivered_at:
        item["delivered_at"] = {"S": delivered_at}
    ddb.put_item(TableName="alert_events", Item=item)


def _build_webhook_payload(
    event_type: str,
    check: dict,
    result: dict,
    previous_status: str | None,
) -> dict:
    """Build the webhook POST body."""
    return {
        "event_type": event_type,
        "check_id": check["check_id"],
        "check_name": check["name"],
        "url": check["url"],
        "timestamp": result["timestamp"],
        "status": result["status"],
        "previous_status": previous_status,
        "status_code": result["status_code"],
        "response_time_ms": result["response_time_ms"],
        "error_message": result["error_message"],
    }


async def _post_webhook(
    session: aiohttp.ClientSession, webhook_url: str, payload: dict
) -> bool:
    """POST payload to a single webhook URL. Returns True on HTTP 2xx."""
    try:
        async with session.post(
            webhook_url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status < 300:
                return True
            logger.warning("Webhook %s returned HTTP %d", webhook_url, resp.status)
            return False
    except Exception as exc:
        logger.error("Webhook delivery failed for %s: %s", webhook_url, exc)
        return False


async def _deliver_webhooks_async(
    rules: list[dict],
    payload: dict,
    result: dict,
    previous_status: str | None,
    ddb,
) -> None:
    """Fire webhooks for all rules concurrently, then log each event."""
    async with aiohttp.ClientSession() as session:
        tasks = [_post_webhook(session, rule["webhook_url"], payload) for rule in rules]
        outcomes = await asyncio.gather(*tasks)

    now = datetime.now(timezone.utc).isoformat()
    for rule, success in zip(rules, outcomes):
        _write_alert_event(
            ddb,
            check_id=rule["check_id"],
            event_id=str(uuid.uuid4()),
            tenant_id=rule["tenant_id"],
            rule_id=rule["rule_id"],
            webhook_url=rule["webhook_url"],
            event_type=result["status"],
            result=result,
            previous_status=previous_status,
            delivery_status="delivered" if success else "failed",
            delivered_at=now if success else None,
        )


def _process_record(ddb, record: dict) -> None:
    """Process one DynamoDB Streams record: detect transition, fire alerts."""
    if record.get("eventName") not in ("INSERT", "MODIFY"):
        return

    result = _parse_new_image(record)
    if result is None:
        return

    check_id = result["check_id"]
    tenant_id = result["tenant_id"]
    new_status = result["status"]

    check = _get_check_state(ddb, tenant_id, check_id)
    if check is None:
        logger.warning("Check %s/%s not found in checks table", tenant_id, check_id)
        return

    previous_status = check.get("current_status")

    if previous_status == new_status:
        # Same status — update silently, no alert needed
        _update_check_current_status(ddb, tenant_id, check_id, new_status, previous_status)
        return

    # Status transition — attempt to claim it via conditional update
    updated = _update_check_current_status(
        ddb, tenant_id, check_id, new_status, previous_status
    )
    if not updated:
        logger.info(
            "Transition for %s already processed (idempotency guard)", check_id
        )
        return

    logger.info(
        "Alert transition: check=%s %s → %s", check_id, previous_status, new_status
    )

    rules = _get_alert_rules(ddb, check_id)
    if not rules:
        return

    payload = _build_webhook_payload(new_status, check, result, previous_status)
    asyncio.run(
        _deliver_webhooks_async(rules, payload, result, previous_status, ddb)
    )


def handler(event, context):
    """AWS Lambda entry point for DynamoDB Streams trigger on the results table."""
    ddb = _get_dynamodb_client()
    records = event.get("Records", [])
    logger.info("Processing %d stream records", len(records))

    for record in records:
        try:
            _process_record(ddb, record)
        except Exception:
            logger.exception("Error processing stream record")

    return {"statusCode": 200, "processed": len(records)}
