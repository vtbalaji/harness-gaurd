"""`python -m order_agent` → `order_agent.cli.main()` (contracts/cli.md)."""

import sys

from order_agent.cli import main

if __name__ == "__main__":
    sys.exit(main())
