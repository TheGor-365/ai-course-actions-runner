#!/usr/bin/env bash
set -euo pipefail

PRODUCTION_REPO="TheGor-365/ai-course-production-system"
PRODUCTION_BRANCH="integration/gold2-wave3-s01-product-v1"
PRODUCTION_SHA="761b63ff806e07d1ea77ab2d716bab1998db7502"
W1F04_DB="ai_course_factory_w1f04"
POSTGRES_CONTAINER="ai-course-w1f04-postgres"
POSTGRES_IMAGE="postgres:16.11"
POSTGRES_HOST_PORT="15432"
TEMPORAL_CONTAINER="ai-course-w1f04-temporal"
TEMPORAL_IMAGE="temporalio/temporal:1.8.1"
TEMPORAL_ADDRESS="127.0.0.1:7233"
VALIDATOR_PATH="04_validators/factory_orchestration/wave3_s01/run_wave3_repair_owner_gate.py"
PRODUCTION_DIR="${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}/_production_checkout"
WORK_ROOT="${RUNNER_TEMP:-/tmp}/wave3_s01_runtime_validation"
VENV_DIR="$WORK_ROOT/venv"

fail() {
  echo "result=FAIL"
  echo "error_class=$1"
  echo "error_code=$2"
  exit "${3:-1}"
}

phase() {
  echo "PHASE=$1"
}

cleanup() {
  docker rm -f "$TEMPORAL_CONTAINER" >/dev/null 2>&1 || true
  docker rm -f "$POSTGRES_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ ! "$PRODUCTION_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  fail policy invalid_bound_production_sha 2
fi
command -v git >/dev/null || fail runtime git_missing 2
command -v docker >/dev/null || fail runtime docker_missing 2
command -v python3 >/dev/null || fail runtime python3_missing 2

phase AUTHORITY_CHECK
if [[ ! -d "$PRODUCTION_DIR/.git" ]]; then
  fail infrastructure production_checkout_missing 2
fi
cd "$PRODUCTION_DIR"
CHECKED_OUT_SHA="$(git rev-parse HEAD)"
if [[ "$CHECKED_OUT_SHA" != "$PRODUCTION_SHA" ]]; then
  echo "expected_production_sha=$PRODUCTION_SHA"
  echo "observed_local_head=$CHECKED_OUT_SHA"
  fail authority local_head_sha_mismatch 2
fi
if ! REMOTE_BRANCH_LINE="$(git ls-remote --exit-code origin "refs/heads/${PRODUCTION_BRANCH}")"; then
  fail infrastructure production_remote_branch_lookup_failed 2
fi
REMOTE_BRANCH_SHA="$(awk 'NR==1 {print $1}' <<<"$REMOTE_BRANCH_LINE")"
if [[ -z "$REMOTE_BRANCH_SHA" ]]; then
  fail infrastructure production_remote_branch_lookup_empty 2
fi
if [[ "$REMOTE_BRANCH_SHA" != "$PRODUCTION_SHA" ]]; then
  echo "expected_production_sha=$PRODUCTION_SHA"
  echo "observed_remote_branch_sha=$REMOTE_BRANCH_SHA"
  fail authority remote_branch_head_sha_mismatch 2
fi
[[ -f "$VALIDATOR_PATH" ]] || fail authority wave3_validator_missing 2

echo "production_repo=$PRODUCTION_REPO"
echo "production_branch=$PRODUCTION_BRANCH"
echo "production_sha=$PRODUCTION_SHA"
echo "production_local_head_verified=true"
echo "production_remote_branch_head_verified=true"
echo "validator_path=$VALIDATOR_PATH"
echo "production_validator_modified=false"

phase PYTHON_ENV
sudo apt-get update -y >/dev/null
sudo apt-get install -y postgresql-client-16 python3-venv >/dev/null
python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --disable-pip-version-check -r \
  "$PRODUCTION_DIR/11_tools/factory_orchestration/requirements.txt" >/dev/null

python - <<'PY'
import importlib.metadata
expected = {
    "psycopg": "3.3.4",
    "psycopg-binary": "3.3.4",
    "temporalio": "1.30.0",
}
for package, version in expected.items():
    actual = importlib.metadata.version(package)
    if actual != version:
        raise SystemExit(f"dependency_version_drift:{package}:{actual}:{version}")
print("python_dependency_versions=PASS")
PY

phase POSTGRES_START
docker rm -f "$POSTGRES_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$POSTGRES_CONTAINER" \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB="$W1F04_DB" \
  -p "${POSTGRES_HOST_PORT}:5432" \
  "$POSTGRES_IMAGE" >/dev/null

export PGHOST="127.0.0.1"
export PGPORT="$POSTGRES_HOST_PORT"
export PGUSER="postgres"
export PGPASSWORD="postgres"
export W1F04_DB
for _ in $(seq 1 60); do
  if pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$W1F04_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$W1F04_DB" >/dev/null \
  || fail runtime postgres_not_ready 3
psql -X -Atc 'SELECT current_database();' "$W1F04_DB" | grep -Fx "$W1F04_DB" >/dev/null \
  || fail runtime postgres_database_mismatch 3
POSTGRES_VERSION="$(psql -X -Atc 'SHOW server_version;' "$W1F04_DB")"
[[ "$POSTGRES_VERSION" == 16.11* ]] || fail runtime postgres_version_drift 3
echo "postgres_version=$POSTGRES_VERSION"
echo "postgres_database=$W1F04_DB"

phase TEMPORAL_START
docker rm -f "$TEMPORAL_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$TEMPORAL_CONTAINER" \
  -p 7233:7233 \
  "$TEMPORAL_IMAGE" \
  server start-dev --ip 0.0.0.0 >/dev/null

for _ in $(seq 1 90); do
  if docker exec "$TEMPORAL_CONTAINER" temporal operator cluster health \
      --address 127.0.0.1:7233 2>/dev/null | grep -q 'SERVING'; then
    break
  fi
  sleep 1
done
TEMPORAL_HEALTH="$(docker exec "$TEMPORAL_CONTAINER" temporal operator cluster health --address 127.0.0.1:7233 2>&1)"
echo "$TEMPORAL_HEALTH"
grep -q 'SERVING' <<<"$TEMPORAL_HEALTH" || fail runtime temporal_not_serving 3
TEMPORAL_VERSION="$(docker exec "$TEMPORAL_CONTAINER" temporal --version 2>&1)"
echo "$TEMPORAL_VERSION"
grep -Fq 'temporal version 1.8.1 (Server 1.31.2,' <<<"$TEMPORAL_VERSION" \
  || fail runtime temporal_runtime_version_drift 3

export W1F04_TEMPORAL_ADDRESS="$TEMPORAL_ADDRESS"
export W1F04_TEMPORAL_CONTAINER="$TEMPORAL_CONTAINER"
export PYTHONPATH="$PRODUCTION_DIR/11_tools"

phase WAVE3_RUNTIME_GATE
cd "$PRODUCTION_DIR"
python "$VALIDATOR_PATH"
