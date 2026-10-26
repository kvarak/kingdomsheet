from django.urls import path

from . import views

app_name = "kingdoms"

urlpatterns = [
    path("", views.home, name="home"),
    path("kingdoms/new/", views.create_kingdom, name="create"),
    path("kingdoms/join/", views.join, name="join"),
    path("join/<str:code>/", views.join_by_link, name="join_link"),
    path("kingdoms/<int:pk>/", views.sheet, name="sheet"),
    path("kingdoms/<int:pk>/edit/", views.edit, name="edit"),
    path("kingdoms/<int:pk>/edit/start/", views.edit_start, name="edit_start"),
    path("kingdoms/<int:pk>/edit/stop/", views.edit_stop, name="edit_stop"),
    path("kingdoms/<int:pk>/statistics/new/", views.statistic_add, name="statistic_add"),
    path(
        "kingdoms/<int:pk>/statistics/<int:stat_pk>/", views.statistic_edit, name="statistic_edit"
    ),
    path(
        "kingdoms/<int:pk>/statistics/<int:stat_pk>/delete/",
        views.statistic_delete,
        name="statistic_delete",
    ),
    path("kingdoms/<int:pk>/history/", views.history, name="history"),
    path("names/", views.names, name="names"),
    path("names/forget/", views.forget_selected_name, name="forget_name"),
]
