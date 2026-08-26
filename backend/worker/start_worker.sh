#!/bin/bash
# Start Celery worker + beat in the same container.
# The beat scheduler fires auto_generate_optimal_pct every 15 minutes.
set -e

echo "Starting Celery worker..."
celery -A worker.tasks worker --loglevel=info --concurrency=1 &
WORKER_PID=$!

echo "Starting Celery beat..."
celery -A worker.tasks beat --loglevel=info &
BEAT_PID=$!

echo "Worker PID=$WORKER_PID Beat PID=$BEAT_PID"

# Trap signals and forward to both children
trap "kill $WORKER_PID $BEAT_PID 2>/dev/null; exit 0" SIGTERM SIGINT

# Wait for any child to exit — if either dies, kill the other and exit
wait -n
EXIT_CODE=$?
echo "A process exited with code $EXIT_CODE, shutting down..."
kill $WORKER_PID $BEAT_PID 2>/dev/null
wait
exit $EXIT_CODE