from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import ssl
import stat
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath


REPO = "gillrajvir950-wq/deckyshare"
API_RELEASES = f"https://api.github.com/repos/{REPO}/releases"
USER_AGENT = "DeckyShare-Updater/1.1"
MAX_ASSET_BYTES = 50 * 1024 * 1024
MAX_UNPACKED_BYTES = 200 * 1024 * 1024
MAX_ZIP_ENTRIES = 2000
CHECK_CACHE_SECONDS = 300

# Decky Loader runs plugin backends from a frozen Python environment.  In that
# environment OpenSSL's compiled-in CA path can point inside Decky's temporary
# extraction directory instead of SteamOS' real trust store.  Prefer explicit
# system CA bundles, while keeping full certificate and hostname verification.
_CA_BUNDLE_CANDIDATES = (
    "/etc/ssl/certs/ca-certificates.crt",      # SteamOS / Arch / Debian
    "/etc/ssl/cert.pem",                      # OpenSSL / Alpine-style
    "/etc/pki/tls/certs/ca-bundle.crt",       # Fedora / RHEL-style
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    "/etc/ssl/ca-bundle.pem",
)


def _candidate_ca_bundles():
    seen = set()

    # Prefer the host OS trust store. Decky's frozen runtime can set Python's
    # defaults to a temporary extraction directory that disappears or is
    # incomplete after startup.
    for value in _CA_BUNDLE_CANDIDATES:
        if value not in seen:
            seen.add(value)
            yield value

    # Respect explicit overrides only after the real SteamOS trust store.
    for env_name in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        value = str(os.environ.get(env_name) or "").strip()
        if value and value not in seen:
            seen.add(value)
            yield value

    # Keep Python/OpenSSL's own reported cafile as a late fallback.  In Decky's
    # frozen runtime it may be stale, which is why the SteamOS paths come first.
    try:
        default_cafile = ssl.get_default_verify_paths().cafile
        if default_cafile and default_cafile not in seen:
            seen.add(default_cafile)
            yield default_cafile
    except Exception:
        pass


def _ssl_context():
    errors = []
    for value in _candidate_ca_bundles():
        try:
            path = Path(value)
            if path.is_file():
                return ssl.create_default_context(cafile=str(path))
        except Exception as exc:
            errors.append(f"{value}: {exc}")

    # Some distributions expose hashed certificates in a directory instead of
    # one bundle file.
    try:
        ca_dir = Path("/etc/ssl/certs")
        if ca_dir.is_dir():
            return ssl.create_default_context(capath=str(ca_dir))
    except Exception as exc:
        errors.append(f"/etc/ssl/certs: {exc}")

    # certifi is optional.  Use it only if Decky's Python environment happens to
    # provide it; DeckyShare does not depend on it.
    try:
        import certifi  # type: ignore

        cafile = str(certifi.where() or "")
        if cafile and Path(cafile).is_file():
            return ssl.create_default_context(cafile=cafile)
    except Exception as exc:
        errors.append(f"certifi: {exc}")

    # Never disable TLS verification.  A normal default context is preferable
    # to an insecure updater even if the host has a broken trust configuration.
    try:
        return ssl.create_default_context()
    except Exception as exc:
        detail = "; ".join(errors[-3:])
        raise UpdateError(
            "Could not initialize a verified TLS context"
            + (f" ({detail})" if detail else "")
        ) from exc


class UpdateError(RuntimeError):
    pass


_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def parse_version(value: str):
    text = str(value or "").strip()
    match = _VERSION_RE.match(text)
    if not match:
        raise ValueError(f"Invalid version: {value}")
    core = (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )
    pre = match.group("pre")
    if pre is None:
        return core, None
    parts = []
    for token in re.split(r"[.-]", pre):
        if token.isdigit():
            parts.append((0, int(token)))
            continue
        token_lower = token.lower()
        compact = re.match(r"^(alpha|beta|rc|pre)(\d+)$", token_lower)
        if compact:
            parts.append((1, compact.group(1)))
            parts.append((0, int(compact.group(2))))
        else:
            parts.append((1, token_lower))
    return core, tuple(parts)


def compare_versions(left: str, right: str) -> int:
    """SemVer-style comparison. Returns -1, 0, or 1."""
    lc, lp = parse_version(left)
    rc, rp = parse_version(right)
    if lc != rc:
        return -1 if lc < rc else 1
    if lp is None and rp is None:
        return 0
    if lp is None:
        return 1
    if rp is None:
        return -1
    for a, b in zip(lp, rp):
        if a == b:
            continue
        if a[0] != b[0]:
            return -1 if a[0] < b[0] else 1
        return -1 if a[1] < b[1] else 1
    if len(lp) == len(rp):
        return 0
    return -1 if len(lp) < len(rp) else 1


def normalize_tag(tag: str) -> str:
    text = str(tag or "").strip()
    return text[1:] if text.lower().startswith("v") else text


def read_package_version(plugin_dir: Path) -> str:
    package = plugin_dir / "package.json"
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
        version = str(data.get("version") or "").strip()
        parse_version(version)
        return version
    except Exception as exc:
        raise UpdateError(f"Could not read current DeckyShare version: {exc}") from exc


def _safe_release_notes(body: str, limit: int = 1400) -> str:
    text = str(body or "").replace("\r", "").strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _asset_sha256(asset: dict) -> str:
    digest = str(asset.get("digest") or "").strip().lower()
    if not digest.startswith("sha256:"):
        raise UpdateError("Release asset has no GitHub SHA-256 digest")
    value = digest.split(":", 1)[1]
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise UpdateError("Release asset SHA-256 digest is invalid")
    return value


def _validate_asset_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    expected_prefix = f"/{REPO}/releases/download/"
    if parsed.scheme != "https" or parsed.hostname != "github.com" or not parsed.path.startswith(expected_prefix):
        raise UpdateError("Release asset URL is not an approved DeckyShare GitHub release URL")


def _choose_asset(release: dict) -> dict:
    tag = normalize_tag(release.get("tag_name"))
    assets = list(release.get("assets") or [])
    preferred = f"DeckyShare-v{tag}.zip".lower()
    candidates = [a for a in assets if str(a.get("name") or "").lower() == preferred]
    if not candidates:
        candidates = [
            a
            for a in assets
            if str(a.get("name") or "").lower().startswith("deckyshare-")
            and str(a.get("name") or "").lower().endswith(".zip")
        ]
    if len(candidates) != 1:
        raise UpdateError("Release does not contain exactly one DeckyShare ZIP asset")
    asset = candidates[0]
    size = int(asset.get("size") or 0)
    if size <= 0 or size > MAX_ASSET_BYTES:
        raise UpdateError("Release asset size is invalid or too large")
    url = str(asset.get("browser_download_url") or "")
    _validate_asset_url(url)
    sha256 = _asset_sha256(asset)
    return {
        "name": str(asset.get("name") or ""),
        "url": url,
        "size": size,
        "sha256": sha256,
    }


def _urlopen_verified(req, timeout: float):
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_ssl_context())
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            raise UpdateError(
                "Secure GitHub connection could not verify its certificate. "
                "DeckyShare tried the SteamOS system CA trust store; check the "
                "Deck date/time and SteamOS CA certificates."
            ) from exc
        raise


def _http_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        },
    )
    with _urlopen_verified(req, timeout) as response:
        if int(getattr(response, "status", 200)) != 200:
            raise UpdateError(f"GitHub returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def _download(url: str, dest: Path, expected_size: int, timeout: float = 20.0):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    total = 0
    with _urlopen_verified(req, timeout) as response, dest.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ASSET_BYTES:
                raise UpdateError("Downloaded update exceeded the allowed size")
            out.write(chunk)
    if total != expected_size:
        raise UpdateError(f"Downloaded update size mismatch ({total} != {expected_size})")
    return total


def _zip_member_is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def validate_update_zip(archive: Path, release_version: str) -> Path:
    total = 0
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            infos = zf.infolist()
            if not infos or len(infos) > MAX_ZIP_ENTRIES:
                raise UpdateError("Update ZIP has an invalid number of files")
            for info in infos:
                name = str(info.filename or "").replace("\\", "/")
                pure = PurePosixPath(name)
                if not name or pure.is_absolute() or ".." in pure.parts:
                    raise UpdateError("Update ZIP contains an unsafe path")
                if not pure.parts or pure.parts[0] != "DeckyShare":
                    raise UpdateError("Update ZIP root must be DeckyShare/")
                if _zip_member_is_symlink(info):
                    raise UpdateError("Update ZIP may not contain symbolic links")
                total += int(info.file_size or 0)
                if total > MAX_UNPACKED_BYTES:
                    raise UpdateError("Update ZIP expands beyond the allowed size")

            required = {
                "DeckyShare/plugin.json",
                "DeckyShare/package.json",
                "DeckyShare/main.py",
                "DeckyShare/dist/index.js",
            }
            names = {str(i.filename).replace("\\", "/").rstrip("/") for i in infos}
            if required - names:
                raise UpdateError("Update ZIP is missing required DeckyShare files")

            plugin_meta = json.loads(zf.read("DeckyShare/plugin.json").decode("utf-8"))
            if plugin_meta.get("name") != "DeckyShare":
                raise UpdateError("Update ZIP plugin identity does not match DeckyShare")

            package = json.loads(zf.read("DeckyShare/package.json").decode("utf-8"))
            archive_version = str(package.get("version") or "").strip()
            if compare_versions(archive_version, release_version) != 0:
                raise UpdateError(
                    f"Update ZIP version {archive_version!r} does not match release {release_version!r}"
                )
    except zipfile.BadZipFile as exc:
        raise UpdateError("Downloaded update is not a valid ZIP") from exc
    return Path("DeckyShare")


def _validate_extracted_plugin(root: Path, release_version: str) -> None:
    if not root.is_dir():
        raise UpdateError("Extracted DeckyShare folder is missing")
    required = [root / "plugin.json", root / "package.json", root / "main.py", root / "dist" / "index.js"]
    if any(not p.is_file() for p in required):
        raise UpdateError("Extracted update is missing required files")
    try:
        plugin = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except Exception as exc:
        raise UpdateError(f"Extracted update metadata is invalid: {exc}") from exc
    if plugin.get("name") != "DeckyShare":
        raise UpdateError("Extracted update has the wrong plugin identity")
    if compare_versions(str(package.get("version") or ""), release_version) != 0:
        raise UpdateError("Extracted update version does not match the release")
    for py in root.rglob("*.py"):
        try:
            compile(py.read_text(encoding="utf-8"), str(py), "exec")
        except Exception as exc:
            raise UpdateError(f"Python syntax validation failed for {py.name}: {exc}") from exc
    if (root / "dist" / "index.js").stat().st_size < 256:
        raise UpdateError("DeckyShare frontend bundle is unexpectedly small")


class UpdateManager:
    def __init__(self, plugin_dir: Path, user_home: Path):
        self.plugin_dir = Path(plugin_dir).resolve()
        self.user_home = Path(user_home).resolve()
        self.data_dir = self.user_home / ".cache" / "DeckyShare" / "updater"
        self.backups_dir = self.data_dir / "backups"
        self.state_path = self.data_dir / "state.json"
        self._lock = threading.RLock()
        self._cached_check = None
        self._cached_at = 0.0

    @property
    def current_version(self) -> str:
        return read_package_version(self.plugin_dir)

    def _read_state(self) -> dict:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_state(self, data: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def state(self) -> dict:
        current = self.current_version
        state = self._read_state()
        backup = Path(state.get("backup_path") or "") if state.get("backup_path") else None
        rollback_available = bool(backup and backup.is_dir() and (backup / "plugin.json").is_file())
        return {
            "ok": True,
            "current": current,
            "rollback_available": rollback_available,
            "previous_version": state.get("previous_version") if rollback_available else None,
            "last_installed": state.get("last_installed"),
            "installed_at": state.get("installed_at"),
        }

    def _fetch_release(self, include_prerelease: bool = False) -> dict:
        releases = _http_json(f"{API_RELEASES}?per_page=12")
        if not isinstance(releases, list):
            raise UpdateError("GitHub returned invalid release data")
        for release in releases:
            if release.get("draft"):
                continue
            if release.get("prerelease") and not include_prerelease:
                continue
            tag = normalize_tag(release.get("tag_name"))
            try:
                parse_version(tag)
            except ValueError:
                continue
            asset = _choose_asset(release)
            return {
                "version": tag,
                "tag": str(release.get("tag_name") or ""),
                "name": str(release.get("name") or release.get("tag_name") or tag),
                "prerelease": bool(release.get("prerelease")),
                "published_at": release.get("published_at"),
                "html_url": release.get("html_url"),
                "notes": _safe_release_notes(release.get("body") or ""),
                "asset": asset,
            }
        raise UpdateError("No compatible DeckyShare release was found")

    def check(self, include_prerelease: bool = False, force: bool = False) -> dict:
        with self._lock:
            now = time.time()
            channel = bool(include_prerelease)
            if (
                not force
                and self._cached_check
                and self._cached_check.get("_channel") == channel
                and now - self._cached_at < CHECK_CACHE_SECONDS
            ):
                cached = dict(self._cached_check)
                cached.pop("_channel", None)
                cached.update(self.state())
                return cached

            current = self.current_version
            release = self._fetch_release(include_prerelease=include_prerelease)
            relation = compare_versions(current, release["version"])
            result = {
                "ok": True,
                "current": current,
                "latest": release["version"],
                "latest_tag": release["tag"],
                "latest_name": release["name"],
                "available": relation < 0,
                "ahead": relation > 0,
                "same": relation == 0,
                "prerelease": release["prerelease"],
                "published_at": release["published_at"],
                "release_url": release["html_url"],
                "notes": release["notes"],
                "asset_name": release["asset"]["name"],
                "asset_size": release["asset"]["size"],
                "sha256": release["asset"]["sha256"],
                "verified_digest": True,
            }
            result.update(self.state())
            cached = dict(result)
            cached["_channel"] = channel
            self._cached_check = cached
            self._cached_at = now
            return result

    def _prepare_backup(self, current_version: str) -> Path:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = self.backups_dir / f"DeckyShare-{current_version}-{stamp}-{uuid.uuid4().hex[:6]}"
        shutil.copytree(self.plugin_dir, backup, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        return backup

    def _extract_archive(self, archive: Path, release_version: str, stage_parent: Path) -> Path:
        validate_update_zip(archive, release_version)
        stage_parent.mkdir(parents=True, exist_ok=True)
        extract_dir = Path(tempfile.mkdtemp(prefix="extract-", dir=str(stage_parent)))
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(extract_dir)
        staged_plugin = extract_dir / "DeckyShare"
        _validate_extracted_plugin(staged_plugin, release_version)
        return staged_plugin

    def _atomic_swap(self, staged_plugin: Path, release_version: str) -> dict:
        current_version = self.current_version
        parent = self.plugin_dir.parent
        backup = self._prepare_backup(current_version)
        old_slot = parent / f".DeckyShare-old-{uuid.uuid4().hex}"
        swapped_old = False
        try:
            os.replace(self.plugin_dir, old_slot)
            swapped_old = True
            try:
                os.replace(staged_plugin, self.plugin_dir)
            except Exception:
                os.replace(old_slot, self.plugin_dir)
                swapped_old = False
                raise
            shutil.rmtree(old_slot, ignore_errors=True)
            swapped_old = False
            self._write_state(
                {
                    "previous_version": current_version,
                    "backup_path": str(backup),
                    "last_installed": release_version,
                    "installed_at": time.time(),
                }
            )
            self._cached_check = None
            return {
                "ok": True,
                "installed": release_version,
                "previous": current_version,
                "rollback_available": True,
                "message": "Update installed. Reload DeckyShare from Decky settings to start the new version.",
            }
        except Exception:
            if swapped_old and old_slot.exists() and not self.plugin_dir.exists():
                try:
                    os.replace(old_slot, self.plugin_dir)
                except Exception:
                    pass
            raise

    def install_archive(self, archive: Path, release_version: str, expected_sha256: str) -> dict:
        """Install a local ZIP after the same validation used for downloaded releases."""
        with self._lock:
            archive = Path(archive)
            expected = str(expected_sha256 or "").lower()
            if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
                raise UpdateError("Expected SHA-256 is invalid")
            actual = _sha256_file(archive)
            if actual != expected:
                raise UpdateError("Update SHA-256 verification failed")
            current = self.current_version
            if compare_versions(release_version, current) <= 0:
                raise UpdateError(f"Refusing to install non-newer version {release_version} over {current}")
            stage_parent = self.data_dir / "staging"
            staged = self._extract_archive(archive, release_version, stage_parent)
            try:
                return self._atomic_swap(staged, release_version)
            finally:
                shutil.rmtree(staged.parent, ignore_errors=True)

    def install_latest(self, expected_tag: str | None = None, include_prerelease: bool = False) -> dict:
        with self._lock:
            release = self._fetch_release(include_prerelease=include_prerelease)
            if expected_tag and str(expected_tag) != release["tag"]:
                raise UpdateError("Release changed since the update check. Check for updates again.")
            current = self.current_version
            if compare_versions(release["version"], current) <= 0:
                raise UpdateError("No newer DeckyShare release is available")

            asset = release["asset"]
            self.data_dir.mkdir(parents=True, exist_ok=True)
            download_dir = Path(tempfile.mkdtemp(prefix="download-", dir=str(self.data_dir)))
            archive = download_dir / asset["name"]
            try:
                _download(asset["url"], archive, asset["size"])
                actual = _sha256_file(archive)
                if actual != asset["sha256"]:
                    raise UpdateError("Downloaded update failed SHA-256 verification")
                stage_parent = self.data_dir / "staging"
                staged = self._extract_archive(archive, release["version"], stage_parent)
                try:
                    return self._atomic_swap(staged, release["version"])
                finally:
                    shutil.rmtree(staged.parent, ignore_errors=True)
            finally:
                shutil.rmtree(download_dir, ignore_errors=True)

    def rollback(self) -> dict:
        with self._lock:
            state = self._read_state()
            backup = Path(state.get("backup_path") or "") if state.get("backup_path") else None
            previous = str(state.get("previous_version") or "").strip()
            if not backup or not backup.is_dir() or not previous:
                raise UpdateError("No DeckyShare rollback backup is available")
            _validate_extracted_plugin(backup, previous)

            parent = self.plugin_dir.parent
            failed_slot = parent / f".DeckyShare-rollback-{uuid.uuid4().hex}"
            moved_current = False
            try:
                os.replace(self.plugin_dir, failed_slot)
                moved_current = True
                rollback_stage = Path(tempfile.mkdtemp(prefix="rollback-", dir=str(parent))) / "DeckyShare"
                shutil.copytree(backup, rollback_stage, symlinks=True)
                os.replace(rollback_stage, self.plugin_dir)
                shutil.rmtree(failed_slot, ignore_errors=True)
                moved_current = False
                state["backup_path"] = None
                state["previous_version"] = None
                state["last_installed"] = previous
                state["installed_at"] = time.time()
                self._write_state(state)
                self._cached_check = None
                return {
                    "ok": True,
                    "installed": previous,
                    "rollback_available": False,
                    "message": "Rollback restored. Reload DeckyShare from Decky settings.",
                }
            except Exception:
                if moved_current and failed_slot.exists() and not self.plugin_dir.exists():
                    try:
                        os.replace(failed_slot, self.plugin_dir)
                    except Exception:
                        pass
                raise
