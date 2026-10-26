from django import forms

from .access import ACCESS_CODE_LENGTH, is_valid_access_code, normalize_access_code

PASSWORD_MIN_LENGTH = 8


class KingdomForm(forms.Form):
    name = forms.CharField(max_length=120)
    description = forms.CharField(widget=forms.Textarea, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)


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
