#!/usr/bin/env python3
"""
Example usage of the new make_all_lyric_baselines function.

This demonstrates how to use the new function that processes all victory odes
and provides comprehensive statistics about the baseline generation process.
"""

from src.baseline import make_all_lyric_baselines

# Example 1: Generate all lyric baselines with summary statistics
print("=== Generating all lyric baselines ===")
stats = make_all_lyric_baselines()

# Example 2: Access individual statistics if needed
if stats:
    print("\n=== Additional analysis ===")
    print(f"Corpus composition: {stats['pindar_lines'] / stats['total_lines'] * 100:.1f}% Pindar, {stats['external_lines'] / stats['total_lines'] * 100:.1f}% external")
    print(f"Modification rate: {(stats['trimmed_lines'] + stats['padded_lines']) / stats['total_lines'] * 100:.1f}% of lines were modified")

# Example 3: Using the original function for individual responsions
from src.baseline import make_lyric_baseline

print("\n=== Generating single baseline for demonstration ===")
individual_stats = make_lyric_baseline("data/compiled/triads/ht_olympians_triads.xml", "ol01", debug=True)
print(f"Stats for ol01: {individual_stats}")