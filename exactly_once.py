import errno
import json
import os
import threading
import time
from pathlib import Path

from transfer_integrity import safe_upload_id, upload_part_path


_COMPLETED_TTL = 60 * 60
_STALE_SESSION_TTL = 24 * 60 * 60
_upload_locks = {}
_upload_locks_guard = threading.Lock()


def _upload_lock(upload_id):
    with _upload_locks_guard:
        lock = _upload_locks.get(upload_id)
        if lock is None:
            lock = threading.Lock()
            _upload_locks[upload_id] = lock
        return lock


def _drain(handler, length):
    remain = max(0, int(length or 0))
    while remain:
        chunk = handler.rfile.read(min(1024 * 1024, remain))
        if not chunk:
            break
        remain -= len(chunk)


def _rollback_part(part, offset):
    try:
        if part.exists():
            with part.open("r+b") as handle:
                handle.truncate(max(0, int(offset)))
        return True
    except OSError:
        return False


def _storage_error(error):
    """Map filesystem failures to stable HTTP/JSON responses."""
    if isinstance(error, OSError) and error.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", -1)):
        return 507, "storage_full", "Not enough free storage on Steam Deck"
    return 500, "write_failed", "Could not save upload on Steam Deck"


def _send_storage_error(handler, error, received):
    status, code, message = _storage_error(error)
    return handler.send_json({
        "error": message,
        "code": code,
        "received": max(0, int(received or 0)),
        "retryable": True,
    }, status)


def _clean_state(core):
    now = time.time()
    stale_parts = []
    with core.STATE.lock:
        completed = getattr(core.STATE, "completed_uploads", {})
        for upload_id, item in list(completed.items()):
            if now - item.get("completed_at", now) > _COMPLETED_TTL:
                completed.pop(upload_id, None)
        sessions = getattr(core.STATE, "upload_sessions", {})
        for upload_id, item in list(sessions.items()):
            if now - item.get("updated", now) > _STALE_SESSION_TTL:
                sessions.pop(upload_id, None)
                stale_parts.append(item.get("part"))
    for raw in stale_parts:
        try:
            if raw:
                Path(raw).unlink(missing_ok=True)
        except OSError:
            pass


def _replay_response(core, handler, record, length):
    _drain(handler, length)
    return handler.send_json({
        "received": record["total"],
        "complete": True,
        "name": record["name"],
        "verified": record.get("verified", False),
        "replayed": True,
    })


def _install_put(core):
    def do_PUT(self):
        u = core.urllib.parse.urlsplit(self.path)
        if not self.token_ok():
            self.send_error(403)
            return
        if u.path != "/upload":
            self.send_error(404)
            return

        q = core.urllib.parse.parse_qs(u.query)
        name = Path(q.get("name", ["upload.bin"])[0]).name
        try:
            upload_id = safe_upload_id(self.headers.get("X-DeckyShare-Upload-ID"))
            offset = core.parse_nonnegative_int(q.get("offset", ["0"])[0], "offset")
            total = core.parse_nonnegative_int(q.get("total", ["0"])[0], "total")
            length = core.parse_nonnegative_int(self.headers.get("Content-Length", "0"), "length")
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)

        target = (core.STATE.receive_dir / name).resolve()
        if core.STATE.receive_dir.resolve() not in target.parents:
            return self.send_json({"error": "Bad filename"}, 400)

        _clean_state(core)
        with _upload_lock(upload_id):
            with core.STATE.lock:
                completed = core.STATE.completed_uploads.get(upload_id)
                if completed:
                    if completed["original_name"] != name or completed["total"] != total:
                        _drain(self, length)
                        return self.send_json({"error": "Upload ID already belongs to another file"}, 409)
                    return _replay_response(core, self, completed, length)

                session = core.STATE.upload_sessions.get(upload_id)
                if session:
                    if session["name"] != name or session["total"] != total:
                        _drain(self, length)
                        return self.send_json({"error": "Upload ID already belongs to another file"}, 409)
                else:
                    part = upload_part_path(core.STATE.receive_dir, upload_id)
                    session = {
                        "name": name,
                        "total": total,
                        "part": str(part),
                        "tid": core.STATE.new_transfer("upload", name, total),
                        "updated": time.time(),
                    }
                    core.STATE.upload_sessions[upload_id] = session

            part = Path(session["part"])
            current = part.stat().st_size if part.exists() else 0
            try:
                core.validate_upload_window(offset, total, length, current)
            except ValueError as e:
                _drain(self, length)
                if str(e) == "Resume offset mismatch":
                    return self.send_json({"received": current, "resume": True}, 409)
                return self.send_json({"error": str(e), "received": current}, 400)

            tid = session["tid"]
            expected_crc = self.headers.get("X-DeckyShare-CRC32", "").strip().lower()
            if expected_crc and (len(expected_crc) != 8 or any(c not in "0123456789abcdef" for c in expected_crc)):
                _drain(self, length)
                return self.send_json({"error": "Bad checksum"}, 400)

            remain = length
            crc = 0
            chunk_start = current
            try:
                part.parent.mkdir(parents=True, exist_ok=True)
                with open(part, "ab", buffering=0) as f:
                    while remain:
                        chunk = self.rfile.read(min(4 * 1024 * 1024, remain))
                        if not chunk:
                            break
                        try:
                            f.write(chunk)
                        except OSError as e:
                            _rollback_part(part, chunk_start)
                            current = chunk_start
                            core.STATE.update_transfer(tid, current)
                            with core.STATE.lock:
                                active = core.STATE.upload_sessions.get(upload_id)
                                if active:
                                    active["updated"] = time.time()
                            _drain(self, remain - len(chunk))
                            return _send_storage_error(self, e, current)
                        crc = core.crc32_update(crc, chunk)
                        remain -= len(chunk)
                        current += len(chunk)
                        core.STATE.update_transfer(tid, current)
                    if remain:
                        f.truncate(chunk_start)
                        current = chunk_start
                        core.STATE.update_transfer(tid, current)
                        return self.send_json({"error": "Incomplete request body", "received": current}, 400)
                    actual_crc = core.crc32_value_hex(crc)
                    if expected_crc and actual_crc != expected_crc:
                        f.truncate(chunk_start)
                        current = chunk_start
                        core.STATE.update_transfer(tid, current)
                        return self.send_json({"received": current, "checksum_mismatch": True}, 422)

                complete = current == total
                saved_target = target
                if complete:
                    saved_target = core.unique_destination_path(target)
                    try:
                        if total == 0:
                            part.unlink(missing_ok=True)
                            saved_target.touch(exist_ok=False)
                        else:
                            os.replace(part, saved_target)
                    except OSError as e:
                        core.STATE.update_transfer(tid, current)
                        with core.STATE.lock:
                            active = core.STATE.upload_sessions.get(upload_id)
                            if active:
                                active["updated"] = time.time()
                        return _send_storage_error(self, e, current)
                    record = {
                        "original_name": name,
                        "name": saved_target.name,
                        "total": total,
                        "verified": bool(expected_crc),
                        "completed_at": time.time(),
                    }
                    with core.STATE.lock:
                        core.STATE.completed_uploads[upload_id] = record
                        core.STATE.upload_sessions.pop(upload_id, None)
                    core.STATE.update_transfer(tid, current, "complete")
                    item = core.STATE.record_received(saved_target)
                    core.notify_file_received(item)

                with core.STATE.lock:
                    active = core.STATE.upload_sessions.get(upload_id)
                    if active:
                        active["updated"] = time.time()
                return self.send_json({
                    "received": current,
                    "complete": complete,
                    "name": saved_target.name if complete else name,
                    "verified": bool(expected_crc),
                    "upload_id": upload_id,
                })
            except OSError as e:
                _rollback_part(part, chunk_start)
                core.STATE.update_transfer(tid, chunk_start)
                with core.STATE.lock:
                    active = core.STATE.upload_sessions.get(upload_id)
                    if active:
                        active["updated"] = time.time()
                return _send_storage_error(self, e, chunk_start)
            except Exception:
                core.STATE.update_transfer(tid, status="failed")
                raise

    core.Handler.do_PUT = do_PUT


def _install_post(core):
    old_post = core.Handler.do_POST

    def do_POST(self):
        u = core.urllib.parse.urlsplit(self.path)
        if u.path != "/api/cancel-upload":
            return old_post(self)
        if not self.token_ok():
            self.send_error(403)
            return

        try:
            n = core.parse_nonnegative_int(self.headers.get("Content-Length", "0"), "length")
            data = json.loads(self.rfile.read(n) or b"{}")
            upload_id = safe_upload_id(data.get("upload_id"))
            name = Path(data.get("name", "")).name
        except (ValueError, json.JSONDecodeError) as e:
            return self.send_json({"error": str(e)}, 400)
        if not name:
            return self.send_json({"error": "Missing filename"}, 400)

        _clean_state(core)
        with _upload_lock(upload_id):
            with core.STATE.lock:
                completed = core.STATE.completed_uploads.get(upload_id)
                session = core.STATE.upload_sessions.get(upload_id)
            if completed:
                return self.send_json({"ok": True, "already_complete": True, "name": completed["name"]})
            if session and (session["name"] != name):
                return self.send_json({"error": "Upload ID does not match filename"}, 409)

            part = upload_part_path(core.STATE.receive_dir, upload_id)
            try:
                part.unlink(missing_ok=True)
            except OSError as e:
                status, code, message = _storage_error(e)
                return self.send_json({"error": message, "code": code}, status)

            tid = session.get("tid") if session else None
            with core.STATE.lock:
                core.STATE.upload_sessions.pop(upload_id, None)
            if tid:
                core.STATE.update_transfer(tid, status="cancelled")
            return self.send_json({"ok": True, "cancelled": name, "upload_id": upload_id})

    core.Handler.do_POST = do_POST


def _wrap_html_page(original):
    def html_page(address):
        page = original(address)
        old_cancel = "async function cancelPartial(name){try{await api('/api/cancel-upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});}catch(e){}}"
        new_cancel = "async function cancelPartial(name,uploadId){try{await api('/api/cancel-upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,upload_id:uploadId})});}catch(e){}}"
        page = page.replace(old_cancel, new_cancel)
        old_start = "async function uploadOne(f,onProgress,onRetry){let chunk=16*1024*1024,off=0,lastName=f.name,retries=0,first=true;"
        new_start = "async function uploadOne(f,onProgress,onRetry){const uploadId=(globalThis.crypto&&crypto.randomUUID)?crypto.randomUUID():('ds_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,12));let chunk=16*1024*1024,off=0,lastName=f.name,retries=0,first=true;"
        page = page.replace(old_start, new_start)
        page = page.replace("'X-DeckyShare-CRC32':sum", "'X-DeckyShare-CRC32':sum,'X-DeckyShare-Upload-ID':uploadId")
        page = page.replace("cancelPartial(f.name)", "cancelPartial(f.name,uploadId)")
        if "X-DeckyShare-Upload-ID" not in page or "upload_id:uploadId" not in page:
            raise RuntimeError("DeckyShare upload-id UI patch did not apply")
        return page
    return html_page


def install(core):
    if getattr(core.STATE, "_exactly_once_installed", False):
        return
    with core.STATE.lock:
        core.STATE.upload_sessions = {}
        core.STATE.completed_uploads = {}
        core.STATE._exactly_once_installed = True
    _install_put(core)
    _install_post(core)
    core.html_page = _wrap_html_page(core.html_page)
