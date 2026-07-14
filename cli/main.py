"""ContextWeave CLI — workspace knowledge graph from the terminal."""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from uuid import UUID

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.prompt import Prompt

from services.parser.parser import WeaveParser, ParsedWeaveFile, ParsedEntry
from services.shared.config import config
from services.shared.models import WeaveFile, Entry, Tag, EntryLink, SessionLocal, init_db
from services.query.engine import QueryEngine
from services.graph.engine import GraphEngine
from services.sync.watcher import WeaveSyncService

console = Console()


def get_db():
    """Get a database session."""
    init_db()
    return SessionLocal()


@click.group()
@click.option("--workspace", "-w", default=None, help="Workspace directory")
@click.pass_context
def cli(ctx, workspace):
    """ContextWeave — workspace knowledge graph for the AI era."""
    ctx.ensure_object(dict)
    if workspace:
        config.workspace_dir = Path(workspace)


@cli.command()
@click.argument("project_name")
@click.option("--dir", "-d", default=".", help="Directory for the .weave.md file")
def init(project_name, dir):
    """Initialize a new .weave.md file for a project."""
    weave_dir = Path(dir)
    weave_dir.mkdir(parents=True, exist_ok=True)

    file_path = weave_dir / f"{project_name.lower().replace(' ', '_')}.weave.md"

    if file_path.exists():
        console.print(f"[yellow]File already exists: {file_path}[/yellow]")
        return

    template = f"""# Project: {project_name}
# Status: Active

# Decision: Use Postgres for main database
Because: Need ACID compliance and complex queries
Risk: Operational overhead
Outcome: Pending
Tags: database, architecture

# Task: Set up database schema
Status: In Progress
Owner: @user

# Requirement: API must handle 1000 req/s
Scope: Active
Tags: performance, api
"""
    file_path.write_text(template)
    console.print(f"[green]Created {file_path}[/green]")


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def parse(file_path):
    """Parse and display a .weave.md file."""
    parser = WeaveParser()
    parsed = parser.parse_file(Path(file_path))

    tree = Tree(f"[bold]{parsed.project_name}[/bold] [{parsed.status}]")

    for entry in parsed.entries:
        tag_str = f" [dim]({', '.join(entry.tags)})[/dim]" if entry.tags else ""
        node = tree.add(f"[cyan]{entry.entry_type}:[/cyan] {entry.title}{tag_str}")

        if entry.outcome:
            node.add(f"[yellow]Outcome:[/yellow] {entry.outcome}")
        if entry.status:
            node.add(f"[blue]Status:[/blue] {entry.status}")
        if entry.owner:
            node.add(f"[green]Owner:[/green] {entry.owner}")
        if entry.source_ref:
            node.add(f"[red]Blocked by:[/red] {entry.source_ref}")

    console.print(tree)


@cli.command()
@click.argument("query_str")
@click.option("--limit", "-l", default=20, help="Max results")
def query(query_str, limit):
    """Query the workspace: 'Decision WHERE outcome=revisit'"""
    db = get_db()
    try:
        engine = QueryEngine(db)
        results = engine.query(query_str, limit=limit)

        if not results:
            console.print("[dim]No results found.[/dim]")
            return

        table = Table(title=f"Query: {query_str}")
        table.add_column("Type", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Project", style="green")
        table.add_column("Status", style="blue")

        for r in results:
            table.add_row(
                r.get("entry_type", ""),
                r.get("title", "")[:50],
                r.get("file_path", "")[:30] if r.get("file_path") else "",
                r.get("status", "") or r.get("outcome", "") or "",
            )

        console.print(table)
    finally:
        db.close()


@cli.command()
@click.argument("search_query")
@click.option("--limit", "-l", default=20, help="Max results")
def search(search_query, limit):
    """Full-text search across all entries."""
    db = get_db()
    try:
        engine = QueryEngine(db)
        results = engine.search(search_query, limit=limit)

        if not results:
            console.print("[dim]No matches found.[/dim]")
            return

        table = Table(title=f"Search: '{search_query}'")
        table.add_column("Type", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Content", style="dim")
        table.add_column("Project", style="green")

        for r in results:
            content_preview = r.get("content", "")[:60] + "..." if len(r.get("content", "")) > 60 else r.get("content", "")
            table.add_row(
                r.get("entry_type", ""),
                r.get("title", "")[:40],
                content_preview,
                r.get("file_path", "")[:25] if r.get("file_path") else "",
            )

        console.print(table)
    finally:
        db.close()


@cli.command()
def status():
    """Show workspace status."""
    db = get_db()
    try:
        engine = QueryEngine(db)
        ws = engine.workspace_status()

        # Type breakdown table
        type_table = Table()
        type_table.add_column("Entry Type", style="cyan")
        type_table.add_column("Count", style="white")

        for etype, count in ws.get("type_breakdown", {}).items():
            type_table.add_row(etype, str(count))

        panel = Panel(
            f"[bold]Workspace Overview[/bold]\n\n"
            f"Files: {ws['total_files']} ({ws['active_files']} active)\n"
            f"Total Entries: {ws['total_entries']}\n"
            f"Blocked Items: {ws['blocked_items']}\n\n"
            f"{type_table}",
            border_style="blue",
        )
        console.print(panel)
    finally:
        db.close()


@cli.command()
@click.argument("entry_id")
def show(entry_id):
    """Show entry details and its links."""
    db = get_db()
    try:
        try:
            uuid_obj = UUID(entry_id)
        except ValueError:
            entry = db.query(Entry).filter(Entry.id.like(f"%{entry_id}%")).first()
        else:
            entry = db.query(Entry).filter(Entry.id == uuid_obj).first()

        if not entry:
            console.print("[red]Entry not found[/red]")
            return

        panel = Panel(
            f"[bold]{entry.title}[/bold]\n"
            f"[cyan]Type:[/cyan] {entry.entry_type}\n"
            f"[cyan]Project:[/cyan] {entry.weave_file.project_name if entry.weave_file else 'N/A'}\n\n"
            f"{entry.content}\n\n"
            f"[dim]Tags:[/dim] {', '.join(t.name for t in entry.tags)}\n"
            f"[dim]Status:[/dim] {entry.status or 'N/A'}\n"
            f"[dim]Outcome:[/dim] {entry.outcome or 'N/A'}\n"
            f"[dim]Owner:[/dim] {entry.owner or 'N/A'}\n"
            f"[dim]Blocked by:[/dim] {entry.source_ref or 'N/A'}\n"
            f"[dim]ID:[/dim] {entry.id}",
            title=f"{entry.entry_type}",
            border_style="blue",
        )
        console.print(panel)

        # Show links
        if entry.outgoing_links or entry.incoming_links:
            link_table = Table(title="Links")
            link_table.add_column("Direction", style="dim")
            link_table.add_column("Type", style="cyan")
            link_table.add_column("Title", style="white")

            for l in entry.outgoing_links:
                link_table.add_row("→", l.link_type, l.to_entry.title if l.to_entry else "?")
            for l in entry.incoming_links:
                link_table.add_row("←", l.link_type, l.from_entry.title if l.from_entry else "?")

            console.print(link_table)
    finally:
        db.close()


@cli.command()
@click.argument("entry_id")
def chain(entry_id):
    """Show the blocking chain for an entry."""
    db = get_db()
    try:
        engine = GraphEngine(db)
        chain = engine.get_blocking_chain(entry_id)

        if not chain:
            console.print("[dim]No blocking chain found.[/dim]")
            return

        table = Table(title="Blocking Chain")
        table.add_column("#", style="dim")
        table.add_column("Type", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Status", style="blue")

        for i, item in enumerate(chain):
            table.add_row(
                str(i + 1),
                item.get("type", ""),
                item.get("title", "")[:50],
                item.get("status", "") or "",
            )

        console.print(table)
    finally:
        db.close()


@cli.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--watch", "-w", is_flag=True, help="Watch for changes")
def sync(directory, watch):
    """Sync a directory of .weave.md files."""
    service = WeaveSyncService(watch_dirs=[directory])
    count = service.initial_sync()
    console.print(f"[green]Synced {count} file(s) from {directory}[/green]")

    if watch:
        console.print("[dim]Watching for changes... (Ctrl+C to stop)[/dim]")
        service.start()
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopping...[/dim]")
        finally:
            service.stop()


@cli.command()
def graph():
    """Show workspace knowledge graph summary."""
    db = get_db()
    try:
        engine = GraphEngine(db)
        g = engine.get_workspace_graph()

        console.print(Panel(
            f"[bold]Knowledge Graph[/bold]\n\n"
            f"Nodes: {g['node_count']}\n"
            f"Edges: {g['edge_count']}\n",
            border_style="green",
        ))

        if g['edges']:
            table = Table(title="Connections")
            table.add_column("From", style="white")
            table.add_column("Type", style="cyan")
            table.add_column("To", style="white")

            for edge in g['edges'][:20]:
                from_node = next((n for n in g['nodes'] if n['id'] == edge['from']), {})
                to_node = next((n for n in g['nodes'] if n['id'] == edge['to']), {})
                table.add_row(
                    from_node.get('title', edge['from'])[:30],
                    edge['type'],
                    to_node.get('title', edge['to'])[:30],
                )

            console.print(table)
    finally:
        db.close()


@cli.command()
@click.argument("from_id")
@click.argument("to_id")
@click.option("--type", "-t", default="references", help="Link type")
def link(from_id, to_id, type):
    """Link two entries together."""
    db = get_db()
    try:
        engine = GraphEngine(db)
        result = engine.create_link(from_id, to_id, type)
        if result:
            console.print(f"[green]Linked {from_id[:8]} → {to_id[:8]} ({type})[/green]")
        else:
            console.print("[red]Failed to create link[/red]")
    finally:
        db.close()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def validate(file_path):
    """Validate a .weave.md file."""
    parser = WeaveParser()
    text = Path(file_path).read_text()
    errors = parser.validate(text)

    if errors:
        console.print(f"[red]Validation failed for {file_path}:[/red]")
        for error in errors:
            console.print(f"  • {error}")
    else:
        summary = parser.get_summary(text)
        console.print(f"[green]Valid[/green] {file_path}")
        console.print(f"  Project: {summary['project_name']}")
        console.print(f"  Status: {summary['status']}")
        console.print(f"  Entries: {summary['entry_count']}")
        for etype, count in summary['types'].items():
            console.print(f"  - {etype}: {count}")


@cli.command()
def projects():
    """List all projects in workspace."""
    db = get_db()
    try:
        files = db.query(WeaveFile).order_by(WeaveFile.updated_at.desc()).all()

        if not files:
            console.print("[dim]No projects found. Run 'weave sync' first.[/dim]")
            return

        table = Table(title="Workspace Projects")
        table.add_column("Project", style="white")
        table.add_column("Status", style="blue")
        table.add_column("Entries", style="cyan")
        table.add_column("Path", style="dim")

        for f in files:
            table.add_row(f.project_name, f.status, str(len(f.entries)), f.file_path[:40])

        console.print(table)
    finally:
        db.close()


if __name__ == "__main__":
    cli()
