from ..sheet import sheet_values

PLAYER_NAME = "Alice"
PASSWORD = "longenough1"


def sheet_post_data(kingdom, **overrides):
    """A full sheet POST built from the saved sheet, like a browser submitting it unchanged."""
    values = {**sheet_values(kingdom), **overrides}
    # Browsers omit unchecked checkboxes, send "on" for checked ones, IDs for chosen options
    # and an empty string for an empty select.
    return {
        name: "on" if value is True else "" if value is None else getattr(value, "pk", value)
        for name, value in values.items()
        if value is not False
    }
