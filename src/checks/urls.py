from django.urls import path

from checks import views

app_name = "checks"

urlpatterns = [
    path("", views.check_list, name="list"),
    path("create/", views.check_create, name="create"),
    path("<str:check_id>/edit/", views.check_edit, name="edit"),
    path("<str:check_id>/delete/", views.check_delete, name="delete"),
]
