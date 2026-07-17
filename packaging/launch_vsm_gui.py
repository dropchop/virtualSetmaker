"""PyInstaller entry point for the standalone exe.

The GUI module uses package-relative imports, so it must be imported as
``virtualsetmaker.gui`` (as the ``vsm-gui`` entry point does) — running the
file directly as a top-level script breaks them.
"""

from virtualsetmaker.gui import main

if __name__ == "__main__":
    main()
