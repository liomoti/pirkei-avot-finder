"""
Rate Limiting Monitor Script

This script helps monitor rate limiting and cache performance.
Run it while the Flask app is running to see real-time statistics.

Usage:
    python scripts/monitor_rate_limits.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime


def print_header():
    """Print monitoring header."""
    print("\n" + "="*70)
    print("  Rate Limiting & Cache Monitor - פרקי אבות")
    print("="*70)
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")


def print_stats(rate_limiter, search_cache):
    """Print current statistics."""
    cache_stats = search_cache.get_stats()
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Current Status:")
    print("-" * 70)
    
    # Cache statistics
    print(f"📦 Cache:")
    print(f"   Size: {cache_stats['size']}/{cache_stats['max_size']}")
    print(f"   TTL: {cache_stats['ttl_seconds']} seconds")
    
    if cache_stats['size'] > 0:
        usage_percent = (cache_stats['size'] / cache_stats['max_size']) * 100
        print(f"   Usage: {usage_percent:.1f}%")
        
        # Visual bar
        bar_length = 30
        filled = int(bar_length * usage_percent / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"   [{bar}]")
    
    # Rate limiter statistics
    print(f"\n🚦 Rate Limiter:")
    print(f"   Active IPs: {len(rate_limiter.requests)}")
    
    if rate_limiter.requests:
        print(f"   Recent activity:")
        for ip, timestamps in list(rate_limiter.requests.items())[:5]:
            recent_count = len([t for t in timestamps if time.time() - t < 60])
            print(f"      {ip}: {recent_count} requests in last minute")
    
    print("-" * 70)


def monitor_loop():
    """Main monitoring loop."""
    try:
        from utils.rate_limiter import rate_limiter
        from utils.search_cache import search_cache
        
        print_header()
        print("Monitoring... (Press Ctrl+C to stop)\n")
        
        while True:
            print_stats(rate_limiter, search_cache)
            time.sleep(5)  # Update every 5 seconds
            
    except KeyboardInterrupt:
        print("\n\n✋ Monitoring stopped by user")
        print("="*70)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


def show_recommendations(rate_limiter, search_cache):
    """Show optimization recommendations."""
    cache_stats = search_cache.get_stats()
    
    print("\n💡 Recommendations:")
    print("-" * 70)
    
    # Cache recommendations
    if cache_stats['size'] >= cache_stats['max_size'] * 0.9:
        print("⚠️  Cache is almost full (>90%)")
        print("   Consider increasing max_size in search_cache.py")
    
    if cache_stats['size'] < cache_stats['max_size'] * 0.1:
        print("ℹ️  Cache usage is low (<10%)")
        print("   This is normal for low traffic")
    
    # Rate limiter recommendations
    if len(rate_limiter.requests) > 50:
        print("⚠️  Many active IPs (>50)")
        print("   Consider implementing Redis-based rate limiting")
    
    if len(rate_limiter.requests) == 0:
        print("ℹ️  No recent requests")
        print("   System is idle")
    
    print("-" * 70)


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # Single snapshot mode
        try:
            from utils.rate_limiter import rate_limiter
            from utils.search_cache import search_cache
            
            print_header()
            print_stats(rate_limiter, search_cache)
            show_recommendations(rate_limiter, search_cache)
            print()
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print("Make sure the Flask app is running!")
    else:
        # Continuous monitoring mode
        monitor_loop()


if __name__ == '__main__':
    main()
