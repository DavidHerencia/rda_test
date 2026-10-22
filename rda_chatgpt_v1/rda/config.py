import json

from rda.paths import config_file, ensure_runtime_dirs


def default_settings():
    return {
        "sheet_url": "",
        "start_row": 2,
        "end_row": 4,
        "link_column": "B",
        "output_column": "C",
        "status_column": "D",
        "prompt": "¿Pudiste leer correctamente el archivo adjunto? Responde únicamente con una frase breve.",
    }


def load_settings():
    ensure_runtime_dirs()
    settings = default_settings()

    if not config_file.exists():
        return settings

    try:
        saved_settings = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return settings

    settings.update(saved_settings)
    return settings


def save_settings(settings):
    ensure_runtime_dirs()
    config_file.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
