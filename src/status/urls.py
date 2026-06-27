from django.urls import path

from status import views

app_name = "status"

urlpatterns = [
    path("<slug:org_slug>/", views.status_page, name="page"),
]
