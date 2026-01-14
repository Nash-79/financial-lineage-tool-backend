#!/usr/bin/env python3
"""
Development Cycle Orchestrator
Automates local regression testing for the Financial Lineage Tool

This script runs frontend E2E tests and provides clear reporting.
Backend contract testing (Schemathesis) is deferred pending venv fixes.

Usage:
    python dev_cycle.py                    # Run all tests
    python dev_cycle.py --frontend         # Run only frontend tests
    python dev_cycle.py --fast             # Skip health checks, run tests immediately
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


# ANSI color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_banner(text: str, color: str = Colors.BLUE):
    """Print a formatted banner"""
    print(f"\n{color}{'=' * 80}")
    print(f"  {text}")
    print(f"{'=' * 80}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def check_backend_health(timeout: int = 30) -> bool:
    """
    Check if backend is healthy and responding

    Args:
        timeout: Maximum seconds to wait for backend

    Returns:
        True if backend is healthy, False otherwise
    """
    import requests

    print_info("Checking backend health...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    print_success("Backend is healthy")
                    return True
        except requests.exceptions.RequestException:
            time.sleep(2)

    print_error(f"Backend not healthy after {timeout}s")
    return False


def run_frontend_tests(fast: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Run Playwright E2E tests

    Args:
        fast: If True, skip health checks

    Returns:
        Tuple of (success, error_message)
    """
    print_banner("Frontend E2E Tests (Playwright)", Colors.BLUE)

    frontend_dir = Path("c:\\repos\\financial-lineage-tool-frontend")

    if not frontend_dir.exists():
        return False, f"Frontend directory not found: {frontend_dir}"

    # Check backend health unless --fast
    if not fast:
        if not check_backend_health():
            return False, "Backend health check failed"

    # Run Playwright tests
    print_info("Running Playwright tests...")
    try:
        result = subprocess.run(
            ["npx", "playwright", "test", "--reporter=list"],
            cwd=frontend_dir,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        # Print output
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        if result.returncode == 0:
            print_success("All frontend tests passed!")
            return True, None
        else:
            error_msg = f"Frontend tests failed with exit code {result.returncode}"
            print_error(error_msg)
            print_info(f"HTML report: {frontend_dir}/playwright-report/index.html")
            return False, error_msg

    except subprocess.TimeoutExpired:
        return False, "Frontend tests timed out after 5 minutes"
    except Exception as e:
        return False, f"Error running frontend tests: {str(e)}"


def print_summary(results: dict):
    """Print final test summary"""
    print_banner("Test Summary", Colors.BOLD)

    total_tests = len(results)
    passed = sum(1 for success, _ in results.values() if success)
    failed = total_tests - passed

    for test_name, (success, error) in results.items():
        if success:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED - {error}")

    print(f"\n{Colors.BOLD}Results: {passed}/{total_tests} passed{Colors.RESET}")

    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests passed!{Colors.RESET}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ {failed} test(s) failed{Colors.RESET}\n")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Run automated regression tests for Financial Lineage Tool"
    )
    parser.add_argument(
        "--frontend", action="store_true", help="Run only frontend E2E tests"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip health checks and run tests immediately",
    )

    args = parser.parse_args()

    print_banner(
        f"Development Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        Colors.BOLD,
    )

    results = {}

    # Run frontend tests
    if args.frontend or True:  # Always run frontend for now
        success, error = run_frontend_tests(fast=args.fast)
        results["Frontend E2E"] = (success, error)

    # Print summary and exit
    exit_code = print_summary(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
