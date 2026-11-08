from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('soporte/', include('support.urls')),
    path('observabilidad/', include('observability.urls')),
    path('', include('gestion_personal.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='gestion_personal/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = 'gestion_personal.error_views.bad_request'
handler403 = 'gestion_personal.error_views.forbidden'
handler404 = 'gestion_personal.error_views.not_found'
handler500 = 'gestion_personal.error_views.server_error'
