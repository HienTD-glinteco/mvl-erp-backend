default_app_config = "apps.realestate.apps.RealestateConfig"


def ready():
    """Import signal handlers when app is ready"""
    import apps.realestate.signals  # noqa: F401
