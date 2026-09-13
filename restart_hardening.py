import time
from pathlib import Path


_STALE_PART_TTL = 24 * 60 * 60


def cleanup_orphan_parts(receive_dir, now=None):
    """Remove stale upload parts left behind across plugin restarts."""
    root = Path(receive_dir)
    now = time.time() if now is None else float(now)
    removed = []
    try:
        candidates = root.glob(".deckyshare-*.part")
    except OSError:
        return removed
    for part in candidates:
        try:
            if not part.is_file():
                continue
            age = now - part.stat().st_mtime
            if age > _STALE_PART_TTL:
                part.unlink()
                removed.append(part.name)
        except OSError:
            continue
    return removed


def zero_byte_download_headers(name, content_type):
    safe_name = str(name).replace('"', '')
    return {
        "Content-Type": content_type or "application/octet-stream",
        "Content-Disposition": f'attachment; filename="{safe_name}"',
        "Accept-Ranges": "bytes",
        "Content-Length": "0",
    }


def install(core):
    if getattr(core.STATE, "_restart_hardening_installed", False):
        return

    old_put = core.Handler.do_PUT
    old_download = core.Handler.handle_download

    def do_PUT(self):
        cleanup_orphan_parts(core.STATE.receive_dir)
        return old_put(self)

    def handle_download(self):
        p = core.STATE.selected
        if not p or not p.exists() or not p.is_file():
            return old_download(self)
        try:
            size = p.stat().st_size
        except OSError:
            return old_download(self)
        if size != 0:
            return old_download(self)

        if self.headers.get("Range"):
            self.send_response(416)
            self.send_header("Content-Range", "bytes */0")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        tid = core.STATE.new_transfer("download", p.name, 0)
        try:
            self.send_response(200)
            headers = zero_byte_download_headers(
                p.name,
                core.mimetypes.guess_type(p.name)[0] or "application/octet-stream",
            )
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            core.STATE.update_transfer(tid, 0, "complete")
        except (BrokenPipeError, ConnectionResetError):
            core.STATE.update_transfer(tid, status="failed")
        except Exception:
            core.STATE.update_transfer(tid, status="failed")
            raise

    core.Handler.do_PUT = do_PUT
    core.Handler.handle_download = handle_download
    cleanup_orphan_parts(core.STATE.receive_dir)
    core.STATE._restart_hardening_installed = True
