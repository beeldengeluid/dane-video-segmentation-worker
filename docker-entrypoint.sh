#!/bin/sh

echo "Starting DANE video segmentation worker"

poetry run python worker.py "$@"

echo The worker crashed, tailing /dev/null for debugging

tail -f /dev/null
