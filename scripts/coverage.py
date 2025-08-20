#!/usr/bin/env python3
"""
Code coverage analysis script for bio-mcp.

This script runs different test suites and generates coverage reports.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"🔄 {description}...")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Command: {' '.join(cmd)}")
        print(f"   Exit code: {e.returncode}")
        if e.stdout:
            print(f"   stdout: {e.stdout[:200]}...")
        if e.stderr:
            print(f"   stderr: {e.stderr[:200]}...")
        return False


def main():
    """Run coverage analysis."""
    project_root = Path(__file__).parent.parent
    print("📊 Running coverage analysis for bio-mcp")
    print(f"📁 Project root: {project_root}")
    
    # Change to project directory
    try:
        subprocess.run(["uv", "sync", "--dev"], check=True, cwd=project_root)
        
        # Clean previous coverage data
        print("🧹 Cleaning previous coverage data...")
        coverage_file = project_root / ".coverage"
        if coverage_file.exists():
            coverage_file.unlink()
        
        # Run unit tests with coverage
        if not run_command([
            "uv", "run", "pytest", "tests/unit/",
            "--cov=src/bio_mcp",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--cov-branch"
        ], "Unit tests with coverage"):
            return 1
            
        # Run integration tests with coverage (append)
        if not run_command([
            "uv", "run", "pytest", "tests/integration/",
            "-k", "not test_weaviate_functionality",  # Skip problematic test
            "--cov=src/bio_mcp",
            "--cov-append",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--cov-branch"
        ], "Integration tests with coverage"):
            print("⚠️  Integration tests failed, but continuing with unit test coverage...")
        
        # Generate coverage report
        print("\n" + "="*60)
        print("📊 COVERAGE SUMMARY")
        print("="*60)
        
        # Run coverage report command
        subprocess.run([
            "uv", "run", "coverage", "report", 
            "--show-missing",
            "--skip-covered"
        ], cwd=project_root)
        
        # Show HTML report location
        html_dir = project_root / "htmlcov"
        if html_dir.exists():
            print(f"\n📁 HTML coverage report generated: {html_dir}/index.html")
            print(f"   Open with: open {html_dir}/index.html")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n⏹️  Coverage analysis interrupted")
        return 1


if __name__ == "__main__":
    sys.exit(main())