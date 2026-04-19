"""Entry point for running Sentinel as a module: ``python -m backend``."""

import logging

from backend.entrypoint import main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

raise SystemExit(main())
