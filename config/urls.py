from django.urls import include, path

urlpatterns = [
    path("", include("kingdoms.urls")),
]
