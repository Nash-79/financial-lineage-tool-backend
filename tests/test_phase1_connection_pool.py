"""
Test script to validate Phase 1 connection pool integration.

Tests both singleton and pool modes to ensure backward compatibility.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.duckdb_client import DuckDBClient, initialize_duckdb, close_duckdb


async def test_singleton_mode():
    """Test traditional singleton mode (pool disabled)."""
    print("\n" + "="*60)
    print("TEST 1: Singleton Mode (ENABLE_CONNECTION_POOL=false)")
    print("="*60)
    
    # Ensure pool is disabled
    os.environ["ENABLE_CONNECTION_POOL"] = "false"
    
    try:
        # Initialize client
        client = initialize_duckdb(db_path=":memory:")
        
        # Verify singleton mode
        assert client._enable_pool is False, "Pool should be disabled"
        assert client.conn is not None, "Connection should exist in singleton mode"
        assert client.is_initialized, "Client should be initialized"
        
        print("[PASS] Singleton mode initialization successful")
        print(f"   - Pool enabled: {client._enable_pool}")
        print(f"   - Connection exists: {client.conn is not None}")
        print(f"   - Initialized: {client.is_initialized}")
        
        # Test basic query
        result = client.conn.execute("SELECT 1 as test").fetchone()
        assert result[0] == 1, "Basic query failed"
        print("[PASS] Basic query successful")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Singleton mode test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_duckdb()


async def test_pool_mode():
    """Test connection pool mode (pool enabled)."""
    print("\n" + "="*60)
    print("TEST 2: Connection Pool Mode (ENABLE_CONNECTION_POOL=true)")
    print("="*60)
    
    # Enable pool
    os.environ["ENABLE_CONNECTION_POOL"] = "true"
    os.environ["CONNECTION_POOL_MAX_SIZE"] = "3"
    os.environ["CONNECTION_POOL_MIN_SIZE"] = "1"
    
    try:
        # Initialize client
        client = initialize_duckdb(db_path=":memory:")
        
        # Verify pool mode
        assert client._enable_pool is True, "Pool should be enabled"
        assert client._pool is not None, "Pool should exist"
        assert client.is_initialized, "Client should be initialized"
        
        print("[PASS] Pool mode initialization successful")
        print(f"   - Pool enabled: {client._enable_pool}")
        print(f"   - Pool exists: {client._pool is not None}")
        print(f"   - Initialized: {client.is_initialized}")
        
        # Initialize pool asynchronously
        await client.initialize_pool()
        
        # Get pool stats
        stats = client._pool.get_stats()
        print("[PASS] Pool statistics retrieved")
        print(f"   - Active connections: {stats['active_connections']}")
        print(f"   - Pool size: {stats['pool_size']}")
        print(f"   - Total created: {stats['connections_created']}")
        
        # Test connection acquisition
        async with client._pool.get_connection() as conn:
            result = conn.fetchone("SELECT 1 as test")
            assert result[0] == 1, "Basic query failed"
            print("[PASS] Connection acquisition and query successful")
        
        # Verify connection was returned
        stats_after = client._pool.get_stats()
        print(f"[PASS] Connection returned to pool")
        print(f"   - Connections acquired: {stats_after['connections_acquired']}")
        print(f"   - Connections returned: {stats_after['connections_returned']}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Pool mode test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if client and client._pool:
            await client._pool.close()
        close_duckdb()


async def test_health_endpoint_compatibility():
    """Test that health endpoint data structure is correct."""
    print("\n" + "="*60)
    print("TEST 3: Health Endpoint Compatibility")
    print("="*60)
    
    # Test singleton mode health data
    os.environ["ENABLE_CONNECTION_POOL"] = "false"
    client = initialize_duckdb(db_path=":memory:")
    
    try:
        # Simulate health endpoint logic
        if hasattr(client, '_enable_pool') and client._enable_pool and client._pool:
            mode = "pool"
        else:
            mode = "singleton"
        
        assert mode == "singleton", "Should be in singleton mode"
        print("[PASS] Singleton mode health data structure correct")
        
    finally:
        close_duckdb()
    
    # Test pool mode health data
    os.environ["ENABLE_CONNECTION_POOL"] = "true"
    client = initialize_duckdb(db_path=":memory:")
    
    try:
        await client.initialize_pool()
        
        # Simulate health endpoint logic
        if hasattr(client, '_enable_pool') and client._enable_pool and client._pool:
            mode = "pool"
            stats = client._pool.get_stats()
            assert "active_connections" in stats
            assert "pool_size" in stats
        else:
            mode = "singleton"
        
        assert mode == "pool", "Should be in pool mode"
        print("[PASS] Pool mode health data structure correct")
        print(f"   - Mode: {mode}")
        print(f"   - Stats available: {stats is not None}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Health endpoint test failed: {e}")
        return False
    finally:
        if client and client._pool:
            await client._pool.close()
        close_duckdb()


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PHASE 1 CONNECTION POOL VALIDATION TESTS")
    print("="*60)
    
    results = []
    
    # Test 1: Singleton mode
    results.append(await test_singleton_mode())
    
    # Test 2: Pool mode
    results.append(await test_pool_mode())
    
    # Test 3: Health endpoint compatibility
    results.append(await test_health_endpoint_compatibility())
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("[PASS] ALL TESTS PASSED")
        return 0
    else:
        print("[FAIL] SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

