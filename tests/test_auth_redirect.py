import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture()
def user(db):
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture()
def client():
    return Client()


@pytest.mark.django_db
def test_login_redirect_rejects_absolute_url(client, user):
    """An absolute URL in the 'next' parameter must be rejected to prevent open redirects."""
    response = client.post(
        "/auth/login/?next=https://evil.com",
        {"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 302
    location = response["Location"]
    assert location.startswith("/"), f"Expected relative redirect, got: {location}"
    assert location != "https://evil.com"


@pytest.mark.django_db
def test_login_redirect_allows_relative_path(client, user):
    """A relative path in the 'next' parameter should be honoured."""
    response = client.post(
        "/auth/login/?next=/checks/",
        {"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 302
    assert response["Location"] == "/checks/"
