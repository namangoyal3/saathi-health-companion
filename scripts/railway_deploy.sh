#!/usr/bin/env bash
# Railway deploy script — creates the project, provisions Postgres + Redis,
# imports every key from local .env, deploys, seeds personas, and sets
# the Telegram webhook.
#
# Run from the repo root of the day3-ivr-samsung worktree:
#   bash scripts/railway_deploy.sh
#
# Safe to re-run: `railway link` is idempotent; `variables set` overwrites;
# `alembic upgrade head` and `seed_personas.py` are both idempotent by design.

set -eu
set -o pipefail

PROJECT_NAME="${PROJECT_NAME:-saathi-health-companion}"
ENV_FILE="${ENV_FILE:-.env}"

if ! command -v railway >/dev/null 2>&1; then
  echo "❌ railway CLI not found. Install: npm i -g @railway/cli"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ $ENV_FILE not found — run this from the repo root."
  exit 1
fi

# echo "=== 1. unlink any prior project binding ==="
# railway unlink --yes 2>/dev/null || true

# echo ""
# echo "=== 2. create or link project: $PROJECT_NAME ==="
# railway link --project "$PROJECT_NAME" || railway init --name "$PROJECT_NAME" --workspace "neuralnextgen's Projects"

echo ""
echo "=== 3. provision Postgres + Redis (idempotent if already present) ==="
railway add --database postgres || true
railway add --database redis    || true

echo ""
echo "=== 3.5 link service ==="
railway service link "$PROJECT_NAME" || true

echo ""
echo "=== 4. import env vars from $ENV_FILE (skipping DATABASE_URL and REDIS_URL) ==="
# Read each KEY=VALUE, skip blank/comments/DB/Redis (Railway plugins provide those)
while IFS= read -r line || [ -n "$line" ]; do
  # strip leading/trailing whitespace
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  # skip blanks and comments
  case "$line" in ''|\#*) continue ;; esac
  # must look like KEY=VALUE
  case "$line" in *=*) : ;; *) continue ;; esac
  key="${line%%=*}"
  val="${line#*=}"
  if [ -z "$val" ]; then
    continue
  fi
  # skip DATABASE_URL / REDIS_URL — Railway's managed plugins provide them
  # case "$key" in DATABASE_URL|REDIS_URL) continue ;; esac
  echo "  → setting $key"
  railway variables --skip-deploys --set "$line" >/dev/null
done < "$ENV_FILE"

echo ""
# echo "=== 5. explicit refs to Postgres + Redis managed URLs ==="
# railway variables --skip-deploys --set 'DATABASE_URL=${{Postgres.DATABASE_URL}}' >/dev/null || \
#   railway variables --skip-deploys --set 'DATABASE_URL=${{Postgres.DATABASE_PUBLIC_URL}}' >/dev/null || true
# railway variables --skip-deploys --set 'REDIS_URL=${{Redis.REDIS_URL}}' >/dev/null || true

echo ""
echo "=== 6. deploy ==="
railway up --detach

echo ""
echo "=== 7. tail logs for 30s so we can see migration + boot ==="
( railway logs --deployment 2>&1 | head -60 ) & LOG_PID=$!
sleep 30
kill "$LOG_PID" 2>/dev/null || true

echo ""
echo "=== 8. seed personas (idempotent) ==="
railway run -- uv run python scripts/seed_personas.py || echo "⚠️  seed failed — can retry manually"

echo ""
echo "=== 9. show the public URL ==="
URL=$(railway domain 2>/dev/null | head -1)
echo ""
echo "──────────────────────────────────────────────────────────────"
echo "  🎉 saath is live at: $URL"
echo ""
echo "  admin workspace:   $URL/admin"
echo "  priya chat:        $URL/priya"
echo "  lakshmi chat:      $URL/"
echo "  watch simulator:   $URL/vitals-simulator"
echo "  health:            $URL/health"
echo "  api docs:          $URL/docs"
echo "──────────────────────────────────────────────────────────────"
echo ""
echo "Next: set the Telegram webhook (if you want alerts):"
# shellcheck disable=SC2016
echo '  TOKEN=$(grep ^TELEGRAM_BOT_TOKEN .env | cut -d= -f2-)'
# shellcheck disable=SC2016
echo '  curl -X POST "https://api.telegram.org/bot${TOKEN}/setWebhook" \\'
echo "    -d \"url=${URL}/telegram/\${TOKEN}\""
