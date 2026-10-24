"""
Main Application Entry Point for Commercial CFD Propeller STEP Generator.

Launches the CustomTkinter desktop interface with CAD generation pipeline.
"""

import sys
import argparse
from pathlib import Path

# Ensure root directory is on sys.path for relative imports
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.main_window import PropellerApp


def main():
    """Initializes and runs the propeller CAD generator desktop application."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-test", action="store_true",
                        help="Exercise the real native UI, then close with a JSON report.")
    parser.add_argument("--report", default="work/ui-smoke.report.json")
    parser.add_argument("--test-export", default="work/ui-smoke.step")
    args = parser.parse_args()
    app = PropellerApp()
    # Mark the native window as mapped before CustomTkinter's main loop. This
    # avoids reentrant startup/close handling in its Windows title-bar update.
    app.update()
    if args.smoke_test:
        from verify_ui import attach_smoke_test
        report = Path(args.report)
        output = Path(args.test_export)
        controller = attach_smoke_test(app,
            report if report.is_absolute() else PROJECT_ROOT/report,
            output if output.is_absolute() else PROJECT_ROOT/output)
    app.mainloop()
    if args.smoke_test:
        return 0 if controller["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
