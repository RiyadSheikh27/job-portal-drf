from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ads.views import *
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions

""" Swagger """
schema_view = get_schema_view(
   openapi.Info(
      title="Job Portal - Opty IT",
      default_version='v1',
      description="This is the API documentation for our project",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="riyad.cse27@gmail.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

router = DefaultRouter()
router.register("ads", AdViewSet, basename="ads")
router.register("watch", AdWatchingViewSet, basename="watch")
router.register("earnings", UserEarningViewSet, basename="earnings")
router.register('users', UserViewSet, basename='users')

#For third party API
router.register("view", ThirdPartyAdWatchingViewSet, basename="thirdpartywatch")
router.register("third-party-ads", ThirdPartyAdViewSet, basename="thirdpartyads")


urlpatterns = [
    path('', include(router.urls)),

    # Swagger URLs
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # JSON format
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger.yaml', schema_view.without_ui(cache_timeout=0), name='schema-yaml'),
]