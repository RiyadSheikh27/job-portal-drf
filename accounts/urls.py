from django.urls import path
from .views import *

urlpatterns = [
    path("register/user/", UserRegisterView.as_view(), name="register_user"),
    path("register/admin/", AdminRegisterView.as_view(), name="register_admin"),
    path('login/', LoginView.as_view(), name="login"),
]
