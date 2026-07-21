"""Console entry point: parse config, build the server, and run it over stdio."""

from __future__ import annotations

import os
import sys

from .client import QnexusClient
from .config import config_from_sources
from .server import build_server


def main() -> None:
    config = config_from_sources(sys.argv[1:], os.environ)
    server = build_server(config, QnexusClient())
    server.run()
