import re
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from rda.chatgpt_ui import wait_for_chatgpt_prompt


class chatgpt_client:
    # Los selectores pueden cambiar entre versiones de la interfaz.
    response_selectors = (
        # Identificados en el DOM inspeccionado de ChatGPT.
        '[data-turn-key$=":assistant"] [data-markdown-style="assistant-message"]',
        '[data-turn-key$=":assistant"] [data-dil-message-id]',
        # Compatibilidad con variantes anteriores de la interfaz.
        '[data-message-author-role="assistant"]',
        '[data-testid^="conversation-turn"] .markdown',
    )
    stop_pattern = re.compile(
        r"stop|detener|parar|cancel generation|detener generación",
        re.IGNORECASE,
    )

    def __init__(self, browser, session_manager, log_callback):
        self.browser = browser
        self.session_manager = session_manager
        self.log_callback = log_callback
        self.page = browser.get_page("chatgpt.com")

    def verify_session(self):
        self.session_manager.ensure_chatgpt_session(self.page)

    def ask_file(self, file_path, prompt, row_number):
        self.session_manager.ensure_chatgpt_session(self.page)
        self.log_callback(f"fila {row_number}: abriendo nuevo chat")
        self._start_new_chat()
        self.log_callback(f"fila {row_number}: subiendo adjunto")
        self._upload_file(file_path)
        self.log_callback(f"fila {row_number}: esperando preparación del adjunto")
        self._wait_attachment_ready()
        self.log_callback(f"fila {row_number}: enviando pregunta")
        response = self._send_prompt(prompt)
        self.log_callback(f"fila {row_number}: respuesta recibida; caracteres={len(response)}")
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
        self.log_callback("chatgpt: input de archivo recibió la ruta local")

        try:
            self.page.get_by_text(file_path.name, exact=False).first.wait_for(
                state="visible",
                timeout=30000,
            )
            self.log_callback("chatgpt: nombre del adjunto visible")
        except PlaywrightTimeoutError:
            # La UI no siempre muestra el nombre; revisar también los estados busy.
            self.log_callback("chatgpt: nombre del adjunto no visible; comprobando carga")

    def _wait_attachment_ready(self):
        # La desaparición de indicadores busy ayuda a evitar envíos prematuros.
        # No demuestra procesamiento interno completo; la observación queda en el log.
        deadline = time.monotonic() + 120
        last_status = None
        idle_since = None
        while time.monotonic() < deadline:
            busy = self.page.locator(
                '[role="progressbar"]:visible, [aria-busy="true"]:visible'
            ).count()
            send_button = self.page.locator('[data-testid="send-button"]')
            send_enabled = send_button.count() > 0 and send_button.first.is_enabled()
            status = (busy, send_enabled)
            if status != last_status:
                self.log_callback(
                    f"chatgpt: carga busy={busy}; boton_enviar_habilitado={send_enabled}"
                )
                last_status = status
            if busy == 0:
                if idle_since is None:
                    idle_since = time.monotonic()
                if time.monotonic() - idle_since >= 2:
                    self.log_callback("chatgpt: sin indicadores visibles de carga")
                    return
            else:
                idle_since = None
            self.page.wait_for_timeout(500)
        raise RuntimeError("chatgpt: adjunto siguió mostrando carga durante 120 segundos")

    def _counts(self):
        return {
            selector: self.page.locator(selector).count()
            for selector in self.response_selectors
        }

    def _is_generating(self):
        button = self.page.get_by_role("button", name=self.stop_pattern)
        return button.count() > 0 and button.first.is_visible()

    def _send_prompt(self, prompt):
        before = self._counts()
        before_user_turns = self.page.locator('[data-turn-key$=":user"]').count()
        self.log_callback(f"chatgpt: respuestas antes del envío={before}")
        self.log_callback(f"chatgpt: turnos usuario antes del envío={before_user_turns}")
        prompt_box = wait_for_chatgpt_prompt(self.page)
        prompt_box.fill(prompt)
        self.log_callback("chatgpt: prompt escrito en el editor")
        prompt_box.press("Enter")
        self.log_callback("chatgpt: Enter pulsado; esperando confirmación de envío")

        deadline = time.monotonic() + 480  # Máximo, no espera fija.
        last_report = 0
        last_text = ""
        stable_since = None
        generation_seen = False
        message_sent = False
        selected = None

        while time.monotonic() < deadline:
            now = time.monotonic()
            try:
                editor_text = prompt_box.inner_text(timeout=1000).strip()
            except Exception:
                try:
                    editor_text = prompt_box.input_value(timeout=1000).strip()
                except Exception:
                    editor_text = None

            user_turns = self.page.locator('[data-turn-key$=":user"]').count()
            if not message_sent and user_turns > before_user_turns:
                message_sent = True
                self.log_callback("chatgpt: nuevo turno de usuario detectado; envío confirmado en DOM")
            elif not message_sent and editor_text == "":
                # Señal provisional; se confirma después con el turno de usuario.
                self.log_callback("chatgpt: editor vacío tras Enter; comprobando turno enviado")
                message_sent = True

            generating = self._is_generating()
            if generating and not generation_seen:
                generation_seen = True
                self.log_callback("chatgpt: detectado botón detener; generación iniciada")

            counts = self._counts()
            for selector in self.response_selectors:
                count = counts[selector]
                if count <= before[selector]:
                    continue
                try:
                    candidate = self.page.locator(selector).last.inner_text(timeout=1000).strip()
                except Exception:
                    continue
                if not candidate:
                    continue
                if selected != selector:
                    selected = selector
                    self.log_callback(f"chatgpt: texto de respuesta localizado; selector={selector}")
                if candidate != last_text:
                    last_text = candidate
                    stable_since = now
                # La captura real mostró data-turn-state="complete" en el
                # contenedor del turno. Priorizar esa señal de finalización.
                complete = False
                if selector.startswith('[data-turn-key'):
                    complete = self.page.locator(
                        '[data-turn-state="complete"] '
                        '[data-turn-key$=":assistant"] '
                        '[data-markdown-style="assistant-message"]'
                    ).count() > 0

                # También exigir estabilidad: un turno puede marcarse completo
                # durante ajustes finales del renderizado.
                quiet_seconds = 2 if complete else (3 if generation_seen else 10)
                if (
                    (message_sent or user_turns > before_user_turns)
                    and stable_since is not None
                    and not generating
                    and now - stable_since >= quiet_seconds
                ):
                    self.log_callback(
                        f"chatgpt: respuesta estable; segundos={quiet_seconds}; "
                        f"selector={selector}; turno_complete={complete}; "
                        f"caracteres={len(candidate)}"
                    )
                    return candidate
                break

            if now - last_report >= 10:
                self.log_callback(
                    f"chatgpt: esperando; transcurridos={int(480 - (deadline - now))}s; "
                    f"envio_probable={message_sent}; turnos_usuario={user_turns}; "
                    f"generando={generating}; "
                    f"respuesta_detectada={bool(last_text)}; conteos={counts}"
                )
                last_report = now

            self.page.wait_for_timeout(500)

        raise RuntimeError(
            "chatgpt: tiempo máximo de 480s superado; "
            f"envio_probable={message_sent}; respuesta_detectada={bool(last_text)}; "
            f"conteos={self._counts()}"
        )
