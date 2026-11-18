from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .auth_views import LoginView, LogoutView, MeView, MyShopsView, ShopTokenView
from .views import DashboardView, ProductViewSet, StockMovementViewSet, SupplierViewSet

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("movements", StockMovementViewSet, basename="movement")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/shops/", MyShopsView.as_view(), name="auth-shops"),
    path("auth/shop-token/", ShopTokenView.as_view(), name="auth-shop-token"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("", include(router.urls)),
]
