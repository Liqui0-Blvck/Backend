"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from django.urls import path
from django.urls import include
from accounts import urls as accounts_urls
from business import urls as business_urls
from inventory import urls as inventory_urls
from sales import urls as sales_urls
from shifts import urls as shifts_urls
from reports import urls as reports_urls
from announcements import urls as announcements_urls
from notifications import urls as notifications_urls
from core.views import DashboardView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/accounts/', include(accounts_urls)),
    path('api/v1/business/', include(business_urls)),
    path('api/v1/inventory/', include(inventory_urls)),
    path('api/v1/', include(sales_urls)),
    path('api/v1/', include(shifts_urls)),
    path('api/v1/reports/', include(reports_urls)),
    path('api/v1/announcements/', include(announcements_urls)),
    path('api/v1/notifications/', include(notifications_urls)),
    
    path('api/v1/dashboard/', DashboardView.as_view(), name='dashboard'),

    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

