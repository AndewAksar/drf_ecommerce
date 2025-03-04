from django.urls import path

from apps.profiles.views import ProfileView, ShippingAddressView, ShippingAddressViewID
from apps.shop.views import OrdersView, OrderItemView


urlpatterns = [
    path("", ProfileView.as_view()),
    path('shipping_addresses/', ShippingAddressView.as_view()),
    path('shipping_addresses/detail/<uuid:id>/', ShippingAddressViewID.as_view()),
    path('orders/', OrdersView.as_view()),
    path('orders/<str:tx_ref>/', OrderItemView.as_view()),
]

