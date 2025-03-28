from django.urls import path

from apps.sellers.views import (SellerView, ProductsBySellerView,
                                SellerProductView, SellerOrdersView, SellerOrderItemView)

urlpatterns = [
    path('', SellerView.as_view()),
    path('products/', ProductsBySellerView.as_view()),
    path('products/<slug:slug>/', SellerProductView.as_view()),
    path('orders/', SellerOrdersView.as_view()),
    path('orders/<str:tx_ref>/', SellerOrderItemView.as_view()),
]
