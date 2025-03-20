"""Control Library for the Ark Metrica Ltd. SMU-4000."""

import logging

logger = logging.getLogger(__name__)

try:
    # _version.py gets created by setuptools_scm at build time
    from ._version import version as __version__
except ImportError:
    __version__ = "0.0.0.dev"  # Fallback version
    logger.debug(f"Version not found. Using fallback version {__version__}")

from .smu4000 import Smu4000

# clean up namespace by defining __all__
__all__ = ["Smu4000"]
