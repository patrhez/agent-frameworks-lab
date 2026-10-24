from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.cli import main
from . import deferred_hitl

if __name__ == "__main__":
    main(deferred_hitl)
