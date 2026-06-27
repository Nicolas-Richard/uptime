"""Tests for the public status page view."""
import pytest
from unittest.mock import patch
from django.test import Client

from organizations.models import Organization


@pytest.fixture()
def org(db):
    return Organization.objects.create(name="Acme Corp", slug="acme")


@pytest.fixture()
def client():
    return Client()


@pytest.mark.django_db
def test_status_page_returns_200(client, org):
    with patch("status.views.list_checks", return_value=[]), \
         patch("status.views.get_latest_result", return_value=None):
        response = client.get(f"/status/{org.slug}/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_status_page_shows_org_name(client, org):
    with patch("status.views.list_checks", return_value=[]), \
         patch("status.views.get_latest_result", return_value=None):
        response = client.get(f"/status/{org.slug}/")
    assert org.name.encode() in response.content


@pytest.mark.django_db
def test_status_page_404_for_unknown_slug(client, db):
    response = client.get("/status/does-not-exist/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_status_page_no_login_required(client, org):
    """Status page must be accessible without authentication."""
    with patch("status.views.list_checks", return_value=[]), \
         patch("status.views.get_latest_result", return_value=None):
        response = client.get(f"/status/{org.slug}/")
    # Should not redirect to login
    assert response.status_code == 200
    assert "/auth/login/" not in response.get("Location", "")


@pytest.mark.django_db
def test_status_page_only_shows_public_checks(client, org):
    """Only checks with is_public=true should appear on the status page."""
    checks = [
        {"check_id": "a1", "name": "Public Check", "is_public": "true"},
        {"check_id": "a2", "name": "Private Check", "is_public": "false"},
        {"check_id": "a3", "name": "No Flag Check"},
    ]
    with patch("status.views.list_checks", return_value=checks), \
         patch("status.views.get_latest_result", return_value=None):
        response = client.get(f"/status/{org.slug}/")
    assert b"Public Check" in response.content
    assert b"Private Check" not in response.content
    assert b"No Flag Check" not in response.content
