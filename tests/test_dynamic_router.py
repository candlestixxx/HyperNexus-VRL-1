"""
Unit Tests for Dynamic Tenant Router & Rate Limiting.
"""

import pytest
import time
from src.router.dynamic_router import TokenBucketRateLimiter

def test_token_bucket_rate_limiter():
    limiter = TokenBucketRateLimiter()
    tenant = "test_tenant"
    
    # Bucket capacity 5, refill rate 1 per sec
    # First 5 should succeed
    for _ in range(5):
        assert limiter.is_allowed(tenant, rate_per_sec=1.0, capacity=5.0) is True

    # 6th immediate call should fail
    assert limiter.is_allowed(tenant, rate_per_sec=1.0, capacity=5.0) is False

    # Simulate waiting 1.1 seconds for refill
    time.sleep(1.1)
    assert limiter.is_allowed(tenant, rate_per_sec=1.0, capacity=5.0) is True
