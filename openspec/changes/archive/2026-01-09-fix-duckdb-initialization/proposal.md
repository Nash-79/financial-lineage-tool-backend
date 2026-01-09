# Fix DuckDB Initialization Race Condition

## Problem
The backend service occasionally fails to start with `Failed to initialize DuckDB: IO Error`. This is caused by file locking issues when DuckDB initializes, likely due to:
1.  Zombies from previous processes holding the lock.
2.  Rapid restarts where the file handle hasn't been released yet.
3.  Docker volume mounting delays on Windows.

## Solution
Implement a robust retry mechanism with backoff in `DuckDBClient.initialize()`:
- Wrap connection logic in a retry loop (e.g., 5 attempts).
- Add exponential or fixed backoff (e.g., 1s).
- Verify database file accessibility before connecting.
- Log warnings on failed attempts to aid debugging.

## Verification
- Simulate file lock (e.g., hold open in another process) and verify retry behavior.
- Ensure efficient failure (don't wait forever) if the file is genuinely corrupted or permissions are wrong.
