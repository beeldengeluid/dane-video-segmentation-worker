#!/bin/sh

echo "Starting DANE video segmentation worker"

python3.10 worker.py "$@"

# echo The worker crashed, tailing /dev/null for debugging

# tail -f /dev/null
