"""Application entrypoint for `python -m excel_intel`."""

import sys
from excel_intel.cli import main

if __name__ == "__main__":
    sys.exit(main())
