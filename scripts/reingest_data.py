#!/usr/bin/env python3
"""CLI tool for managing data re-ingestion."""

import asyncio
from datetime import datetime, timedelta

import click

from bio_mcp.config.config import Config
from bio_mcp.services.reingest_service import ReingestionMode, ReingestionService


@click.group()
def cli():
    """Bio-MCP Data Re-ingestion Management."""
    pass


@cli.command()
@click.option(
    "--mode",
    type=click.Choice(["full", "incremental", "repair", "validation"]),
    required=True,
)
@click.option("--source", help="Filter by source (e.g., 'pubmed')")
@click.option("--since-days", type=int, help="Process documents from N days ago")
@click.option("--pmids", help="Comma-separated list of PMIDs to process")
@click.option("--dry-run", is_flag=True, help="Validate without storing")
@click.option("--batch-size", type=int, default=100, help="Batch size for processing")
@click.option("--concurrency", type=int, default=10, help="Max concurrent operations")
def start(mode, source, since_days, pmids, dry_run, batch_size, concurrency):
    """Start a re-ingestion job."""

    async def _start():
        config = Config()
        config.BIO_MCP_REINGEST_BATCH_SIZE = str(batch_size)
        config.BIO_MCP_REINGEST_CONCURRENCY = str(concurrency)

        service = ReingestionService(config)

        # Parse date filter
        date_filter = None
        if since_days:
            start_date = datetime.now() - timedelta(days=since_days)
            date_filter = (start_date, datetime.now())

        # Parse PMID list
        pmid_list = None
        if pmids:
            pmid_list = [p.strip() for p in pmids.split(",")]

        try:
            job_id = await service.start_reingest_job(
                mode=ReingestionMode(mode),
                source_filter=source,
                date_filter=date_filter,
                pmid_list=pmid_list,
                dry_run=dry_run,
            )

            click.echo(f"Started re-ingestion job: {job_id}")

            if click.confirm("Run job immediately?"):
                click.echo("Running job...")
                result = await service.execute_reingest_job(job_id)

                click.echo("\nJob completed!")
                click.echo(f"Documents processed: {result['documents_processed']}")
                click.echo(f"Documents failed: {result['documents_failed']}")
                click.echo(f"Chunks created: {result['chunks_created']}")
                click.echo(f"Success rate: {result['success_rate']:.1%}")
                click.echo(f"Processing rate: {result['docs_per_minute']:.1f} docs/min")

                if result["documents_failed"] > 0:
                    click.echo("\nFirst few errors:")
                    for error in result["errors_sample"]:
                        click.echo(f"  {error['doc_uid']}: {error['error']}")

        except Exception as e:
            click.echo(f"Error: {e}")
            raise click.Abort()

    asyncio.run(_start())


@cli.command()
@click.argument("job_id")
def status(job_id):
    """Get status of a re-ingestion job."""

    async def _status():
        config = Config()
        service = ReingestionService(config)

        try:
            status_info = await service.get_reingest_status(job_id)

            click.echo(f"Job ID: {status_info['job_id']}")
            click.echo(f"Status: {status_info['status']}")
            click.echo(f"Progress: {status_info.get('progress', 0)}%")
            click.echo(f"Created: {status_info['created_at']}")
            click.echo(f"Updated: {status_info['updated_at']}")

            if status_info["result"]:
                result = status_info["result"]
                click.echo("\nResults:")
                click.echo(
                    f"  Documents processed: {result.get('documents_processed', 0)}"
                )
                click.echo(f"  Documents failed: {result.get('documents_failed', 0)}")
                click.echo(f"  Success rate: {result.get('success_rate', 0):.1%}")

        except Exception as e:
            click.echo(f"Error: {e}")
            raise click.Abort()

    asyncio.run(_status())


@cli.command()
@click.argument("job_id")
def cancel(job_id):
    """Cancel a running re-ingestion job."""

    async def _cancel():
        config = Config()
        service = ReingestionService(config)

        try:
            success = await service.cancel_reingest_job(job_id)

            if success:
                click.echo(f"Job {job_id} cancelled successfully")
            else:
                click.echo(
                    f"Could not cancel job {job_id} (may not exist or already completed)"
                )

        except Exception as e:
            click.echo(f"Error: {e}")
            raise click.Abort()

    asyncio.run(_cancel())


@cli.command()
def list_jobs():
    """List recent re-ingestion jobs."""

    async def _list_jobs():
        config = Config()
        service = ReingestionService(config)

        try:
            jobs = await service.db_service.list_jobs(
                limit=10, operation_filter="reingest"
            )

            if not jobs:
                click.echo("No re-ingestion jobs found.")
                return

            click.echo("Recent re-ingestion jobs:")
            click.echo("-" * 80)
            for job in jobs:
                status_color = (
                    "green"
                    if job["status"] == "completed"
                    else "yellow"
                    if job["status"] == "running"
                    else "red"
                )
                click.echo(
                    f"ID: {job['id'][:8]}... | Mode: {job.get('mode', 'unknown'):12} | Status: ",
                    nl=False,
                )
                click.secho(f"{job['status']:20}", fg=status_color, nl=False)
                click.echo(f" | Created: {job['created_at'][:19]}")

        except Exception as e:
            click.echo(f"Error: {e}")
            raise click.Abort()

    asyncio.run(_list_jobs())


if __name__ == "__main__":
    cli()
