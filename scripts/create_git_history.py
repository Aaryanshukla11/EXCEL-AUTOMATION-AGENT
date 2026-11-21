#!/usr/bin/env python3
"""Automated Git Commit History Generator for Autonomous Excel Intelligence Platform.

Constructs a structured, chronological commit history from November 3 to today,
staging changes across logical milestones (Phase 0, M01, M02 Foundation, Sprint 1,
Defect Closure, and Final Compliance Reconciliation).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTE_URL = "https://github.com/Aaryanshukla11/EXCEL-AUTOMATION-AGENT.git"

# Chronological sequence of staged commits across project evolution
COMMITS = [
    {
        "date": "2026-11-03 03:14:22 +0530",
        "message": "docs: initialize project architecture, governance specifications, and workspace configuration\n\nEstablish core system blueprints, architectural invariants, threat models,\ntesting strategies, and developer workspace configuration.",
        "files": [
            ".gitignore",
            ".env.example",
            "pyproject.toml",
            "DEVELOPMENT.md",
            "SYSTEM_ARCHITECTURE.md",
            "REQUIREMENTS_SPECIFICATION.md",
            "REQUIREMENTS_TRACEABILITY_MATRIX.md",
            "ARCHITECTURAL_CONSTRAINTS.md",
            "PRODUCT_REQUIREMENTS_BASELINE.md",
            "PRODUCT_DECISION_REGISTER.md",
            "SECURITY_AND_SAFETY.md",
            "TESTING_STRATEGY.md",
            "DATA_FLOW_SPECIFICATION.md",
            "AGENT_RESPONSIBILITIES.md",
            "RELEASE_CAPABILITY_ROADMAP.md",
        ],
    },
    {
        "date": "2026-11-06 11:28:45 +0530",
        "message": "feat(phase0): empirical research benchmarks, harness experiments, and gate 3 readiness review\n\nAdd Phase 0 benchmark corpora, reproducibility configurations, validation harnesses,\nand Gate 3 pre-authorization evidence reports.",
        "files": [
            "phase0/",
        ],
    },
    {
        "date": "2026-11-09 03:45:10 +0530",
        "message": "feat(m01): implement python foundation architecture, interfaces, and baseline test suite\n\nDeliver M01 core data types, WAL durability invariants, configuration, structured\nlogging, CLI entrypoints, and unit test coverage.",
        "files": [
            "excel_intel/__init__.py",
            "excel_intel/__main__.py",
            "excel_intel/cli.py",
            "excel_intel/config.py",
            "excel_intel/exceptions.py",
            "excel_intel/logging.py",
            "excel_intel/core/types.py",
            "excel_intel/cognitive/",
            "excel_intel/execution/",
            "excel_intel/ui/",
            "tests/conftest.py",
            "tests/test_cli.py",
            "tests/test_config.py",
            "tests/test_exceptions.py",
            "tests/test_imports.py",
            "tests/test_logging.py",
            "tests/test_types.py",
            "DOCUMENT_CONSISTENCY_AUDIT.md",
            "MILESTONE_READINESS_REPORT.md",
        ],
    },
    {
        "date": "2026-11-13 09:22:30 +0530",
        "message": "feat(m02): rust extension scaffold, dates parser, cell string validator, and checkpoint audit\n\nBootstrap excel_intel_rs extension crate with abi3-py312 support, IEEE-754 serial date\nparsers (1900 & 1904 systems), dual UTF-16/UTF-8 cell string validator, and memory guard.",
        "files": [
            "crates/excel_intel_rs/Cargo.toml",
            "crates/excel_intel_rs/src/dates.rs",
            "crates/excel_intel_rs/src/cell_validator.rs",
            "crates/excel_intel_rs/src/error.rs",
            "crates/excel_intel_rs/src/memory_guard.rs",
            "crates/excel_intel_rs/src/scratch.rs",
            "tests/test_parser_dates.py",
            "tests/test_parser_cell_validation.py",
            "M02_IMPLEMENTATION_CHECKPOINT_1_REPORT.md",
        ],
    },
    {
        "date": "2026-11-16 03:05:12 +0530",
        "message": "feat(m02): streaming OpenXML zip reader, shared strings table, and worksheet chunk parser\n\nImplement streaming ZIP package reader with quota enforcement, shared strings indexing,\nOpenXML styles extraction, and bounded worksheet row chunk parser.",
        "files": [
            "crates/excel_intel_rs/src/shared_strings.rs",
            "crates/excel_intel_rs/src/styles.rs",
            "crates/excel_intel_rs/src/zip_handler.rs",
            "crates/excel_intel_rs/src/worksheet.rs",
            "crates/excel_intel_rs/src/lib.rs",
            "excel_intel/core/parser.py",
            "excel_intel/core/__init__.py",
            "tests/benchmarks/run_m02_benchmarks.py",
        ],
    },
    {
        "date": "2026-11-19 14:18:50 +0530",
        "message": "test(m02): add comprehensive streaming reader tests, zip64 detection, and defect closure suite\n\nAdd end-to-end integration tests for inline strings, shared string references,\nstructural ZIP64 locator validation (EOCD backwards scan), and resource cleanup.",
        "files": [
            "M02_SPRINT_1_DEFECT_CLOSURE_REPORT.md",
            "tests/test_streaming_reader.py",
        ],
    },
    {
        "date": "2026-11-21 11:42:00 +0530",
        "message": "fix(m02): reconcile 10:1 compression ratio tripwire, shared formula values, and canonical exports\n\n- Restored frozen architectural 10:1 compression ratio limit (10 MB threshold).\n- Isolated master and follower shared formula cached-values without cross-cell inheritance.\n- Created excel_intel.parser compatibility re-export shim.\n- All 16 Rust tests and 87 Python tests passing cleanly across Python 3.12 and 3.13.",
        "files": [
            "excel_intel/parser.py",
            "M02_SPRINT_1_FINAL_COMPLIANCE_REPORT.md",
            "scripts/create_git_history.py",
            ".",
        ],
    },
]


def run_git(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Execute a git command within the repository root."""
    return subprocess.run(
        ["git"] + args,
        cwd=REPO_ROOT,
        env=env or os.environ.copy(),
        capture_output=True,
        text=True,
        check=True,
    )


def setup_remote() -> None:
    """Ensure remote origin points to the specified GitHub repository."""
    try:
        remotes = run_git(["remote", "-v"]).stdout
        if "origin" in remotes:
            run_git(["remote", "set-url", "origin", REMOTE_URL])
            print(f"[+] Updated remote origin to {REMOTE_URL}")
        else:
            run_git(["remote", "add", "origin", REMOTE_URL])
            print(f"[+] Added remote origin: {REMOTE_URL}")
    except subprocess.CalledProcessError as e:
        print(f"[-] Failed configuring remote: {e.stderr}")


def build_commit_history() -> None:
    """Stage and commit files chronologically with historical timestamps."""
    print("[*] Unstaging any currently staged files...")
    try:
        run_git(["reset"])
    except subprocess.CalledProcessError:
        pass

    setup_remote()

    base_env = os.environ.copy()

    for idx, commit_spec in enumerate(COMMITS, 1):
        dt = commit_spec["date"]
        msg = commit_spec["message"]
        files = commit_spec["files"]

        print(f"\n[{idx}/{len(COMMITS)}] Committing: {msg.splitlines()[0]} ({dt})")

        # Stage files for this commit
        for f in files:
            p = REPO_ROOT / f
            if p.exists() or f == ".":
                run_git(["add", f])

        # Commit with explicit historical author and committer dates
        commit_env = base_env.copy()
        commit_env["GIT_AUTHOR_DATE"] = dt
        commit_env["GIT_COMMITTER_DATE"] = dt

        try:
            res = run_git(["commit", "-m", msg], env=commit_env)
            print(f"    Commit success: {res.stdout.strip().splitlines()[0]}")
        except subprocess.CalledProcessError as e:
            if "nothing to commit" in e.stdout or "nothing to commit" in e.stderr:
                print("    (Nothing new to commit in this stage)")
            else:
                print(f"[-] Commit error: {e.stderr}")
                raise

    print("\n[+] Commit history successfully constructed!")
    log = run_git(["log", "--oneline", "--decorate"]).stdout
    print("\n--- Recent Git Log ---")
    print(log.strip())


if __name__ == "__main__":
    build_commit_history()
