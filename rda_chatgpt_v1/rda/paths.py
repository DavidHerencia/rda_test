import os
import tempfile
from pathlib import Path


app_name = "rda_chatgpt"
local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home()))
data_dir = local_app_data / app_name
profile_dir = data_dir / "chrome_profile"
log_dir = data_dir / "logs"
config_file = data_dir / "settings.json"
download_dir = Path(tempfile.gettempdir()) / app_name / "downloads"


def ensure_runtime_dirs():
    for path in (data_dir, profile_dir, log_dir, download_dir):
        path.mkdir(parents=True, exist_ok=True)
