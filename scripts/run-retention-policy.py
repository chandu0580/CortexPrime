#!/usr/bin/env python3
"""
CortexPrime — Data Retention Policy Executor

Run as a cron job to purge old records according to configured retention policies.

Usage:
    python scripts/run-retention-policy.py [--category CATEGORY] [--dry-run]

Examples:
    # Purge all categories
    python scripts/run-retention-policy.py

    # Show what would be purged without deleting
    python scripts/run-retention-policy.py --dry-run

    # Purge only audit logs
    python scripts/run-retention-policy.py --category audit_logs
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.data_retention import get_retention_policy


def main():
    parser = argparse.ArgumentParser(description="Run data retention purge")
    parser.add_argument("--category", help="Specific category to purge (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be purged")
    args = parser.parse_args()

    policy = get_retention_policy()
    policies = policy.list_policies()

    if args.dry_run:
        print("[retention] DRY RUN — no records will be deleted")
        print(f"[retention] Current policies:")
        for category, days in policies.items():
            print(f"  {category}: {days} days")
        return

    categories = [args.category] if args.category else policies.keys()
    total = 0

    for category in categories:
        if category in ("mission_executions", "cost_tracking", "connector_logs"):
            print(f"[retention] Skipping DB-backed category '{category}' (requires database session)")
            continue
        count = policy.purge_old_records(category, f"data/{category.replace('_', '/')}")
        total += count
        print(f"[retention] Purged {count} records from '{category}'")

    # Additional mission-specific purges
    mission_counts = policy.purge_missions()
    for source, count in mission_counts.items():
        print(f"[retention] Purged {count} records from missions/{source}")
        total += count

    print(f"[retention] Total records purged: {total}")


if __name__ == "__main__":
    main()
