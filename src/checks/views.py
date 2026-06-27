"""CRUD views for checks."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from checks import services
from organizations.middleware import get_current_tenant_id
from results.services import get_latest_result


@login_required
def check_list(request):
    tenant_id = get_current_tenant_id(request)
    if tenant_id is None:
        return render(request, "checks/no_org.html")
    checks = services.list_checks(tenant_id)
    for check in checks:
        latest = get_latest_result(tenant_id, check["check_id"])
        check["latest_status"] = latest["status"] if latest else None
        check["last_checked"] = latest["timestamp"] if latest else None
    return render(request, "checks/list.html", {"checks": checks})


@login_required
def check_create(request):
    tenant_id = get_current_tenant_id(request)
    if tenant_id is None:
        return render(request, "checks/no_org.html")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        url = request.POST.get("url", "").strip()
        timeout = request.POST.get("timeout_seconds", "30")
        errors = []
        if not name:
            errors.append("Name is required.")
        if not url:
            errors.append("URL is required.")
        try:
            timeout_seconds = int(timeout)
        except (ValueError, TypeError):
            errors.append("Timeout must be a number.")
            timeout_seconds = 30

        if errors:
            return render(request, "checks/create.html", {
                "errors": errors,
                "name": name,
                "url": url,
                "timeout_seconds": timeout,
            })

        is_public = request.POST.get("is_public") == "on"
        services.create_check(tenant_id, name, url, timeout_seconds, is_public=is_public)
        return redirect("checks:list")

    return render(request, "checks/create.html", {"timeout_seconds": 30})


@login_required
def check_edit(request, check_id):
    tenant_id = get_current_tenant_id(request)
    if tenant_id is None:
        return render(request, "checks/no_org.html")

    check = services.get_check(tenant_id, check_id)
    if check is None:
        return redirect("checks:list")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        url = request.POST.get("url", "").strip()
        timeout = request.POST.get("timeout_seconds", "30")
        is_active = request.POST.get("is_active", "false")
        errors = []
        if not name:
            errors.append("Name is required.")
        if not url:
            errors.append("URL is required.")
        try:
            timeout_seconds = int(timeout)
        except (ValueError, TypeError):
            errors.append("Timeout must be a number.")
            timeout_seconds = 30

        if errors:
            check.update({"name": name, "url": url, "timeout_seconds": timeout})
            return render(request, "checks/edit.html", {
                "check": check,
                "errors": errors,
            })

        is_public = request.POST.get("is_public") == "on"
        services.update_check(
            tenant_id,
            check_id,
            name=name,
            url=url,
            timeout_seconds=timeout_seconds,
            is_active="true" if is_active == "true" else "false",
            is_public="true" if is_public else "false",
        )
        return redirect("checks:list")

    return render(request, "checks/edit.html", {"check": check})


@login_required
def check_delete(request, check_id):
    tenant_id = get_current_tenant_id(request)
    if tenant_id is None:
        return render(request, "checks/no_org.html")

    check = services.get_check(tenant_id, check_id)
    if check is None:
        return redirect("checks:list")

    if request.method == "POST":
        services.delete_check(tenant_id, check_id)
        return redirect("checks:list")

    return render(request, "checks/delete.html", {"check": check})
