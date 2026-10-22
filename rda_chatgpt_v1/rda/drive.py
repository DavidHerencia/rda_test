import re
import shutil
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from rda.paths import download_dir


class drive_client:
    def __init__(self, browser, session_manager, log_callback):
        self.browser = browser
        self.session_manager = session_manager
        self.log_callback = log_callback

    def download_file(self, file_url, row_number):
        row_dir = download_dir / f"row_{row_number}"
        shutil.rmtree(row_dir, ignore_errors=True)
        row_dir.mkdir(parents=True, exist_ok=True)

        page = self.browser.new_page()

        try:
            self.session_manager.ensure_google_session(page, file_url)
            self.log_callback(f"fila {row_number}: descargando archivo")
            download = self._download_from_preview(page)
            file_path = row_dir / self._safe_file_name(download.suggested_filename)
            download.save_as(str(file_path))
            if not file_path.is_file() or file_path.stat().st_size == 0:
                raise RuntimeError("descarga vacía o archivo inexistente")
            self.log_callback(f"fila {row_number}: archivo guardado; bytes={file_path.stat().st_size}")
            return file_path
        finally:
            try:
                page.close()
            except Exception:
                pass

    def cleanup_row(self, row_number):
        shutil.rmtree(download_dir / f"row_{row_number}", ignore_errors=True)

    def _download_from_preview(self, page):
        download_pattern = re.compile(r"download|descargar", re.IGNORECASE)
        deadline = time.monotonic() + 20

        while time.monotonic() < deadline:
            candidates = [
                page.get_by_role("button", name=download_pattern),
                page.get_by_role("menuitem", name=download_pattern),
                page.get_by_label(download_pattern),
            ]

            for locator in candidates:
                count = locator.count()

                for index in range(min(count, 5)):
                    candidate = locator.nth(index)

                    try:
                        if not candidate.is_visible():
                            continue

                        with page.expect_download(timeout=30000) as download_info:
                            candidate.click()

                        return download_info.value
                    except PlaywrightTimeoutError:
                        self.log_callback("drive: clic sin evento de descarga")
                        continue
                    except Exception as exc:
                        # No registrar URLs o rutas de los archivos.
                        self.log_callback(f"drive: fallo en clic; tipo={type(exc).__name__}")
                        continue

            page.wait_for_timeout(500)

        raise RuntimeError("no se encontró una acción de descarga en google drive")

    def _safe_file_name(self, file_name):
        clean_name = re.sub(r'[<>:"/\\|?*]+', "_", file_name).strip()
        return clean_name or "archivo_descargado"
