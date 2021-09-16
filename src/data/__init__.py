from sqlalchemy.orm import declarative_base
from pathlib import Path

Base = declarative_base()
ROOT_DIR = Path(__file__).resolve().parents[2]
