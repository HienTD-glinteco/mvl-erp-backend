# ruff: noqa

from .base import *


if ENVIRONMENT == "local":
    from .local import *
if ENVIRONMENT == "develop":
    from .develop import *
if ENVIRONMENT == "prod":
    from .prod import *
if ENVIRONMENT == "staging":
    from .staging import *
if ENVIRONMENT == "test":
    from .test import *
