from django import forms
from django.forms.models import fields_for_model

from . import growth, pictures, rules
from . import settlements as grid
from .access import ACCESS_CODE_LENGTH, is_valid_access_code, normalize_access_code
from .models import Army, Battle, Character, Kingdom, Placement, Settlement, Unit
from .sheet import KINGDOM_FIELDS, LEADER_ROWS, ROW_GROUPS

PASSWORD_MIN_LENGTH = 8


def _join_form(form):
    """Point every input at the page's <form id>, so inputs can sit anywhere in the layout."""
    for field in form.fields.values():
        field.widget.attrs["form"] = form.FORM_ID


class NewKingdomForm(forms.Form):
    name = forms.CharField(max_length=120)
    description = forms.CharField(widget=forms.Textarea, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)


class SheetForm(forms.Form):
    """The whole PF2e kingdom sheet as one form. Field names come from `sheet`."""

    FORM_ID = "sheet-form"

    def __init__(self, *args, kingdom, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(fields_for_model(Kingdom, fields=KINGDOM_FIELDS))
        for group in ROW_GROUPS:
            for key in group.keys:
                # Each call returns fresh field objects, so rows never share widgets.
                for name, field in fields_for_model(group.model, fields=group.fields).items():
                    self.fields[group.field_name(key, name)] = field
        characters = Character.objects.filter(kingdom=kingdom)
        for key in LEADER_ROWS.keys:
            # Leaders may only be this kingdom's characters.
            field = self.fields[LEADER_ROWS.field_name(key, "character")]
            field.queryset = characters
            field.empty_label = "Vacant"
        _join_form(self)

    def clean(self):
        data = super().clean()
        invested = []
        for key in LEADER_ROWS.keys:
            invested_name = LEADER_ROWS.field_name(key, "invested")
            if data.get(LEADER_ROWS.field_name(key, "character")) is None:
                # A vacant role cannot be invested.
                data[invested_name] = False
            elif data.get(invested_name):
                invested.append(rules.ROLE_LABELS[key])
        if len(invested) > rules.MAX_INVESTED_LEADERS:
            raise forms.ValidationError(
                f"At most {rules.MAX_INVESTED_LEADERS} leaders can be invested, "
                f"not {len(invested)} ({', '.join(invested)})."
            )
        return data


class NewSettlementForm(forms.Form):
    name = forms.CharField(label="Settlement name", max_length=120)
    settlement_type = forms.ChoiceField(label="Type", choices=Settlement.Type.choices)


class SettlementForm(forms.Form):
    """Everything on the urban grid sheet except the buildings."""

    FORM_ID = "settlement-form"
    MODEL_FIELDS = grid.DETAIL_FIELDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(fields_for_model(Settlement, fields=self.MODEL_FIELDS))
        for side, label in grid.SIDES:
            self.fields[f"border_{side}_water"] = forms.BooleanField(label="Water", required=False)
            self.fields[f"border_{side}_bridge"] = forms.BooleanField(
                label="Bridge", required=False
            )
            self.fields[f"border_{side}_wall"] = forms.ChoiceField(
                label=f"{label} wall",
                choices=grid.WALLS,
                required=False,
                widget=forms.RadioSelect,
            )
        _join_form(self)

    @classmethod
    def initial_for(cls, settlement):
        initial = {name: getattr(settlement, name) for name in cls.MODEL_FIELDS}
        for side, _ in grid.SIDES:
            for part, value in grid.side_features(settlement.borders, side).items():
                initial[f"border_{side}_{part}"] = value
        return initial

    def clean(self):
        data = super().clean()
        for side, label in grid.SIDES:
            if data.get(f"border_{side}_bridge") and not data.get(f"border_{side}_water"):
                self.add_error(
                    f"border_{side}_bridge",
                    f"A bridge needs water. Tick Water on the {label.lower()} side too.",
                )
        return data

    def settlement_values(self):
        """Cleaned data in the shape the Settlement model stores."""
        values = {name: self.cleaned_data[name] for name in self.MODEL_FIELDS}
        borders = {}
        for side, _ in grid.SIDES:
            features = grid.features_list(
                *(
                    self.cleaned_data[f"border_{side}_{part}"]
                    for part in ("water", "bridge", "wall")
                )
            )
            if features:
                borders[side] = features
        values["borders"] = borders
        return values


class NewArmyForm(forms.Form):
    name = forms.CharField(label="Army name", max_length=120)


class ArmyForm(forms.ModelForm):
    """The army roster details. Saved through services.update_army, never with ModelForm.save()."""

    class Meta:
        model = Army
        fields = Army.ROSTER_FIELDS
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, army, **kwargs):
        super().__init__(*args, **kwargs)
        self.army = army
        # Commanders and garrisons may only come from this kingdom.
        self.fields["commander"].queryset = Character.objects.filter(kingdom=army.kingdom)
        self.fields["commander"].empty_label = "None"
        self.fields["garrison"].queryset = Settlement.objects.filter(kingdom=army.kingdom)
        self.fields["garrison"].empty_label = "None"

    def clean_commander(self):
        commander = self.cleaned_data["commander"]
        led = commander and self.army.units.filter(hero=commander).first()
        if led:
            raise forms.ValidationError(
                f"{commander} is the hero of {led}. A character can fill only one role."
            )
        return commander


class NewUnitForm(forms.Form):
    name = forms.CharField(label="Unit name", max_length=120)


class UnitForm(forms.ModelForm):
    """One unit's record. Saved through services.update_unit, never with ModelForm.save()."""

    class Meta:
        model = Unit
        fields = Unit.FIELDS
        widgets = {
            "traits": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, unit, **kwargs):
        super().__init__(*args, **kwargs)
        self.unit = unit
        self.fields["quality"].choices = [("", "-"), *Unit.Quality.choices]
        self.fields["hero"].queryset = Character.objects.filter(kingdom=unit.army.kingdom)
        self.fields["hero"].empty_label = "None"

    def clean_hero(self):
        """A character fills only one role in an army: its commander or one unit's hero."""
        hero = self.cleaned_data["hero"]
        if hero is None:
            return hero
        army = self.unit.army
        if hero.pk == army.commander_id:
            raise forms.ValidationError(
                f"{hero} commands this army. A character can fill only one role."
            )
        other = army.units.filter(hero=hero).exclude(pk=self.unit.pk).first()
        if other:
            raise forms.ValidationError(f"{hero} is already the hero of {other}.")
        return hero

    def clean(self):
        data = super().clean()
        current, maximum = data.get("current_strength"), data.get("max_strength")
        if current is not None and maximum is not None and current > maximum:
            self.add_error("current_strength", "Current strength cannot be more than maximum.")
        return data


class BattleForm(forms.ModelForm):
    """A battle log entry. Saved through services, never with ModelForm.save()."""

    class Meta:
        model = Battle
        fields = Battle.FIELDS
        widgets = {
            "opponents": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class CharacterForm(forms.Form):
    name = forms.CharField(max_length=80)
    kind = forms.ChoiceField(
        choices=Character.Kind.choices, initial=Character.Kind.NPC, widget=forms.RadioSelect
    )
    picture = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"accept": "image/jpeg,image/png,image/gif,image/webp"}
        ),
        help_text="JPEG, PNG, GIF or WebP. It is shrunk to at most "
        f"{pictures.MAX_SIDE} pixels on its longest side.",
    )

    def clean_picture(self):
        upload = self.cleaned_data["picture"]
        return pictures.downscale(upload) if upload else None


class PlacementForm(forms.Form):
    building = forms.ChoiceField(widget=forms.RadioSelect)
    block = forms.TypedChoiceField(coerce=int, choices=[(b, f"Block {b + 1}") for b in grid.BLOCKS])
    lot = forms.TypedChoiceField(coerce=int, choices=list(enumerate(grid.LOT_NAMES)))
    rotation = forms.TypedChoiceField(
        coerce=int, choices=[(r, f"{r} degrees") for r in grid.ROTATIONS], initial=0
    )

    def __init__(self, *args, settlement, **kwargs):
        super().__init__(*args, **kwargs)
        self.settlement = settlement
        self.fields["building"].choices = [(key, b.label) for key, b in grid.catalog().items()]

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        building = grid.catalog()[data["building"]]
        lots = grid.covered_lots(building.lots, data["lot"], data["rotation"])
        if lots is None:
            raise forms.ValidationError(_fit_hint(building.lots, data["rotation"]))
        taken = grid.blocked_lots(
            Placement.objects.filter(settlement=self.settlement), data["block"]
        )
        clashes = sorted({grid.building_label(taken[lot].building) for lot in lots if lot in taken})
        if clashes:
            raise forms.ValidationError(
                f"{building.label} would overlap {', '.join(clashes)}. Pick a free spot."
            )
        counts = growth.lots_per_block(Placement.objects.filter(settlement=self.settlement))
        try:
            growth.check_placement(self.settlement.settlement_type, counts, data["block"])
        except growth.PlacementNotAllowed as error:
            raise forms.ValidationError(str(error)) from error
        return data


def _fit_hint(lots, rotation):
    if lots == 4:
        return "A 4-lot building fills a whole block, so start it in the top left lot."
    if rotation in (0, 180):
        return (
            "A horizontal 2-lot building must start in a left lot. Use 90 degrees to stand it up."
        )
    return "A vertical 2-lot building must start in a top lot."


class JoinForm(forms.Form):
    code = forms.CharField(label="Sharing ID", max_length=128)

    def clean_code(self):
        code = normalize_access_code(self.cleaned_data["code"])
        if not is_valid_access_code(code):
            raise forms.ValidationError(
                f"Sharing IDs are {ACCESS_CODE_LENGTH} lowercase hexadecimal characters."
            )
        return code


class SelectNameForm(forms.Form):
    display_name = forms.CharField(label="Name", max_length=40)
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        min_length=PASSWORD_MIN_LENGTH,
    )


class ProtectForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        min_length=PASSWORD_MIN_LENGTH,
    )


class StatisticForm(forms.Form):
    label = forms.CharField(max_length=80)
    value = forms.IntegerField()
    display_order = forms.IntegerField()
