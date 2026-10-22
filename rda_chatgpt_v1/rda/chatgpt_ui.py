import re
import time


prompt_selectors = (
    "#prompt-textarea",
    '[data-testid="prompt-textarea"]',
    '[data-testid="composer-input"]',
    '[contenteditable="true"][role="textbox"]',
    '.ProseMirror[contenteditable="true"]',
    'textarea[aria-label*="ensaje"]',
    'textarea[aria-label*="essage"]',
    'textarea[placeholder*="ensaje"]',
    'textarea[placeholder*="essage"]',
    '[contenteditable="true"]',
)

login_pattern = re.compile(
    r"^(?:log in|login|sign in|sign up|iniciar sesi[oó]n|inicia sesi[oó]n|"
    r"acceder|registrarse|reg[ií]strate)$",
    re.IGNORECASE,
)

new_chat_pattern = re.compile(
    r"^(?:nuevo chat|new chat|nueva conversaci[oó]n|new conversation)$",
    re.IGNORECASE,
)


def _has_visible(locator):
    try:
        for index in range(min(locator.count(), 5)):
            if locator.nth(index).is_visible():
                return True
    except Exception:
        return False

    return False


def find_chatgpt_prompt(page):
    for selector in prompt_selectors:
        try:
            locator = page.locator(f"{selector}:visible")
            if locator.count() > 0:
                return locator.first
        except Exception:
            continue

    return None


def wait_for_chatgpt_prompt(page, timeout_ms=60000):
    deadline = time.monotonic() + timeout_ms / 1000

    while time.monotonic() < deadline:
        prompt_box = find_chatgpt_prompt(page)

        if prompt_box is not None:
            return prompt_box

        page.wait_for_timeout(500)

    raise RuntimeError("no se encontró el cuadro para escribir en chatgpt")


def is_chatgpt_ui_ready(page):
    for role in ("button", "link"):
        if _has_visible(page.get_by_role(role, name=login_pattern)):
            return False

    for role in ("button", "link"):
        if _has_visible(page.get_by_role(role, name=new_chat_pattern)):
            return True

    if _has_visible(page.get_by_text(new_chat_pattern, exact=True)):
        return True

    return False
