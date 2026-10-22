from playwright.sync_api import sync_playwright

from rda.paths import ensure_runtime_dirs, profile_dir


class browser_controller:
    def __init__(self):
        self.playwright = None
        self.context = None

    def start(self):
        ensure_runtime_dirs()
        self.playwright = sync_playwright().start()

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
            accept_downloads=True,
            args=["--start-maximized"],
        )

        try:
            self.context.grant_permissions(
                ["clipboard-read", "clipboard-write"],
                origin="https://docs.google.com",
            )
        except Exception:
            pass

        return self

    def get_page(self, url_contains=None):
        if url_contains:
            for page in self.context.pages:
                if url_contains in page.url:
                    return page

            return self.context.new_page()

        if self.context.pages:
            return self.context.pages[0]

        return self.context.new_page()

    def new_page(self):
        return self.context.new_page()

    def close(self):
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass

        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass

        self.context = None
        self.playwright = None
