#!/usr/bin/env bash
# 仅热更 API（含 DATA_ROOT 修复），用 build cache 加速；保留 web / certs / .env
set -euo pipefail

TS="$(date +%Y%m%d%H%M%S)"
ZIP="/opt/intern-platform-deploy-new.zip"
TARGET="/opt/intern-platform"
NEW="/opt/intern-platform.new-api"

test -f "$ZIP"
test -f "${TARGET}/.env"

rm -rf "$NEW"
mkdir -p "$NEW"
python3 - <<'PY'
import zipfile
from pathlib import Path
zf = zipfile.ZipFile("/opt/intern-platform-deploy-new.zip")
zf.extractall("/opt/intern-platform.new-api")
root = Path("/opt/intern-platform.new-api")
assert (root / "src" / "intern_platform" / "config.py").is_file()
assert (root / "Dockerfile.api").is_file()
print("extracted_ok")
PY

# 同步代码到现网目录（保留 .env / certs / data 外的运行态）
rsync -a --delete \
  --exclude '.env' \
  --exclude 'certs' \
  --exclude 'data' \
  --exclude '.git' \
  "${NEW}/" "${TARGET}/"

rm -rf "$NEW"
cd "$TARGET"
cp -a .env "/opt/intern-platform.env.bak.${TS}"

# 确保卷内 uploads 目录存在
docker exec intern-platform-api-1 mkdir -p /app/data/uploads || true

docker compose build api
docker compose up -d --no-deps --force-recreate api
docker compose ps

sleep 2
docker exec intern-platform-api-1 python - <<'PY'
from intern_platform.config import PROJECT_ROOT, DATA_ROOT
from intern_platform.api.routes.uploads import UPLOAD_ROOT
print("PROJECT_ROOT", PROJECT_ROOT)
print("DATA_ROOT", DATA_ROOT)
print("UPLOAD_ROOT", UPLOAD_ROOT)
assert str(DATA_ROOT) == "/app/data", DATA_ROOT
assert str(UPLOAD_ROOT) == "/app/data/uploads", UPLOAD_ROOT
assert UPLOAD_ROOT.exists()
print("data_root_ok")
PY

curl -sS "http://127.0.0.1/api/v1/health"
echo
echo "deploy_api_fast_ok bak=/opt/intern-platform.env.bak.${TS}"
