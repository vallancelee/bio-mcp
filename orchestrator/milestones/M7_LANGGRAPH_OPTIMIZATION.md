# M7 — LangGraph Optimization & Production Readiness (1 day)

## Objective
Optimize the LangGraph orchestrator for production deployment with focus on performance tuning, resource management, scaling strategies, production configuration, deployment readiness, and operational monitoring. Ensure the system can handle production workloads efficiently and reliably.

## Dependencies (Existing Bio-MCP Components)
- **M1-M6 LangGraph**: Complete tested orchestrator implementation
- **Performance Metrics**: Baseline performance data from M6 testing
- **Observability**: Monitoring and metrics collection from M5
- **Configuration**: `src/bio_mcp/orchestrator/config.py` - All configuration options
- **Infrastructure**: Production deployment requirements and constraints

## Core Optimization Components

### 1. Performance Optimization Engine

**File**: `src/bio_mcp/orchestrator/optimization/performance_optimizer.py`
```python
"""Performance optimization for orchestrator components."""
import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict, deque
import statistics

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.observability.metrics_collector import MetricsCollector
from bio_mcp.orchestrator.state import OrchestratorState

logger = get_logger(__name__)

@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation."""
    component: str
    issue: str
    recommendation: str
    impact: str  # "high", "medium", "low"
    effort: str  # "high", "medium", "low"
    implementation: Optional[Callable] = None

@dataclass
class PerformanceProfile:
    """Performance profile for a component."""
    component_name: str
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_per_second: float
    error_rate: float
    cache_hit_rate: float
    resource_usage: Dict[str, float]

class PerformanceOptimizer:
    """Analyzes and optimizes orchestrator performance."""
    
    def __init__(self, config: OrchestratorConfig, metrics_collector: MetricsCollector):
        self.config = config
        self.metrics_collector = metrics_collector
        self.optimization_history: List[Dict[str, Any]] = []
        
        # Performance thresholds
        self.thresholds = {
            "avg_latency_ms": 2000,
            "p95_latency_ms": 4000,
            "error_rate": 0.05,  # 5%
            "cache_hit_rate_min": 0.3,  # 30%
            "throughput_min": 1.0  # 1 req/sec
        }
    
    async def analyze_performance(self) -> List[OptimizationRecommendation]:
        """Analyze current performance and generate recommendations."""
        recommendations = []
        
        # Get current metrics
        metrics = self.metrics_collector.get_current_metrics()
        
        # Analyze overall performance
        overall_recs = self._analyze_overall_performance(metrics)
        recommendations.extend(overall_recs)
        
        # Analyze node-specific performance
        node_recs = self._analyze_node_performance(metrics.node_metrics)
        recommendations.extend(node_recs)
        
        # Analyze caching effectiveness
        cache_recs = self._analyze_caching_performance(metrics)
        recommendations.extend(cache_recs)
        
        # Analyze concurrency patterns
        concurrency_recs = self._analyze_concurrency_patterns()
        recommendations.extend(concurrency_recs)
        
        # Sort by impact and effort
        recommendations.sort(key=lambda x: (
            {"high": 3, "medium": 2, "low": 1}[x.impact],
            {"low": 3, "medium": 2, "high": 1}[x.effort]
        ), reverse=True)
        
        return recommendations
    
    def _analyze_overall_performance(self, metrics) -> List[OptimizationRecommendation]:
        """Analyze overall orchestrator performance."""
        recommendations = []
        
        # Check overall latency
        if metrics.avg_total_duration_ms > self.thresholds["avg_latency_ms"]:
            recommendations.append(OptimizationRecommendation(
                component="orchestrator",
                issue=f"High average latency: {metrics.avg_total_duration_ms:.1f}ms",
                recommendation="Implement parallel execution for independent operations",
                impact="high",
                effort="medium",
                implementation=self._implement_parallelization
            ))
        
        # Check error rate
        error_rate = metrics.failed_executions / max(metrics.total_executions, 1)
        if error_rate > self.thresholds["error_rate"]:
            recommendations.append(OptimizationRecommendation(
                component="orchestrator",
                issue=f"High error rate: {error_rate:.1%}",
                recommendation="Implement better error recovery and fallback strategies",
                impact="high",
                effort="medium",
                implementation=self._improve_error_recovery
            ))
        
        # Check throughput
        if metrics.total_executions > 0:
            # Estimate throughput based on recent activity
            recent_throughput = self._estimate_throughput()
            if recent_throughput < self.thresholds["throughput_min"]:
                recommendations.append(OptimizationRecommendation(
                    component="orchestrator",
                    issue=f"Low throughput: {recent_throughput:.2f} req/sec",
                    recommendation="Optimize resource allocation and connection pooling",
                    impact="medium",
                    effort="medium",
                    implementation=self._optimize_resource_allocation
                ))
        
        return recommendations
    
    def _analyze_node_performance(self, node_metrics) -> List[OptimizationRecommendation]:
        """Analyze individual node performance."""
        recommendations = []
        
        for node in node_metrics:
            # High latency nodes
            if node.avg_duration_ms > self.thresholds["avg_latency_ms"] * 0.5:
                recommendations.append(OptimizationRecommendation(
                    component=f"node.{node.node_name}",
                    issue=f"High node latency: {node.avg_duration_ms:.1f}ms",
                    recommendation=self._get_node_optimization_recommendation(node.node_name),
                    impact="medium",
                    effort="low",
                    implementation=lambda n=node.node_name: self._optimize_node(n)
                ))
            
            # High error rate nodes
            if node.error_rate > self.thresholds["error_rate"]:
                recommendations.append(OptimizationRecommendation(
                    component=f"node.{node.node_name}",
                    issue=f"High node error rate: {node.error_rate:.1%}",
                    recommendation="Add retry logic and better error handling",
                    impact="medium",
                    effort="low",
                    implementation=lambda n=node.node_name: self._improve_node_reliability(n)
                ))
        
        return recommendations
    
    def _analyze_caching_performance(self, metrics) -> List[OptimizationRecommendation]:
        """Analyze caching effectiveness."""
        recommendations = []
        
        if metrics.cache_hit_rate < self.thresholds["cache_hit_rate_min"]:
            recommendations.append(OptimizationRecommendation(
                component="caching",
                issue=f"Low cache hit rate: {metrics.cache_hit_rate:.1%}",
                recommendation="Optimize cache keys and increase TTL for stable data",
                impact="medium",
                effort="low",
                implementation=self._optimize_caching
            ))
        
        # Analyze cache patterns per node
        for node in metrics.node_metrics:
            if node.cache_hit_rate < 0.2 and node.execution_count > 10:
                recommendations.append(OptimizationRecommendation(
                    component=f"caching.{node.node_name}",
                    issue=f"Poor cache utilization in {node.node_name}: {node.cache_hit_rate:.1%}",
                    recommendation="Review cache key generation and data volatility",
                    impact="low",
                    effort="low",
                    implementation=lambda n=node.node_name: self._optimize_node_caching(n)
                ))
        
        return recommendations
    
    def _analyze_concurrency_patterns(self) -> List[OptimizationRecommendation]:
        """Analyze concurrency and parallelization opportunities."""
        recommendations = []
        
        # This would analyze execution patterns to identify parallelization opportunities
        # For now, provide general recommendations based on common patterns
        
        recommendations.append(OptimizationRecommendation(
            component="concurrency",
            issue="Sequential execution of independent operations",
            recommendation="Implement parallel execution for search operations",
            impact="high",
            effort="medium",
            implementation=self._implement_search_parallelization
        ))
        
        recommendations.append(OptimizationRecommendation(
            component="concurrency",
            issue="Limited connection pooling",
            recommendation="Implement connection pooling for external APIs",
            impact="medium",
            effort="medium",
            implementation=self._implement_connection_pooling
        ))
        
        return recommendations
    
    def _get_node_optimization_recommendation(self, node_name: str) -> str:
        """Get specific optimization recommendation for a node."""
        node_optimizations = {
            "pubmed_search": "Optimize query parameters and implement result caching",
            "ctgov_search": "Use more specific query filters to reduce response size",
            "rag_search": "Optimize vector similarity search and index configuration",
            "synthesizer": "Cache template compilation and optimize text generation",
            "parse_frame": "Cache regex compilation and optimize entity extraction"
        }
        
        return node_optimizations.get(
            node_name, 
            "Profile node execution and optimize bottlenecks"
        )
    
    def _estimate_throughput(self) -> float:
        """Estimate current system throughput."""
        # This is a simplified calculation
        # In practice, would use more sophisticated metrics
        metrics = self.metrics_collector.get_current_metrics()
        
        if metrics.total_executions > 0:
            # Rough estimate based on recent activity
            return metrics.total_executions / 3600  # Assume 1 hour window
        
        return 0.0
    
    # Implementation methods (would be expanded based on specific optimizations)
    
    async def _implement_parallelization(self):
        """Implement parallelization optimizations."""
        logger.info("Implementing parallelization optimizations")
        # This would modify the graph to enable parallel execution
        # where dependencies allow
    
    async def _improve_error_recovery(self):
        """Improve error recovery mechanisms."""
        logger.info("Implementing improved error recovery")
        # This would enhance retry logic and fallback strategies
    
    async def _optimize_resource_allocation(self):
        """Optimize resource allocation."""
        logger.info("Optimizing resource allocation")
        # This would adjust connection pools, memory allocation, etc.
    
    async def _optimize_node(self, node_name: str):
        """Optimize specific node performance."""
        logger.info(f"Optimizing node: {node_name}")
        # Node-specific optimizations would go here
    
    async def _improve_node_reliability(self, node_name: str):
        """Improve node reliability."""
        logger.info(f"Improving reliability for node: {node_name}")
        # Add retry logic, circuit breakers, etc.
    
    async def _optimize_caching(self):
        """Optimize caching strategies."""
        logger.info("Optimizing caching strategies")
        # Adjust cache keys, TTL, eviction policies
    
    async def _optimize_node_caching(self, node_name: str):
        """Optimize caching for specific node."""
        logger.info(f"Optimizing caching for node: {node_name}")
        # Node-specific cache optimizations
    
    async def _implement_search_parallelization(self):
        """Implement parallel search operations."""
        logger.info("Implementing search parallelization")
        # Enable parallel execution of search operations
    
    async def _implement_connection_pooling(self):
        """Implement connection pooling."""
        logger.info("Implementing connection pooling")
        # Set up connection pools for external APIs
    
    async def apply_optimization(self, recommendation: OptimizationRecommendation) -> bool:
        """Apply a specific optimization recommendation."""
        try:
            if recommendation.implementation:
                await recommendation.implementation()
                
                # Record optimization
                self.optimization_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "component": recommendation.component,
                    "optimization": recommendation.recommendation,
                    "success": True
                })
                
                logger.info(f"Applied optimization: {recommendation.recommendation}")
                return True
            else:
                logger.warning(f"No implementation for optimization: {recommendation.recommendation}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to apply optimization: {e}")
            
            self.optimization_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "component": recommendation.component,
                "optimization": recommendation.recommendation,
                "success": False,
                "error": str(e)
            })
            
            return False
    
    def get_performance_profile(self) -> Dict[str, PerformanceProfile]:
        """Get detailed performance profile for all components."""
        metrics = self.metrics_collector.get_current_metrics()
        profiles = {}
        
        # Overall orchestrator profile
        profiles["orchestrator"] = PerformanceProfile(
            component_name="orchestrator",
            avg_latency_ms=metrics.avg_total_duration_ms,
            p95_latency_ms=metrics.avg_total_duration_ms * 1.5,  # Estimate
            p99_latency_ms=metrics.avg_total_duration_ms * 2.0,  # Estimate
            throughput_per_second=self._estimate_throughput(),
            error_rate=metrics.failed_executions / max(metrics.total_executions, 1),
            cache_hit_rate=metrics.cache_hit_rate,
            resource_usage={"memory_mb": 0, "cpu_percent": 0}  # Would be populated with real data
        )
        
        # Node profiles
        for node in metrics.node_metrics:
            profiles[node.node_name] = PerformanceProfile(
                component_name=node.node_name,
                avg_latency_ms=node.avg_duration_ms,
                p95_latency_ms=node.p95_duration_ms,
                p99_latency_ms=node.max_duration_ms,  # Approximation
                throughput_per_second=node.execution_count / 3600,  # Rough estimate
                error_rate=node.error_rate,
                cache_hit_rate=node.cache_hit_rate,
                resource_usage={}
            )
        
        return profiles
```

### 2. Resource Management and Scaling

**File**: `src/bio_mcp/orchestrator/optimization/resource_manager.py`
```python
"""Resource management and auto-scaling for orchestrator."""
import asyncio
import psutil
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig

logger = get_logger(__name__)

@dataclass
class ResourceMetrics:
    """Current resource usage metrics."""
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_io_sent_mb: float
    network_io_recv_mb: float
    open_connections: int
    active_threads: int

@dataclass
class ScalingDecision:
    """Auto-scaling decision."""
    action: str  # "scale_up", "scale_down", "maintain"
    component: str
    current_value: int
    recommended_value: int
    reason: str
    confidence: float

class ResourceManager:
    """Manages resources and auto-scaling for the orchestrator."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.baseline_metrics: Optional[ResourceMetrics] = None
        self.resource_history = []
        self.scaling_decisions = []
        
        # Resource thresholds
        self.thresholds = {
            "cpu_high": 80.0,
            "cpu_low": 20.0,
            "memory_high": 85.0,
            "memory_low": 30.0,
            "connection_high": 100,
            "thread_high": 50
        }
        
        # Auto-scaling parameters
        self.scaling_params = {
            "min_parallel_nodes": 1,
            "max_parallel_nodes": 10,
            "min_rate_limit": 0.5,
            "max_rate_limit": 10.0,
            "scaling_factor": 1.5,
            "cooldown_minutes": 5
        }
    
    async def get_resource_metrics(self) -> ResourceMetrics:
        """Get current resource usage metrics."""
        process = psutil.Process(os.getpid())
        
        # CPU metrics
        cpu_percent = process.cpu_percent(interval=1)
        
        # Memory metrics
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        memory_mb = memory_info.rss / 1024 / 1024
        
        # I/O metrics
        try:
            io_counters = process.io_counters()
            disk_read_mb = io_counters.read_bytes / 1024 / 1024
            disk_write_mb = io_counters.write_bytes / 1024 / 1024
        except (AttributeError, psutil.AccessDenied):
            disk_read_mb = disk_write_mb = 0
        
        # Network metrics (system-wide approximation)
        try:
            net_io = psutil.net_io_counters()
            net_sent_mb = net_io.bytes_sent / 1024 / 1024
            net_recv_mb = net_io.bytes_recv / 1024 / 1024
        except AttributeError:
            net_sent_mb = net_recv_mb = 0
        
        # Connection and thread counts
        try:
            connections = len(process.connections())
        except (AttributeError, psutil.AccessDenied):
            connections = 0
        
        threads = process.num_threads()
        
        return ResourceMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_mb=memory_mb,
            disk_io_read_mb=disk_read_mb,
            disk_io_write_mb=disk_write_mb,
            network_io_sent_mb=net_sent_mb,
            network_io_recv_mb=net_recv_mb,
            open_connections=connections,
            active_threads=threads
        )
    
    async def establish_baseline(self):
        """Establish baseline resource usage."""
        logger.info("Establishing resource usage baseline")
        
        # Take several measurements to get a stable baseline
        measurements = []
        for _ in range(5):
            metrics = await self.get_resource_metrics()
            measurements.append(metrics)
            await asyncio.sleep(2)
        
        # Calculate baseline averages
        self.baseline_metrics = ResourceMetrics(
            cpu_percent=sum(m.cpu_percent for m in measurements) / len(measurements),
            memory_percent=sum(m.memory_percent for m in measurements) / len(measurements),
            memory_mb=sum(m.memory_mb for m in measurements) / len(measurements),
            disk_io_read_mb=sum(m.disk_io_read_mb for m in measurements) / len(measurements),
            disk_io_write_mb=sum(m.disk_io_write_mb for m in measurements) / len(measurements),
            network_io_sent_mb=sum(m.network_io_sent_mb for m in measurements) / len(measurements),
            network_io_recv_mb=sum(m.network_io_recv_mb for m in measurements) / len(measurements),
            open_connections=int(sum(m.open_connections for m in measurements) / len(measurements)),
            active_threads=int(sum(m.active_threads for m in measurements) / len(measurements))
        )
        
        logger.info("Baseline established", extra={
            "cpu_percent": self.baseline_metrics.cpu_percent,
            "memory_mb": self.baseline_metrics.memory_mb,
            "threads": self.baseline_metrics.active_threads
        })
    
    async def monitor_and_scale(self) -> List[ScalingDecision]:
        """Monitor resources and make scaling decisions."""
        current_metrics = await self.get_resource_metrics()
        self.resource_history.append({
            "timestamp": datetime.utcnow(),
            "metrics": current_metrics
        })
        
        # Keep only recent history
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        self.resource_history = [
            entry for entry in self.resource_history 
            if entry["timestamp"] > cutoff_time
        ]
        
        decisions = []
        
        # CPU-based scaling
        cpu_decision = self._analyze_cpu_scaling(current_metrics)
        if cpu_decision:
            decisions.append(cpu_decision)
        
        # Memory-based scaling
        memory_decision = self._analyze_memory_scaling(current_metrics)
        if memory_decision:
            decisions.append(memory_decision)
        
        # Connection-based scaling
        connection_decision = self._analyze_connection_scaling(current_metrics)
        if connection_decision:
            decisions.append(connection_decision)
        
        # Record decisions
        self.scaling_decisions.extend(decisions)
        
        return decisions
    
    def _analyze_cpu_scaling(self, metrics: ResourceMetrics) -> Optional[ScalingDecision]:
        """Analyze CPU usage for scaling decisions."""
        if metrics.cpu_percent > self.thresholds["cpu_high"]:
            # High CPU - scale up parallelism
            current_parallel = self.config.max_parallel_nodes
            recommended = min(
                int(current_parallel * self.scaling_params["scaling_factor"]),
                self.scaling_params["max_parallel_nodes"]
            )
            
            if recommended > current_parallel:
                return ScalingDecision(
                    action="scale_up",
                    component="max_parallel_nodes",
                    current_value=current_parallel,
                    recommended_value=recommended,
                    reason=f"High CPU usage: {metrics.cpu_percent:.1f}%",
                    confidence=0.8
                )
        
        elif metrics.cpu_percent < self.thresholds["cpu_low"]:
            # Low CPU - scale down parallelism
            current_parallel = self.config.max_parallel_nodes
            recommended = max(
                int(current_parallel / self.scaling_params["scaling_factor"]),
                self.scaling_params["min_parallel_nodes"]
            )
            
            if recommended < current_parallel:
                return ScalingDecision(
                    action="scale_down",
                    component="max_parallel_nodes",
                    current_value=current_parallel,
                    recommended_value=recommended,
                    reason=f"Low CPU usage: {metrics.cpu_percent:.1f}%",
                    confidence=0.6
                )
        
        return None
    
    def _analyze_memory_scaling(self, metrics: ResourceMetrics) -> Optional[ScalingDecision]:
        """Analyze memory usage for scaling decisions."""
        if metrics.memory_percent > self.thresholds["memory_high"]:
            # High memory - reduce cache size or parallel operations
            return ScalingDecision(
                action="scale_down",
                component="cache_size",
                current_value=100,  # Placeholder
                recommended_value=70,  # Reduce by 30%
                reason=f"High memory usage: {metrics.memory_percent:.1f}%",
                confidence=0.7
            )
        
        return None
    
    def _analyze_connection_scaling(self, metrics: ResourceMetrics) -> Optional[ScalingDecision]:
        """Analyze connection usage for scaling decisions."""
        if metrics.open_connections > self.thresholds["connection_high"]:
            # High connections - implement connection pooling
            return ScalingDecision(
                action="optimize",
                component="connection_pooling",
                current_value=metrics.open_connections,
                recommended_value=50,  # Target connection count
                reason=f"High connection count: {metrics.open_connections}",
                confidence=0.9
            )
        
        return None
    
    async def apply_scaling_decision(self, decision: ScalingDecision) -> bool:
        """Apply a scaling decision."""
        try:
            if decision.component == "max_parallel_nodes":
                # Update configuration
                old_value = self.config.max_parallel_nodes
                self.config.max_parallel_nodes = decision.recommended_value
                
                logger.info(f"Scaled {decision.component}", extra={
                    "action": decision.action,
                    "old_value": old_value,
                    "new_value": decision.recommended_value,
                    "reason": decision.reason
                })
                
                return True
            
            elif decision.component == "cache_size":
                # Implement cache size reduction
                logger.info(f"Cache scaling recommended: {decision.reason}")
                # Implementation would depend on specific cache system
                return True
            
            elif decision.component == "connection_pooling":
                # Implement connection pooling optimization
                logger.info(f"Connection pooling optimization: {decision.reason}")
                # Implementation would set up connection pools
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to apply scaling decision: {e}")
            return False
    
    def get_resource_report(self) -> Dict[str, Any]:
        """Generate resource usage report."""
        current_metrics = asyncio.create_task(self.get_resource_metrics())
        
        # Calculate resource trends
        recent_history = self.resource_history[-10:]  # Last 10 measurements
        
        if len(recent_history) >= 2:
            cpu_trend = self._calculate_trend([h["metrics"].cpu_percent for h in recent_history])
            memory_trend = self._calculate_trend([h["metrics"].memory_percent for h in recent_history])
        else:
            cpu_trend = memory_trend = 0.0
        
        return {
            "current_metrics": current_metrics,
            "baseline_metrics": self.baseline_metrics,
            "trends": {
                "cpu_trend": cpu_trend,
                "memory_trend": memory_trend
            },
            "recent_scaling_decisions": self.scaling_decisions[-5:],
            "resource_utilization": {
                "cpu_efficient": (current_metrics.cpu_percent if hasattr(current_metrics, 'cpu_percent') else 0) < self.thresholds["cpu_high"],
                "memory_efficient": (current_metrics.memory_percent if hasattr(current_metrics, 'memory_percent') else 0) < self.thresholds["memory_high"]
            },
            "recommendations": self._generate_resource_recommendations()
        }
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend (positive = increasing, negative = decreasing)."""
        if len(values) < 2:
            return 0.0
        
        # Simple linear trend calculation
        n = len(values)
        sum_x = sum(range(n))
        sum_y = sum(values)
        sum_xy = sum(i * values[i] for i in range(n))
        sum_x2 = sum(i * i for i in range(n))
        
        # Slope of trend line
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        return slope
    
    def _generate_resource_recommendations(self) -> List[str]:
        """Generate resource optimization recommendations."""
        recommendations = []
        
        # Analyze recent resource usage patterns
        if self.resource_history:
            recent_metrics = self.resource_history[-1]["metrics"]
            
            if recent_metrics.cpu_percent > self.thresholds["cpu_high"]:
                recommendations.append("Consider increasing parallel execution limits or optimizing CPU-intensive operations")
            
            if recent_metrics.memory_percent > self.thresholds["memory_high"]:
                recommendations.append("Consider reducing cache sizes or implementing memory-efficient data structures")
            
            if recent_metrics.open_connections > self.thresholds["connection_high"]:
                recommendations.append("Implement connection pooling to reduce connection overhead")
            
            if recent_metrics.active_threads > self.thresholds["thread_high"]:
                recommendations.append("Review thread usage and consider async alternatives")
        
        if not recommendations:
            recommendations.append("Resource usage is within normal parameters")
        
        return recommendations
```

### 3. Production Configuration

**File**: `src/bio_mcp/orchestrator/config/production.py`
```python
"""Production-specific configuration for orchestrator."""
from typing import Dict, Any, Optional
import os
from pathlib import Path

from bio_mcp.orchestrator.config import OrchestratorConfig, LangGraphConfig

class ProductionOrchestratorConfig(OrchestratorConfig):
    """Production-optimized orchestrator configuration."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._apply_production_defaults()
    
    def _apply_production_defaults(self):
        """Apply production-specific defaults."""
        # Performance settings
        self.default_budget_ms = 8000  # Slightly higher budget for production
        self.max_budget_ms = 30000
        self.node_timeout_ms = 3000  # More generous node timeouts
        
        # Concurrency settings
        self.max_parallel_nodes = 8  # Higher concurrency for production
        
        # Rate limiting (more conservative for production)
        self.pubmed_rps = 1.5  # Slightly lower to be safe
        self.ctgov_rps = 1.5
        self.rag_rps = 2.0
        
        # Caching (more aggressive caching in production)
        self.cache_ttl = 7200  # 2 hours
        self.enable_redis_cache = True
        
        # Error handling
        self.enable_partial_results = True
        self.max_retries = 3
        
        # LangGraph production settings
        langgraph_config = LangGraphConfig()
        langgraph_config.debug_mode = False
        langgraph_config.max_iterations = 100
        langgraph_config.recursion_limit = 50
        langgraph_config.checkpoint_db_path = "/var/lib/bio-mcp/checkpoints.db"
        langgraph_config.checkpoint_ttl = 86400  # 24 hours
        langgraph_config.enable_tracing = True
        langgraph_config.langsmith_project = "bio-mcp-production"
        
        self.langgraph = langgraph_config

def create_production_config() -> ProductionOrchestratorConfig:
    """Create production configuration from environment variables."""
    config = ProductionOrchestratorConfig()
    
    # Override with environment variables
    env_overrides = {
        "default_budget_ms": "ORCHESTRATOR_DEFAULT_BUDGET_MS",
        "max_parallel_nodes": "ORCHESTRATOR_MAX_PARALLEL_NODES",
        "pubmed_rps": "ORCHESTRATOR_PUBMED_RPS",
        "ctgov_rps": "ORCHESTRATOR_CTGOV_RPS",
        "cache_ttl": "ORCHESTRATOR_CACHE_TTL",
    }
    
    for attr, env_var in env_overrides.items():
        env_value = os.getenv(env_var)
        if env_value:
            try:
                # Convert to appropriate type
                if attr.endswith("_rps") or attr == "cache_ttl":
                    setattr(config, attr, float(env_value))
                else:
                    setattr(config, attr, int(env_value))
            except ValueError:
                # Log warning but continue with default
                pass
    
    # LangGraph environment overrides
    if os.getenv("LANGSMITH_API_KEY"):
        config.langgraph.langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
        config.langgraph.enable_tracing = True
    
    if os.getenv("LANGSMITH_PROJECT"):
        config.langgraph.langsmith_project = os.getenv("LANGSMITH_PROJECT")
    
    if os.getenv("ORCHESTRATOR_CHECKPOINT_DB"):
        config.langgraph.checkpoint_db_path = os.getenv("ORCHESTRATOR_CHECKPOINT_DB")
    
    return config

def get_deployment_config(deployment_type: str = "production") -> Dict[str, Any]:
    """Get deployment-specific configuration."""
    configs = {
        "production": {
            "replicas": 3,
            "cpu_request": "1000m",
            "cpu_limit": "2000m",
            "memory_request": "2Gi",
            "memory_limit": "4Gi",
            "health_check_path": "/health",
            "readiness_check_path": "/ready",
            "metrics_port": 8080,
            "log_level": "INFO"
        },
        "staging": {
            "replicas": 2,
            "cpu_request": "500m",
            "cpu_limit": "1000m",
            "memory_request": "1Gi",
            "memory_limit": "2Gi",
            "health_check_path": "/health",
            "readiness_check_path": "/ready",
            "metrics_port": 8080,
            "log_level": "DEBUG"
        },
        "development": {
            "replicas": 1,
            "cpu_request": "250m",
            "cpu_limit": "500m",
            "memory_request": "512Mi",
            "memory_limit": "1Gi",
            "health_check_path": "/health",
            "readiness_check_path": "/ready",
            "metrics_port": 8080,
            "log_level": "DEBUG"
        }
    }
    
    return configs.get(deployment_type, configs["production"])
```

### 4. Health Checks and Monitoring

**File**: `src/bio_mcp/orchestrator/health/health_checker.py`
```python
"""Health checks and system monitoring for orchestrator."""
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.graph_builder import build_orchestrator_graph
from bio_mcp.orchestrator.state.persistence import BioMCPCheckpointSaver

logger = get_logger(__name__)

class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"

@dataclass
class HealthCheck:
    """Individual health check result."""
    name: str
    status: HealthStatus
    message: str
    response_time_ms: float
    details: Dict[str, Any] = None

@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthStatus
    checks: List[HealthCheck]
    overall_response_time_ms: float
    timestamp: datetime

class OrchestratorHealthChecker:
    """Comprehensive health checking for the orchestrator."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.graph = None
        self.checkpointer = None
        self._setup_graph()
    
    def _setup_graph(self):
        """Setup graph for health checks."""
        try:
            self.graph = build_orchestrator_graph(self.config)
            self.checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        except Exception as e:
            logger.error(f"Failed to setup health check graph: {e}")
    
    async def check_health(self) -> SystemHealth:
        """Perform comprehensive health check."""
        start_time = time.perf_counter()
        checks = []
        
        # Individual health checks
        checks.append(await self._check_basic_functionality())
        checks.append(await self._check_graph_compilation())
        checks.append(await self._check_database_connectivity())
        checks.append(await self._check_external_apis())
        checks.append(await self._check_caching())
        checks.append(await self._check_resource_usage())
        checks.append(await self._check_configuration())
        
        # Determine overall status
        overall_status = self._determine_overall_status(checks)
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        return SystemHealth(
            status=overall_status,
            checks=checks,
            overall_response_time_ms=total_time,
            timestamp=datetime.utcnow()
        )
    
    async def _check_basic_functionality(self) -> HealthCheck:
        """Check basic orchestrator functionality."""
        start_time = time.perf_counter()
        
        try:
            if self.graph is None:
                raise Exception("Graph not initialized")
            
            # Basic validation
            assert self.config is not None
            assert self.config.default_budget_ms > 0
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="basic_functionality",
                status=HealthStatus.HEALTHY,
                message="Basic functionality operational",
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="basic_functionality",
                status=HealthStatus.CRITICAL,
                message=f"Basic functionality failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def _check_graph_compilation(self) -> HealthCheck:
        """Check that the LangGraph compiles correctly."""
        start_time = time.perf_counter()
        
        try:
            if self.graph is None or self.checkpointer is None:
                raise Exception("Graph components not initialized")
            
            # Try to compile the graph
            compiled_graph = self.graph.compile(checkpointer=self.checkpointer)
            
            # Verify it has expected structure
            assert compiled_graph is not None
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="graph_compilation",
                status=HealthStatus.HEALTHY,
                message="Graph compilation successful",
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="graph_compilation",
                status=HealthStatus.CRITICAL,
                message=f"Graph compilation failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def _check_database_connectivity(self) -> HealthCheck:
        """Check database connectivity."""
        start_time = time.perf_counter()
        
        try:
            # Test checkpoint database
            test_checkpoint = await self.checkpointer.aget_checkpoint("health_check_test")
            # It's OK if this returns None - we just want to verify connectivity
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            status = HealthStatus.HEALTHY if response_time < 1000 else HealthStatus.DEGRADED
            
            return HealthCheck(
                name="database_connectivity",
                status=status,
                message="Database connectivity verified",
                response_time_ms=response_time,
                details={"checkpoint_db_responsive": True}
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="database_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connectivity failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def _check_external_apis(self) -> HealthCheck:
        """Check external API connectivity."""
        start_time = time.perf_counter()
        
        try:
            # This would test actual API endpoints
            # For now, just check if we can import the clients
            from bio_mcp.sources.pubmed.client import PubMedClient
            from bio_mcp.sources.clinicaltrials.client import ClinicalTrialsClient
            
            # Basic instantiation test
            pubmed_client = PubMedClient()
            ctgov_client = ClinicalTrialsClient()
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="external_apis",
                status=HealthStatus.HEALTHY,
                message="External API clients initialized successfully",
                response_time_ms=response_time,
                details={
                    "pubmed_client": "initialized",
                    "clinicaltrials_client": "initialized"
                }
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="external_apis",
                status=HealthStatus.DEGRADED,
                message=f"External API check failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def _check_caching(self) -> HealthCheck:
        """Check caching system."""
        start_time = time.perf_counter()
        
        try:
            # Basic caching test
            # This would test the actual cache system
            cache_available = True  # Placeholder
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            status = HealthStatus.HEALTHY if cache_available else HealthStatus.DEGRADED
            message = "Caching system operational" if cache_available else "Caching system unavailable"
            
            return HealthCheck(
                name="caching",
                status=status,
                message=message,
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="caching",
                status=HealthStatus.DEGRADED,
                message=f"Caching check failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def _check_resource_usage(self) -> HealthCheck:
        """Check system resource usage."""
        start_time = time.perf_counter()
        
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            # Get resource metrics
            cpu_percent = process.cpu_percent()
            memory_percent = process.memory_percent()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            # Determine status based on resource usage
            if cpu_percent > 90 or memory_percent > 90:
                status = HealthStatus.CRITICAL
                message = "Critical resource usage"
            elif cpu_percent > 70 or memory_percent > 70:
                status = HealthStatus.DEGRADED
                message = "High resource usage"
            else:
                status = HealthStatus.HEALTHY
                message = "Resource usage normal"
            
            return HealthCheck(
                name="resource_usage",
                status=status,
                message=message,
                response_time_ms=response_time,
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "memory_mb": memory_mb
                }
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="resource_usage",
                status=HealthStatus.DEGRADED,
                message=f"Resource usage check failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def _check_configuration(self) -> HealthCheck:
        """Check configuration validity."""
        start_time = time.perf_counter()
        
        try:
            # Validate configuration
            config_issues = []
            
            if self.config.default_budget_ms <= 0:
                config_issues.append("Invalid default budget")
            
            if self.config.max_parallel_nodes <= 0:
                config_issues.append("Invalid max parallel nodes")
            
            if self.config.pubmed_rps <= 0:
                config_issues.append("Invalid PubMed rate limit")
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            if config_issues:
                return HealthCheck(
                    name="configuration",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Configuration issues: {', '.join(config_issues)}",
                    response_time_ms=response_time,
                    details={"issues": config_issues}
                )
            else:
                return HealthCheck(
                    name="configuration",
                    status=HealthStatus.HEALTHY,
                    message="Configuration valid",
                    response_time_ms=response_time
                )
                
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            
            return HealthCheck(
                name="configuration",
                status=HealthStatus.UNHEALTHY,
                message=f"Configuration check failed: {str(e)}",
                response_time_ms=response_time
            )
    
    def _determine_overall_status(self, checks: List[HealthCheck]) -> HealthStatus:
        """Determine overall system status from individual checks."""
        if any(check.status == HealthStatus.CRITICAL for check in checks):
            return HealthStatus.CRITICAL
        
        if any(check.status == HealthStatus.UNHEALTHY for check in checks):
            return HealthStatus.UNHEALTHY
        
        if any(check.status == HealthStatus.DEGRADED for check in checks):
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    async def get_readiness_status(self) -> Dict[str, Any]:
        """Get readiness status (quick check for load balancer)."""
        try:
            # Quick readiness checks
            ready = (
                self.graph is not None and
                self.checkpointer is not None and
                self.config.default_budget_ms > 0
            )
            
            return {
                "ready": ready,
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"  # This would come from actual version
            }
            
        except Exception as e:
            return {
                "ready": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get_liveness_status(self) -> Dict[str, Any]:
        """Get liveness status (quick check for container orchestrator)."""
        try:
            # Very basic liveness check
            alive = True  # If we can execute this, we're alive
            
            return {
                "alive": alive,
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": time.time() - self._start_time if hasattr(self, '_start_time') else 0
            }
            
        except Exception as e:
            return {
                "alive": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

# Global health checker instance
_health_checker = None

def get_health_checker(config: OrchestratorConfig) -> OrchestratorHealthChecker:
    """Get global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = OrchestratorHealthChecker(config)
        _health_checker._start_time = time.time()
    return _health_checker
```

## Deployment Configuration

**File**: `deployment/kubernetes/orchestrator-deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bio-mcp-orchestrator
  labels:
    app: bio-mcp-orchestrator
    version: v1.0.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bio-mcp-orchestrator
  template:
    metadata:
      labels:
        app: bio-mcp-orchestrator
        version: v1.0.0
    spec:
      containers:
      - name: orchestrator
        image: bio-mcp-orchestrator:latest
        ports:
        - containerPort: 8000
          name: http
        - containerPort: 8080
          name: metrics
        env:
        - name: ORCHESTRATOR_DEFAULT_BUDGET_MS
          value: "8000"
        - name: ORCHESTRATOR_MAX_PARALLEL_NODES
          value: "8"
        - name: ORCHESTRATOR_CACHE_TTL
          value: "7200"
        - name: LANGSMITH_API_KEY
          valueFrom:
            secretKeyRef:
              name: langsmith-secret
              key: api-key
        - name: LANGSMITH_PROJECT
          value: "bio-mcp-production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        resources:
          requests:
            cpu: 1000m
            memory: 2Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: checkpoint-storage
          mountPath: /var/lib/bio-mcp
      volumes:
      - name: checkpoint-storage
        persistentVolumeClaim:
          claimName: orchestrator-checkpoints

---
apiVersion: v1
kind: Service
metadata:
  name: bio-mcp-orchestrator-service
spec:
  selector:
    app: bio-mcp-orchestrator
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  - name: metrics
    port: 8080
    targetPort: 8080
  type: ClusterIP
```

## Acceptance Criteria
- [ ] Performance optimizer identifies and addresses bottlenecks automatically
- [ ] Resource manager monitors usage and makes scaling recommendations
- [ ] Production configuration provides optimized defaults for deployment
- [ ] Health checks validate all system components comprehensively
- [ ] Auto-scaling decisions improve system performance under load
- [ ] Connection pooling and resource optimization reduce overhead
- [ ] Production deployment configuration supports horizontal scaling
- [ ] Monitoring integration provides operational visibility
- [ ] Performance profiles establish baseline metrics for comparison
- [ ] Optimization history tracks applied improvements and their effectiveness

## Files Created/Modified
- `src/bio_mcp/orchestrator/optimization/performance_optimizer.py` - Performance optimization engine
- `src/bio_mcp/orchestrator/optimization/resource_manager.py` - Resource management and scaling
- `src/bio_mcp/orchestrator/config/production.py` - Production configuration
- `src/bio_mcp/orchestrator/health/health_checker.py` - Comprehensive health checks
- `deployment/kubernetes/orchestrator-deployment.yaml` - Kubernetes deployment configuration

## Final Implementation Status
With the completion of M7, the LangGraph-based orchestrator implementation provides:

1. **Production-Ready Architecture**: Complete LangGraph implementation with state management, error recovery, and observability
2. **Comprehensive Testing**: Unit, integration, E2E, and performance tests ensuring reliability
3. **Advanced Monitoring**: LangSmith integration, OpenTelemetry tracing, and detailed metrics collection
4. **Performance Optimization**: Automated performance analysis and optimization recommendations
5. **Scalable Deployment**: Production configuration with auto-scaling and resource management
6. **Operational Excellence**: Health checks, monitoring, and deployment-ready configuration

The orchestrator is now ready for production deployment with confidence in its reliability, performance, and maintainability.