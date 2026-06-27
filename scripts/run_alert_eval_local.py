"""Local alert evaluator: polls recent results and fires webhooks on transitions.

In production, alert_handler.py is triggered by DynamoDB Streams. This script
simulates that behaviour locally by polling the results table and evaluating
transitions against the current_status stored on each check.

Usage:
    DYNAMODB_ENDPOINT_URL=http://localhost:8001 python scripts/run_alert_eval_local.py

The script runs once per INTERVAL_SECONDS, mirrors the Lambda logic, and logs
each transition + webhook outcome to stdout.
"""

import asyncio
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path so lambda_handler and core are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boto3
import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 60
RESULTS_LIMIT = 1  # Only care about the latest result per check


def _get_dynamodb_client():
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8001")
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client(
        "dynamodb",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "local"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "local"),
    )


def _load_all_checks(ddb) -> list[dict]:
    """Return all active checks."""
    checks = []
    params = {
        "TableName": "checks",
        "IndexName": "is_active-tenant_id",
        "KeyConditionExpression": "is_active = :active",
        "ExpressionAttributeValues": {":active": {"S": "true"}},
    }
    while True:
        resp = ddb.query(**params)
        for item in resp.get("Items", []):
            checks.append({
                "tenant_id": item["tenant_id"]["S"],
                "check_id": item["check_id"]["S"],
                "name": item.get("name", {}).get("S", ""),
                "url": item.get("url", {}).get("S", ""),
                "current_status": item.get("current_status", {}).get("S"),
            })
        if "LastEvaluatedKey" not in resp:
            break
        params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return checks


def _get_latest_result(ddb, check_id: str) -> dict | None:
    """Return the most recent result for a check, or None."""
    resp = ddb.query(
        TableName="results",
        KeyConditionExpression="check_id = :cid",
        ExpressionAttributeValues={":cid": {"S": check_id}},
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return None
    item = items[0]
    return {
        "check_id": item["check_id"]["S"],
        "tenant_id": item.get("tenant_id", {}).get("S", ""),
        "timestamp": item.get("timestamp", {}).get("S", ""),
        "status": item.get("status", {}).get("S", ""),
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
        "error_message": item.get("error_message", {}).get("S"),
    }


def _update_check_current_status(
    ddb, tenant_id: str, check_id: str, new_status: str, expected_old_status: str | None
) -> bool:
    """Conditionally update current_status; returns True if the update landed."""
    from botocore.exceptions import ClientError
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
    """Return active alert rules for a check via GSI."""
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
        rules.append({
            "tenant_id": item["tenant_id"]["S"],
            "rule_id": item["rule_id"]["S"],
            "check_id": item["check_id"]["S"],
            "webhook_url": item.get("webhook_url", {}).get("S", ""),
            "name": item.get("name", {}).get("S", ""),
        })
    return rules


def _write_alert_event(ddb, *, check_id, event_id, tenant_id, rule_id,
                       webhook_url, event_type, result, previous_status,
                       delivery_status, delivered_at):
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


async def _post_webhook(session: aiohttp.ClientSession, url: str, payload: dict) -> bool:
    try:
        async with session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status < 300:
                return True
            logger.warning("Webhook %s returned HTTP %d", url, resp.status)
            return False
    except Exception as exc:
        logger.error("Webhook delivery failed for %s: %s", url, exc)
        return False


async def _fire_and_log(rules, payload, result, previous_status, ddb):
    async with aiohttp.ClientSession() as session:
        tasks = [_post_webhook(session, r["webhook_url"], payload) for r in rules]
        outcomes = await asyncio.gather(*tasks)

    now = datetime.now(timezone.utc).isoformat()
    for rule, success in zip(rules, outcomes):
        status = "delivered" if success else "failed"
        logger.info("  rule=%s url=%s delivery=%s", rule["name"], rule["webhook_url"], status)
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
            delivery_status=status,
            delivered_at=now if success else None,
        )


def evaluate_transitions(ddb):
    """Check each active check for a status transition and fire alerts."""
    checks = _load_all_checks(ddb)
    if not checks:
        logger.info("No active checks found")
        return

    transitions = 0
    for check in checks:
        result = _get_latest_result(ddb, check["check_id"])
        if not result:
            continue

        new_status = result["status"]
        previous_status = check["current_status"]

        if previous_status == new_status:
            _update_check_current_status(
                ddb, check["tenant_id"], check["check_id"], new_status, previous_status
            )
            continue

        # Transition detected
        updated = _update_check_current_status(
            ddb, check["tenant_id"], check["check_id"], new_status, previous_status
        )
        if not updated:
            continue

        transitions += 1
        logger.info(
            "Transition: check=%s (%s) %s → %s",
            check["check_id"], check["name"], previous_status, new_status,
        )

        rules = _get_alert_rules(ddb, check["check_id"])
        if not rules:
            logger.info("  No alert rules for this check")
            continue

        payload = {
            "event_type": new_status,
            "check_id": check["check_id"],
            "check_name": check["name"],
            "url": check["url"],
            "timestamp": result["timestamp"],
            "status": new_status,
            "previous_status": previous_status,
            "status_code": result["status_code"],
            "response_time_ms": result["response_time_ms"],
            "error_message": result["error_message"],
        }
        asyncio.run(_fire_and_log(rules, payload, result, previous_status, ddb))

    logger.info("Evaluation complete: %d check(s), %d transition(s)", len(checks), transitions)


def main():
    logger.info(
        "Starting local alert evaluator (interval=%ds)", INTERVAL_SECONDS
    )
    while True:
        try:
            ddb = _get_dynamodb_client()
            evaluate_transitions(ddb)
        except Exception:
            logger.exception("Error during alert evaluation cycle")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
