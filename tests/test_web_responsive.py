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

    assert "new XMLHttpRequest()" in page
    assert "X-DeckyShare-Fast" in page
    assert "xhr.send(f.slice(off))" in page
    assert "uploadControl.controller.abort()" in page
    assert "Cancelling now…" in page
    assert "Cancelling after current chunk" not in page
    assert "input.value=''" in page
    assert "queueState=[];renderQueue()" in page
    assert "diag.textContent=''" in page


def test_browser_uses_native_fast_stream_with_receiver_checkpoint():
    page = html_page("http://192.168.1.20:8787")

    assert "uploadOneFast(f,onProgress,onRetry)" in page
    assert "uploadOneReliable(f,onProgress,onRetry)" in page
    assert "typeof XMLHttpRequest==='undefined'" in page
    assert "/api/upload-status?upload_id=" in page
    assert "stableCheckpoint(f,uploadId,off)" in page
    assert "native continuous stream" in page
    assert "xhr.upload.onprogress" in page
    assert 'id="diag"' in page
    assert "prepareUploadChunk(f,off,chunk)" in page  # retained reliability helper


def test_immediate_cancel_survives_exactly_once_upload_wrapper():
    page = _wrap_html_page(html_page)("http://192.168.1.20:8787")

    assert "new XMLHttpRequest()" in page
    assert "X-DeckyShare-Fast" in page
    assert "uploadControl.controller.abort()" in page
    assert "X-DeckyShare-Upload-ID" in page
    assert "cancelPartial(f.name,uploadId)" in page
