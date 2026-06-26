from django.urls import path

from . import views

urlpatterns = [
    path("", views.client, name="client"),
    path("products/<int:pk>/", views.productdetail, name="productdetail"),
    path("productdetail", views.productdetail, name="productdetail_legacy"),
    path("cart/", views.shoppingcart, name="shoppingcart"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:product_id>/", views.update_cart, name="update_cart"),
    path("cart/remove/<int:product_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/<uuid:order_id>/success/", views.order_success, name="order_success"),
    path("adminlog", views.adminlogin, name="adminlog"),
    path("adminlogin", views.adminlogin, name="adminlogin"),
    path("adminlogout", views.adminlogout, name="adminlogout"),
    path("admindash", views.admindashboard, name="admindash"),
    path("admindashboard", views.admindashboard, name="admindashboard"),
    path("admindash/products/add/", views.add_product, name="add_product"),
    path("adminsignup", views.adminsignup, name="adminsignup"),
    path("resetpassword", views.resetpass, name="resetpassword"),
    path('payment/initiate/<uuid:order_id>/', views.initiate_payment, name='initiate_payment'),
    path('payment/verify/', views.verify_payment, name='verify_payment'),
]