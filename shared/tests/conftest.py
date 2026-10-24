"""Allow shared tests to run in any of the isolated framework environments."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
