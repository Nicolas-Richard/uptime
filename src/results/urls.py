from django.urls import path

from results import views

app_name = "results"

urlpatterns = [
    path("<str:check_id>/results/", views.recent_results, name="recent"),
]
