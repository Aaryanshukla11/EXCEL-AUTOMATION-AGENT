# Developer Guide — Autonomous Excel Intelligence Platform (M01 & M02 Foundation)

Welcome to the development environment for the Autonomous Excel Intelligence Platform.

This guide outlines setup instructions, directory structure, configuration conventions, and testing procedures for **M01 (Repository Foundation)** and **M02 (Rust Streaming Parser)**.

---

## 1. Prerequisites

- **Python:** Python 3.12+ (CPython 3.12 or 3.13 verified via stable `abi3-py312` extension)
- **Rust Toolchain:** Rustc 1.80+ / Cargo (installed via `rustup default stable-x86_64-pc-windows-msvc`)
- **C++ Compiler:** Visual Studio Build Tools 2019/2022 with MSVC C++ x86/x64 tools
- **Packaging Tools:** `maturin>=1.5` for building the PyO3 native extension

---

## 2. Directory Structure

```
excel_intel/
├── __init__.py               # Package metadata and version definition
├── __main__.py               # Execution entry point for `python -m excel_intel`
├── _rs.pyd                   # Compiled PyO3 abi3 Rust native streaming extension (M02)
├── cli.py                    # Command-line interface dispatcher
├── config.py                 # Pydantic v2 application configuration and validation
├── exceptions.py             # Platform error taxonomy and standardized exit codes (§13.2)
├── logging.py                # Structured JSON-Lines contextual logging (§13.1)
├── core/
│   ├── __init__.py           # Exposes models, parser, dates, and contracts
│   ├── parser.py             # StreamingWorkbookReader interface wrapping _rs (M02)
│   └── types.py              # Frozen architectural data models and contracts (§6.2, §14)
├── cognitive/
│   ├── __init__.py
│   └── interfaces.py         # Cognitive Orchestrator typed protocols
├── execution/
│   ├── __init__.py
│   └── interfaces.py         # Deterministic Execution Layer, WAL, HMAC & Audit protocols
└── ui/
    ├── __init__.py
    └── interfaces.py         # CLI & Diff presentation protocols

crates/excel_intel_rs/        # High-performance Rust OpenXML streaming parser (M02)
├── Cargo.toml                # Rust crate definition with pyo3, quick-xml, zip, chrono
└── src/
    ├── lib.rs                # PyO3 module definition and WorkbookStreamReader class
    ├── cell_validator.rs     # 32,767 UTF-16 code units and 131,072 byte validation
    ├── dates.rs              # 1900/1904 date conversion, Lotus defect, IEEE-754 safety
    ├── error.rs              # RustParserError mapping to Python exception hierarchy
    ├── memory_guard.rs       # Proactive 235 MB Working Set defensive tripwire
    ├── scratch.rs            # Verified local NTFS scratch storage with atomic locks
    ├── shared_strings.rs     # Dual-tier shared strings (32 MB RAM + 24 MB 12B index + LRU)
    ├── styles.rs             # Built-in and custom date number format detection
    ├── worksheet.rs          # Incremental quick-xml streaming parser and chunker
    └── zip_handler.rs        # Streaming zip reader with 1.0 GiB ceiling and OLE guards

tests/
├── conftest.py               # Shared test fixtures and environment isolators
├── test_config.py            # Configuration loading and constraint validation tests
├── test_logging.py           # Structured JSON logging format and context tests
├── test_exceptions.py        # Error taxonomy, exit codes, and serialization tests
├── test_types.py             # Contract model validation tests
├── test_cli.py               # CLI entry point, arguments, and smoke tests
├── test_imports.py           # Clean import and dependency boundary tests
├── test_parser_dates.py      # M02 date conversion, serial 60, and IEEE-754 bit tests
├── test_parser_cell_validation.py # M02 cell length and surrogate pair boundary tests
├── test_streaming_reader.py  # M02 end-to-end streaming reader integration tests
└── benchmarks/
    └── run_m02_benchmarks.py # Reproducible benchmark verification on Phase 0 corpora
```

---

## 3. Building the Rust Extension (M02)

To build the native extension:

```powershell
# In crates/excel_intel_rs:
cd crates\excel_intel_rs
cargo build --release

# Copy the compiled DLL as _rs.pyd into the python package:
Copy-Item target\release\_rs.dll ..\..\excel_intel\_rs.pyd
cd ..\..
```

To run native Rust unit and boundary tests:
```powershell
cd crates\excel_intel_rs
cargo test
cd ..\..
```

---

## 4. Running Automated Tests

Run the complete test suite (69 tests) across Python 3.12 and Python 3.13:

```powershell
# Python 3.12:
C:\Python312\python.exe -m pytest -v

# Python 3.13:
C:\Python313\python.exe -m pytest -v
```

---

## 5. Running Performance Benchmarks

Run the empirical benchmark evaluation on the frozen Phase 0 benchmark corpora:

```powershell
python tests\benchmarks\run_m02_benchmarks.py
```

Target Benchmark Criteria:
- **`BENCH-SCALE-100K.xlsx` (100k data rows × 50 cols, 4,000,050 cells):**
  - Contractual Target: Streaming Latency $< 15.0\text{ s}$, Peak RSS $\le 250.0\text{ MB}$.
  - Measured Result: **$9.963\text{ s}$**, Peak RSS: **$132.8\text{ MB}$** (**PASS**).
- **`BENCH-PERF-MULTI-5` (5 workbooks × 20k rows + 1 master, $N=5$ runs):**
  - Contractual Target: Mean Total Latency $\le 60.0\text{ s}$, Peak RSS $\le 250.0\text{ MB}$.
  - Measured Result: Mean Latency **$5.553\text{ s}$** ($\text{Mean} + 2\sigma = 6.016\text{ s}$), Peak RSS: **$90.8\text{ MB}$** (**PASS**).

---

## 6. Architecture & Governance Compliance

- **Domain-Agnostic Design:** Zero hardcoded sheet names, business logic, or customer-specific schemas.
- **Air-Gapped Isolation:** The Cognitive Orchestrator interfaces are strictly separated from physical workbook handles and mutation engines.
- **No Production Workbook Mutation:** Benchmark evaluations execute strictly on disposable copies. Original Phase 0 corpora remain 100% unaltered.
