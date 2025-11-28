#!/usr/bin/env python
"""
Fix PostgreSQL sequences that are out of sync with their tables.

This script resets all sequences to match the maximum ID in their corresponding tables.
Run this after importing data or restoring from a backup.

Usage:
    poetry run python scripts/fix_sequences.py
"""

import os
import sys
from pathlib import Path

import django
from django.db import connection

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

django.setup()


def fix_sequences():
    """Fix all PostgreSQL sequences to match max IDs in tables."""
    with connection.cursor() as cursor:
        # Get all sequences and their associated tables
        cursor.execute("""
            SELECT
                s.relname AS sequence_name,
                t.relname AS table_name,
                a.attname AS column_name
            FROM pg_class s
            JOIN pg_depend d ON d.objid = s.oid
            JOIN pg_class t ON d.refobjid = t.oid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
            JOIN pg_namespace n ON s.relnamespace = n.oid
            WHERE s.relkind = 'S'
              AND n.nspname = 'public'
            ORDER BY t.relname, s.relname;
        """)

        sequences = cursor.fetchall()
        fixed_count = 0

        print(f"Found {len(sequences)} sequences to check and fix...\n")

        for sequence_name, table_name, column_name in sequences:
            try:
                # Get the max ID from the table
                cursor.execute(f"SELECT COALESCE(MAX({column_name}), 0) FROM {table_name}")
                max_id = cursor.fetchone()[0]

                # Set the sequence to max_id + 1
                cursor.execute(f"SELECT setval('{sequence_name}', {max_id + 1}, false)")
                new_val = cursor.fetchone()[0]

                print(f"✓ Fixed {table_name}.{column_name} → sequence value: {new_val}")
                fixed_count += 1

            except Exception as e:
                print(f"✗ Error fixing {table_name}.{column_name}: {e}")

        print(f"\nSuccessfully fixed {fixed_count} sequences!")


if __name__ == "__main__":
    print("=" * 70)
    print("PostgreSQL Sequence Fixer")
    print("=" * 70)
    print()

    fix_sequences()

    print()
    print("=" * 70)
    print("Done! You can now run migrations without sequence errors.")
    print("=" * 70)
