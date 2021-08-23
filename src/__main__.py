"""Allow analysis scripts to be executable through `python -m scitrend-analysis`."""
from src.cli import main


if __name__ == "__main__":
    main(prog_name="scitrend-analysis")
