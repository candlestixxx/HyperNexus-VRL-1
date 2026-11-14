"""
HyperNexus VRL-1: Real-Time Telemetry & Metric Aggregator
Tracks request volumes, routing latencies, tenant distribution, and error stats.
"""

import time
import threading
from typing import Dict, Any, List

class GatewayTelemetryTracker:
    def __init__(self):
        self.start_time = time.time()
        self.total_requests = 0
        self.total_errors = 0
        self.total_latency_ms = 0.0
        self.tenant_request_counts: Dict[str, int] = {}
        self.recent_events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def record_request(self, company_id: str, path: str, status_code: int, latency_ms: float):
        with self._lock:
            self.total_requests += 1
            if status_code >= 400:
                self.total_errors += 1
            self.total_latency_ms += latency_ms
            self.tenant_request_counts[company_id] = self.tenant_request_counts.get(company_id, 0) + 1
            
            event = {
                "timestamp": time.time(),
                "company_id": company_id,
                "path": path,
                "status_code": status_code,
                "latency_ms": round(latency_ms, 2)
            }
            self.recent_events.insert(0, event)
            if len(self.recent_events) > 100:
                self.recent_events.pop()

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.time() - self.start_time
            avg_lat = (self.total_latency_ms / self.total_requests) if self.total_requests > 0 else 0.0
            error_rate = (self.total_errors / self.total_requests * 100.0) if self.total_requests > 0 else 0.0
            return {
                "uptime_seconds": round(uptime, 1),
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "error_rate_pct": round(error_rate, 2),
                "avg_latency_ms": round(avg_lat, 2),
                "tenant_traffic": dict(self.tenant_request_counts),
                "recent_events": list(self.recent_events[:20])
            }

telemetry_tracker = GatewayTelemetryTracker()
