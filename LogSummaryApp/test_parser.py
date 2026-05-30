"""Test script to verify parsers work with new log format"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'backend')

from backend.app import parse_case_created, parse_duplicates_increments, parse_errors
from datetime import date
from pathlib import Path

# Use the test log samples
TEST_LOG = Path('../test_log_samples.txt')

print("=" * 60)
print("TESTING PARSERS WITH NEW LOG FORMAT")
print("=" * 60)

# Test with May 12, 2026 (the date in test samples)
test_date = date(2026, 5, 12)

print(f"\nTesting with date: {test_date}")
print("-" * 60)

# Test case creation parser
print("\n[1] CASE CREATION PARSER")
print("-" * 60)
cases = parse_case_created(TEST_LOG, filter_date=test_date)
print(f"Found {len(cases)} cases\n")

for i, case in enumerate(cases, 1):
    print(f"Case {i}:")
    print(f"  Store: {case['store']}")
    print(f"  Contact: {case['account']}")
    print(f"  Subject: {case['subject']}")
    print(f"  Case Type: {case['case_type']}")
    print(f"  Time Diff: {case.get('time_difference', 'N/A')}")
    print(f"  Red Flag: {case.get('has_red_flag', False)}")
    print(f"  Email Verified: {case.get('email_verified', False)}")
    print(f"  Draft Status: {case.get('draft_status', 'N/A')}")
    print()

# Test duplicate/increment parser
print("\n[2] DUPLICATE/INCREMENT PARSER")
print("-" * 60)
duplicates = parse_duplicates_increments(TEST_LOG, filter_date=test_date)
print(f"Found {len(duplicates)} duplicates/increments\n")

for i, dup in enumerate(duplicates, 1):
    print(f"Entry {i}:")
    print(f"  Store: {dup['store']}")
    print(f"  Contact: {dup['account']}")
    print(f"  Subject: {dup['subject']}")
    print(f"  Type: {dup['duplicate_type']}")
    print(f"  Is Increment: {dup['is_increment']}")
    print(f"  Email Verified: {dup.get('email_verified', False)}")
    print()

# Test error parser
print("\n[3] ERROR PARSER")
print("-" * 60)
errors = parse_errors(TEST_LOG, filter_date=test_date)
print(f"Found {len(errors)} errors\n")

for i, error in enumerate(errors, 1):
    print(f"Error {i}:")
    print(f"  Store: {error.get('store', 'N/A')}")
    print(f"  Message: {error['message'][:80]}...")
    print(f"  Red Flag: {error.get('is_red_flag', False)}")
    print()

print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"[OK] Cases: {len(cases)}")
print(f"[OK] Duplicates/Increments: {len(duplicates)}")
print(f"[OK] Errors: {len(errors)}")
print()

# Verify specific scenarios
print("\nVERIFICATION CHECKS")
print("-" * 60)

# Check if we found the case with red flag (store 80967)
red_flag_cases = [c for c in cases if c.get('has_red_flag')]
print(f"[CHECK] Cases with RED FLAG: {len(red_flag_cases)}")
if red_flag_cases:
    print(f"  -> Store {red_flag_cases[0]['store']} (Expected: 80967)")

# Check if we found email verified cases
email_verified_cases = [c for c in cases if c.get('email_verified')]
print(f"[CHECK] Cases with email verified: {len(email_verified_cases)}")

# Check if we found draft status
draft_moved = [c for c in cases if c.get('draft_status') == 'moved']
draft_not_found = [c for c in cases if c.get('draft_status') == 'not_found']
print(f"[CHECK] Cases with draft moved: {len(draft_moved)}")
print(f"[CHECK] Cases with draft not found: {len(draft_not_found)}")

# Check increments vs duplicates
increments = [d for d in duplicates if d['is_increment']]
true_duplicates = [d for d in duplicates if not d['is_increment']]
print(f"[CHECK] Increments: {len(increments)}")
print(f"[CHECK] True Duplicates: {len(true_duplicates)}")

print("\n" + "=" * 60)
print("TEST COMPLETE!")
print("=" * 60)
