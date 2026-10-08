"""Read-only audio validation; only an explicit --report writes a new JSON file."""

from scripts.datasets.cli import main


if __name__ == '__main__':
    raise SystemExit(main())
