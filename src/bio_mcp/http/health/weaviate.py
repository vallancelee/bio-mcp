"""Weaviate health checker implementation."""

import time

import weaviate

from bio_mcp.http.health.interface import HealthChecker, HealthCheckResult


class WeaviateHealthChecker(HealthChecker):
    """Weaviate connectivity and schema health checker."""
    
    def __init__(self, weaviate_url: str, timeout_seconds: float = 5.0):
        """Initialize Weaviate health checker.
        
        Args:
            weaviate_url: Weaviate connection URL
            timeout_seconds: Timeout for health checks
            
        Raises:
            ValueError: If Weaviate URL is invalid
        """
        if not weaviate_url or not weaviate_url.startswith(('http://', 'https://')):
            raise ValueError("Invalid Weaviate URL")
        
        self.weaviate_url = weaviate_url
        self._timeout_seconds = timeout_seconds
        self._required_classes = ["PubmedDocument"]  # Expected schema classes
    
    @property
    def name(self) -> str:
        """Name of this health checker."""
        return "weaviate"
    
    @property
    def timeout_seconds(self) -> float:
        """Timeout for Weaviate health checks."""
        return self._timeout_seconds
    
    async def check_health(self) -> HealthCheckResult:
        """Check Weaviate connectivity and schema status.
        
        Returns:
            HealthCheckResult with Weaviate health status
        """
        start_time = time.time()
        
        try:
            # Connect to Weaviate
            async with weaviate.connect_to_weaviate_cloud(
                cluster_url=self.weaviate_url
            ) as client:
                # Check if Weaviate is live and ready
                is_live = await client.is_live()
                is_ready = await client.is_ready()
                
                if not is_live:
                    raise Exception("Weaviate is not live")
                if not is_ready:
                    raise Exception("Weaviate is not ready")
                
                # Check cluster status
                cluster_status = await self._check_cluster_status(client)
                
                # Check schema
                schema_status = await self._check_schema_status(client)
                
                duration_ms = (time.time() - start_time) * 1000
                
                # Determine overall health
                if cluster_status["healthy"] and schema_status["healthy"]:
                    return HealthCheckResult(
                        healthy=True,
                        message="Weaviate connection healthy and schema complete",
                        details={
                            "cluster_status": "healthy",
                            "schema_classes": schema_status["classes"],
                            "nodes": cluster_status["nodes"]
                        },
                        check_duration_ms=duration_ms,
                        checker_name=self.name
                    )
                elif cluster_status["healthy"]:
                    return HealthCheckResult(
                        healthy=False,
                        message="Weaviate cluster healthy but schema incomplete",
                        details={
                            "cluster_status": "healthy",
                            "schema_classes": schema_status["classes"],
                            "missing_classes": schema_status["missing_classes"],
                            "nodes": cluster_status["nodes"]
                        },
                        check_duration_ms=duration_ms,
                        checker_name=self.name
                    )
                else:
                    return HealthCheckResult(
                        healthy=False,
                        message="Weaviate cluster unhealthy",
                        details={
                            "cluster_status": "unhealthy",
                            "nodes": cluster_status["nodes"]
                        },
                        check_duration_ms=duration_ms,
                        checker_name=self.name
                    )
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                healthy=False,
                message=f"Weaviate health check failed: {e!s}",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                check_duration_ms=duration_ms,
                checker_name=self.name
            )
    
    async def _check_cluster_status(self, client) -> dict[str, any]:
        """Check Weaviate cluster health.
        
        Args:
            client: Weaviate client instance
            
        Returns:
            Dict with cluster status information
        """
        try:
            nodes_status = await client.cluster.get_nodes_status()
            nodes = nodes_status.get("nodes", [])
            
            healthy_nodes = [
                node for node in nodes 
                if node.get("status", "").upper() == "HEALTHY"
            ]
            
            return {
                "healthy": len(healthy_nodes) == len(nodes) and len(nodes) > 0,
                "nodes": nodes,
                "healthy_count": len(healthy_nodes),
                "total_count": len(nodes)
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "nodes": [],
                "error": str(e)
            }
    
    async def _check_schema_status(self, client) -> dict[str, any]:
        """Check Weaviate schema completeness.
        
        Args:
            client: Weaviate client instance
            
        Returns:
            Dict with schema status information
        """
        try:
            schema = await client.schema.get()
            existing_classes = [
                cls.get("class", "") for cls in schema.get("classes", [])
            ]
            
            missing_classes = [
                cls for cls in self._required_classes 
                if cls not in existing_classes
            ]
            
            return {
                "healthy": len(missing_classes) == 0,
                "classes": existing_classes,
                "missing_classes": missing_classes,
                "required_classes": self._required_classes
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "classes": [],
                "missing_classes": self._required_classes,
                "error": str(e)
            }