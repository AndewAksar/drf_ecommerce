from django.urls import path

from apps.shop.views import (CategoriesView, ProductsByCategoryView,
                             ProductsBySellerView, ProductView, ProductsView,
                             CartView, CheckoutView)
from apps.shop.views import ReviewsView, ReviewItemView, CreateReviewView


urlpatterns = [
    path('categories/', CategoriesView.as_view()),
    path('categories/<slug:slug>/', ProductsByCategoryView.as_view()),
    path('sellers/<slug:slug>/', ProductsBySellerView.as_view()),
    path('products/', ProductsView.as_view()),
    path('products/<slug:slug>/', ProductView.as_view()),
    path('cart/', CartView.as_view()),
    path('checkout/', CheckoutView.as_view()),
    path('product/<slug:slug>/reviews/', ReviewsView.as_view()),
    path('product/<slug:slug>/review/<uuid:uuid>/', ReviewItemView.as_view()),
    path('product/<slug:slug>/review/', CreateReviewView.as_view()),
]
