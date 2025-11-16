#!/usr/bin/env python3
"""
Simple script to check current memory usage of the application.
Useful for debugging memory issues in production.

Usage:
    python scripts/check_memory.py
"""

import psutil
import os
import sys

def format_bytes(bytes_value):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"

def check_memory():
    """Check and display memory usage information."""
    try:
        # Get current process
        process = psutil.Process(os.getpid())
        
        # Memory info
        mem_info = process.memory_info()
        
        print("=" * 60)
        print("MEMORY USAGE REPORT")
        print("=" * 60)
        print(f"\nProcess ID: {process.pid}")
        print(f"Process Name: {process.name()}")
        print(f"\nMemory Usage:")
        print(f"  RSS (Resident Set Size): {format_bytes(mem_info.rss)}")
        print(f"  VMS (Virtual Memory Size): {format_bytes(mem_info.vms)}")
        
        # Memory percentage
        mem_percent = process.memory_percent()
        print(f"  Percentage of total RAM: {mem_percent:.2f}%")
        
        # System memory
        sys_mem = psutil.virtual_memory()
        print(f"\nSystem Memory:")
        print(f"  Total: {format_bytes(sys_mem.total)}")
        print(f"  Available: {format_bytes(sys_mem.available)}")
        print(f"  Used: {format_bytes(sys_mem.used)} ({sys_mem.percent}%)")
        
        # Warning thresholds
        rss_mb = mem_info.rss / (1024 * 1024)
        print(f"\n{'=' * 60}")
        print("STATUS CHECK")
        print("=" * 60)
        
        if rss_mb < 150:
            print("✅ GOOD: Memory usage is low (< 150 MB)")
            print("   Semantic search model is likely not loaded yet.")
        elif rss_mb < 450:
            print("⚠️  MODERATE: Memory usage is moderate (150-450 MB)")
            print("   Semantic search model may be loaded.")
        elif rss_mb < 512:
            print("⚠️  HIGH: Memory usage is high (450-512 MB)")
            print("   Close to 512MB limit. Monitor closely.")
        else:
            print("❌ CRITICAL: Memory usage exceeds 512 MB!")
            print("   Risk of out-of-memory errors.")
            print("   Consider upgrading instance or disabling semantic search.")
        
        print("=" * 60)
        
        return rss_mb
        
    except Exception as e:
        print(f"Error checking memory: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_memory()
