"""Command-Line Interface (CLI) Dispatcher.

Provides command routing, configuration validation, and standardized exit codes
conforming to Section 13.2 of the Release 1.0 System Architecture Design.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from excel_intel import __version__
from excel_intel.config import PlatformConfig, load_config
from excel_intel.exceptions import ConfigurationError, PlatformError
from excel_intel.logging import configure_logging, get_logger

logger = get_logger("cli")


def create_parser() -> argparse.ArgumentParser:
    """Creates the root CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="excel-intel",
        description=(
            "Autonomous Excel Intelligence Platform (Release 1.0 Skeleton)\n"
            "Deterministic, domain-agnostic enterprise spreadsheet intelligence."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show platform version and exit.",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Override logging verbosity threshold.",
    )

    parser.add_argument(
        "--log-format",
        choices=["json", "text"],
        default=None,
        help="Override log output format.",
    )

    subparsers = parser.add_subparsers(
        title="Subcommands",
        dest="subcommand",
        help="Operational task commands",
    )

    # 1. Validate Configuration Command
    subparsers.add_parser(
        "validate-config",
        help="Validate environment settings, quotas, and storage boundaries.",
    )

    # 2. Inspect Command (Module 03 / 04 Placeholder)
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect workbook structure, tables, and formula dependencies.",
    )
    inspect_parser.add_argument(
        "workbook",
        help="Path to the Excel workbook (.xlsx, .xlsm) to inspect.",
    )

    # 3. Plan Command (Module 06 Placeholder)
    plan_parser = subparsers.add_parser(
        "plan",
        help="Generate a declarative consolidation OperationPlan JSON.",
    )
    plan_parser.add_argument(
        "--sources",
        nargs="+",
        required=True,
        help="Path(s) to source workbooks.",
    )
    plan_parser.add_argument(
        "--target",
        required=True,
        help="Path to Master/target workbook.",
    )

    # 4. Apply Command (Module 10 Placeholder)
    apply_parser = subparsers.add_parser(
        "apply",
        help="Execute approved OperationPlan with 6-phase WAL durability.",
    )
    apply_parser.add_argument(
        "--plan",
        required=True,
        help="Path to authorized OperationPlan JSON file.",
    )
    apply_parser.add_argument(
        "--token",
        required=True,
        help="Cryptographic HMAC-SHA256 approval token string.",
    )

    # 5. Rollback Command (Module 10 Placeholder)
    rollback_parser = subparsers.add_parser(
        "rollback",
        help="Roll back an uncommitted transaction to pre-state backup.",
    )
    rollback_parser.add_argument(
        "--target",
        required=True,
        help="Path to the workbook to roll back.",
    )

    # 6. Audit Command (Module 11 Placeholder)
    audit_parser = subparsers.add_parser(
        "audit",
        help="Verify the cryptographic integrity of the audit hash chain.",
    )
    audit_parser.add_argument(
        "--vault",
        default="audit_vault.db",
        help="Path to SQLite audit ledger.",
    )

    return parser


def run_validate_config(config: PlatformConfig) -> int:
    """Validates configuration and outputs active runtime parameters."""
    logger.info(
        "CONFIG_VALIDATION_SUCCESS",
        message="Platform configuration and environment quotas successfully validated.",
        context={
            "env": config.env,
            "log_level": config.log_level,
            "log_format": config.log_format,
            "storage_root": str(config.storage_root),
            "max_rss_mb": config.max_rss_mb,
            "token_ttl_seconds": config.token_ttl_seconds,
            "wal_flush_barrier": config.wal_flush_barrier,
        },
    )
    sys.stdout.write(
        f"Excel Intelligence Platform v{__version__}\n"
        f"Configuration Status: VALID\n"
        f"Environment:          {config.env}\n"
        f"Storage Root:         {config.storage_root}\n"
        f"Max RSS Limit:        {config.max_rss_mb} MB (Baseline Compliant)\n"
        f"Token TTL:            {config.token_ttl_seconds}s\n"
        f"WAL Flush Barrier:    {'ENABLED' if config.wal_flush_barrier else 'DISABLED'}\n"
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI execution router."""
    parser = create_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as err:
        return err.code if isinstance(err.code, int) else 2

    # Determine logging overrides from CLI flags
    overrides: dict[str, str] = {}
    if args.log_level:
        overrides["log_level"] = args.log_level
    if args.log_format:
        overrides["log_format"] = args.log_format

    try:
        config = load_config(overrides=overrides)
        configure_logging(
            level=config.log_level,
            log_format=config.log_format,
        )
    except ConfigurationError as err:
        sys.stderr.write(f"Configuration Error: {err.message}\n")
        return err.exit_code
    except Exception as err:
        sys.stderr.write(f"Fatal Startup Error: {err}\n")
        return 1

    if not args.subcommand:
        parser.print_help(sys.stdout)
        return 0

    if args.subcommand == "validate-config":
        return run_validate_config(config)

    # Subcommand routing for foundation skeleton (M01)
    logger.info(
        "COMMAND_DISPATCH",
        message=f"Subcommand '{args.subcommand}' dispatched in skeleton foundation.",
        context={"subcommand": args.subcommand, "args": vars(args)},
    )

    sys.stdout.write(
        f"Autonomous Excel Intelligence Platform v{__version__}\n"
        f"Subcommand: {args.subcommand}\n"
        f"Notice: Foundation M01 established. Downstream execution modules "
        f"(M02-M13) remain gated pending milestone authorization.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
