"""Job worker pool for executing jobs asynchronously with concurrency control."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from bio_mcp.http.jobs.models import JobData

logger = logging.getLogger(__name__)


class ToolExecutor(ABC):
    """Abstract interface for tool execution."""

    @abstractmethod
    async def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        """Execute a tool with given parameters."""
        pass


class JobWorker:
    """Worker pool for executing jobs with concurrency control."""

    def __init__(
        self,
        tool_executor: ToolExecutor,
        job_service: Any,  # JobService - avoiding circular import
        max_concurrent_jobs: int = 10,
        poll_interval_seconds: float = 1.0,
    ):
        """Initialize job worker.

        Args:
            tool_executor: Tool execution interface
            job_service: Job service for status updates
            max_concurrent_jobs: Maximum concurrent jobs
            poll_interval_seconds: Interval between polling for new jobs
        """
        self.tool_executor = tool_executor
        self.job_service = job_service
        self.max_concurrent_jobs = max_concurrent_jobs
        self.poll_interval_seconds = poll_interval_seconds

        # Concurrency control
        self.job_semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self.running_jobs: dict[str, asyncio.Task] = {}

        # Worker control
        self.is_running = False
        self._stop_event = asyncio.Event()

    async def execute_job(self, job_data: JobData) -> None:
        """Execute a single job with proper error handling.

        Args:
            job_data: Job to execute
        """
        job_id = job_data.id

        try:
            # Mark job as started
            await self.job_service.start_job(job_id)
            logger.info(f"Started job {job_id}: {job_data.tool_name}")

            # Execute the tool
            result = await self.tool_executor.execute_tool(
                job_data.tool_name, job_data.parameters
            )

            # Mark job as completed
            await self.job_service.complete_job(job_id, result)
            logger.info(f"Completed job {job_id}")

        except Exception as e:
            # Mark job as failed
            error_message = str(e)
            await self.job_service.fail_job(job_id, error_message)
            logger.error(f"Failed job {job_id}: {error_message}")

        finally:
            # Clean up running job tracking
            if job_id in self.running_jobs:
                del self.running_jobs[job_id]

    async def _execute_job_with_semaphore(self, job_data: JobData) -> None:
        """Execute job with semaphore for concurrency control."""
        async with self.job_semaphore:
            await self.execute_job(job_data)

    async def start_worker_pool(self) -> None:
        """Start the worker pool to process pending jobs."""
        self.is_running = True
        self._stop_event.clear()

        logger.info(
            f"Starting job worker pool (max_concurrent={self.max_concurrent_jobs})"
        )

        try:
            while self.is_running:
                # Check for pending jobs
                try:
                    pending_jobs = await self.job_service.get_pending_jobs(
                        limit=self.max_concurrent_jobs
                    )

                    # Start jobs up to concurrency limit
                    for job_data in pending_jobs:
                        if len(self.running_jobs) >= self.max_concurrent_jobs:
                            break

                        # Start job execution
                        task = asyncio.create_task(
                            self._execute_job_with_semaphore(job_data)
                        )
                        self.running_jobs[job_data.id] = task

                        logger.debug(f"Started executing job {job_data.id}")

                    # Clean up completed tasks
                    completed_job_ids = []
                    for job_id, task in self.running_jobs.items():
                        if task.done():
                            completed_job_ids.append(job_id)

                    for job_id in completed_job_ids:
                        del self.running_jobs[job_id]

                except Exception as e:
                    logger.error(f"Error in worker pool: {e}")

                # Wait before next poll or until stop requested
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.poll_interval_seconds
                    )
                    # Stop event was set
                    break
                except TimeoutError:
                    # Normal polling timeout, continue
                    continue

        finally:
            # Wait for running jobs to complete
            if self.running_jobs:
                logger.info(f"Waiting for {len(self.running_jobs)} jobs to complete...")
                await asyncio.gather(
                    *self.running_jobs.values(), return_exceptions=True
                )
                self.running_jobs.clear()

            logger.info("Job worker pool stopped")

    async def stop_worker_pool(self) -> None:
        """Stop the worker pool gracefully."""
        if not self.is_running:
            return

        logger.info("Stopping job worker pool...")
        self.is_running = False
        self._stop_event.set()

    def get_worker_stats(self) -> dict[str, Any]:
        """Get current worker statistics.

        Returns:
            Dict with worker statistics
        """
        return {
            "is_running": self.is_running,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "current_running_jobs": len(self.running_jobs),
            "available_slots": self.max_concurrent_jobs - len(self.running_jobs),
            "running_job_ids": list(self.running_jobs.keys()),
        }
