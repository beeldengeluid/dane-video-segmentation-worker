#!/bin/sh

echo "Starting DANE video segmentation worker"

poetry run python worker.py "$@"
