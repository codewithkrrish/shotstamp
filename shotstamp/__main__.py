"""Run shotstamp as a module: python -m shotstamp photos/ --dry-run."""

from .cli import run

if __name__ == "__main__":
    run()
