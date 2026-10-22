import re
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from rda.chatgpt_ui import wait_for_chatgpt_prompt


class chatgpt_client:
    def __init__(self, browser, session_manager, log_callback):
        self.browser = browser
        self.session_manager = session_manager
        self.log_callback = log_callback
        self.page = browser.get_page("chatgpt.com")

    def verify_session(self):
        self.session_manager.ensure_chatgpt_session(self.page)

    def ask_file(self, file_path, prompt, row_number):
        self.session_manager.ensure_chatgpt_session(self.page)
        self._start_new_chat()
        self._upload_file(file_path)
        self.log_callback(f"fila {row_number}: archivo adjuntado en chatgpt")
        response = self._send_prompt(prompt)
        return response

    def _start_new_chat(self):
        self.page.goto(
            "https://chatgpt.com/",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        wait_for_chatgpt_prompt(self.page)

    def _upload_file(self, file_path):
        file_path = Path(file_path)
        file_input = self.page.locator('input[type="file"]')

        if file_input.count() == 0:
            attach_pattern = re.compile(
                r"attach|adjuntar|add files|agregar archivos|upload|subir",
                re.IGNORECASE,
            )
            attach_button = self.page.get_by_role("button", name=attach_pattern)

            if attach_button.count() == 0:
                raise RuntimeError("no se encontró el control para adjuntar archivos en chatgpt")

            attach_button.first.click()
            file_input = self.page.locator('input[type="file"]')
            file_input.first.wait_for(state="attached", timeout=10000)

        file_input.last.set_input_files(str(file_path))

        try:
            self.page.get_by_text(file_path.name, exact=False).first.wait_for(
                state="visible",
                timeout=30000,
            )
        except PlaywrightTimeoutError:
            self.page.wait_for_timeout(2000)

    def _send_prompt(self, prompt):
        assistant_messages = self.page.locator('[data-message-author-role="assistant"]')
        previous_count = assistant_messages.count()
        prompt_box = wait_for_chatgpt_prompt(self.page)

        prompt_box.fill(prompt)
        prompt_box.press("Enter")

        deadline = time.monotonic() + 240

        while time.monotonic() < deadline:
            current_count = assistant_messages.count()

            if current_count > previous_count:
                return self._wait_for_final_response(assistant_messages.last, deadline)

            self.page.wait_for_timeout(500)

        raise RuntimeError("chatgpt no inició una respuesta dentro del tiempo esperado")

    def _wait_for_final_response(self, message, deadline):
        stop_pattern = re.compile(
            r"stop|detener|parar|cancel generation|detener generación",
            re.IGNORECASE,
        )
        last_text = ""
        stable_checks = 0

        while time.monotonic() < deadline:
            try:
                text = message.inner_text(timeout=5000).strip()
            except Exception:
                text = ""

            is_generating = False
            stop_button = self.page.get_by_role("button", name=stop_pattern)

            if stop_button.count() > 0:
                try:
                    is_generating = stop_button.first.is_visible()
                except Exception:
                    is_generating = False

            if text and text == last_text and not is_generating:
                stable_checks += 1
            else:
                stable_checks = 0

            if stable_checks >= 3:
                return text

            last_text = text
            self.page.wait_for_timeout(1000)

        raise RuntimeError("chatgpt no terminó la respuesta dentro del tiempo esperado")
