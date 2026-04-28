"""Views for check results."""
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render

from organizations.middleware import get_current_tenant_id
from results.services import get_recent_results, _get_dynamodb_client


def _get_check(tenant_id: str, check_id: str) -> dict | None:
    """Fetch a check from DynamoDB and verify it belongs to the tenant."""
    client = _get_dynamodb_client()
    resp = client.get_item(
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
    }


@login_required
def recent_results(request, check_id):
    """Show recent results for a specific check."""
    tenant_id = get_current_tenant_id(request)
    if not tenant_id:
        raise Http404("No organization selected.")

    check = _get_check(tenant_id, check_id)
    if not check:
        raise Http404("Check not found.")

    results = get_recent_results(tenant_id, check_id)

    if request.GET.get("format") == "json":
        return JsonResponse({"results": results})

    return render(
        request,
        "results/recent.html",
        {"check": check, "results": results},
    )
