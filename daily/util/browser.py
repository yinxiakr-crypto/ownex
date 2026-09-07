from __future__ import annotations

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from util.logger import get_logger

LOGGER = get_logger()


class HeadlessBrowser:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.page: Page | None = None

    def __enter__(self) -> "HeadlessBrowser":
        LOGGER.info("[브라우저] 헤드리스 브라우저 시작")
        self._playwright = sync_playwright().start()
        self._browser = self._launch()
        self.page = self._browser.new_page(locale="ko-KR", viewport={"width": 1400, "height": 900})
        self.page.set_default_timeout(25000)
        return self

    def _launch(self) -> Browser:
        args = ["--disable-blink-features=AutomationControlled"]
        last = None
        for kwargs in (
            {"headless": True, "args": args},
            {"channel": "msedge", "headless": True, "args": args},
            {"channel": "chrome", "headless": True, "args": args},
        ):
            try:
                return self._playwright.chromium.launch(**kwargs)
            except Exception as exc:
                last = exc
                LOGGER.info(f"[브라우저] 실행 실패, 다른 방법으로 시도합니다: {exc}")
        raise last

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        LOGGER.info("[브라우저] 종료")

    def goto(self, url: str, wait_ms: int = 2500) -> Page:
        assert self.page is not None
        LOGGER.info(f"[브라우저] 이동: {url}")
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            if self._browser:
                self.page = self._browser.new_page(locale="ko-KR", viewport={"width": 1400, "height": 900})
                self.page.set_default_timeout(25000)
                self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
        self.page.wait_for_timeout(wait_ms)
        return self.page
