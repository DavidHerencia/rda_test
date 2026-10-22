import re
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from rda.config import load_settings, save_settings
from rda.workflow import workflow as workflow_class


class rda_app:
    def __init__(self, root):
        self.root = root
        self.root.title("RDA ChatGPT v1")
        self.root.geometry("760x650")
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.settings = load_settings()
        self.variables = {}
        self.prompt_text = None
        self.log_text = None
        self.verify_button = None
        self.start_button = None
        self.stop_button = None

        self._build_ui()
        self._load_values()

    def _build_ui(self):
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill="both", expand=True)

        container.columnconfigure(1, weight=1)
        container.rowconfigure(8, weight=1)

        fields = [
            ("URL Google Sheet", "sheet_url"),
            ("Fila inicial", "start_row"),
            ("Fila final", "end_row"),
            ("Columna enlace Drive", "link_column"),
            ("Columna respuesta", "output_column"),
            ("Columna estado", "status_column"),
        ]

        for row_index, (label_text, key) in enumerate(fields):
            ttk.Label(container, text=label_text).grid(
                row=row_index,
                column=0,
                sticky="w",
                padx=(0, 10),
                pady=5,
            )
            variable = tk.StringVar()
            self.variables[key] = variable
            ttk.Entry(container, textvariable=variable).grid(
                row=row_index,
                column=1,
                sticky="ew",
                pady=5,
            )

        ttk.Label(container, text="Prompt").grid(
            row=6,
            column=0,
            sticky="nw",
            padx=(0, 10),
            pady=5,
        )

        self.prompt_text = tk.Text(container, height=4, wrap="word")
        self.prompt_text.grid(row=6, column=1, sticky="ew", pady=5)

        button_frame = ttk.Frame(container)
        button_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 8))

        self.verify_button = ttk.Button(
            button_frame,
            text="Verificar sesiones",
            command=self._verify_sessions,
        )
        self.verify_button.pack(side="left", padx=(0, 8))

        self.start_button = ttk.Button(
            button_frame,
            text="Iniciar",
            command=self._start_run,
        )
        self.start_button.pack(side="left", padx=(0, 8))

        self.stop_button = ttk.Button(
            button_frame,
            text="Detener",
            command=self._stop_run,
            state="disabled",
        )
        self.stop_button.pack(side="left")

        self.log_text = tk.Text(container, height=16, state="disabled", wrap="word")
        self.log_text.grid(row=8, column=0, columnspan=2, sticky="nsew")

    def _load_values(self):
        for key, variable in self.variables.items():
            variable.set(str(self.settings.get(key, "")))

        self.prompt_text.insert("1.0", self.settings.get("prompt", ""))

    def _collect_settings(self):
        sheet_url = self.variables["sheet_url"].get().strip()
        start_row = int(self.variables["start_row"].get().strip())
        end_row = int(self.variables["end_row"].get().strip())
        link_column = self.variables["link_column"].get().strip().upper()
        output_column = self.variables["output_column"].get().strip().upper()
        status_column = self.variables["status_column"].get().strip().upper()
        prompt = self.prompt_text.get("1.0", "end").strip()

        if not sheet_url.startswith("https://docs.google.com/spreadsheets/"):
            raise ValueError("ingresa una url válida de google sheets")

        if start_row < 1 or end_row < start_row:
            raise ValueError("el rango de filas no es válido")

        for column in (link_column, output_column):
            if not re.fullmatch(r"[A-Z]{1,3}", column):
                raise ValueError("las columnas deben usar letras como B, C o AA")

        if status_column and not re.fullmatch(r"[A-Z]{1,3}", status_column):
            raise ValueError("la columna de estado no es válida")

        if link_column == output_column:
            raise ValueError("la columna de enlace y respuesta deben ser distintas")

        if not prompt:
            raise ValueError("el prompt no puede estar vacío")

        return {
            "sheet_url": sheet_url,
            "start_row": start_row,
            "end_row": end_row,
            "link_column": link_column,
            "output_column": output_column,
            "status_column": status_column,
            "prompt": prompt,
        }

    def _verify_sessions(self):
        self._run_background("verify")

    def _start_run(self):
        self._run_background("run")

    def _run_background(self, mode):
        if self.worker_thread and self.worker_thread.is_alive():
            return

        try:
            settings = self._collect_settings()
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Configuración", str(exc))
            return

        save_settings(settings)
        self.stop_event.clear()
        self._set_running_state(True)

        def worker():
            try:
                workflow_runner = workflow_class(
                    settings=settings,
                    log_callback=self._append_log,
                    manual_login_callback=self._request_manual_login,
                    stop_event=self.stop_event,
                )

                if mode == "verify":
                    workflow_runner.verify_sessions()
                    self._append_log("verificación terminada")
                else:
                    workflow_runner.run()
                    self._append_log("ejecución terminada")
            except Exception as exc:
                self._append_log(f"error general {type(exc).__name__}")
                self.root.after(
                    0,
                    lambda: messagebox.showerror("RDA", str(exc)),
                )
            finally:
                self.root.after(0, lambda: self._set_running_state(False))

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def _stop_run(self):
        self.stop_event.set()
        self._append_log("solicitud de detención recibida")

    def _set_running_state(self, is_running):
        if is_running:
            self.verify_button.configure(state="disabled")
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
        else:
            self.verify_button.configure(state="normal")
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")

    def _append_log(self, message):
        def update():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"{message}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.root.after(0, update)

    def _request_manual_login(self, service_name, instruction):
        result = {"accepted": False}
        finished = threading.Event()

        def ask():
            result["accepted"] = messagebox.askokcancel(
                f"Sesión requerida - {service_name}",
                instruction,
            )
            finished.set()

        self.root.after(0, ask)
        finished.wait()
        return result["accepted"]


def main():
    root = tk.Tk()
    rda_app(root)
    root.mainloop()


if __name__ == "__main__":
    main()
