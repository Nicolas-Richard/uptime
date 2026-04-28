"""AuthBackend abstraction for future SSO/OAuth support.

Default implementation wraps Django's built-in authentication.
To add SSO later, implement the AuthBackend protocol with a new class.
"""
from __future__ import annotations

from typing import Any, Protocol

from django.contrib.auth import authenticate as django_authenticate
from django.contrib.auth.models import User
from django.http import HttpRequest


class AuthBackend(Protocol):
    """Protocol defining the authentication interface."""

    def authenticate(self, request: HttpRequest, **credentials: Any) -> User | None: ...

    def get_user(self, user_id: int) -> User | None: ...


class DjangoAuthBackend:
    """Default backend using Django's built-in authentication."""

    def authenticate(self, request: HttpRequest, **credentials: Any) -> User | None:
        return django_authenticate(request, **credentials)

    def get_user(self, user_id: int) -> User | None:
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
