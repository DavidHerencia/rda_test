import logging
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

        self._log(f"fila {row_number}: iniciando")

        try:
            file_url = sheets_client.read_cell(link_cell)

            if not file_url:
                raise RuntimeError("la celda de enlace está vacía")

            if not file_url.lower().startswith(("https://", "http://")):
                raise RuntimeError("la celda no contiene una url válida")

            file_path = drive_client.download_file(file_url, row_number)

            if self.stop_event.is_set():
                return

            self._log(f"fila {row_number}: consultando chatgpt")
            response = chatgpt_client.ask_file(
                file_path,
                self.settings["prompt"],
                row_number,
            )

            sheets_client.write_cell(output_cell, response)

            if status_cell:
                sheets_client.write_cell(status_cell, "OK")

            self._log(f"fila {row_number}: ok")
        except Exception as exc:
            error_name = type(exc).__name__
            self._log(f"fila {row_number}: error {error_name}")

            if status_cell:
                try:
                    sheets_client.write_cell(status_cell, f"ERROR_{error_name}")
                except Exception:
                    self._log(f"fila {row_number}: no se pudo escribir el estado")
        finally:
            drive_client.cleanup_row(row_number)

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
