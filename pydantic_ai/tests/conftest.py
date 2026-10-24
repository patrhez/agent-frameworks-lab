from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from shared.testing.fixtures import no_network
