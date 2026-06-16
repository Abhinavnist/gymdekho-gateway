"""
Run this once to apply the schema to your database ok.
Usage: python scripts/run_migrations.py ---
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg
from dotenv import load_dotenv

load_dotenv()

MIGRATION_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "database", "migrations")


def run():
    conn_str = (
        f"host={os.getenv('DB_HOST', 'localhost')} "
        f"port={os.getenv('DB_PORT', '5432')} "
        f"dbname={os.getenv('DB_NAME', 'gymconnect_ai')} "
        f"user={os.getenv('DB_USER', 'gymconnect_user')} "
        f"password={os.getenv('DB_PASSWORD', 'gymconnect_pass')}"
    )

    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            migration_files = sorted(f for f in os.listdir(MIGRATION_DIR) if f.endswith(".sql"))
            for filename in migration_files:
                filepath = os.path.join(MIGRATION_DIR, filename)
                print(f"Applying {filename}...")
                with open(filepath, "r") as f:
                    sql = f.read()
                cur.execute(sql)
                conn.commit()
                print(f"  ✅ {filename} applied.")

    print("\n✅ All migrations complete.")


if __name__ == "__main__":
    run()
