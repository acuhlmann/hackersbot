"""Tests to verify mobile CSS is correctly configured."""

import pytest
import re
from pathlib import Path


class TestMobileCss:
    """Test mobile CSS configuration."""
    
    @pytest.fixture
    def index_html(self):
        """Load the index.html file."""
        index_path = Path(__file__).parent.parent / "web" / "index.html"
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_mobile_media_query_exists(self, index_html):
        """Test that mobile media query exists."""
        assert "@media (max-width: 768px)" in index_html, \
            "Mobile media query should exist"
    
    def test_mobile_container_is_single_column(self, index_html):
        """Test that container becomes single column on mobile."""
        # Find the mobile media query section
        mobile_section = re.search(
            r'@media \(max-width: 768px\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            index_html,
            re.DOTALL
        )
        assert mobile_section, "Mobile media query section should exist"
        
        mobile_css = mobile_section.group(1)
        
        # Check container has grid-template-columns: 1fr
        assert "grid-template-columns: 1fr" in mobile_css, \
            "Container should be single column on mobile"
    
    def test_mobile_sidebar_has_no_max_height_40vh(self, index_html):
        """Test that sidebar doesn't have the restrictive 40vh max-height on mobile."""
        # Find the mobile media query section
        mobile_section = re.search(
            r'@media \(max-width: 768px\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            index_html,
            re.DOTALL
        )
        assert mobile_section, "Mobile media query section should exist"
        
        mobile_css = mobile_section.group(1)
        
        # The old problematic CSS had "max-height: 40vh" on .sidebar
        # We want to ensure the sidebar section doesn't have this restrictive setting
        sidebar_section = re.search(r'\.sidebar\s*\{([^}]*)\}', mobile_css)
        if sidebar_section:
            sidebar_css = sidebar_section.group(1)
            # Check that max-height is either 'none' or not 40vh
            if 'max-height' in sidebar_css:
                assert 'max-height: none' in sidebar_css or 'max-height: 40vh' not in sidebar_css, \
                    "Sidebar should not have restrictive max-height: 40vh"
    
    def test_mobile_summary_list_has_scrolling(self, index_html):
        """Test that summary list has proper scrolling on mobile."""
        # Find the mobile media query section
        mobile_section = re.search(
            r'@media \(max-width: 768px\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            index_html,
            re.DOTALL
        )
        assert mobile_section, "Mobile media query section should exist"
        
        mobile_css = mobile_section.group(1)
        
        # Check that .summary-list has overflow handling
        summary_list_section = re.search(r'\.summary-list\s*\{([^}]*)\}', mobile_css)
        if summary_list_section:
            summary_list_css = summary_list_section.group(1)
            # Should have overflow-y: auto for scrolling
            assert 'overflow-y: auto' in summary_list_css, \
                "Summary list should have overflow-y: auto for scrolling on mobile"
    
    def test_mobile_sidebar_has_bottom_border(self, index_html):
        """Test that sidebar has bottom border instead of right border on mobile."""
        mobile_section = re.search(
            r'@media \(max-width: 768px\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            index_html,
            re.DOTALL
        )
        assert mobile_section, "Mobile media query section should exist"
        
        mobile_css = mobile_section.group(1)
        
        sidebar_section = re.search(r'\.sidebar\s*\{([^}]*)\}', mobile_css)
        if sidebar_section:
            sidebar_css = sidebar_section.group(1)
            # Should have border-bottom instead of border-right
            assert 'border-bottom' in sidebar_css, \
                "Sidebar should have border-bottom on mobile (stacked layout)"
    
    def test_refresh_button_exists_in_html(self, index_html):
        """Test that the refresh button exists in the HTML."""
        assert 'id="refreshButton"' in index_html, \
            "Refresh button should exist with id='refreshButton'"
        assert "Refresh Today's Summary" in index_html, \
            "Refresh button should have 'Refresh Today's Summary' text"
    
    def test_refresh_status_element_exists(self, index_html):
        """Test that refresh status element exists."""
        assert 'id="refreshStatus"' in index_html, \
            "Refresh status element should exist"
    
    def test_summary_list_container_exists(self, index_html):
        """Test that summary list container exists."""
        assert 'id="summaryList"' in index_html, \
            "Summary list container should exist"
        assert 'class="summary-list"' in index_html, \
            "Summary list should have proper class"
