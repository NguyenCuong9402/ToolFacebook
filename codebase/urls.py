"""
URL configuration for codebase project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path, re_path
from django.views.generic import TemplateView

from app.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path('healthz', healthz, name='healthz'),
    path('api/v1/', include([
        path('', include(('app.urls', 'v1'))),
        path('accounts/', include('accounts.urls')),
    ])),
]

if settings.DEBUG:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
    # urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns.append(re_path(r'^.*/*$', login_required(TemplateView.as_view(template_name='index.html'))))
else:
    urlpatterns.append(re_path(r'^.*/*$', login_required(TemplateView.as_view(template_name='index.html'))))

