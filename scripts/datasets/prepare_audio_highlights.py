"""Create the approved 60-second local highlights without overwriting files."""

from scripts.datasets.cli import main


if __name__ == '__main__':
    raise SystemExit(main(prepare=True))
