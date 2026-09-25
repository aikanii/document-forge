#!/usr/bin/env python3
"""Convenience launcher: python run_hephaestus.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hephaestus.app import main  # noqa: E402

if __name__ == "__main__":
    main()
