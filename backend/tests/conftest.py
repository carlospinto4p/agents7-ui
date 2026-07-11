import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

# Redirect file-based logging to a throwaway dir for the whole test
# session. Importing ``main`` runs ``configure_logging()`` as a module
# side effect, which installs WARNING/ERROR file handlers rooted at
# ``$LOGS_DIR/logs`` (or ``<backend>/logs`` when unset). Without this,
# any warning a router test triggers would be persisted into the
# committed ``backend/logs/`` tree and later trip the session-start
# container-log check. Set it at conftest import time, before any test
# module imports ``main``. Tests that exercise ``logging_setup``
# directly override ``LOGS_DIR`` per-test via ``monkeypatch``.
os.environ.setdefault(
    "LOGS_DIR", tempfile.mkdtemp(prefix="agents7ui-test-logs-")
)
