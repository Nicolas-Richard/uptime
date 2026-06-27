from django.contrib import admin
from django.urls import include, path

from landing.views import LandingView

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("admin/", admin.site.urls),
    path("auth/", include("auth.urls")),
    path("checks/", include("checks.urls")),
    path("checks/", include("results.urls")),
    path("checks/", include("alerts.urls")),
]
