"""
Ops Supervisor — Flask CLI worker (spec 11 §9).

Usage
-----
    flask ops-worker           # default: block forever, process events
    flask ops-worker --max 100 # stop after 100 successful messages (dev)

Registration (add to server.py when wiring is approved):

    try:
        from ops_worker_cli import register_worker_cli
        register_worker_cli(app)
    except Exception as _exc:
        logging.getLogger(__name__).warning("ops-worker CLI not registered: %s", _exc)

Stand-alone invocation (no Flask CLI):

    python -m ops_worker_cli

Both paths call ``ops_event_bus.consume`` with
``ops_langgraph.run_situation_workflow`` as the handler.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)


def _handler(event_id: str):
    """Thin wrapper so the consumer can call a module-level function."""
    from ops_langgraph import run_situation_workflow
    return run_situation_workflow(event_id)


def register_worker_cli(app) -> None:
    """Attach the ``flask ops-worker`` command to the given Flask app.

    Idempotent: re-registration replaces the existing command.
    """
    try:
        import click  # Flask depends on click already
    except ImportError:  # pragma: no cover
        logger.error("ops-worker: click is not installed")
        return

    @app.cli.command("ops-worker")
    @click.option("--consumer", default="worker-1",
                  help="Consumer name (unique per worker process).")
    @click.option("--max", "max_iterations", default=None, type=int,
                  help="Exit after N XREADGROUP iterations (dev / tests).")
    @click.option("--block-ms", default=5000, type=int,
                  help="XREADGROUP block-ms timeout.")
    def ops_worker(consumer: str, max_iterations, block_ms: int):
        """Run the ops supervisor LangGraph worker against Redis Streams."""
        from ops_event_bus import consume, ensure_group
        ensure_group()
        click.echo("ops-worker: consuming as {}; block_ms={}".format(
            consumer, block_ms))
        processed = consume(
            _handler,
            consumer_name=consumer,
            block_ms=block_ms,
            max_iterations=max_iterations,
        )
        click.echo("ops-worker: processed {} messages".format(processed))


def _standalone_main(argv=None) -> int:
    from ops_event_bus import consume, ensure_group
    ensure_group()
    logger.info("ops-worker: starting stand-alone consumer")
    consume(_handler)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_standalone_main(sys.argv[1:]))


__all__ = ["register_worker_cli"]
