"""End-to-end smoke tests for the live demo app.

These tests verify the full user flow against a running DynamoDB Local instance.
They require:
  - DynamoDB Local running on DYNAMODB_ENDPOINT_URL (default http://localhost:8001)
  - Tables created (make create-tables)

Run with: make test  (or pytest tests/test_e2e_smoke.py -v)
Skip with: pytest -m "not e2e"
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure project root and src are on the path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uptime.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402

from checks.services import create_check, list_checks  # noqa: E402
from lambda_handler.handler import handler as lambda_handler  # noqa: E402
from organizations.models import Organization, OrganizationMembership  # noqa: E402

User = get_user_model()

pytestmark = pytest.mark.e2e


def _dynamo_available():
    """Check if DynamoDB Local is reachable."""
    try:
        list_checks("__probe__")
        return True
    except Exception:
        return False


skip_no_dynamo = pytest.mark.skipif(
    not _dynamo_available(),
    reason="DynamoDB Local not running",
)


@pytest.fixture()
def demo_env(db):
    """Set up a minimal demo environment: user, org, membership, checks."""
    user = User.objects.create_user(username="e2e_user", password="e2e_pass")
    org = Organization.objects.create(name="E2E Org", slug="e2e-org")
    OrganizationMembership.objects.create(user=user, organization=org, role="owner")
    tenant_id = str(org.id)

    create_check(tenant_id, "E2E Google", "https://www.google.com", 10)
    create_check(tenant_id, "E2E Httpbin 503", "https://httpbin.org/status/503", 10)

    return {"user": user, "org": org, "tenant_id": tenant_id}


@skip_no_dynamo
@pytest.mark.django_db
def test_landing_page_anonymous(demo_env):
    """Anonymous users see the landing page at /."""
    client = Client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Uptime" in resp.content


@skip_no_dynamo
@pytest.mark.django_db
def test_landing_redirects_authenticated(demo_env):
    """Authenticated users hitting / get redirected to /checks/."""
    client = Client()
    client.login(username="e2e_user", password="e2e_pass")
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp["Location"] == "/checks/"


@skip_no_dynamo
@pytest.mark.django_db
def test_checks_page_requires_login():
    """Unauthenticated request to /checks/ redirects to login."""
    client = Client()
    resp = client.get("/checks/")
    assert resp.status_code == 302
    assert "/auth/login/" in resp["Location"]


@skip_no_dynamo
@pytest.mark.django_db
def test_checks_page_shows_checks(demo_env):
    """Authenticated user sees their checks listed."""
    client = Client()
    client.login(username="e2e_user", password="e2e_pass")
    resp = client.get("/checks/")
    assert resp.status_code == 200
    assert b"E2E Google" in resp.content
    assert b"E2E Httpbin 503" in resp.content


@skip_no_dynamo
@pytest.mark.django_db
def test_check_cycle_produces_results(demo_env):
    """Running the Lambda handler produces results visible in the JSON API."""
    client = Client()
    client.login(username="e2e_user", password="e2e_pass")

    # Run one check cycle
    result = lambda_handler({}, None)
    assert result["statusCode"] == 200

    # Get a check_id to query results for
    checks = list_checks(demo_env["tenant_id"])
    assert len(checks) >= 2
    check_id = checks[0]["check_id"]

    # Fetch results via JSON endpoint
    resp = client.get(f"/checks/{check_id}/results/?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) >= 1

    # Verify result structure
    r = data["results"][0]
    assert r["status"] in ("up", "down")
    assert "timestamp" in r
    assert "response_time_ms" in r


@skip_no_dynamo
@pytest.mark.django_db
def test_results_page_renders(demo_env):
    """Results HTML page renders with check details."""
    client = Client()
    client.login(username="e2e_user", password="e2e_pass")

    # Run checks so we have results
    lambda_handler({}, None)

    checks = list_checks(demo_env["tenant_id"])
    check_id = checks[0]["check_id"]

    resp = client.get(f"/checks/{check_id}/results/")
    assert resp.status_code == 200
    assert b"results-table-body" in resp.content  # auto-refresh table id


@skip_no_dynamo
@pytest.mark.django_db
def test_cross_tenant_isolation(demo_env):
    """User cannot see another tenant's check results."""
    # Create a second user + org
    user2 = User.objects.create_user(username="e2e_other", password="e2e_pass")
    org2 = Organization.objects.create(name="Other Org", slug="other-org")
    OrganizationMembership.objects.create(user=user2, organization=org2, role="owner")

    # Get a check_id from the first tenant
    checks = list_checks(demo_env["tenant_id"])
    check_id = checks[0]["check_id"]

    # Login as the second user
    client = Client()
    client.login(username="e2e_other", password="e2e_pass")

    # Try to access first tenant's results — should 404
    resp = client.get(f"/checks/{check_id}/results/")
    assert resp.status_code == 404
