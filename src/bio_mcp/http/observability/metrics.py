"""Metrics collection and export."""

import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any


class MetricsCollector:
    """Collect and aggregate metrics."""
    
    def __init__(self, max_labels: int = 1000):
        self.max_labels = max_labels
        self.label_count = 0
        
        # Counters
        self.request_counts = defaultdict(lambda: defaultdict(int))
        self.error_counts = defaultdict(lambda: defaultdict(int))
        
        # Histograms (store all values for percentile calculation)
        self.latencies = defaultdict(list)
        
        # Gauges
        self.inflight_requests = defaultdict(int)
    
    def increment_request(self, tool: str, status: str):
        """Increment request counter."""
        if self.label_count < self.max_labels:
            self.request_counts[tool][status] += 1
            self.label_count += 1
    
    def increment_error(self, tool: str, error_code: str):
        """Increment error counter."""
        if self.label_count < self.max_labels:
            self.error_counts[tool][error_code] += 1
            self.label_count += 1
    
    def record_latency(self, tool: str, latency_ms: float):
        """Record latency measurement."""
        self.latencies[tool].append(latency_ms)
    
    def increment_inflight(self, tool: str):
        """Increment inflight requests gauge."""
        self.inflight_requests[tool] += 1
    
    def decrement_inflight(self, tool: str):
        """Decrement inflight requests gauge."""
        if self.inflight_requests[tool] > 0:
            self.inflight_requests[tool] -= 1
    
    def _calculate_percentile(self, values: list[float], percentile: float) -> float:
        """Calculate percentile from list of values."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = (len(sorted_values) - 1) * percentile / 100
        lower = math.floor(index)
        upper = math.ceil(index)
        
        if lower == upper:
            return sorted_values[int(index)]
        
        # Linear interpolation
        return sorted_values[lower] * (upper - index) + sorted_values[upper] * (index - lower)
    
    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics snapshot."""
        metrics = {
            "bio_mcp_requests_total": dict(self.request_counts),
            "bio_mcp_errors_total": dict(self.error_counts),
            "bio_mcp_inflight_requests": dict(self.inflight_requests),
            "bio_mcp_latency_ms": {}
        }
        
        # Calculate histogram statistics
        for tool, latencies in self.latencies.items():
            if latencies:
                metrics["bio_mcp_latency_ms"][tool] = {
                    "count": len(latencies),
                    "sum": sum(latencies),
                    "mean": sum(latencies) / len(latencies),
                    "p50": self._calculate_percentile(latencies, 50),
                    "p95": self._calculate_percentile(latencies, 95),
                    "p99": self._calculate_percentile(latencies, 99),
                }
        
        return metrics


class PrometheusExporter:
    """Export metrics in Prometheus format."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def export(self) -> str:
        """Export metrics as Prometheus text."""
        lines = []
        metrics = self.collector.get_metrics()
        
        # Export request counters
        if metrics["bio_mcp_requests_total"]:
            lines.append("# HELP bio_mcp_requests_total Total number of requests")
            lines.append("# TYPE bio_mcp_requests_total counter")
            for tool, statuses in metrics["bio_mcp_requests_total"].items():
                for status, count in statuses.items():
                    lines.append(f'bio_mcp_requests_total{{tool="{tool}",status="{status}"}} {count}')
        
        # Export error counters
        if metrics["bio_mcp_errors_total"]:
            lines.append("# HELP bio_mcp_errors_total Total number of errors")
            lines.append("# TYPE bio_mcp_errors_total counter")
            for tool, errors in metrics["bio_mcp_errors_total"].items():
                for error_code, count in errors.items():
                    lines.append(f'bio_mcp_errors_total{{tool="{tool}",error_code="{error_code}"}} {count}')
        
        # Export latency histograms
        if metrics["bio_mcp_latency_ms"]:
            lines.append("# HELP bio_mcp_latency_ms Request latency in milliseconds")
            lines.append("# TYPE bio_mcp_latency_ms histogram")
            for tool, stats in metrics["bio_mcp_latency_ms"].items():
                lines.append(f'bio_mcp_latency_ms_count{{tool="{tool}"}} {stats["count"]}')
                lines.append(f'bio_mcp_latency_ms_sum{{tool="{tool}"}} {stats["sum"]}')
                # Add percentile buckets
                for percentile in ["p50", "p95", "p99"]:
                    if percentile in stats:
                        quantile = percentile[1:] + ".0"  # p50 -> 50.0
                        lines.append(f'bio_mcp_latency_ms{{tool="{tool}",quantile="0.{quantile[:-2]}"}} {stats[percentile]}')
        
        # Export inflight gauges
        if metrics["bio_mcp_inflight_requests"]:
            lines.append("# HELP bio_mcp_inflight_requests Number of inflight requests")
            lines.append("# TYPE bio_mcp_inflight_requests gauge")
            for tool, count in metrics["bio_mcp_inflight_requests"].items():
                lines.append(f'bio_mcp_inflight_requests{{tool="{tool}"}} {count}')
        
        return "\n".join(lines)


class CloudWatchEMFExporter:
    """Export metrics in CloudWatch EMF format."""
    
    def __init__(self, collector: MetricsCollector, namespace: str):
        self.collector = collector
        self.namespace = namespace
    
    def export(self) -> str:
        """Export metrics as CloudWatch EMF JSON."""
        metrics = self.collector.get_metrics()
        
        emf_metrics = []
        dimensions = []
        properties = {}
        
        # Add request count metrics
        for tool, statuses in metrics.get("bio_mcp_requests_total", {}).items():
            for status, count in statuses.items():
                emf_metrics.append({
                    "Name": "RequestCount",
                    "Unit": "Count"
                })
                properties["RequestCount"] = count
                properties["Tool"] = tool
                properties["Status"] = status
                if ["Tool", "Status"] not in dimensions:
                    dimensions.append(["Tool", "Status"])
        
        # Add latency metrics
        for tool, stats in metrics.get("bio_mcp_latency_ms", {}).items():
            if stats:
                emf_metrics.append({
                    "Name": "Latency",
                    "Unit": "Milliseconds"
                })
                properties["Latency"] = stats.get("mean", 0)
                properties["Tool"] = tool
                if ["Tool"] not in dimensions:
                    dimensions.append(["Tool"])
        
        emf = {
            "_aws": {
                "Timestamp": int(datetime.now(UTC).timestamp() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": self.namespace,
                        "Dimensions": dimensions,
                        "Metrics": emf_metrics
                    }
                ]
            }
        }
        emf.update(properties)
        
        return json.dumps(emf)


# Global singleton instance
_global_collector = None


def get_global_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector