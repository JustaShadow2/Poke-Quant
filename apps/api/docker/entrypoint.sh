#!/usr/bin/env sh
# Container entrypoint: wait for the DB, apply migrations, then start the API
# server IMMEDIATELY so the port opens fast (Render/PaaS port-scan requirement).
# The heavy demo bootstrap (synth -> train -> forecast -> phase2) runs in the
# BACKGROUND after the server is up, so the service becomes healthy right away
# and data populates over the next few minutes.
set -eu

echo "[entrypoint] applying migrations (waiting for database)..."
n=0
until pokequant db upgrade; do
  n=$((n + 1))
  if [ "$n" -ge 30 ]; then
    echo "[entrypoint] database not ready after $n attempts; giving up." >&2
    exit 1
  fi
  echo "[entrypoint]   db not ready yet, retry $n/30 ..."
  sleep 2
done

SENTINEL="${ARTIFACT_DIR:-/data/artifacts}/.bootstrapped"
BOOTSTRAP="${BOOTSTRAP:-1}"

DO_BOOT=0
if [ "$BOOTSTRAP" = "force" ]; then
  DO_BOOT=1
elif [ "$BOOTSTRAP" = "1" ] && [ ! -f "$SENTINEL" ]; then
  DO_BOOT=1
fi

# Bootstrap runs as a background job so it never blocks the port from opening.
run_bootstrap() {
  echo "[bootstrap] starting demo data generation (seed -> synth -> features -> train -> forecast -> phase2)..."
  pokequant seed
  pokequant synth --days 900
  pokequant features build
  for H in d30 d90 d180 d365; do
    pokequant train --horizon "$H"
    pokequant forecast run --horizon "$H"
  done
  # Vision CNN training only runs when the optional 'vision' extra (torch) is
  # installed. On memory-constrained hosts the Grade tab uses the heuristic scorer.
  if python -c "import torch, torchvision" >/dev/null 2>&1; then
    pokequant vision-train --epochs 5 --samples 800
  else
    echo "[bootstrap] torch not installed; skipping vision-train (heuristic grader active)."
  fi
  pokequant phase2
  mkdir -p "$(dirname "$SENTINEL")"
  touch "$SENTINEL"
  echo "[bootstrap] complete."
}

if [ "$DO_BOOT" = "1" ]; then
  echo "[entrypoint] launching bootstrap in the background..."
  run_bootstrap > /tmp/bootstrap.log 2>&1 &
else
  echo "[entrypoint] skipping bootstrap (BOOTSTRAP=$BOOTSTRAP, sentinel present=$( [ -f "$SENTINEL" ] && echo yes || echo no ))."
fi

# Render (and some PaaS) inject $PORT; default to 8000 for local/compose.
PORT="${PORT:-8000}"
echo "[entrypoint] starting API on :$PORT (serving immediately; bootstrap continues in background if running) ..."
exec pokequant serve --host 0.0.0.0 --port "$PORT"
