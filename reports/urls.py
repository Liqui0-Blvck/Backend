from django.urls import path
from . import views
from .dashboard_views import DashboardSummaryView
from .debug_views import DebugUserBusinessView

urlpatterns = [
    # path('summary/', views.ReportSummaryView.as_view(), name='report-summary'),
    path('stock/', views.StockReportView.as_view(), name='report-stock'),
    path('sales/', views.SalesReportView.as_view(), name='report-sales'),
    path('shifts/', views.ShiftReportView.as_view(), name='report-shifts'),
    path('summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('debug/', DebugUserBusinessView.as_view(), name='report-debug'),
]
