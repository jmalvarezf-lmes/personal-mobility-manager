"""
CLI entry point (presentation layer).

Wires together use cases with infrastructure adapters and exposes
them as Click commands. No business logic lives here.
"""

import click


@click.group()
def cli() -> None:
    """Personal mobility manager."""
    pass
