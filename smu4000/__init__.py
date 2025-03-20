"""Control Library for the Ark Metrica Ltd. SMU-4000."""

import logging

logger = logging.getLogger(__name__)

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("smu4000")
except PackageNotFoundError:
    __version__ = "0.0.0"  # Fallback version
    logger.debug(f"Version not found. Using fallback version {__version__}")

from .smu4000 import Smu4000

# clean up namespace by defining __all__
__all__ = ["Smu4000"]
