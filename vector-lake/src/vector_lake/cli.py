"""CLI tool for Vector-Lake (§22.2)."""

from __future__ import annotations

import click


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Vector-Lake: Intelligent Knowledge Search Engine Layer."""
    pass


@cli.command()
@click.option("--host", default="0.0.0.0", help="API server host")
@click.option("--port", default=8080, help="API server port")
def serve(host: str, port: int):
    """Start the API server."""
    import uvicorn

    uvicorn.run("vector_lake.api.app:create_app", host=host, port=port, factory=True)


@cli.command()
@click.option("--concurrency", default=4, help="Worker concurrency")
def worker(concurrency: int):
    """Start a pipeline worker."""
    click.echo(f"Starting worker with concurrency={concurrency}")
    # TODO: implement worker loop


@cli.command()
@click.option("--once", is_flag=True, help="Run once and exit")
@click.option("--interval", default=900, help="Run interval in seconds")
def reconcile(once: bool, interval: int):
    """Run the reconciler."""
    click.echo(f"Running reconciler (once={once}, interval={interval})")
    # TODO: implement reconciler


@cli.group()
def entity():
    """Entity management commands."""
    pass


@entity.command("create")
@click.option("--collection", required=True)
@click.option("--source", required=True, help="OSS source path")
@click.option("--labels", default="{}", help="JSON labels")
def entity_create(collection: str, source: str, labels: str):
    """Create a new entity."""
    click.echo(f"Creating entity: collection={collection}, source={source}")


@entity.command("list")
@click.option("--collection", required=True)
def entity_list(collection: str):
    """List entities."""
    click.echo(f"Listing entities in collection={collection}")


@entity.command("get")
@click.option("--collection", required=True)
@click.option("--entity-id", required=True)
def entity_get(collection: str, entity_id: str):
    """Get entity details."""
    click.echo(f"Getting entity: {entity_id}")


@entity.command("delete")
@click.option("--collection", required=True)
@click.option("--entity-id", required=True)
def entity_delete(collection: str, entity_id: str):
    """Soft delete an entity."""
    click.echo(f"Deleting entity: {entity_id}")


@entity.command("rebuild")
@click.option("--collection", required=True)
@click.option("--entity-id", required=True)
@click.option("--pipeline", default="", help="Specific pipeline to rebuild")
def entity_rebuild(collection: str, entity_id: str, pipeline: str):
    """Rebuild entity pipelines."""
    click.echo(f"Rebuilding entity: {entity_id}, pipeline={pipeline}")


@cli.command()
@click.argument("query")
@click.option("--collection", default="", help="Collection to search")
@click.option("--top-k", default=10, help="Number of results")
@click.option("--type", "search_type", default="hybrid", help="Search type")
def search(query: str, collection: str, top_k: int, search_type: str):
    """Search the knowledge lake."""
    click.echo(f"Searching: '{query}' (type={search_type}, top_k={top_k})")


@cli.command()
def health():
    """Check system health."""
    click.echo("Checking health...")


@cli.command()
def queue_status():
    """Show queue status."""
    click.echo("Queue status: TODO")


if __name__ == "__main__":
    cli()
