import os
import sys

# This code adds project root to PYTHON_PATH.
# !! May work improperly if test files are organized in subpaths.
file_dir = os.path.dirname(__file__)  # this is a path to one of the tests
base_path, _ = os.path.split(file_dir)
sys.path.append(base_path)

