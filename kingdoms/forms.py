from django import forms
from django.forms.models import fields_for_model

from . import settlements as grid
from .access import ACCESS_CODE_LENGTH, is_valid_access_code, normalize_access_code
from .models import Kingdom, Placement, Settlement
from .sheet import KINGDOM_FIELDS, ROW_GROUPS

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(fields_for_model(Kingdom, fields=KINGDOM_FIELDS))
        for group in ROW_GROUPS:
            for key in group.keys:
                # Each call returns fresh field objects, so rows never share widgets.
                for name, field in fields_for_model(group.model, fields=group.fields).items():
                    self.fields[group.field_name(key, name)] = field
        _join_form(self)


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
            self.fields[f"border_{side}"] = forms.MultipleChoiceField(
                label=label,
                choices=grid.BORDER_FEATURES,
                required=False,
                widget=forms.CheckboxSelectMultiple,
            )
        _join_form(self)

    @classmethod
    def initial_for(cls, settlement):
        initial = {name: getattr(settlement, name) for name in cls.MODEL_FIELDS}
        for side, _ in grid.SIDES:
            initial[f"border_{side}"] = settlement.borders.get(side, [])
        return initial

    def settlement_values(self):
        """Cleaned data in the shape the Settlement model stores."""
        values = {name: self.cleaned_data[name] for name in self.MODEL_FIELDS}
        values["borders"] = {
            side: self.cleaned_data[f"border_{side}"]
            for side, _ in grid.SIDES
            if self.cleaned_data[f"border_{side}"]
        }
        return values


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
