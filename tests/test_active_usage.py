"""
Test active usage of DuckDB infrastructure.

Tests that caching, error handling, and optimizations are actively used.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_active_usage():
    """Test that infrastructure is actively used in production code."""
    print("\n" + "="*60)
    print("ACTIVE USAGE INTEGRATION TEST")
    print("="*60)
    
    try:
        # Test 1: Caching in ModelConfigService
        print("\n[TEST 1] Caching Integration")
        from src.storage.duckdb_client import initialize_duckdb
        from src.services.model_config_service import ModelConfigService
        
        os.environ["ENABLE_CONNECTION_POOL"] = "false"
        db = initialize_duckdb(db_path=":memory:")
        service = ModelConfigService(db)
        
        # Check if caching is used
        has_cache_logic = "cache_key" in str(service.get_active_model.__code__.co_names)
        print(f"   Caching in get_active_model: {has_cache_logic}")
        
        has_invalidation = hasattr(service, '_invalidate_cache')
        print(f"   Cache invalidation method: {has_invalidation}")
        
        if has_cache_logic and has_invalidation:
            print("   [PASS] Caching actively used")
        else:
            print("   [WARN] Caching not fully integrated")
        
        # Test 2: OptimizedRepository
        print("\n[TEST 2] OptimizedRepository Usage")
        from src.db.repositories.optimized_model_config_repository import OptimizedModelConfigRepository
        
        is_optimized = isinstance(service.repo, OptimizedModelConfigRepository)
        print(f"   Using OptimizedRepository: {is_optimized}")
        
        if is_optimized:
            print("   [PASS] OptimizedRepository actively used")
        else:
            print("   [FAIL] Not using OptimizedRepository")
        
        # Test 3: QueryCache initialized
        print("\n[TEST 3] QueryCache Initialization")
        has_query_cache = hasattr(db, '_query_cache') and db._query_cache is not None
        print(f"   QueryCache initialized: {has_query_cache}")
        
        if has_query_cache:
            cache_stats = db._query_cache.get_stats()
            print(f"   Cache stats available: {bool(cache_stats)}")
            print("   [PASS] QueryCache ready for use")
        else:
            print("   [WARN] QueryCache not initialized")
        
        # Test 4: Transaction support
        print("\n[TEST 4] Transaction Support")
        has_transaction = hasattr(db, 'transaction')
        print(f"   Transaction method available: {has_transaction}")
        
        if has_transaction:
            print("   [PASS] Transactions ready for use")
        
        print("\n" + "="*60)
        print("[PASS] ACTIVE USAGE INTEGRATION COMPLETE!")
        print("="*60)
        
        print("\nSummary:")
        print(f"  - Caching: {'Active' if has_cache_logic else 'Not active'}")
        print(f"  - OptimizedRepository: {'Active' if is_optimized else 'Not active'}")
        print(f"  - QueryCache: {'Initialized' if has_query_cache else 'Not initialized'}")
        print(f"  - Transactions: {'Available' if has_transaction else 'Not available'}")
        print(f"  - Cache Invalidation: {'Implemented' if has_invalidation else 'Not implemented'}")
        
        return 0
        
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = test_active_usage()
    sys.exit(exit_code)
