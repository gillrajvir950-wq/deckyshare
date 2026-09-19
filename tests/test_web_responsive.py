from web_ui import html_page


def test_web_page_has_separate_mobile_and_desktop_layouts():
    page = html_page("http://192.168.1.20:8787")

    assert 'name="viewport"' in page
    assert "@media(max-width:700px)" in page
    assert "@media(min-width:701px)" in page
    assert ".grid{grid-template-columns:1fr" in page
    assert "grid-template-columns:minmax(0,1fr) minmax(0,1fr)" in page
    assert "env(safe-area-inset-bottom)" in page
    assert ".controls #upload{grid-column:1/-1}" in page
    assert ".download-row" in page


def test_web_page_escapes_displayed_address():
    page = html_page("http://deck/<script>")

    assert "http://deck/&lt;script&gt;" in page
    assert "http://deck/<script>" not in page
