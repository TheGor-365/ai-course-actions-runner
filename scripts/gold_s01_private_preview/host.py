from __future__ import annotations

from .common import *
from .contracts import validate_profile, require_private_execution_host


_BROWSER_VERSION = re.compile(r"\b(?:Chromium|Google Chrome|Chrome for Testing)\b", re.IGNORECASE)
_BROWSER_BINARY_NAMES = {"chrome", "chromium", "chromium-browser"}


def _first_line(argv: Sequence[str]) -> str | None:
    try:
        proc = subprocess.run(list(argv), text=True, capture_output=True, check=False, timeout=15)
    except Exception:
        return None
    lines = (proc.stdout or proc.stderr).splitlines()
    return lines[0][:300] if lines else None


def _tool_identity(command: str) -> dict[str, Any] | None:
    resolved = shutil.which(command)
    if not resolved:
        return None
    launcher = Path(resolved)
    path = launcher.resolve()
    return {
        "command": command,
        "version": _first_line([str(launcher), "--version"]),
        "executable_sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "filename": path.name,
    }


def _snap_browser_binary(command: str) -> tuple[Path, str] | None:
    package = "chromium" if command in {"chromium", "chromium-browser"} else command
    current = Path("/snap") / package / "current"
    if not current.exists():
        return None
    try:
        revision = current.resolve().name
    except OSError:
        return None
    candidates: list[Path] = []
    for name in sorted(_BROWSER_BINARY_NAMES):
        try:
            for path in current.rglob(name):
                if path.is_file() and os.access(path, os.X_OK):
                    try:
                        if path.stat().st_size >= 1_000_000:
                            candidates.append(path)
                    except OSError:
                        continue
        except OSError:
            continue
    if not candidates:
        return None
    binary = max(candidates, key=lambda item: item.stat().st_size)
    return binary, revision


def _browser_identity(candidates: Sequence[str]) -> dict[str, Any] | None:
    for command in candidates:
        resolved = shutil.which(command)
        if not resolved:
            continue
        launcher = Path(resolved)
        version = _first_line([str(launcher), "--version"])
        if not version or not _BROWSER_VERSION.search(version):
            continue
        resolved_launcher = launcher.resolve()
        packaging = "native"
        binary = resolved_launcher
        snap_revision: str | None = None
        if resolved_launcher.name == "snap":
            discovered = _snap_browser_binary(command)
            if discovered is None:
                continue
            binary, snap_revision = discovered
            packaging = "snap"
        if binary.name == "snap" or binary.name not in _BROWSER_BINARY_NAMES:
            continue
        try:
            size = binary.stat().st_size
        except OSError:
            continue
        if size < 1_000_000:
            continue
        identity: dict[str, Any] = {
            "command": command,
            "selected_candidate": command,
            "version": version,
            "executable_sha256": sha256_file(binary),
            "size_bytes": size,
            "filename": binary.name,
            "packaging": packaging,
            "launcher_filename": launcher.name,
            "launcher_sha256": sha256_file(resolved_launcher),
        }
        if snap_revision is not None:
            identity["snap_revision"] = snap_revision
        return identity
    return None


def _font_identity(alias: str) -> dict[str, Any] | None:
    fc_match = shutil.which("fc-match")
    if not fc_match:
        return None
    proc = subprocess.run(
        [fc_match, "-f", "%{family[0]}|%{style[0]}|%{file}\n", alias],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    line = proc.stdout.strip().splitlines()[0] if proc.returncode == 0 and proc.stdout.strip() else ""
    parts = line.split("|", 2)
    if len(parts) != 3:
        return None
    family, style, file_value = parts
    path = Path(file_value).resolve()
    if not path.is_file():
        return None
    return {
        "alias": alias,
        "family": family,
        "style": style,
        "filename": path.name,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _resolved_versions(lock_path: Path, expected: Mapping[str, str]) -> dict[str, str]:
    packages = load_json(lock_path).get("packages")
    if not isinstance(packages, Mapping):
        raise PreviewError("PACKAGE_LOCK_INVALID", "packages")
    result: dict[str, str] = {}
    for package, version in expected.items():
        item = packages.get(f"node_modules/{package}")
        if not isinstance(item, Mapping) or item.get("version") != version:
            raise PreviewError("PACKAGE_VERSION_LOCK_MISMATCH", f"{package}:{version}")
        result[package] = str(item["version"])
    return result


def _package_lock_identity(profile: Mapping[str, Any], production_dir: Path, production_sha: str) -> dict[str, Any]:
    validate_git_checkout(production_dir, production_sha)
    lock = profile["runtime_lock"]
    path = validate_blob(production_dir, lock["package_lock_path"], lock["package_lock_git_blob_sha"], lock["package_lock_sha256"])
    if path.stat().st_size != lock["package_lock_size_bytes"]:
        raise PreviewError("PACKAGE_LOCK_SIZE_MISMATCH", lock["package_lock_path"])
    return {
        "git_blob_sha": lock["package_lock_git_blob_sha"],
        "sha256": lock["package_lock_sha256"],
        "size_bytes": path.stat().st_size,
        "lockfile_version": load_json(path).get("lockfileVersion"),
        "resolved_versions": _resolved_versions(path, lock["resolved_versions"]),
    }


def host_probe(profile: Mapping[str, Any], private_root: Path, *, production_dir: Path | None = None, production_sha: str | None = None) -> dict[str, Any]:
    profile = validate_profile(profile)
    policy = profile["host_lock_policy"]
    exists = private_root.exists()
    receipt: dict[str, Any] = {
        "schema_version": HOST_RECEIPT_SCHEMA,
        "profile_id": profile["profile_id"],
        "platform": platform.system().lower(),
        "machine": platform.machine(),
        "github_actions": os.environ.get("GITHUB_ACTIONS", "").lower() == "true",
        "private_execution_allowed": os.environ.get("GITHUB_ACTIONS", "").lower() != "true",
        "tools": {},
        "browser": None,
        "fonts": [],
        "package_lock": None,
        "private_root": {
            "exists": exists,
            "writable": os.access(private_root, os.W_OK) if exists else False,
            "mode": stat.S_IMODE(private_root.stat().st_mode) if exists else None,
            "free_bytes": shutil.disk_usage(private_root).free if exists else None,
        },
        "minimum_free_bytes": profile["minimum_free_bytes"],
        "blockers": [],
        "install_plan": [],
        "media_created": False,
        "public_artifacts_created": False,
        "private_content_public_exposure": False,
        "raw_private_paths_in_receipt": False,
        "no_fake_green": True,
        "observed_at": utc_now(),
    }
    if receipt["github_actions"]:
        receipt["blockers"].append("PUBLIC_WORKFLOW_PRIVATE_EXECUTION_FORBIDDEN")
    if not exists:
        receipt["blockers"].append("PRIVATE_ARTIFACT_ROOT_MISSING")
    else:
        root = receipt["private_root"]
        if not root["writable"]:
            receipt["blockers"].append("PRIVATE_ARTIFACT_ROOT_NOT_WRITABLE")
        if int(root["free_bytes"] or 0) < profile["minimum_free_bytes"]:
            receipt["blockers"].append("INSUFFICIENT_PRIVATE_DISK_SPACE")
        if root["mode"] & 0o077:
            receipt["blockers"].append("PRIVATE_ARTIFACT_ROOT_PERMISSIONS_TOO_OPEN")
    for command in policy["required_commands"]:
        identity = _tool_identity(command)
        receipt["tools"][command] = identity
        if identity is None or not identity.get("version"):
            receipt["blockers"].append(f"{command.upper()}_MISSING")
    receipt["browser"] = _browser_identity(policy["browser_candidates"])
    if receipt["browser"] is None:
        receipt["blockers"].append("CHROMIUM_BROWSER_EXACT_IDENTITY_MISSING")
    for alias in policy["required_font_aliases"]:
        identity = _font_identity(alias)
        if identity is None:
            receipt["blockers"].append("FONT_ALIAS_UNRESOLVED:" + alias)
        else:
            receipt["fonts"].append(identity)
    if production_dir is None or production_sha is None:
        receipt["blockers"].append("EXACT_PRODUCTION_CHECKOUT_REQUIRED")
    else:
        try:
            receipt["package_lock"] = _package_lock_identity(profile, production_dir, production_sha)
        except PreviewError as exc:
            receipt["blockers"].append(exc.code)
    ffmpeg = receipt["tools"].get("ffmpeg") or {}
    ffprobe = receipt["tools"].get("ffprobe") or {}
    if profile["runtime_lock"]["ffmpeg_version"] not in str(ffmpeg.get("version") or ""):
        receipt["blockers"].append("FFMPEG_VERSION_LOCK_MISMATCH")
    if profile["runtime_lock"]["ffprobe_version"] not in str(ffprobe.get("version") or ""):
        receipt["blockers"].append("FFPROBE_VERSION_LOCK_MISMATCH")
    receipt["font_manifest_sha256"] = hashlib.sha256(canonical_bytes(receipt["fonts"])).hexdigest()
    lock_payload = {key: receipt[key] for key in ("platform", "machine", "tools", "browser", "fonts", "font_manifest_sha256", "package_lock")}
    receipt["lock_fingerprint"] = hashlib.sha256(canonical_bytes(lock_payload)).hexdigest()
    receipt["install_plan"] = [
        {"action": "verify_exact_host_lock_receipt", "automatic": False},
        {"action": "verify_package_lock", "sha256": profile["runtime_lock"]["package_lock_sha256"], "automatic": False},
        {"action": "npm_ci", "authorized": False, "automatic": False},
    ]
    receipt["blockers"] = sorted(set(receipt["blockers"]))
    receipt["host_lock_status"] = "READY" if not receipt["blockers"] else "BLOCKED"
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def _probe_namespace(root: Path, class_name: str, payload_size: int) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    payload = secrets.token_bytes(payload_size)
    digest = hashlib.sha256(payload).hexdigest()
    target = root / f".gold-s01-probe-{digest[:16]}.bin"
    if target.exists():
        raise PreviewError("STORE_PROBE_COLLISION", class_name)
    with target.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    write_ok = target.stat().st_size == payload_size
    observed = target.read_bytes()
    read_ok = observed == payload and hashlib.sha256(observed).hexdigest() == digest
    target.unlink()
    delete_ok = not target.exists()
    st = root.stat()
    return {
        "store_class": class_name,
        "write_status": "PASS" if write_ok else "FAIL",
        "read_status": "PASS" if read_ok else "FAIL",
        "delete_status": "PASS" if delete_ok else "FAIL",
        "payload_sha256": digest,
        "size_bytes": payload_size,
        "root_mode": stat.S_IMODE(st.st_mode),
        "filesystem_device_hash": hashlib.sha256(str(st.st_dev).encode("ascii")).hexdigest(),
        "free_bytes": shutil.disk_usage(root).free,
    }


def store_probe(profile: Mapping[str, Any], primary_root: Path, replica_root: Path) -> dict[str, Any]:
    require_private_execution_host()
    profile = validate_profile(profile)
    if primary_root.resolve() == replica_root.resolve():
        raise PreviewError("STORE_NAMESPACES_NOT_DISTINCT", "primary/replica")
    size = profile["host_lock_policy"]["store_probe_bytes"]
    primary = _probe_namespace(primary_root, DEFAULT_PRIMARY_CLASS, size)
    replica = _probe_namespace(replica_root, DEFAULT_REPLICA_CLASS, size)
    statuses = [primary["write_status"], primary["read_status"], primary["delete_status"], replica["write_status"], replica["read_status"], replica["delete_status"]]
    receipt: dict[str, Any] = {
        "schema_version": STORE_PROBE_RECEIPT_SCHEMA,
        "profile_id": profile["profile_id"],
        "probe_status": "PASS" if set(statuses) == {"PASS"} else "FAIL",
        "primary": primary,
        "replica": replica,
        "distinct_namespaces": True,
        "distinct_filesystem_devices": primary["filesystem_device_hash"] != replica["filesystem_device_hash"],
        "raw_private_paths_in_receipt": False,
        "media_created": False,
        "public_artifacts_created": False,
        "private_content_public_exposure": False,
        "no_fake_green": True,
        "observed_at": utc_now(),
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def validate_host_locks(receipt: Mapping[str, Any], profile: Mapping[str, Any], expected_hash: str | None = None) -> None:
    profile = validate_profile(profile)
    require_fields(receipt, {"schema_version", "profile_id", "tools", "browser", "fonts", "package_lock", "font_manifest_sha256", "lock_fingerprint", "blockers", "host_lock_status", "receipt_hash", "no_fake_green"}, "host_receipt")
    if receipt["schema_version"] != HOST_RECEIPT_SCHEMA or receipt["profile_id"] != profile["profile_id"]:
        raise PreviewError("HOST_RECEIPT_SCHEMA_INVALID", "schema/profile")
    validate_embedded_hash(receipt)
    if expected_hash is not None and receipt["receipt_hash"] != expected_hash:
        raise PreviewError("HOST_RECEIPT_BINDING_MISMATCH", expected_hash)
    if receipt["host_lock_status"] != "READY" or receipt.get("blockers"):
        raise PreviewError("HOST_LOCKS_NOT_READY", ",".join(receipt.get("blockers") or []))
    for command in profile["host_lock_policy"]["required_commands"]:
        identity = receipt["tools"].get(command)
        if not isinstance(identity, Mapping):
            raise PreviewError("HOST_TOOL_IDENTITY_MISSING", command)
        require_hex(identity.get("executable_sha256"), 64, f"host.tools.{command}.executable_sha256")
    browser = receipt.get("browser")
    if not isinstance(browser, Mapping):
        raise PreviewError("HOST_BROWSER_IDENTITY_MISSING", "browser")
    require_hex(browser.get("executable_sha256"), 64, "host.browser.executable_sha256")
    require_hex(browser.get("launcher_sha256"), 64, "host.browser.launcher_sha256")
    if not _BROWSER_VERSION.search(str(browser.get("version") or "")):
        raise PreviewError("HOST_BROWSER_VERSION_INVALID", str(browser.get("version")))
    if browser.get("filename") == "snap" or browser.get("filename") not in _BROWSER_BINARY_NAMES:
        raise PreviewError("HOST_BROWSER_BINARY_INVALID", str(browser.get("filename")))
    if int(browser.get("size_bytes") or 0) < 1_000_000:
        raise PreviewError("HOST_BROWSER_BINARY_INVALID", str(browser.get("size_bytes")))
    if browser.get("packaging") not in {"native", "snap"}:
        raise PreviewError("HOST_BROWSER_PACKAGING_INVALID", str(browser.get("packaging")))
    if browser.get("packaging") == "snap" and not str(browser.get("snap_revision") or "").strip():
        raise PreviewError("HOST_BROWSER_SNAP_REVISION_MISSING", "snap_revision")
    aliases = {item.get("alias") for item in receipt.get("fonts", []) if isinstance(item, Mapping)}
    if aliases != set(profile["host_lock_policy"]["required_font_aliases"]):
        raise PreviewError("HOST_FONT_ALIAS_SET_MISMATCH", ",".join(sorted(str(x) for x in aliases)))
    for item in receipt["fonts"]:
        require_hex(item.get("sha256"), 64, "host.font.sha256")
    package = receipt.get("package_lock")
    if not isinstance(package, Mapping) or package.get("sha256") != profile["runtime_lock"]["package_lock_sha256"] or package.get("git_blob_sha") != profile["runtime_lock"]["package_lock_git_blob_sha"]:
        raise PreviewError("HOST_PACKAGE_LOCK_MISMATCH", "package_lock")
    if package.get("resolved_versions") != profile["runtime_lock"]["resolved_versions"]:
        raise PreviewError("HOST_REMOTION_LOCK_MISMATCH", "resolved_versions")


def validate_store_probe_receipt(receipt: Mapping[str, Any], profile: Mapping[str, Any], expected_hash: str | None = None) -> None:
    profile = validate_profile(profile)
    require_fields(receipt, {"schema_version", "profile_id", "probe_status", "primary", "replica", "distinct_namespaces", "receipt_hash", "no_fake_green"}, "store_probe_receipt")
    if receipt["schema_version"] != STORE_PROBE_RECEIPT_SCHEMA or receipt["profile_id"] != profile["profile_id"]:
        raise PreviewError("STORE_PROBE_SCHEMA_INVALID", "schema/profile")
    validate_embedded_hash(receipt)
    if expected_hash is not None and receipt["receipt_hash"] != expected_hash:
        raise PreviewError("STORE_PROBE_BINDING_MISMATCH", expected_hash)
    if receipt["probe_status"] != "PASS" or receipt["distinct_namespaces"] is not True:
        raise PreviewError("STORE_PROBE_NOT_GREEN", str(receipt.get("probe_status")))
    for key, expected_class in (("primary", DEFAULT_PRIMARY_CLASS), ("replica", DEFAULT_REPLICA_CLASS)):
        item = receipt.get(key)
        if not isinstance(item, Mapping) or item.get("store_class") != expected_class:
            raise PreviewError("STORE_PROBE_CLASS_MISMATCH", key)
        if {item.get("write_status"), item.get("read_status"), item.get("delete_status")} != {"PASS"}:
            raise PreviewError("STORE_PROBE_NOT_GREEN", key)
        require_hex(item.get("payload_sha256"), 64, f"store_probe.{key}.payload_sha256")
