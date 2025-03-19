"""Control Library for the Ark Metric SMU-4000."""

import logging

from setuptools_scm import get_version

logger = logging.getLogger(__name__)

try:
    __version__ = get_version()
except LookupError:
    __version__ = "0.0.0.dev"  # Fallback version
    logger.warning("Version not found. Using fallback version 0.0.0.dev")

from .smu4000 import Smu4000

# clean up namespace by defining __all__
__all__ = ["Smu4000"]
