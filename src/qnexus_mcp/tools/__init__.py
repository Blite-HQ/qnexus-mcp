"""Tool registry: the full list of ToolSpecs the server can register."""

from .execute import EXECUTE_SPECS
from .read import READ_SPECS

ALL_SPECS = [*READ_SPECS, *EXECUTE_SPECS]
