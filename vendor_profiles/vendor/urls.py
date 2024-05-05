from django.urls import path
from .views import *

urlpatterns = [
    path('vendors/', VendorList.as_view(), name='vendor-list'),
    path('vendors/<int:id>/', VendorDetails.as_view(), name='vendor-details'),
    path('purchase_orders/', PurchaseOrderList.as_view(), name='po-list'),
    path('purchase_orders/<int:id>/', PurchaseOrderDetails.as_view(), name='po-details'),
    path('vendors/<int:id>/performance/', vendor_performance_metrics, name='vendor-performance'),
    path('purchase_orders/<int:id>/acknowledge/', acknowledge_purchase_order, name='acknowledge-po'),
]
