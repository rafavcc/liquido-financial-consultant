import os
import tempfile
from pathlib import Path

# app.main instancia `app` na importação: aponta para um banco descartável antes de qualquer import
os.environ.setdefault("LIQUIDO_DB", str(Path(tempfile.mkdtemp(prefix="liquido-tests-")) / "import.db"))
