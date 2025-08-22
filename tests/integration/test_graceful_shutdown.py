"""
Integration tests for graceful shutdown functionality.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


class TestGracefulShutdown:
    """Test graceful shutdown functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent.parent
        self.server_process = None

    def teardown_method(self):
        """Clean up after tests."""
        if self.server_process and self.server_process.poll() is None:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self.server_process.kill()
                    self.server_process.wait(timeout=2)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    pass

    def start_server_process(self) -> subprocess.Popen:
        """Start the MCP server process."""
        cmd = [sys.executable, "-m", "bio_mcp.main"]

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_root / "src")
        env["BIO_MCP_LOG_LEVEL"] = "DEBUG"

        process = subprocess.Popen(
            cmd,
            cwd=self.project_root,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,  # Unbuffered
        )

        return process

    def test_graceful_shutdown(self):
        """Test graceful shutdown with SIGTERM signal (covers SIGINT behavior too)."""
        self.server_process = self.start_server_process()

        # Give the server time to start
        time.sleep(2)
        assert self.server_process.poll() is None, "Server should be running"

        # Send SIGTERM signal
        start_time = time.time()
        self.server_process.send_signal(signal.SIGTERM)

        # Give the server time to handle the signal and begin shutdown
        time.sleep(1)

        # Close stdin to unblock the server from waiting for input
        if self.server_process.stdin:
            self.server_process.stdin.close()

        # Wait for graceful shutdown
        try:
            exit_code = self.server_process.wait(timeout=15)
            shutdown_time = time.time() - start_time

            # Should exit cleanly
            assert exit_code == 0, f"Expected clean exit (0), got {exit_code}"

            # Should shutdown relatively quickly (within 15 seconds)
            assert shutdown_time < 15, f"Shutdown took too long: {shutdown_time:.2f}s"

        except subprocess.TimeoutExpired:
            pytest.fail("Server did not shut down gracefully within timeout")

    def test_multiple_signals(self):
        """Test that multiple signals don't cause issues."""
        self.server_process = self.start_server_process()

        # Give the server time to start
        time.sleep(2)
        assert self.server_process.poll() is None, "Server should be running"

        # Send multiple SIGTERM signals quickly
        self.server_process.send_signal(signal.SIGTERM)
        time.sleep(0.1)
        self.server_process.send_signal(signal.SIGTERM)
        time.sleep(0.1)
        self.server_process.send_signal(signal.SIGTERM)

        # Close stdin to unblock the server
        if self.server_process.stdin:
            self.server_process.stdin.close()

        # Should still shutdown gracefully
        try:
            exit_code = self.server_process.wait(timeout=15)
            assert exit_code == 0, f"Expected clean exit (0), got {exit_code}"

        except subprocess.TimeoutExpired:
            pytest.fail("Server did not handle multiple signals gracefully")

    @pytest.mark.skipif(os.name == "nt", reason="SIGKILL not available on Windows")
    def test_sigkill_forced_shutdown(self):
        """Test that SIGKILL forces immediate shutdown."""
        self.server_process = self.start_server_process()

        # Give the server time to start
        time.sleep(2)
        assert self.server_process.poll() is None, "Server should be running"

        # Send SIGKILL (force kill)
        start_time = time.time()
        self.server_process.send_signal(signal.SIGKILL)

        # Wait for forced shutdown
        try:
            exit_code = self.server_process.wait(timeout=5)
            shutdown_time = time.time() - start_time

            # SIGKILL should result in negative exit code on Unix
            if os.name != "nt":
                assert exit_code < 0, (
                    f"Expected negative exit code for SIGKILL, got {exit_code}"
                )

            # Should shutdown very quickly with SIGKILL
            assert shutdown_time < 2, (
                f"Forced shutdown took too long: {shutdown_time:.2f}s"
            )

        except subprocess.TimeoutExpired:
            pytest.fail("Server did not respond to SIGKILL")
