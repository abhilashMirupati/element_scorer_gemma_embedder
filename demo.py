#!/usr/bin/env python3
"""
Demo script showing XPath generation examples
"""

import asyncio
import sys
sys.path.append('/workspace')

from xpath_generator import choose_best_xpath


class MockPage:
    """Mock Playwright page for demo purposes."""
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


async def demo():
    """Run demonstration examples."""
    print("=== XPath Generator Demo ===\n")
    
    # Example 1: Form input with aria-label
    print("Example 1: Form input with aria-label")
    print("HTML: <input type='email' aria-label='Email Address' placeholder='Enter email'>")
    page = MockPage([1])
    xpath, diags = await choose_best_xpath(
        node_html="<input type='email' aria-label='Email Address' placeholder='Enter email'>",
        parent_html=None,
        grand_html=None,
        target_text="Email Address",
        page=page,
        validate=True
    )
    print(f"Generated XPath: {xpath}")
    print()
    
    # Example 2: Button with text content
    print("Example 2: Button with text content")
    print("HTML: <button class='btn-primary'>Save Changes</button>")
    page = MockPage([1])
    xpath, diags = await choose_best_xpath(
        node_html="<button class='btn-primary'>Save Changes</button>",
        parent_html=None,
        grand_html=None,
        target_text=None,
        page=page,
        validate=True
    )
    print(f"Generated XPath: {xpath}")
    print()
    
    # Example 3: Complex nested structure
    print("Example 3: Complex nested structure")
    print("HTML: <div class='product-card'><h3>iPhone 15 Pro</h3><span class='price'>$999</span></div>")
    page = MockPage([3, 1])  # Multiple matches, then unique with parent
    xpath, diags = await choose_best_xpath(
        node_html="<div class='product-card'><h3>iPhone 15 Pro</h3><span class='price'>$999</span></div>",
        parent_html="<section class='products' data-testid='product-grid'></section>",
        grand_html=None,
        target_text="iPhone 15 Pro",
        page=page,
        validate=True
    )
    print(f"Generated XPath: {xpath}")
    print()
    
    # Example 4: Checkbox with data attributes
    print("Example 4: Checkbox with data attributes")
    print("HTML: <input type='checkbox' data-testid='newsletter-signup' aria-label='Subscribe to newsletter'>")
    page = MockPage([1])
    xpath, diags = await choose_best_xpath(
        node_html="<input type='checkbox' data-testid='newsletter-signup' aria-label='Subscribe to newsletter'>",
        parent_html=None,
        grand_html=None,
        target_text="Subscribe to newsletter",
        page=page,
        validate=True
    )
    print(f"Generated XPath: {xpath}")
    print()
    
    # Example 5: Link with href and text
    print("Example 5: Link with href and text")
    print("HTML: <a href='/contact' class='nav-link'>Contact Us</a>")
    page = MockPage([1])
    xpath, diags = await choose_best_xpath(
        node_html="<a href='/contact' class='nav-link'>Contact Us</a>",
        parent_html=None,
        grand_html=None,
        target_text=None,
        page=page,
        validate=True
    )
    print(f"Generated XPath: {xpath}")
    print()
    
    print("Demo completed!")


if __name__ == "__main__":
    asyncio.run(demo())