"""Public status page views — no login required."""
from django.http import Http404
from django.shortcuts import render

from checks.services import list_checks
from organizations.models import Organization
from results.services import get_latest_result


def status_page(request, org_slug):
    try:
        org = Organization.objects.get(slug=org_slug)
    except Organization.DoesNotExist:
        raise Http404

    tenant_id = str(org.id)
    all_checks = list_checks(tenant_id)
    public_checks = [c for c in all_checks if c.get("is_public") == "true"]

    for check in public_checks:
        latest = get_latest_result(tenant_id, check["check_id"])
        check["latest_status"] = latest["status"] if latest else None
        check["last_checked"] = latest["timestamp"] if latest else None

    return render(request, "status/status_page.html", {
        "org": org,
        "checks": public_checks,
    })
