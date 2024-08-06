#!/bin/sh

echo "Starting DANE video segmentation worker"

python worker.py "$@"
