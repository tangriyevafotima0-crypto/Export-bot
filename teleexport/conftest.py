"""Root conftest for teleexport - ensures python package is importable."""
import sys
from pathlib import Path

# Add teleexport/ to sys.path so 'python.*' imports resolve correctly
sys.path.insert(0, str(Path(__file__).parent))
