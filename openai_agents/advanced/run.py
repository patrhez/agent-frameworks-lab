from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.cli import main
from . import approvals_handoff

if __name__ == "__main__":
    main(approvals_handoff)
