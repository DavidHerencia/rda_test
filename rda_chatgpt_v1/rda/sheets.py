from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class sheets_client:
    def __init__(self, browser, session_manager, sheet_url):
        self.browser = browser
        self.session_manager = session_manager
        self.sheet_url = sheet_url
        self.page = browser.get_page("docs.google.com/spreadsheets")

    def verify_session(self):
        self.session_manager.ensure_google_session(self.page, self.sheet_url)

    def read_cell(self, cell_reference):
        self.session_manager.ensure_google_session(self.page, self.sheet_url)
        self._select_cell(cell_reference)

        self.page.evaluate("navigator.clipboard.writeText('')")
        self.page.keyboard.press("Control+C")
        self.page.wait_for_timeout(400)

        value = self.page.evaluate("navigator.clipboard.readText()")
        return value.strip()

    def write_cell(self, cell_reference, value):
        self.session_manager.ensure_google_session(self.page, self.sheet_url)
        self._select_cell(cell_reference)

        clean_value = " ".join(str(value).split())

        try:
            self.page.evaluate(
                "value => navigator.clipboard.writeText(value)",
                clean_value,
            )
            self.page.keyboard.press("Control+V")
        except Exception:
            self.page.keyboard.insert_text(clean_value)

        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(400)

    def _select_cell(self, cell_reference):
        target_url = self._build_range_url(cell_reference)
        self.page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_timeout(700)

    def _build_range_url(self, cell_reference):
        parts = urlsplit(self.sheet_url)
        fragment_values = dict(parse_qsl(parts.fragment, keep_blank_values=True))
        query_values = dict(parse_qsl(parts.query, keep_blank_values=True))

        if "gid" not in fragment_values and "gid" in query_values:
            fragment_values["gid"] = query_values["gid"]

        fragment_values["range"] = cell_reference
        new_fragment = urlencode(fragment_values)

        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                parts.query,
                new_fragment,
            )
        )
