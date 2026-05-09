#!/usr/bin/env sh

set -x
set -e

run_experiment() {
  uv run --frozen python "attic/experiments/$1"
}

run_experiment pid_tracking.py
run_experiment error_reporting.py
run_experiment latency.py
run_experiment text_monitor_demo.py
run_experiment async_run.py
run_experiment cmd_trace_examples.py
