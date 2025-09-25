import re
import asyncio
from typing import List, Dict, Any

from playwright.async_api import async_playwright


SOURCE_PATH = "/workspace/llm_powered_elem_selection.py"
URL = "https://www.verizon.com/smartphones/"
TARGET_TEXT = "test-input"


def extract_js_exact_from_source() -> str:
    with open(SOURCE_PATH, "r", encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"_JS_EXACT\s*=\s*r\"\"\"([\s\S]*?)\"\"\"", src)
    if not m:
        raise RuntimeError("Could not locate _JS_EXACT in source file")
    return m.group(1)


async def run_once(url: str, target_text: str, js_exact: str, timeout_ms: int = 10000) -> int:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        # Match original helper behavior: wait for text selector (will often time out for unknown text)
        try:
            await page.wait_for_selector(f'text="{target_text}"', timeout=timeout_ms)
        except Exception:
            pass

        total: List[Dict[str, Any]] = []
        for fr in page.frames:
            try:
                res = await fr.evaluate(js_exact, target_text)
                if res:
                    total.extend(res)
            except Exception:
                # Ignore frame errors to match original behavior
                pass

        await browser.close()
        return len(total)


async def main():
    js_exact = extract_js_exact_from_source()
    # Run twice as requested
    count1 = await run_once(URL, TARGET_TEXT, js_exact)
    count2 = await run_once(URL, TARGET_TEXT, js_exact)
    print(f"Run 1: Extracted {count1} elements")
    print(f"Run 2: Extracted {count2} elements")


if __name__ == "__main__":
    asyncio.run(main())

