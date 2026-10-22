import time
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from rda.chatgpt_ui import is_chatgpt_ui_ready


class session_cancelled_error(RuntimeError):
    pass


class session_manager:
    def __init__(self, manual_login_callback, log_callback):
        self.manual_login_callback = manual_login_callback
        self.log_callback = log_callback

    def ensure_google_session(self, page, target_url):
        self._open(page, target_url)

        while self._is_google_login_page(page):
            self.log_callback("sesión de google requerida")

            accepted = self.manual_login_callback(
                "Google",
                "Inicia sesión en Google en la ventana de Chrome abierta y luego pulsa Aceptar",
            )

            if not accepted:
                raise session_cancelled_error("inicio de sesión de google cancelado")

            page.wait_for_timeout(1000)
            self._open(page, target_url)

        return page

    def ensure_chatgpt_session(self, page):
        self._open(page, "https://chatgpt.com/")

        for attempt in range(3):
            if self._wait_for_chatgpt_ui(page):
                return page

            if attempt == 2:
                break

            self.log_callback("sesión de chatgpt requerida o interfaz no detectada")

            accepted = self.manual_login_callback(
                "ChatGPT",
                "Comprueba que aparece Nuevo chat en Chrome. "
                "Si hace falta, inicia sesión y luego pulsa Aceptar",
            )

            if not accepted:
                raise session_cancelled_error("inicio de sesión de chatgpt cancelado")

            self._open(page, "https://chatgpt.com/")

        raise RuntimeError("no se pudo verificar la interfaz de chatgpt")

    def _wait_for_chatgpt_ui(self, page):
        deadline = time.monotonic() + 20

        while time.monotonic() < deadline:
            if is_chatgpt_ui_ready(page):
                return True

            page.wait_for_timeout(500)

        return False

    def _open(self, page, url):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightTimeoutError:
            if not page.url:
                raise

    def _is_google_login_page(self, page):
        host = urlparse(page.url).hostname or ""

        if host.endswith("accounts.google.com"):
            return True

        email_input = page.locator('input[type="email"]')
        return email_input.count() > 0 and email_input.first.is_visible()
