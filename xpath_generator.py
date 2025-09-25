"""
XPath Generator Module for QA Automation

This module provides a deterministic XPath generation function that creates
stable, reliable XPath selectors for web elements based on HTML snippets
and optional target text.
"""

import re
import html
from typing import Optional, Tuple, List, Dict, Any

# Import Playwright only when needed for production use
try:
    from playwright.async_api import Page
except ImportError:
    Page = Any  # Type placeholder for demo


async def choose_best_xpath(
    node_html: str,
    parent_html: Optional[str],
    grand_html: Optional[str],
    target_text: Optional[str],
    page,  # Playwright Page object
    validate: bool = True,
) -> Tuple[Optional[str], List[Tuple[str, int]]]:
    """
    Generate the best deterministic XPath for a given HTML node.
    
    Args:
        node_html: The outerHTML of the target element
        parent_html: The outerHTML of the parent element (optional)
        grand_html: The outerHTML of the grandparent element (optional)
        target_text: Optional text to anchor the XPath
        page: Playwright Page object for validation
        validate: Whether to validate XPath uniqueness
        
    Returns:
        Tuple of (best_xpath, diagnostics) where diagnostics is list of (xpath, count)
    """
    diagnostics: List[Tuple[str, int]] = []
    
    # Parse HTML snippets
    node_tag, node_attrs = _parse_outer_html(node_html)
    parent_tag, parent_attrs = _parse_outer_html(parent_html) if parent_html else (None, {})
    grand_tag, grand_attrs = _parse_outer_html(grand_html) if grand_html else (None, {})
    
    # Determine anchor text
    anchor_text = target_text if target_text and target_text.strip() else _auto_anchor_from_node(node_html)
    
    # Build ROOT base XPath
    if anchor_text:
        root_xpath = _build_root_with_anchor(node_html, anchor_text, node_tag)
    else:
        root_xpath = _build_root_without_anchor(node_tag, node_attrs)
    
    if not root_xpath:
        return None, diagnostics
    
    # Validate ROOT base
    if validate:
        count = await _count(page, root_xpath)
        diagnostics.append((root_xpath, count))
        if count == 1:
            return root_xpath, diagnostics
    
    # Try with parent scope
    if parent_tag:
        parent_scope = _ancestor_scope(parent_tag, parent_attrs)
        parent_xpath = _combine(parent_scope, root_xpath)
        
        if validate:
            count = await _count(page, parent_xpath)
            diagnostics.append((parent_xpath, count))
            if count == 1:
                return parent_xpath, diagnostics
        else:
            root_xpath = parent_xpath  # Update base for grandparent
    
    # Try with grandparent scope
    if grand_tag:
        grand_scope = _ancestor_scope(grand_tag, grand_attrs)
        grand_xpath = _combine(grand_scope, root_xpath)
        
        if validate:
            count = await _count(page, grand_xpath)
            diagnostics.append((grand_xpath, count))
            if count == 1:
                return grand_xpath, diagnostics
    
    # Return best candidate (smallest positive count or None)
    if validate and diagnostics:
        positive_candidates = [(xp, cnt) for xp, cnt in diagnostics if cnt > 0]
        if positive_candidates:
            best_xpath, _ = min(positive_candidates, key=lambda x: x[1])
            return best_xpath, diagnostics
    
    return None, diagnostics


def _norm(s: str) -> str:
    """Normalize string by collapsing whitespace and converting special chars."""
    if not s:
        return ""
    
    # Convert <br> tags to spaces
    s = re.sub(r'<br\s*/?>', ' ', s, flags=re.IGNORECASE)
    
    # Decode HTML entities
    s = html.unescape(s)
    
    # Convert Unicode spaces (including NBSP) to ASCII space
    s = re.sub(r'[\u00A0\u2000-\u200F\u2028-\u202F\u205F\u3000]', ' ', s)
    
    # Collapse multiple spaces and trim
    s = ' '.join(s.split())
    
    return s


def _xp_literal(s: str) -> str:
    """Safely escape string for XPath literal."""
    if not s:
        return "''"
    
    # Escape single quotes by doubling them
    escaped = s.replace("'", "''")
    return f"'{escaped}'"


def _parse_outer_html(snippet: Optional[str]) -> Tuple[Optional[str], Dict[str, str]]:
    """Parse outerHTML snippet to extract tag and attributes."""
    if not snippet or not snippet.strip():
        return None, {}
    
    # Find the first tag
    match = re.search(r'<(\w+)([^>]*)>', snippet.strip())
    if not match:
        return None, {}
    
    tag = match.group(1).lower()
    attrs_str = match.group(2)
    
    # Parse attributes
    attrs = {}
    attr_pattern = r'(\w+(?:-\w+)*)\s*=\s*["\']([^"\']*)["\']'
    for attr_match in re.finditer(attr_pattern, attrs_str):
        key = attr_match.group(1).lower()
        value = attr_match.group(2)
        
        # Skip empty attribute values
        if value.strip():
            attrs[key] = value
    
    return tag, attrs


def _best_attr(attrs: Dict[str, str]) -> Optional[Tuple[str, str]]:
    """Get the best stable attribute from the priority order."""
    priority_order = [
        'data-testid', 'data-test', 'data-qa', 'data-automation-id',
        'aria-label', 'name', 'role', 'value', 'title', 'alt', 'id'
    ]
    
    for attr in priority_order:
        if attr in attrs and attrs[attr].strip():
            return attr, attrs[attr]
    
    return None


def _find_control_with_aria_label(snippet: str, target_text: str) -> Optional[str]:
    """Find control element with matching aria-label."""
    if not target_text or not snippet:
        return None
    
    controls = ['input', 'button', 'a', 'select', 'textarea', 'label']
    
    for control in controls:
        pattern = rf'<{control}[^>]*aria-label\s*=\s*["\']([^"\']*?)["\'][^>]*>'
        match = re.search(pattern, snippet, re.IGNORECASE)
        if match and _norm(match.group(1)) == _norm(target_text):
            return control
    
    return None


def _find_descendant_ids_or_testids(snippet: str) -> List[Tuple[str, str]]:
    """Find descendant elements with strong internal anchors."""
    anchors = []
    test_attrs = ['id', 'data-testid', 'data-automation-id', 'data-qa', 'data-test']
    
    for attr in test_attrs:
        pattern = rf'<[^>]*{attr}\s*=\s*["\']([^"\']+)["\'][^>]*>'
        for match in re.finditer(pattern, snippet, re.IGNORECASE):
            value = match.group(1).strip()
            if value:
                anchors.append((attr, value))
    
    return anchors


def _auto_anchor_from_node(snippet: str) -> Optional[str]:
    """Auto-extract anchor text from node subtree."""
    if not snippet:
        return None
    
    # First try aria-label on controls
    controls = ['input', 'button', 'a', 'select', 'textarea', 'label']
    for control in controls:
        pattern = rf'<{control}[^>]*aria-label\s*=\s*["\']([^"\']*?)["\'][^>]*>'
        match = re.search(pattern, snippet, re.IGNORECASE)
        if match:
            text = _norm(match.group(1))
            if text:
                return text
    
    # Try other attributes
    attr_pattern = r'(?:aria-label|value|title|name|alt)\s*=\s*["\']([^"\']*?)["\']'
    for match in re.finditer(attr_pattern, snippet, re.IGNORECASE):
        text = _norm(match.group(1))
        if text:
            return text
    
    # Try descendant inner text from common tags
    text_tags = ['span', 'p', 'label', 'a', 'button', 'div']
    for tag in text_tags:
        pattern = rf'<{tag}[^>]*>([^<]+)</{tag}>'
        match = re.search(pattern, snippet, re.IGNORECASE | re.DOTALL)
        if match:
            text = _norm(match.group(1))
            if text and len(text) <= 50:  # Reasonable length limit
                return text
    
    return None


def _ancestor_scope(tag: str, attrs: Dict[str, str]) -> str:
    """Build ancestor scope XPath."""
    best_attr = _best_attr(attrs)
    if best_attr:
        attr_name, attr_value = best_attr
        return f"//{tag}[@{attr_name}={_xp_literal(attr_value)}]"
    else:
        return f"//{tag}"


def _combine(scope: str, base: str) -> str:
    """Combine scope and base XPath."""
    # Remove leading // from base if present
    if base.startswith('//'):
        base = base[2:]
    return f"{scope}//{base}"


def _build_root_with_anchor(snippet: str, anchor_text: str, root_tag: str) -> str:
    """Build root XPath with anchor text."""
    if not root_tag:
        return ""
    
    # Try control-specific predicates first
    control = _find_control_with_aria_label(snippet, anchor_text)
    if control:
        predicate = f".//{control}[@aria-label={_xp_literal(anchor_text)}]"
    else:
        # Try other attributes
        predicates = []
        for attr in ['aria-label', 'value', 'title', 'name', 'alt']:
            if attr in ['aria-label', 'value', 'title', 'name', 'alt']:
                predicates.append(f".//*[@{attr}={_xp_literal(anchor_text)}]")
        
        # Add text content predicate
        predicates.append(f".//*[normalize-space(.)={_xp_literal(anchor_text)}]")
        
        predicate = ' or '.join(predicates)
    
    # Add internal anchors if they help
    internal_anchors = _find_descendant_ids_or_testids(snippet)
    if internal_anchors:
        anchor_predicates = []
        for attr, value in internal_anchors[:2]:  # Use at most 2
            anchor_predicates.append(f".//*[@{attr}={_xp_literal(value)}]")
        
        if anchor_predicates:
            predicate = f"({predicate}) and {' and '.join(anchor_predicates)}"
    
    return f"//{root_tag}[{predicate}]"


def _build_root_without_anchor(tag: str, attrs: Dict[str, str]) -> str:
    """Build root XPath without anchor text."""
    if not tag:
        return ""
    
    best_attr = _best_attr(attrs)
    if best_attr:
        attr_name, attr_value = best_attr
        return f"//{tag}[@{attr_name}={_xp_literal(attr_value)}]"
    else:
        return f"//{tag}"


async def _count(page, xpath: str) -> int:
    """Count elements matching XPath using Playwright."""
    try:
        return await page.locator(f"xpath={xpath}").count()
    except Exception:
        return 0


# Test harness
if __name__ == "__main__":
    import asyncio
    
    class MockPage:
        """Mock Playwright page for testing."""
        def __init__(self, counts):
            self.counts = counts
            self.call_count = 0
        
        def locator(self, xpath):
            class MockLocator:
                def __init__(self, page, xpath):
                    self.page = page
                    self.xpath = xpath
                
                async def count(self):
                    count = self.page.counts[min(self.page.call_count, len(self.page.counts) - 1)]
                    self.page.call_count += 1
                    return count
            
            return MockLocator(self, xpath)
    
    async def run_tests():
        """Run acceptance tests."""
        print("Running XPath Generator Tests\n")
        
        # Test 1: Exact text in descendant span
        print("Test 1: Exact text in descendant span")
        node_html = '<li class="item"><span>Delivery + Setup</span></li>'
        parent_html = '<p class="parent" data-testid="delivery-section"></p>'
        
        mock_page = MockPage([2, 1])  # First call returns 2, second returns 1
        
        xpath, diags = await choose_best_xpath(
            node_html=node_html,
            parent_html=parent_html,
            grand_html=None,
            target_text="Delivery + Setup",
            page=mock_page,
            validate=True
        )
        
        print(f"Generated XPath: {xpath}")
        print("Diagnostics:")
        for xp, count in diags:
            print(f"  {xp} -> {count} matches")
        print()
        
        # Test 2: Control with aria-label
        print("Test 2: Control with aria-label")
        node_html = '<div class="toggle-container"><input aria-label="Lowest price with trade-in offer" type="checkbox"><div id="trade-inToggle"></div></div>'
        
        mock_page = MockPage([1])  # Should be unique
        
        xpath, diags = await choose_best_xpath(
            node_html=node_html,
            parent_html=None,
            grand_html=None,
            target_text="Lowest price with trade-in offer",
            page=mock_page,
            validate=True
        )
        
        print(f"Generated XPath: {xpath}")
        print("Diagnostics:")
        for xp, count in diags:
            print(f"  {xp} -> {count} matches")
        print()
        
        # Test 3: Auto-anchor from node
        print("Test 3: Auto-anchor from node")
        node_html = '<button class="submit-btn"><span>Submit Order</span></button>'
        
        mock_page = MockPage([1])
        
        xpath, diags = await choose_best_xpath(
            node_html=node_html,
            parent_html=None,
            grand_html=None,
            target_text=None,
            page=mock_page,
            validate=True
        )
        
        print(f"Generated XPath: {xpath}")
        print("Diagnostics:")
        for xp, count in diags:
            print(f"  {xp} -> {count} matches")
        print()
        
        # Test 4: No validation (just show generated XPaths)
        print("Test 4: XPath generation without validation")
        node_html = '<div class="container"><input type="text" aria-label="Username" placeholder="Enter username"></div>'
        
        mock_page = MockPage([])  # No validation calls
        
        xpath, diags = await choose_best_xpath(
            node_html=node_html,
            parent_html=None,
            grand_html=None,
            target_text="Username",
            page=mock_page,
            validate=False
        )
        
        print(f"Generated XPath: {xpath}")
        print("Diagnostics:", diags)
        print()
        
        print("All tests completed!")
    
    # Run the tests
    asyncio.run(run_tests())