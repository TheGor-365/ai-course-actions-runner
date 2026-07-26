from __future__ import annotations

from .common import *


def initial_state(request: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema_version": STATION_RECEIPT_SCHEMA, "request_id": request["request_id"], "input_fingerprint": request["input_fingerprint"], "profile_id": profile["profile_id"], "stations": {}, "failure_evidence": [], "resume_token_hash": None, "completed": False, "no_fake_green": True}


def run_state_machine(request: Mapping[str, Any], profile: Mapping[str, Any], state_path: Path, station_runner: Callable[[str], Mapping[str, Any]], *, resume_token: str | None = None, inject_failure_after_station: str | None = None) -> dict[str, Any]:
    state = load_json(state_path) if state_path.exists() else initial_state(request, profile)
    if state["input_fingerprint"] != request["input_fingerprint"]:
        raise PreviewError("STATE_FINGERPRINT_CONFLICT", "input fingerprint")
    if state.get("resume_token_hash"):
        if not resume_token or not hmac.compare_digest(state["resume_token_hash"], hashlib.sha256(resume_token.encode()).hexdigest()):
            raise PreviewError("RESUME_TOKEN_MISMATCH", "resume token required")
    max_retries = profile["max_station_retries"]
    for station in profile["stations"]:
        existing = state["stations"].get(station)
        if existing and existing.get("status") == "GREEN" and existing.get("input_fingerprint") == request["input_fingerprint"]:
            continue
        attempts = 1 + sum(1 for item in state["failure_evidence"] if item["station"] == station)
        if attempts > max_retries:
            raise PreviewError("STATION_RETRY_LIMIT", station)
        try:
            evidence = dict(station_runner(station))
            if evidence.get("status") != "GREEN":
                raise PreviewError("STATION_NOT_GREEN", station)
            record = {"station": station, "status": "GREEN", "input_fingerprint": request["input_fingerprint"], "evidence_hash": hashlib.sha256(canonical_bytes(evidence)).hexdigest(), "completed_at": utc_now()}
            state["stations"][station] = record
            atomic_json(state_path, state)
            if inject_failure_after_station == station and station != profile["stations"][-1]:
                token = secrets.token_hex(32)
                state["resume_token_hash"] = hashlib.sha256(token.encode()).hexdigest()
                failure = {"station": station, "attempt": attempts, "failure_class": "INJECTED_RETRYABLE_INFRASTRUCTURE_FAILURE", "input_fingerprint": request["input_fingerprint"], "evidence_hash": record["evidence_hash"], "recorded_at": utc_now()}
                state["failure_evidence"].append(failure)
                atomic_json(state_path, state)
                raise RetryablePreviewError(station, token)
        except RetryablePreviewError:
            raise
        except PreviewError as exc:
            failure = {"station": station, "attempt": attempts, "failure_class": exc.code, "input_fingerprint": request["input_fingerprint"], "recorded_at": utc_now()}
            state["failure_evidence"].append(failure)
            atomic_json(state_path, state)
            raise
    state["resume_token_hash"] = None
    state["completed"] = True
    state["receipt_hash"] = canonical_hash(state)
    atomic_json(state_path, state)
    return state
