from django.urls import path
from . import views

urlpatterns = [
    path('', views.client, name='client'),
    path('productdetail',views.productdetail,name='productdetail'),
    path('shoppingcart',views.shopppingcart,name='shoppingcart'),
    path('adminlog',views.adminlogin,name='adminlog'),
    path('admindash',views.admindashboard,name='admindash'),
    path('adminsignup',views.adminsignup,name='adminsignup'),
    path('resetpassword',views.resetpass,name='resetpassword'),
]
