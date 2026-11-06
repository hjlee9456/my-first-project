"""exe 빌드용 진입점 (PyInstaller: pyinstaller --onefile --name filetidy-scan filetidy_scan.py)."""
import sys

from scanner.cli import main

if __name__ == "__main__":
    sys.exit(main())
