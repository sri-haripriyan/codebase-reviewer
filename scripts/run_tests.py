import sys
from pathlib import Path

# Ensure project root is in Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


def main():
    """Run pytest with passed CLI arguments or standard defaults."""
    args = sys.argv[1:] if len(sys.argv) > 1 else ["-v", "tests"]
    print(f"Running pytest with arguments: {args}")
    exit_code = pytest.main(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
