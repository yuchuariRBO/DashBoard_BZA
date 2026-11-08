from django.urls import path

from . import views

app_name = "support"
urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("nuevo/", views.ticket_create, name="create"),
    path("configuracion/", views.configuration, name="configuration"),
    path("estadisticas/", views.dashboard, name="dashboard"),
    path("notificaciones/", views.notifications, name="notifications"),
    path(
        "notificaciones/<int:pk>/leer/",
        views.read_notification,
        name="read_notification",
    ),
    path("adjuntos/<int:pk>/", views.download, name="download"),
    path("<uuid:pk>/", views.ticket_detail, name="detail"),
]
