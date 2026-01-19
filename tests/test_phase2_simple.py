"""
Simple transaction test - validates Phase 2 transaction support.
"""

import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.duckdb_client import initialize_duckdb, close_duckdb


async def test_basic_transaction():
    """Test basic transaction functionality."""
    print("\n" + "="*60)
    print("PHASE 2 TRANSACTION TEST")
    print("="*60)
    
    os.environ["ENABLE_CONNECTION_POOL"] = "false"
    
    try:
        client = initialize_duckdb(db_path=":memory:")
        
        # Create test table
        client.conn.execute("CREATE TABLE IF NOT EXISTS tx_test (id INTEGER, value TEXT)")
        client.conn.execute("DELETE FROM tx_test")  # Clean slate
        
        print("\n[TEST 1] Transaction Commit")
        async with client.transaction() as tx:
            await tx.execute("INSERT INTO tx_test VALUES (?, ?)", (1, "test1"))
            await tx.execute("INSERT INTO tx_test VALUES (?, ?)", (2, "test2"))
        
        result = client.conn.execute("SELECT COUNT(*) FROM tx_test").fetchone()
        print(f"   Result: {result[0]} rows inserted")
        assert result[0] == 2, "Transaction commit failed"
        print("   [PASS] Transaction committed successfully")
        
        print("\n[TEST 2] Transaction Rollback")
        client.conn.execute("DELETE FROM tx_test")
        client.conn.execute("CREATE TABLE IF NOT EXISTS tx_pk (id INTEGER PRIMARY KEY)")
        client.conn.execute("DELETE FROM tx_pk")
        client.conn.execute("INSERT INTO tx_pk VALUES (1)")
        
        try:
            async with client.transaction() as tx:
                await tx.execute("INSERT INTO tx_pk VALUES (?)", (2,))
                await tx.execute("INSERT INTO tx_pk VALUES (?)", (1,))  # Duplicate - should fail
        except Exception:
            pass  # Expected
        
        result = client.conn.execute("SELECT COUNT(*) FROM tx_pk WHERE id = 2").fetchone()
        print(f"   Result: Row 2 exists = {result[0] > 0}")
        assert result[0] == 0, "Transaction rollback failed"
        print("   [PASS] Transaction rolled back correctly")
        
        print("\n[TEST 3] Transaction Methods")
        client.conn.execute("DELETE FROM tx_test")
        client.conn.execute("INSERT INTO tx_test VALUES (1, 'one'), (2, 'two')")
        
        async with client.transaction() as tx:
            row = await tx.fetchone("SELECT * FROM tx_test WHERE id = ?", (1,))
            assert row == (1, 'one'), "fetchone failed"
            
            rows = await tx.fetchall("SELECT * FROM tx_test ORDER BY id")
            assert len(rows) == 2, "fetchall failed"
            
            await tx.execute("INSERT INTO tx_test VALUES (?, ?)", (3, 'three'))
        
        result = client.conn.execute("SELECT COUNT(*) FROM tx_test").fetchone()
        print(f"   Result: {result[0]} rows total")
        assert result[0] == 3, "Transaction methods failed"
        print("   [PASS] Transaction methods work correctly")
        
        print("\n" + "="*60)
        print("[PASS] ALL TESTS PASSED - Phase 2 Transaction Support Working!")
        print("="*60)
        
        return 0
        
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        close_duckdb()


if __name__ == "__main__":
    exit_code = asyncio.run(test_basic_transaction())
    sys.exit(exit_code)
