from django import forms
from django.forms.models import fields_for_model

from .access import ACCESS_CODE_LENGTH, is_valid_access_code, normalize_access_code
from .models import Kingdom
from .sheet import KINGDOM_FIELDS, ROW_GROUPS

PASSWORD_MIN_LENGTH = 8


class KingdomForm(forms.Form):
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
        for field in self.fields.values():
            # Inputs are spread across the page and join the sheet form through this attribute.
            field.widget.attrs["form"] = self.FORM_ID


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
        help_text="",
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
