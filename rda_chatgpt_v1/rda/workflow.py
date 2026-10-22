import logging
import re
import time
import traceback
from datetime import datetime

from rda.browser import browser_controller
from rda.chatgpt import chatgpt_client as chatgpt_client_class
from rda.drive import drive_client as drive_client_class
from rda.paths import ensure_runtime_dirs, log_dir
from rda.session import session_manager as session_manager_class
from rda.sheets import sheets_client as sheets_client_class


class workflow:
    def __init__(
        self,
        settings,
        log_callback,
        manual_login_callback,
        stop_event,
    ):
        self.settings = settings
        self.log_callback = log_callback
        self.manual_login_callback = manual_login_callback
        self.stop_event = stop_event
        self.logger = self._create_logger()

    def verify_sessions(self):
        browser = browser_controller().start()

        try:
            session = session_manager_class(
                self.manual_login_callback,
                self._log,
            )
            sheets = sheets_client_class(
                browser,
                session,
                self.settings["sheet_url"],
            )
            chatgpt = chatgpt_client_class(
                browser,
                session,
                self._log,
            )

            self._log("verificando sesión de google")
            sheets.verify_session()
            self._log("sesión de google correcta")
            self._log("verificando sesión de chatgpt")
            chatgpt.verify_session()
            self._log("sesión de chatgpt correcta")
        finally:
            browser.close()

    def run(self):
        browser = browser_controller().start()

        try:
            session = session_manager_class(
                self.manual_login_callback,
                self._log,
            )
            sheets = sheets_client_class(
                browser,
                session,
                self.settings["sheet_url"],
            )
            drive = drive_client_class(
                browser,
                session,
                self._log,
            )
            chatgpt = chatgpt_client_class(
                browser,
                session,
                self._log,
            )

            self._log("verificando sesiones")
            sheets.verify_session()
            chatgpt.verify_session()
            self._log("sesiones correctas")

            for row_number in range(
                self.settings["start_row"],
                self.settings["end_row"] + 1,
            ):
                if self.stop_event.is_set():
                    self._log("ejecución detenida por el usuario")
                    break

                self._process_row(
                    row_number,
                    sheets,
                    drive,
                    chatgpt,
                )
        finally:
            browser.close()

    def _process_row(
        self,
        row_number,
        sheets_client,
        drive_client,
        chatgpt_client,
    ):
        link_cell = f"{self.settings['link_column']}{row_number}"
        output_cell = f"{self.settings['output_column']}{row_number}"
        status_column = self.settings.get("status_column", "").strip()
        status_cell = f"{status_column}{row_number}" if status_column else None

        # Registrar etapas, no URLs ni el contenido de los archivos.
        stage = "leer_sheet"
        started_at = time.monotonic()
        self._log(f"fila {row_number}: iniciando; enlace={link_cell}; salida={output_cell}")

        try:
            self._log(f"fila {row_number}: leyendo enlace de sheets")
            file_url = sheets_client.read_cell(link_cell)
            self._log(f"fila {row_number}: lectura terminada; tiene_valor={bool(file_url)}")

            if not file_url:
                raise RuntimeError("la celda de enlace está vacía")

            if not file_url.lower().startswith(("https://", "http://")):
                raise RuntimeError("la celda no contiene una url válida")

            stage = "descargar_drive"
            self._log(f"fila {row_number}: iniciando descarga")
            file_path = drive_client.download_file(file_url, row_number)
            self._log(f"fila {row_number}: descarga completada; extension={file_path.suffix.lower()}")

            if self.stop_event.is_set():
                return

            stage = "consultar_chatgpt"
            self._log(f"fila {row_number}: consultando chatgpt")
            response = chatgpt_client.ask_file(
                file_path,
                self.settings["prompt"],
                row_number,
            )

            stage = "escribir_respuesta"
            self._log(f"fila {row_number}: escribiendo respuesta; caracteres={len(response)}")
            sheets_client.write_cell(output_cell, response)
            self._log(f"fila {row_number}: respuesta escrita")

            if status_cell:
                stage = "escribir_estado"
                self._log(f"fila {row_number}: escribiendo estado OK")
                sheets_client.write_cell(status_cell, "OK")

            self._log(f"fila {row_number}: ok")
        except Exception as exc:
            error_name = type(exc).__name__
            self._log(f"fila {row_number}: error etapa={stage}; tipo={error_name}; detalle={self._safe_log(exc)}")
            # Guardar la traza completa en disco, con URLs ocultas.
            self.logger.error("fila %s traceback:\n%s", row_number, self._safe_log(traceback.format_exc()))

            if status_cell:
                try:
                    sheets_client.write_cell(status_cell, f"ERROR_{error_name}")
                except Exception as status_exc:
                    self._log(f"fila {row_number}: fallo al escribir estado; tipo={type(status_exc).__name__}")
        finally:
            try:
                self._log(f"fila {row_number}: limpiando temporales")
                drive_client.cleanup_row(row_number)
            except Exception as cleanup_exc:
                self._log(f"fila {row_number}: fallo limpieza; tipo={type(cleanup_exc).__name__}")
            self._log(f"fila {row_number}: fin; segundos={time.monotonic() - started_at:.1f}")

    def _safe_log(self, message):
        # Playwright puede incluir enlaces sensibles en los errores.
        return re.sub(r"https?://\S+", "[url_omitida]", str(message))[:12000]

    def _create_logger(self):
        ensure_runtime_dirs()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger = logging.getLogger(f"rda_chatgpt_{timestamp}_{id(self)}")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        handler = logging.FileHandler(
            log_dir / f"run_{timestamp}.log",
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
        return logger

    def _log(self, message):
        self.logger.info(message)
        self.log_callback(message)
