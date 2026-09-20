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


class _UploadCancelled(Exception):
    pass


def _upload_lock(upload_id):
    with _upload_locks_guard:
        lock = _upload_locks.get(upload_id)
        if lock is None:
            lock = threading.Lock()
            _upload_locks[upload_id] = lock
        return lock


def _retire_transfer(core, tid):
    """Hide a disconnected request while keeping its resumable upload session."""
    with core.STATE.lock:
        core.STATE.transfers.pop(tid, None)


def _supersede_prior_streams(core, upload_id, client_key, name):
    """Stop an older browser stream when the same device retries the same file."""
    stale_parts = []
    with core.STATE.lock:
        sessions = getattr(core.STATE, "upload_sessions", {})
        for old_id, old in list(sessions.items()):
            if old_id == upload_id:
                continue
            if old.get("client_key") != client_key or old.get("name") != name:
                continue
            old["cancel_event"].set()
            tid = old.get("tid")
            if tid in core.STATE.transfers:
                core.STATE.update_transfer(tid, status="cancelled")
            else:
                sessions.pop(old_id, None)
                stale_parts.append(old.get("part"))
    for raw in stale_parts:
        try:
            if raw:
                Path(raw).unlink(missing_ok=True)
        except OSError:
            pass


def _read_upload_chunk(handler, remain, fast_mode):
    size = min(4 * 1024 * 1024 if fast_mode else 4 * 1024 * 1024, remain)
    if fast_mode and hasattr(handler.rfile, "read1"):
        # BufferedReader.read(n) waits for the whole large request. read1() takes
        # currently available socket data, keeping mobile uploads and cancel
        # signals responsive without reducing the TCP receive window.
        return handler.rfile.read1(size)
    return handler.rfile.read(size)


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
        request_started = time.perf_counter()
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
        client_key = str(self.client_address[0]) if self.client_address else ""
        _supersede_prior_streams(core, upload_id, client_key, name)
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
                        "client_key": client_key,
                        "cancel_event": threading.Event(),
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

            with core.STATE.lock:
                tid = session["tid"]
                if tid not in core.STATE.transfers:
                    tid = core.STATE.new_transfer("upload", name, total, current)
                    session["tid"] = tid
            cancel_event = session["cancel_event"]
            expected_crc = self.headers.get("X-DeckyShare-CRC32", "").strip().lower()
            fast_mode = self.headers.get("X-DeckyShare-Fast", "") == "1"
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
                        if cancel_event.is_set():
                            raise _UploadCancelled()
                        chunk = _read_upload_chunk(self, remain, fast_mode)
                        if cancel_event.is_set():
                            raise _UploadCancelled()
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
                        if expected_crc:
                            crc = core.crc32_update(crc, chunk)
                        remain -= len(chunk)
                        current += len(chunk)
                        core.STATE.update_transfer(tid, current)
                    if cancel_event.is_set():
                        raise _UploadCancelled()
                    if remain:
                        if not fast_mode:
                            f.truncate(chunk_start)
                            current = chunk_start
                        with core.STATE.lock:
                            active = core.STATE.upload_sessions.get(upload_id)
                            if active:
                                active["updated"] = time.time()
                        _retire_transfer(core, tid)
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
                    "server_ms": round((time.perf_counter() - request_started) * 1000, 1),
                })
            except _UploadCancelled:
                _rollback_part(part, chunk_start)
                try:
                    part.unlink(missing_ok=True)
                except OSError:
                    pass
                with core.STATE.lock:
                    if core.STATE.upload_sessions.get(upload_id) is session:
                        core.STATE.upload_sessions.pop(upload_id, None)
                core.STATE.update_transfer(tid, chunk_start, "cancelled")
                try:
                    return self.send_json({"cancelled": True, "received": chunk_start, "upload_id": upload_id})
                except OSError:
                    return None
            except (BrokenPipeError, ConnectionResetError):
                # Fast mode intentionally keeps every byte already accepted by the
                # Deck. Safari pause/background/network interruption can then resume
                # from this exact checkpoint instead of replaying the whole request.
                if fast_mode:
                    current = part.stat().st_size if part.exists() else chunk_start
                    with core.STATE.lock:
                        active = core.STATE.upload_sessions.get(upload_id)
                        if active:
                            active["updated"] = time.time()
                    _retire_transfer(core, tid)
                    return None
                _rollback_part(part, chunk_start)
                _retire_transfer(core, tid)
                return None
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


def _install_get(core):
    old_get = core.Handler.do_GET

    def do_GET(self):
        u = core.urllib.parse.urlsplit(self.path)
        if u.path != "/api/upload-status":
            return old_get(self)
        if not self.token_ok():
            self.send_error(403)
            return

        q = core.urllib.parse.parse_qs(u.query)
        try:
            upload_id = safe_upload_id(q.get("upload_id", [""])[0])
            name = Path(q.get("name", [""])[0]).name
            total = core.parse_nonnegative_int(q.get("total", ["0"])[0], "total")
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)
        if not name:
            return self.send_json({"error": "Missing filename"}, 400)

        _clean_state(core)
        with core.STATE.lock:
            completed = core.STATE.completed_uploads.get(upload_id)
            session = core.STATE.upload_sessions.get(upload_id)
        if completed:
            if completed["original_name"] != name or completed["total"] != total:
                return self.send_json({"error": "Upload ID already belongs to another file"}, 409)
            return self.send_json({
                "received": total,
                "complete": True,
                "name": completed["name"],
                "verified": completed.get("verified", False),
            })
        if session:
            if session["name"] != name or session["total"] != total:
                return self.send_json({"error": "Upload ID already belongs to another file"}, 409)
            part = Path(session["part"])
            received = part.stat().st_size if part.exists() else 0
            return self.send_json({
                "received": min(received, total),
                "complete": False,
                "name": name,
            })
        return self.send_json({"received": 0, "complete": False, "name": name})

    core.Handler.do_GET = do_GET


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
        with core.STATE.lock:
            completed = core.STATE.completed_uploads.get(upload_id)
            session = core.STATE.upload_sessions.get(upload_id)
        if completed:
            return self.send_json({"ok": True, "already_complete": True, "name": completed["name"]})
        if session and (session["name"] != name):
            return self.send_json({"error": "Upload ID does not match filename"}, 409)

        part = upload_part_path(core.STATE.receive_dir, upload_id)
        if session:
            session["cancel_event"].set()
            core.STATE.update_transfer(session["tid"], status="cancelled")
            return self.send_json({"ok": True, "cancelled": name, "upload_id": upload_id, "cleanup_pending": True})

        try:
            part.unlink(missing_ok=True)
        except OSError as e:
            status, code, message = _storage_error(e)
            return self.send_json({"error": message, "code": code}, status)

        return self.send_json({"ok": True, "cancelled": name, "upload_id": upload_id})

    core.Handler.do_POST = do_POST


def _wrap_html_page(original):
    def html_page(address):
        page = original(address)
        if "X-DeckyShare-Upload-ID" not in page or "upload_id:uploadId" not in page or "X-DeckyShare-Fast" not in page:
            raise RuntimeError("DeckyShare fast upload UI is missing reliability markers")
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
    _install_get(core)
    _install_post(core)
    core.html_page = _wrap_html_page(core.html_page)
