from web_ui import html_page
from exactly_once import _wrap_html_page


def test_web_page_is_single_column_and_phone_safe():
    page = html_page("http://192.168.1.20:8787")

    assert 'name="viewport"' in page
    assert "viewport-fit=cover" in page
    assert "env(safe-area-inset-bottom)" in page
    assert ".wrap{max-width:520px" in page
    assert 'role="tablist"' in page
    assert 'id="panel-send"' in page and 'id="panel-get"' in page
    assert 'id="xfer"' in page  # transfer card sits above the tabs
    assert page.index('id="xfer"') < page.index('role="tablist"')


def test_web_page_escapes_displayed_address():
    page = html_page("http://deck/<script>")

    assert "http://deck/&lt;script&gt;" in page
    assert "http://deck/<script>" not in page


def test_browser_cancel_aborts_active_upload_immediately():
    page = html_page("http://192.168.1.20:8787")

    assert "new XMLHttpRequest()" in page
    assert "X-DeckyShare-Fast" in page
    assert "xhr.send(f.slice(off))" in page
    assert "abortActiveUploads()" in page
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


def test_large_browser_uploads_use_three_parallel_native_lanes():
    page = html_page("http://192.168.1.20:8787")

    assert "uploadOneParallel(f,onProgress,onRetry)" in page
    assert "X-DeckyShare-Parallel" in page
    assert "lanes=3" in page
    assert "f.size>=64*1024*1024" in page
    assert "Turbo mode • 3 parallel native streams" in page


def test_maximum_speed_mode_is_a_single_non_resumable_stream():
    page = html_page("http://192.168.1.20:8787")

    assert 'id="maxspeed" type="checkbox" checked' in page
    assert "<b>Maximum Speed</b>" in page
    assert "No resume: if Wi-Fi drops, the file starts again." in page
    assert "uploadOneMaximum(f,onProgress)" in page
    assert "X-DeckyShare-No-Resume" in page
    assert "xhr.send(f)" in page
    assert "one raw continuous stream • no checkpoints" in page
    assert "pause.disabled=noResume" in page


def test_immediate_cancel_survives_exactly_once_upload_wrapper():
    page = _wrap_html_page(html_page)("http://192.168.1.20:8787")

    assert "new XMLHttpRequest()" in page
    assert "X-DeckyShare-Fast" in page
    assert "abortActiveUploads()" in page
    assert "X-DeckyShare-Upload-ID" in page
    assert "cancelPartial(f.name,uploadId)" in page
