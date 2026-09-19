from web_ui import html_page
from exactly_once import _wrap_html_page


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


def test_browser_cancel_aborts_active_upload_immediately():
    page = html_page("http://192.168.1.20:8787")

    assert "let chunk=4*1024*1024" in page
    assert "new AbortController()" in page
    assert "signal:controller.signal" in page
    assert "uploadControl.controller.abort()" in page
    assert "Cancelling now…" in page
    assert "Cancelling after current chunk" not in page


def test_browser_prepares_crc_off_main_thread_and_pipelines_next_chunk():
    page = html_page("http://192.168.1.20:8787")

    assert "new Worker(" in page
    assert "crc32Async(buffer)" in page
    assert "prepareUploadChunk(f,off,chunk)" in page
    assert "nextPromise=current.end<f.size?prepareUploadChunk" in page
    assert "body:current.blob" in page


def test_immediate_cancel_survives_exactly_once_upload_wrapper():
    page = _wrap_html_page(html_page)("http://192.168.1.20:8787")

    assert "new AbortController()" in page
    assert "let chunk=4*1024*1024" in page
    assert "signal:controller.signal" in page
    assert "uploadControl.controller.abort()" in page
    assert "X-DeckyShare-Upload-ID" in page
    assert "cancelPartial(f.name,uploadId)" in page
