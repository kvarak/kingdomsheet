from .names import current_writer, is_admin_writer


def current_name(request):
    """The selected name and admin flag for every page. Name is None if no name is selected."""
    writer = current_writer(request)
    return {
        "current_name": writer.display_name if writer else None,
        "is_admin": is_admin_writer(writer),
    }
