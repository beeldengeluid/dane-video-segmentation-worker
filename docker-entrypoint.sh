#!/bin/sh

# echo "Starting virtual env and DANE video segmentation worker"

python3.10 work_it_locally.py
# python3.10 worker.py

echo the worker crashed, tailing /dev/null for debugging

tail -f /dev/null
