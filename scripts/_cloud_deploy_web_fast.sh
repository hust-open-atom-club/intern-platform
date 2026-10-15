#!/usr/bin/env bash
# 仅热更 Web（nginx 静态站），保留 .env / certs / 数据卷与 API 容器
set -euo pipefail

TS="$(date +%Y%m%d%H%M%S)"
ZIP="/opt/intern-platform-deploy-new.zip"
TARGET="/opt/intern-platform"
NEW="/opt/intern-platform.new-web"

test -f "$ZIP"
test -f "${TARGET}/.env"

rm -rf "$NEW"
mkdir -p "$NEW"
python3 - <<'PY'
import zipfile
from pathlib import Path
zf = zipfile.ZipFile("/opt/intern-platform-deploy-new.zip")
zf.extractall("/opt/intern-platform.new-web")
root = Path("/opt/intern-platform.new-web")
assert (root / "apps" / "web" / "package.json").is_file()
print("extracted_ok")
PY

rsync -a \
  --exclude '.env' \
  --exclude 'certs' \
  --exclude 'data' \
  --exclude '.git' \
  "${NEW}/" "${TARGET}/"
rm -rf "$NEW"
cd "$TARGET"

docker compose build web
docker compose up -d --no-deps --force-recreate web
docker compose ps

for i in $(seq 1 20); do
  if curl -fsS -o /dev/null http://127.0.0.1/; then
    echo "web_ok"
    break
  fi
  sleep 2
done

docker exec intern-platform-web-1 sh -c 'ls -la "/usr/share/nginx/html/templates/" | head -20; grep -l 申请实习 /usr/share/nginx/html/assets/*.js | head -1'
echo "deploy_web_fast_ok bak_ts=${TS}"
