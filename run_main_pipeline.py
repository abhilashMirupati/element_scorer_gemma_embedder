import json
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


def run_once(url: str, target_text: str, js_exact: str, exact: bool, timeout_ms: int = 15000) -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        try:
            page.wait_for_selector(f'text="{target_text}"', timeout=timeout_ms)
        except Exception:
            pass

        total: List[Dict[str, Any]] = []
        # Build a wrapper that constructs the function from source and invokes with (targetText, opts)
        wrapper = f"(payload) => ( {js_exact} )(payload.targetText, payload.opts)"
        payload = {"targetText": target_text, "opts": {"exact": bool(exact)}}
        for fr in page.frames:
            try:
                res = fr.evaluate(wrapper, payload)
                if res:
                    total.extend(res)
            except Exception:
                pass

        browser.close()
        return len(total)


def run_mode(url: str, target_text: str, js_exact: str, mode: str) -> Dict[str, int]:
    if mode == "exact":
        return {"exact": run_once(url, target_text, js_exact, True)}
    if mode == "fuzzy":
        return {"fuzzy": run_once(url, target_text, js_exact, False)}
    if mode == "both":
        return {
            "exact": run_once(url, target_text, js_exact, True),
            "fuzzy": run_once(url, target_text, js_exact, False),
        }
    raise ValueError("mode must be one of: exact, fuzzy, both")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.verizon.com/smartphones/")
    parser.add_argument("--target", required=True)
    parser.add_argument("--mode", choices=["exact", "fuzzy", "both"], default="both")
    args = parser.parse_args()

    js_exact = extract_js_exact_from_source()

    t0 = time.time()
    results = run_mode(args.url, args.target, js_exact, args.mode)
    t1 = time.time()
    print(json.dumps({"counts": results, "elapsed_s": round(t1 - t0, 2)}, indent=2))


if __name__ == "__main__":
    main()

