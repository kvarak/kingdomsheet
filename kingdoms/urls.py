from django.urls import path

from . import settlement_views, views

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
    path(
        "kingdoms/<int:pk>/settlements/new/",
        views.settlement_add,
        name="settlement_add",
    ),
    path(
        "kingdoms/<int:pk>/settlements/<int:spk>/",
        settlement_views.settlement,
        name="settlement",
    ),
    path(
        "kingdoms/<int:pk>/settlements/<int:spk>/delete/",
        views.settlement_delete,
        name="settlement_delete",
    ),
    path(
        "kingdoms/<int:pk>/settlements/<int:spk>/edit/",
        settlement_views.settlement_edit,
        name="settlement_edit",
    ),
    path(
        "kingdoms/<int:pk>/settlements/<int:spk>/edit/start/",
        settlement_views.settlement_edit_start,
        name="settlement_edit_start",
    ),
    path(
        "kingdoms/<int:pk>/settlements/<int:spk>/edit/stop/",
        settlement_views.settlement_edit_stop,
        name="settlement_edit_stop",
    ),
    path(
        "kingdoms/<int:pk>/settlements/<int:spk>/buildings/",
        settlement_views.building_place,
        name="building_place",
    ),
    path(
        "kingdoms/<int:pk>/settlements/<int:spk>/buildings/<int:ppk>/delete/",
        settlement_views.building_remove,
        name="building_remove",
    ),
    path("names/", views.names, name="names"),
    path("names/forget/", views.forget_selected_name, name="forget_name"),
]
