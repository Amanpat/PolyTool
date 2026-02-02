#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"
python tools/guard/pre_commit_guard.py
python tools/guard/pre_push_guard.py
