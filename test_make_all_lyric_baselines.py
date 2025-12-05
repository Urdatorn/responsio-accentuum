#!/usr/bin/env python3
"""
Test script for the new make_all_lyric_baselines function.
"""

from tqdm import tqdm
from src.baseline import make_all_lyric_baselines

if __name__ == "__main__":
    print("Testing make_all_lyric_baselines function...")
    
    # Run the function
    stats = make_all_lyric_baselines()
    
    print("\nTest completed!")
    if stats:
        print(f"Function returned statistics: {stats}")
    else:
        print("Function returned None - check for errors")