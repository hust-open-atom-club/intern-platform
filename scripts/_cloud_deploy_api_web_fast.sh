#!/usr/bin/env bash
# 热更 API + Web（保留 .env / certs / 数据卷），使用 build cache
set -euo pipefail

TS="$(date +%Y%m%d%H%M%S)"
ZIP="/opt/intern-platform-deploy-new.zip"
TARGET="/opt/intern-platform"
NEW="/opt/intern-platform.new-fast"

test -f "$ZIP"
test -f "${TARGET}/.env"

rm -rf "$NEW"
mkdir -p "$NEW"
python3 - <<'PY'
import zipfile
from pathlib import Path
zf = zipfile.ZipFile("/opt/intern-platform-deploy-new.zip")
zf.extractall("/opt/intern-platform.new-fast")
root = Path("/opt/intern-platform.new-fast")
assert (root / "src" / "intern_platform" / "config.py").is_file()
assert (root / "apps" / "web" / "package.json").is_file()
print("extracted_ok")
PY

rsync -a --delete \
  --exclude '.env' \
  --exclude 'certs' \
  --exclude 'data' \
  --exclude '.git' \
  "${NEW}/" "${TARGET}/"
rm -rf "$NEW"
cd "$TARGET"
cp -a .env "/opt/intern-platform.env.bak.${TS}"

docker compose build api web
docker compose up -d --force-recreate api web
docker compose ps

for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1/api/v1/health >/tmp/h.json; then
    cat /tmp/h.json; echo
    break
  fi
  sleep 2
done

docker exec intern-platform-api-1 python -c 'from intern_platform.config import DATA_ROOT; from intern_platform.api.routes.uploads import UPLOAD_ROOT; assert str(DATA_ROOT)=="/app/data"; assert str(UPLOAD_ROOT)=="/app/data/uploads"; print("data_root_ok")'
echo "deploy_api_web_fast_ok bak=/opt/intern-platform.env.bak.${TS}"
