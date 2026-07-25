from __future__ import annotations

from .common import *
from .contracts import validate_profile


def _version(command: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        proc = subprocess.run([path, "--version"], text=True, capture_output=True, check=False, timeout=10)
        line = (proc.stdout or proc.stderr).splitlines()
        return line[0][:240] if line else None
    except Exception:
        return None


def _font_inventory(limit: int = 256) -> list[dict[str, Any]]:
    roots = [Path("/usr/share/fonts"), Path.home() / ".local/share/fonts"]
    rows: list[dict[str, Any]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if len(rows) >= limit:
                return rows
            if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".woff", ".woff2"}:
                rows.append({"name": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    return rows


def host_probe(profile: Mapping[str, Any], private_root: Path, *, authorize_store_probe: bool = False) -> dict[str, Any]:
    profile = validate_profile(profile)
    lock = profile["runtime_lock"]
    receipt: dict[str, Any] = {
        "schema_version": HOST_RECEIPT_SCHEMA,
        "profile_id": profile["profile_id"],
        "platform": platform.system().lower(),
        "machine": platform.machine(),
        "github_actions": os.environ.get("GITHUB_ACTIONS", "").lower() == "true",
        "private_execution_allowed": os.environ.get("GITHUB_ACTIONS", "").lower() != "true",
        "versions": {name: _version(name) for name in ("python3", "node", "npm", "ffmpeg", "ffprobe", "chromium", "chromium-browser", "google-chrome")},
        "font_inventory": _font_inventory(),
        "store_probe_authorized": authorize_store_probe,
        "primary_probe": "NOT_RUN",
        "replica_probe": "NOT_RUN",
        "minimum_free_bytes": profile["minimum_free_bytes"],
        "free_bytes": None,
        "root_exists": private_root.exists(),
        "root_writable": os.access(private_root, os.W_OK) if private_root.exists() else False,
        "blockers": [],
        "install_plan": [],
        "media_created": False,
        "public_artifacts_created": False,
        "private_content_public_exposure": False,
        "no_fake_green": True,
        "observed_at": utc_now(),
    }
    if receipt["github_actions"]:
        receipt["blockers"].append("PUBLIC_WORKFLOW_PRIVATE_EXECUTION_FORBIDDEN")
    if not private_root.exists():
        receipt["blockers"].append("PRIVATE_ARTIFACT_ROOT_MISSING")
    else:
        usage = shutil.disk_usage(private_root)
        receipt["free_bytes"] = usage.free
        if usage.free < profile["minimum_free_bytes"]:
            receipt["blockers"].append("INSUFFICIENT_PRIVATE_DISK_SPACE")
        if not receipt["root_writable"]:
            receipt["blockers"].append("PRIVATE_ARTIFACT_ROOT_NOT_WRITABLE")
    for command in ("node", "npm", "ffmpeg", "ffprobe"):
        if receipt["versions"][command] is None:
            receipt["blockers"].append(f"{command.upper()}_MISSING")
    for field, blocker in (("node_version", "NODE_VERSION_LOCK_UNPUBLISHED"), ("npm_version", "NPM_VERSION_LOCK_UNPUBLISHED"), ("chromium_version", "CHROMIUM_VERSION_LOCK_UNPUBLISHED"), ("chromium_sha256", "CHROMIUM_SHA_LOCK_UNPUBLISHED"), ("font_manifest_sha256", "FONT_LOCK_UNPUBLISHED")):
        if lock.get(field) is None:
            receipt["blockers"].append(blocker)
    receipt["install_plan"] = [
        {"action": "publish_exact_node_npm_browser_font_locks", "automatic": False},
        {"action": "verify_package_lock", "path": lock["package_lock_path"], "sha256": lock["package_lock_sha256"], "automatic": False},
        {"action": "npm_ci", "command": lock["install_command"], "authorized": False},
    ]
    if authorize_store_probe and private_root.exists() and receipt["root_writable"]:
        for class_name, key in ((DEFAULT_PRIMARY_CLASS, "primary_probe"), (DEFAULT_REPLICA_CLASS, "replica_probe")):
            root = private_root / ("gold_s01_primary_v1" if key == "primary_probe" else "gold_s01_replica_v1") / ".probe"
            root.mkdir(parents=True, exist_ok=True)
            os.chmod(root.parent, 0o700)
            token = secrets.token_bytes(64)
            probe = root / (hashlib.sha256(token).hexdigest() + ".bin")
            probe.write_bytes(token)
            ok = probe.read_bytes() == token
            probe.unlink()
            root.rmdir()
            receipt[key] = "PASS" if ok else "FAIL"
            if not ok:
                receipt["blockers"].append(class_name + "_PROBE_FAILED")
    receipt["font_manifest_sha256"] = hashlib.sha256(canonical_bytes(receipt["font_inventory"])).hexdigest()
    receipt["host_lock_status"] = "READY" if not receipt["blockers"] else "BLOCKED"
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def validate_host_locks(receipt: Mapping[str, Any], profile: Mapping[str, Any]) -> None:
    lock = profile["runtime_lock"]
    versions = receipt["versions"]
    comparisons = (
        ("node_version", "node", "NODE_VERSION_LOCK_MISMATCH"),
        ("npm_version", "npm", "NPM_VERSION_LOCK_MISMATCH"),
        ("chromium_version", "chromium", "CHROMIUM_VERSION_LOCK_MISMATCH"),
    )
    for lock_key, command, blocker in comparisons:
        expected = lock.get(lock_key)
        if expected is not None and expected not in str(versions.get(command) or versions.get("chromium-browser") or versions.get("google-chrome") or ""):
            raise PreviewError(blocker, str(expected))
    for lock_key, command, blocker in (("ffmpeg_version", "ffmpeg", "FFMPEG_VERSION_LOCK_MISMATCH"), ("ffprobe_version", "ffprobe", "FFPROBE_VERSION_LOCK_MISMATCH")):
        expected = lock.get(lock_key)
        if expected and expected not in str(versions.get(command) or ""):
            raise PreviewError(blocker, str(expected))
    expected_font = lock.get("font_manifest_sha256")
    if expected_font is not None and receipt.get("font_manifest_sha256") != expected_font:
        raise PreviewError("FONT_LOCK_MISMATCH", str(expected_font))
