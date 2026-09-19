import json
import os
import urllib.request
import ssl
import io
import zipfile
import tempfile
from pathlib import Path

try:
    import decky
except ImportError:
    import decky_plugin as decky

PLUGIN_DIR = Path(getattr(decky, "DECKY_PLUGIN_DIR", Path(__file__).resolve().parent))
BASE = "https://raw.githubusercontent.com/gillrajvir950-wq/deckyshare/prototype/remote-demo-separate"
LOCAL_VERSION_FILE = PLUGIN_DIR / "local_version.txt"

def _read_local_version():
    try:
        return LOCAL_VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    except Exception:
        return "0.0.0"

def _ssl_context():
    candidates = [
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/ssl/cert.pem",
        "/etc/pki/tls/certs/ca-bundle.crt",
    ]
    for cafile in candidates:
        if os.path.isfile(cafile):
            return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()

def _get_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DeckyShareRemoteDemo"})
    with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as r:
        return r.read().decode("utf-8")

class Plugin:
    async def updater_status(self, *args, **kwargs):
        local = _read_local_version()
        try:
            manifest = json.loads(_get_text(BASE + "/update.json"))
            remote = str(manifest.get("version", "0.0.0"))
            return {"ok": True, "local": local, "remote": remote, "available": local != remote}
        except Exception as e:
            decky.logger.exception("Remote Demo update check failed")
            return {"ok": False, "local": local, "error": str(e)}

    async def updater_package(self, *args, **kwargs):
        try:
            manifest = json.loads(_get_text(BASE + "/update.json"))
            version = str(manifest["version"])
            files = manifest.get("files", ["dist/index.js", "main.py", "plugin.json"])
            tmpdir = Path(tempfile.gettempdir()) / "deckyshare-remote-updater"
            tmpdir.mkdir(parents=True, exist_ok=True)
            artifact = tmpdir / ("DeckyShareRemoteDemo-" + version + ".zip")
            with zipfile.ZipFile(artifact, "w", zipfile.ZIP_DEFLATED) as z:
                for rel in files:
                    if rel.startswith("/") or ".." in Path(rel).parts:
                        raise ValueError("Unsafe update path")
                    z.writestr("DeckyShareRemoteDemo/" + rel, _get_text(BASE + "/" + rel))
                z.writestr("DeckyShareRemoteDemo/local_version.txt", version + "\n")
            return {"ok": True, "version": version, "artifact": str(artifact)}
        except Exception as e:
            decky.logger.exception("Remote Demo update package failed")
            return {"ok": False, "error": str(e)}

    async def _main(self):
        decky.logger.info("DeckyShare Remote Demo updater backend loaded")

    async def _unload(self):
        pass
