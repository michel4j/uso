#!/bin/bash

PID_FILE="/var/run/gunicorn/gunicorn.pid"
if pgrep -F "$PID_FILE" >/dev/null; then
    exit 0
else
    exit 1
fi