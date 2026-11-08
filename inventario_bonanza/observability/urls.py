from django.urls import path

from . import views

app_name = "observability"
urlpatterns = [
    path("grafana/acceso/", views.grafana_access, name="grafana_access"),
    path("", views.dashboard, name="dashboard"),
    path("metricas/", views.metrics, name="metrics"),
    path("reglas/", views.rules, name="rules"),
    path("grafana/<slug:slug>/", views.grafana, name="grafana"),
]
