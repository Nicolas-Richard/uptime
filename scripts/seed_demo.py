"""Seed the local environment with demo data (idempotent)."""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup – must happen before any Django / project imports
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

sys.path.insert(0, str(ROOT_DIR))  # lambda_handler, core
sys.path.insert(0, str(SRC_DIR))  # Django apps

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uptime.settings")

import django  # noqa: E402

django.setup()

# ---------------------------------------------------------------------------
# Imports that require Django to be ready
# ---------------------------------------------------------------------------
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402

from checks.services import create_check, list_checks  # noqa: E402
from lambda_handler.handler import handler as lambda_handler  # noqa: E402
from organizations.models import Organization, OrganizationMembership  # noqa: E402

User = get_user_model()

# ---------------------------------------------------------------------------
# Data definitions
# ---------------------------------------------------------------------------
SUPERUSER = {"username": "admin", "email": "admin@demo.com", "password": "check-check-uptime-local"}

USERS = [
    {"username": "alice", "password": "alice123"},
    {"username": "bob", "password": "bob123"},
]

ORGS = [
    {"name": "Acme Corp", "slug": "acme-corp"},
    {"name": "Demo Inc", "slug": "demo-inc"},
]

MEMBERSHIPS = [
    # (username, org_slug, role)
    ("alice", "acme-corp", "owner"),
    ("bob", "demo-inc", "owner"),
    ("admin", "acme-corp", "admin"),
]

CHECKS = {
    "acme-corp": [
        ("Google", "https://www.google.com", 10),
        ("GitHub", "https://github.com", 10),
        ("Httpbin 503", "https://httpbin.org/status/503", 10),
    ],
    "demo-inc": [
        ("Cloudflare", "https://www.cloudflare.com", 10),
        ("Example.com", "https://example.com", 10),
    ],
}


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
def seed_migrations():
    print("Running migrations …")
    call_command("migrate", verbosity=0)
    print("  ✓ migrations applied")


def seed_superuser():
    if User.objects.filter(username=SUPERUSER["username"]).exists():
        print(f"  – superuser '{SUPERUSER['username']}' already exists, skipping")
        return
    User.objects.create_superuser(**SUPERUSER)
    print(f"  ✓ created superuser '{SUPERUSER['username']}'")


def seed_users():
    for u in USERS:
        if User.objects.filter(username=u["username"]).exists():
            print(f"  – user '{u['username']}' already exists, skipping")
            continue
        User.objects.create_user(username=u["username"], password=u["password"])
        print(f"  ✓ created user '{u['username']}'")


def seed_orgs():
    for o in ORGS:
        org, created = Organization.objects.get_or_create(
            slug=o["slug"], defaults={"name": o["name"]}
        )
        status = "created" if created else "already exists, skipping"
        print(f"  {'✓' if created else '–'} org '{org.name}' {status}")


def seed_memberships():
    for username, org_slug, role in MEMBERSHIPS:
        user = User.objects.get(username=username)
        org = Organization.objects.get(slug=org_slug)
        _, created = OrganizationMembership.objects.get_or_create(
            user=user, organization=org, defaults={"role": role}
        )
        status = "added" if created else "already exists, skipping"
        print(f"  {'✓' if created else '–'} {username} → {org.name} ({role}) {status}")


def seed_checks():
    total_created = 0
    for org_slug, checks_list in CHECKS.items():
        org = Organization.objects.get(slug=org_slug)
        tenant_id = str(org.id)

        existing = list_checks(tenant_id)
        if existing:
            print(f"  – {org.name} already has {len(existing)} checks, skipping")
            continue

        for name, url, timeout in checks_list:
            create_check(tenant_id=tenant_id, name=name, url=url, timeout_seconds=timeout)
            print(f"  ✓ [{org.name}] check '{name}' → {url}")
            total_created += 1
    return total_created


def run_check_cycle():
    print("Running check cycle …")
    result = lambda_handler({}, None)
    print(f"  ✓ {result['body']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("Uptime demo seeder")
    print("=" * 60)

    seed_migrations()

    print("\nUsers:")
    seed_superuser()
    seed_users()

    print("\nOrganizations:")
    seed_orgs()

    print("\nMemberships:")
    seed_memberships()

    print("\nChecks (DynamoDB):")
    checks_created = seed_checks()

    print("\nResults:")
    run_check_cycle()

    print("\n" + "=" * 60)
    print("Done! Log in at http://localhost:8000/auth/login/")
    print("  admin / check-check-uptime-local  |  alice / alice123  |  bob / bob123")
    print("=" * 60)


if __name__ == "__main__":
    main()
