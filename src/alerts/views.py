"""Views for alert rules CRUD and delivery history."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from alerts import services
from checks.services import get_check
from organizations.middleware import get_current_tenant_id


def _get_check_or_404(tenant_id: str, check_id: str) -> dict:
    check = get_check(tenant_id, check_id)
    if not check:
        raise Http404("Check not found.")
    return check


@login_required
def alert_rule_list(request, check_id):
    """List all alert rules for a check."""
    tenant_id = get_current_tenant_id(request)
    if not tenant_id:
        raise Http404("No organization selected.")

    check = _get_check_or_404(tenant_id, check_id)
    rules = services.list_rules_for_check(tenant_id, check_id)
    return render(request, "alerts/list.html", {"check": check, "rules": rules})


@login_required
def alert_rule_create(request, check_id):
    """Create a new alert rule for a check."""
    tenant_id = get_current_tenant_id(request)
    if not tenant_id:
        raise Http404("No organization selected.")

    check = _get_check_or_404(tenant_id, check_id)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        webhook_url = request.POST.get("webhook_url", "").strip()
        errors = []
        if not name:
            errors.append("Name is required.")
        if not webhook_url:
            errors.append("Webhook URL is required.")
        elif not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
            errors.append("Webhook URL must start with http:// or https://.")

        if errors:
            return render(request, "alerts/create.html", {
                "check": check,
                "errors": errors,
                "name": name,
                "webhook_url": webhook_url,
            })

        services.create_rule(tenant_id, check_id, name, webhook_url)
        return redirect("alerts:list", check_id=check_id)

    return render(request, "alerts/create.html", {"check": check})


@login_required
def alert_rule_delete(request, check_id, rule_id):
    """Delete an alert rule."""
    tenant_id = get_current_tenant_id(request)
    if not tenant_id:
        raise Http404("No organization selected.")

    check = _get_check_or_404(tenant_id, check_id)
    rule = services.get_rule(tenant_id, rule_id)
    if not rule or rule["check_id"] != check_id:
        raise Http404("Alert rule not found.")

    if request.method == "POST":
        services.delete_rule(tenant_id, rule_id)
        return redirect("alerts:list", check_id=check_id)

    return render(request, "alerts/delete.html", {"check": check, "rule": rule})


@login_required
def alert_events(request, check_id):
    """Show delivery history for all alerts on a check."""
    tenant_id = get_current_tenant_id(request)
    if not tenant_id:
        raise Http404("No organization selected.")

    check = _get_check_or_404(tenant_id, check_id)
    events = services.list_events_for_check(check_id)
    return render(request, "alerts/events.html", {"check": check, "events": events})
