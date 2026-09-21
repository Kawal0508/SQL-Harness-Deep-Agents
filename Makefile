# Local development commands. On Windows without make, use ./dev instead.
#
#   make install   virtualenv, Python deps, npm deps
#   make db        build Database/health.db from the Synthea CSVs
#   make build     compile the frontend bundle into Frontend/dist
#   make up        build, then run both services; Ctrl-C stops both
#   make check     read-only self-check, needs no API key
#   make clean     remove the bundle and node_modules

# The venv layout differs by platform, and git-bash on Windows still has
# Scripts/, so probe rather than branch on uname.
PY := $(shell [ -x .venv/Scripts/python.exe ] && echo .venv/Scripts/python.exe || echo .venv/bin/python)

.DEFAULT_GOAL := help
.PHONY: help install db build up check clean

help:
	@sed -n 's/^#   //p' Makefile

install:
	python -m venv .venv
	$(PY) -m pip install -r requirements.txt
	npm --prefix Frontend install

db:
	$(PY) Database/load.py

build:
	npm --prefix Frontend run build

check:
	$(PY) Backend/tools.py

up: build
	@[ -f Database/health.db ] || { echo "No Database/health.db. Run: make db"; exit 1; }
	@echo "agent  http://localhost:8000"
	@echo "admin  http://localhost:8001"
# The trap matters: without it Ctrl-C leaves the admin service orphaned on
# 8001, and the next run fails to bind.
	@$(PY) -m uvicorn admin:app --app-dir Backend --port 8001 & 	 trap 'kill %1 2>/dev/null' EXIT; 	 $(PY) -m uvicorn api:app --app-dir Backend --port 8000

clean:
	rm -rf Frontend/dist Frontend/node_modules
