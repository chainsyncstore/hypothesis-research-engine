"""
Database inspection script - shows contents of all key tables.
"""
import sqlite3
from pathlib import Path

DB_PATH = "results/research.db"

def main():
    if not Path(DB_PATH).exists():
        print(f"Database not found: {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Show schema for key tables
    print("=" * 70)
    print("DATABASE INSPECTION")
    print("=" * 70)
    
    tables = ["hypothesis_status_history", "evaluations", "portfolio_evaluations", "hypotheses", "policies"]
    
    for table in tables:
        print(f"\n{'='*30} {table} {'='*30}")
        
        # Get schema
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            if columns:
                print("Columns:", [c['name'] for c in columns])
            else:
                print(f"Table {table} does not exist")
                continue
        except Exception as e:
            print(f"Schema error: {e}")
            continue
        
        # Get data
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            print(f"Total Rows: {len(rows)}")
            
            if rows:
                print("\nSample Data (last 5 rows):")
                for row in rows[-5:]:
                    row_dict = dict(row)
                    # Truncate long values for display
                    for k, v in row_dict.items():
                        if isinstance(v, str) and len(v) > 50:
                            row_dict[k] = v[:50] + "..."
                    print(f"  {row_dict}")
        except Exception as e:
            print(f"Data error: {e}")
    
    conn.close()
    print("\n" + "=" * 70)
    print("INSPECTION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
