"""Tool registry: the full list of ToolSpecs the server can register."""

from .destructive import DESTRUCTIVE_SPECS
from .execute import EXECUTE_SPECS
from .manage import MANAGE_SPECS
from .read import READ_SPECS

ALL_SPECS = [*READ_SPECS, *EXECUTE_SPECS, *MANAGE_SPECS, *DESTRUCTIVE_SPECS]
