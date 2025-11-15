"""
Test script for Compromise Mode

This script demonstrates how the compromise mode works with example scenarios.
Run this to verify the compromise mode logic without needing a full app context.
"""

from compromise_mode import CompromiseMode


def test_compromise_mode():
    """Test the CompromiseMode class with various scenarios."""
    
    print("=" * 60)
    print("Testing Compromise Mode")
    print("=" * 60)
    
    # Test 1: Basic threshold reduction
    print("\n[Test 1] Basic threshold reduction from 70%")
    print("-" * 60)
    compromise = CompromiseMode(initial_threshold=70)
    
    print(f"Initial state: {compromise.get_status()}")
    
    iteration = 1
    while compromise.should_continue():
        new_threshold = compromise.reduce_threshold()
        print(f"Iteration {iteration}: Threshold reduced to {new_threshold}%")
        iteration += 1
        
        # Simulate finding results at 55%
        if new_threshold == 55:
            print(f"✓ Results found at {new_threshold}%!")
            break
    
    print(f"Final state: {compromise.get_status()}")
    
    # Test 2: Reaching minimum threshold
    print("\n[Test 2] Reaching minimum threshold (30%)")
    print("-" * 60)
    compromise2 = CompromiseMode(initial_threshold=70)
    
    iteration = 1
    while compromise2.should_continue():
        new_threshold = compromise2.reduce_threshold()
        print(f"Iteration {iteration}: Threshold reduced to {new_threshold}%")
        iteration += 1
    
    print(f"✓ Reached minimum threshold: {compromise2.current_threshold}%")
    print(f"Final state: {compromise2.get_status()}")
    
    # Test 3: Result limiting
    print("\n[Test 3] Result limiting in compromise mode")
    print("-" * 60)
    compromise3 = CompromiseMode(initial_threshold=70)
    compromise3.reduce_threshold()  # Activate compromise mode
    
    mock_results = [f"Result {i}" for i in range(1, 11)]  # 10 results
    print(f"Original results count: {len(mock_results)}")
    
    limited_results = compromise3.limit_results(mock_results)
    print(f"Limited results count: {len(limited_results)}")
    print(f"Limited results: {limited_results}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_compromise_mode()
