"""Middleware to set request.current_organization from session."""
from organizations.models import Organization


class CurrentOrganizationMiddleware:
    """Sets request.current_organization from session['organization_id']."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.current_organization = None
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return self.get_response(request)

        org_id = request.session.get("organization_id")
        if org_id:
            try:
                request.current_organization = Organization.objects.get(
                    pk=org_id,
                    memberships__user=request.user,
                )
            except Organization.DoesNotExist:
                request.session.pop("organization_id", None)

        # Auto-select first org if none is set in session
        if request.current_organization is None:
            org = Organization.objects.filter(memberships__user=request.user).first()
            if org:
                request.current_organization = org
                request.session["organization_id"] = str(org.id)

        return self.get_response(request)


def get_current_tenant_id(request) -> str | None:
    """Return the current organization UUID as a string for DynamoDB scoping."""
    org = getattr(request, "current_organization", None)
    if org is not None:
        return str(org.id)
    return None
