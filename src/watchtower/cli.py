"""Command-line interface for the watchtower.

Three commands:
    watchtower probe        Run one polling cycle (writes to DB).
    watchtower stats        Show counts and latency stats (read-only).
    watchtower healthcheck  Verify config + DB + EUMDAC reachable.

Built on Typer, which provides type-driven argument parsing and
auto-generated --help text.
"""
import sys
from datetime import UTC, datetime, timedelta

import typer
from sqlmodel import func, select

from .collector import poll_once
from .config import get_settings
from .logging_setup import configure
from .models import Product
from .storage import get_engine, session

app = typer.Typer(
    help="Watchtower: monitoring for the EUMETSAT Data Store.",
    add_completion=False,
)


@app.command()
def probe(
    log_level: str = typer.Option("INFO", help="Logging verbosity."),
) -> None:
    """Run one polling cycle across all configured collections."""
    configure(log_level)
    result = poll_once()
    typer.echo("\nPolled:")
    for collection_id, new_count in result.items():
        typer.echo(f"  {collection_id}: {new_count} new products")


@app.command()
def stats(
    hours: int = typer.Option(24, help="Window for recent product count."),
) -> None:
    """Show database statistics: per-collection counts and latency."""
    configure("WARNING")  # quiet logs; this command is for humans reading output
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    with session() as s:
        total = s.exec(select(func.count()).select_from(Product)).one()

        per_collection = s.exec(
            select(Product.collection_id, func.count())
            .group_by(Product.collection_id)
        ).all()

        recent = s.exec(
            select(Product.collection_id, func.count())
            .where(Product.observed_at >= cutoff)
            .group_by(Product.collection_id)
        ).all()

    typer.echo(f"\nTotal products in database: {total}")
    typer.echo(f"\nProducts per collection (all time):")
    for collection, count in per_collection:
        typer.echo(f"  {collection}: {count}")

    typer.echo(f"\nProducts observed in last {hours}h:")
    if not recent:
        typer.echo("  (none)")
    for collection, count in recent:
        typer.echo(f"  {collection}: {count}")


@app.command()
def healthcheck() -> None:
    """Exit 0 if config, DB, and EUMDAC are reachable. Exit 1 otherwise.

    Designed for container orchestrators (Docker HEALTHCHECK, K8s probes).
    Prints minimal output. Use --help on the parent command to see all commands.
    """
    configure("WARNING")

    # Check 1: config loads
    try:
        settings = get_settings()
        assert settings.eumetsat_consumer_key
    except Exception as exc:
        typer.echo(f"FAIL: config — {exc}", err=True)
        raise typer.Exit(code=1)

    # Check 2: database engine works
    try:
        engine = get_engine()
        with engine.connect():
            pass
    except Exception as exc:
        typer.echo(f"FAIL: database — {exc}", err=True)
        raise typer.Exit(code=1)

    # Check 3: EUMDAC token can be acquired
    try:
        from .eumdac_client import EumdacClient
        client = EumdacClient(
            settings.eumetsat_consumer_key,
            settings.eumetsat_consumer_secret,
        )
        client._ensure()  # forces token acquisition
    except Exception as exc:
        typer.echo(f"FAIL: eumdac — {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo("OK")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()