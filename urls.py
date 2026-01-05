"""backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularSwaggerView

from libs.drf.spectacular.client_schema import MobileSpectacularAPIView, WebSpectacularAPIView

urlpatterns = []
urlpatterns += [
    path("health/", include("health_check.urls")),
    # Mobile API routes (web routes remain unchanged)
    path("api/mobile/", include(("apps.core.urls", "core"), namespace="mobile-core")),
    path("api/mobile/hrm/", include(("apps.hrm.mobile_urls", "hrm"), namespace="mobile-hrm")),
    path("api/mobile/payroll/", include(("apps.payroll.mobile_urls", "payroll"), namespace="mobile-payroll")),
    path("api/mobile/realestate/", include(("apps.realestate.urls", "realestate"), namespace="mobile-realestate")),
    # path("api/mobile/audit-logs/", include(("apps.audit_logging.urls", "audit_logging"), namespace="mobile-audit-logs")),
    path(
        "api/mobile/notifications/",
        include(("apps.notifications.urls", "notifications"), namespace="mobile-notifications"),
    ),
    path("api/mobile/files/", include(("apps.files.urls", "files"), namespace="mobile-files")),
    path(
        "api/mobile/mailtemplates/",
        include(("apps.mailtemplates.urls", "mailtemplates"), namespace="mobile-mailtemplates"),
    ),
    # Web API routes
    path("api/", include("apps.core.urls")),
    path("api/hrm/", include("apps.hrm.urls")),
    path("api/payroll/", include("apps.payroll.urls")),
    path("api/realestate/", include("apps.realestate.urls")),
    path("api/audit-logs/", include("apps.audit_logging.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/files/", include("apps.files.urls")),
    path("api/mailtemplates/", include("apps.mailtemplates.urls")),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.ENVIRONMENT in ["local", "develop"]:
    urlpatterns += i18n_patterns(path("admin/", admin.site.urls), prefix_default_language=False) + [
        # Combined schema (backward-compatible)
        # path("schema/", SpectacularAPIView.as_view(), name="schema"),
        # path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        # Web-only schema/docs
        path("schema/", WebSpectacularAPIView.as_view(), name="schema"),
        path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        # Mobile-only schema/docs
        path("schema/mobile/", MobileSpectacularAPIView.as_view(), name="schema-mobile"),
        path("docs/mobile/", SpectacularSwaggerView.as_view(url_name="schema-mobile"), name="swagger-mobile"),
    ]
