import re
import time
import argparse
from typing import List, Dict, Any

from playwright.sync_api import sync_playwright


SOURCE_PATH = "/workspace/llm_powered_elem_selection.py"


def extract_js_exact_from_source() -> str:
    with open(SOURCE_PATH, "r", encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"_JS_EXACT\s*=\s*r\"\"\"([\s\S]*?)\"\"\"", src)
    if not m:
        raise RuntimeError("Could not locate _JS_EXACT in source file")
    return m.group(1)


def run_once(url: str, target_text: str, js_exact: str, timeout_ms: int = 15000) -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        # Attempt a short wait for exact text for parity with main pipeline
        try:
            page.wait_for_selector(f'text="{target_text}"', timeout=timeout_ms)
        except Exception:
            pass

        total: List[Dict[str, Any]] = []
        for fr in page.frames:
            try:
                res = fr.evaluate(js_exact, target_text)
                if res:
                    total.extend(res)
            except Exception:
                pass

        browser.close()
        return len(total)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.verizon.com/smartphones/")
    parser.add_argument("--target", required=True)
    parser.add_argument("--runs", type=int, default=2)
    args = parser.parse_args()

    js_exact = extract_js_exact_from_source()

    counts = []
    t0 = time.time()
    for i in range(args.runs):
        start = time.time()
        c = run_once(args.url, args.target, js_exact)
        end = time.time()
        print(f"Extracted {c} candidates in {end - start:.2f} seconds (Run {i+1})")
        counts.append(c)
    t1 = time.time()
    print(f"Total runtime: {t1 - t0:.2f}s; Counts: {counts}")


if __name__ == "__main__":
    main()

