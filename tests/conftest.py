import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEST_ROOT = Path("/tmp/test-api-pytest")
shutil.rmtree(TEST_ROOT, ignore_errors=True)
TEST_ROOT.mkdir(parents=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{TEST_ROOT}/test.db",
    UPLOAD_DIR=str(TEST_ROOT / "uploads"),
    MODEL_MOCK="true",
    API_TOKEN="",
)
