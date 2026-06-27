from django.urls import path

from alerts import views

app_name = "alerts"

urlpatterns = [
    path("<str:check_id>/alerts/", views.alert_rule_list, name="list"),
    path("<str:check_id>/alerts/create/", views.alert_rule_create, name="create"),
    path("<str:check_id>/alerts/<str:rule_id>/delete/", views.alert_rule_delete, name="delete"),
    path("<str:check_id>/alerts/events/", views.alert_events, name="events"),
]
