"""Results service layer — queries DynamoDB results table."""
import boto3
from django.conf import settings


def _get_dynamodb_client():
    kwargs = {"region_name": settings.AWS_REGION}
    if settings.DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
    return boto3.client("dynamodb", **kwargs)


def get_recent_results(
    tenant_id: str, check_id: str, limit: int = 50
) -> list[dict]:
    """Query recent results for a check, newest first.

    Returns list of dicts with: timestamp, status, status_code,
    response_time_ms, error_message.
    """
    client = _get_dynamodb_client()
    resp = client.query(
        TableName="results",
        KeyConditionExpression="check_id = :cid",
        ExpressionAttributeValues={":cid": {"S": check_id}},
        ScanIndexForward=False,  # newest first
        Limit=limit,
    )
    results = []
    for item in resp.get("Items", []):
        # Verify tenant_id matches
        if item.get("tenant_id", {}).get("S") != tenant_id:
            continue
        results.append(
            {
                "timestamp": item.get("timestamp", {}).get("S", ""),
                "status": item.get("status", {}).get("S", ""),
                "status_code": (
                    int(item["status_code"]["N"])
                    if "status_code" in item and "N" in item["status_code"]
                    else None
                ),
                "response_time_ms": (
                    int(item["response_time_ms"]["N"])
                    if "response_time_ms" in item
                    and "N" in item["response_time_ms"]
                    else 0
                ),
                "error_message": item.get("error_message", {}).get("S", ""),
            }
        )
    return results


def get_latest_result(tenant_id: str, check_id: str) -> dict | None:
    """Return the most recent result for a check, or None."""
    results = get_recent_results(tenant_id, check_id, limit=1)
    return results[0] if results else None
