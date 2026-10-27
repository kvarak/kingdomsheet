from django.urls import path

from . import army_views, battle_views, character_views, settlement_views, views

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
        "kingdoms/<int:pk>/history/<int:entry_pk>/restore/",
        views.history_restore,
        name="history_restore",
    ),
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
    path("kingdoms/<int:pk>/characters/", character_views.characters, name="characters"),
    path("kingdoms/<int:pk>/characters/new/", character_views.character_add, name="character_add"),
    path(
        "kingdoms/<int:pk>/characters/<int:character_pk>/",
        character_views.character_edit,
        name="character_edit",
    ),
    path(
        "kingdoms/<int:pk>/characters/<int:character_pk>/delete/",
        character_views.character_delete,
        name="character_delete",
    ),
    path(
        "kingdoms/<int:pk>/characters/<int:character_pk>/picture/",
        character_views.character_picture,
        name="character_picture",
    ),
    path("kingdoms/<int:pk>/armies/new/", views.army_add, name="army_add"),
    path("kingdoms/<int:pk>/armies/<int:apk>/", army_views.army, name="army"),
    path("kingdoms/<int:pk>/armies/<int:apk>/delete/", views.army_delete, name="army_delete"),
    path("kingdoms/<int:pk>/armies/<int:apk>/edit/", army_views.army_edit, name="army_edit"),
    path(
        "kingdoms/<int:pk>/armies/<int:apk>/edit/start/",
        army_views.army_edit_start,
        name="army_edit_start",
    ),
    path(
        "kingdoms/<int:pk>/armies/<int:apk>/edit/stop/",
        army_views.army_edit_stop,
        name="army_edit_stop",
    ),
    path("kingdoms/<int:pk>/armies/<int:apk>/units/new/", army_views.unit_add, name="unit_add"),
    path(
        "kingdoms/<int:pk>/armies/<int:apk>/units/<int:upk>/edit/",
        army_views.unit_edit,
        name="unit_edit",
    ),
    path(
        "kingdoms/<int:pk>/armies/<int:apk>/units/<int:upk>/delete/",
        army_views.unit_delete,
        name="unit_delete",
    ),
    path("kingdoms/<int:pk>/battles/", battle_views.battles, name="battles"),
    path("kingdoms/<int:pk>/battles/new/", battle_views.battle_add, name="battle_add"),
    path("kingdoms/<int:pk>/battles/<int:bpk>/", battle_views.battle_edit, name="battle_edit"),
    path(
        "kingdoms/<int:pk>/battles/<int:bpk>/delete/",
        battle_views.battle_delete,
        name="battle_delete",
    ),
    path("names/", views.names, name="names"),
    path("names/forget/", views.forget_selected_name, name="forget_name"),
]
