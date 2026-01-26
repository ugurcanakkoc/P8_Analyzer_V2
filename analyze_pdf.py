#!/usr/bin/env python
"""
P8 Analyzer CLI - Analyze electrical schematics from the command line.

Usage:
    ./venv/Scripts/python.exe analyze_pdf.py data/ornek.pdf -p 11 --include-annotations
    ./venv/Scripts/python.exe analyze_pdf.py data/ornek.pdf -p 11-14 -f json -o results.json

For full help:
    ./venv/Scripts/python.exe analyze_pdf.py --help
"""
import sys
from p8_analyzer.cli.main import main

if __name__ == '__main__':
    sys.exit(main())
