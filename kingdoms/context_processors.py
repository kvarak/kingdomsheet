from .names import current_writer


def current_name(request):
    """The selected name for the top bar on every page, or None if no name is selected."""
    writer = current_writer(request)
    return {"current_name": writer.display_name if writer else None}
