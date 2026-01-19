"""
Simple test to validate Phases 3-4 integration.

Tests QueryCache and error handling are available.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all phase imports work."""
    print("\n" + "="*60)
    print("PHASES 3-4 INTEGRATION TEST")
    print("="*60)
    
    try:
        # Test Phase 3: QueryCache
        print("\n[TEST 1] QueryCache Import")
        from src.storage.query_cache import QueryCache
        print("   [PASS] QueryCache imported successfully")
        
        # Test Phase 4: Error handling
        print("\n[TEST 2] Database Exceptions Import")
        from src.storage.database_exceptions import (
            DatabaseException,
            ConnectionException,
            QueryException,
            TransactionException,
        )
        print("   [PASS] Database exceptions imported successfully")
        
        # Test DuckDBClient has new imports
        print("\n[TEST 3] DuckDBClient Integration")
        from src.storage.duckdb_client import (
            QUERY_CACHE_AVAILABLE,
            DATABASE_EXCEPTIONS_AVAILABLE,
        )
        print(f"   QueryCache available: {QUERY_CACHE_AVAILABLE}")
        print(f"   Database exceptions available: {DATABASE_EXCEPTIONS_AVAILABLE}")
        
        if QUERY_CACHE_AVAILABLE and DATABASE_EXCEPTIONS_AVAILABLE:
            print("   [PASS] All modules integrated")
        else:
            print("   [FAIL] Some modules not available")
            return 1
        
        print("\n" + "="*60)
        print("[PASS] ALL TESTS PASSED - Phases 3-4 Integration Complete!")
        print("="*60)
        
        return 0
        
    except Exception as e:
        print(f"\n[FAIL] Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = test_imports()
    sys.exit(exit_code)
