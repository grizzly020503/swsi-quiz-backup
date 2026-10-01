#!/usr/bin/env python3
"""Compatibility entrypoint for the shared historical-law provenance core.

Keep this module path stable because existing V1 builders, tests, and workflows
import from it. All implementation lives in historical_law_provenance_core.py.
"""

from historical_law_provenance_core import *  # noqa: F401,F403
from historical_law_provenance_core import main


if __name__ == "__main__":
    raise SystemExit(main())
