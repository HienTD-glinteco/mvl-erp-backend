# flake8: noqa

from .base import *


if ENVIRONMENT == "local":
    from .local import *
if ENVIRONMENT == "prod":
    from .prod import *
if ENVIRONMENT == "test":
    from .test import *
