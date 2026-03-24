"""
Daskalo Content Generation CLI — operator entrypoint.

Usage:
    uv run daskalo generate [OPTIONS]

All options are optional — missing values are prompted for interactively.

Examples:
    # Fully interactive, writes directly to Firestore emulator:
    uv run daskalo generate

    # Scripted:
    uv run daskalo generate \
        --curriculum-chapter b1_c2 \
        --topic "Boxing match" \
        --length long

    # Production: generates ZIP only, no upload (operator uploads to GCS manually):
    uv run daskalo generate --no-local \
        --curriculum-chapter b1_c2 \
        --topic "Boxing match"

    # Upload an existing ZIP and ingest directly into Firestore emulator:
    uv run daskalo upload output/b1_c2_boxing.zip
"""

from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

load_dotenv(".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

console = Console()

# Ensure shared package is importable.
_repo_root = Path(__file__).parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from shared.data.curriculum_loader import load_curriculum  # noqa: E402


def _slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _get_curriculum_data() -> dict:
    root_dir = Path(__file__).parent.parent
    return load_curriculum(root_dir)


def _prompt_for_chapter() -> tuple[dict, dict]:
    """Interactive prompt for curriculum chapter selection."""
    data = _get_curriculum_data()

    console.print("\n[bold]Select a Book:[/bold]")
    for i, book in enumerate(data["books"], 1):
        console.print(f"  {i}. {book['title']} ({book['level']})")

    book_idx = click.prompt("Book number", type=int) - 1
    book = data["books"][book_idx]

    console.print(f"\n[bold]Select a Chapter in '{book['title']}':[/bold]")
    for i, ch in enumerate(book["chapters"], 1):
        console.print(f"  {i}. Chapter {book['order']}.{ch['order']} ({ch['id']}) - {ch['suggested_length']}")

    ch_idx = click.prompt("Chapter number", type=int) - 1
    chapter = book["chapters"][ch_idx]

    return book, chapter


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Daskalo content generation tools."""


# ---------------------------------------------------------------------------
# generate command
# ---------------------------------------------------------------------------


@cli.command("generate")
@click.option("--curriculum-chapter", help="Curriculum chapter ID (e.g. b1_c2).")
@click.option(
    "--topic",
    prompt="Topic description (e.g. Ordering food at a taverna)",
    help="Subject matter of the lesson.",
)
@click.option(
    "--interests",
    default="general",
    show_default=True,
    help="Student interests to personalise content (e.g. 'football, cooking').",
)
@click.option(
    "--length",
    help="Lesson length override. Defaults to the curriculum's suggested length.",
    type=click.Choice(["short", "medium", "long"], case_sensitive=False),
)
@click.option(
    "--local/--no-local",
    default=True,
    show_default=True,
    help=(
        "Target the local Firebase Emulator Suite (default). "
        "Use --no-local to produce the ZIP only (for manual upload to production GCS)."
    ),
)
def generate(
    curriculum_chapter: str | None,
    topic: str,
    interests: str,
    length: str | None,
    local: bool,
) -> None:
    """Generate a Greek lesson chapter and deliver it to the configured environment."""

    _check_env()

    # --- Curriculum resolution -----------------------------------------------
    data = _get_curriculum_data()
    selected_book = None
    selected_chapter = None

    if curriculum_chapter:
        for b in data["books"]:
            for c in b["chapters"]:
                if c["id"] == curriculum_chapter:
                    selected_book = b
                    selected_chapter = c
                    break
        if not selected_book:
            raise click.UsageError(f"Chapter ID '{curriculum_chapter}' not found in curriculum books.")
    else:
        selected_book, selected_chapter = _prompt_for_chapter()

    book_id = selected_book["id"]
    chapter_id = selected_chapter["id"]
    chapter_order = selected_chapter["order"]
    final_length = length or selected_chapter["suggested_length"]
    variant_id = f"{chapter_id}_{_slugify(topic)}"

    # --- Header --------------------------------------------------------------
    console.print(Panel(Text("Daskalo Content Generator", justify="center"), style="bold blue"))
    console.print()

    env_label = "[cyan]local emulators[/cyan]" if local else "[yellow]production[/yellow]"
    console.print(f"  Target environment : {env_label}")
    console.print(f"  Book               : {book_id} ({selected_book['title']})")
    console.print(f"  Curriculum Chapter : {chapter_id} (order {chapter_order})")
    console.print("  Variant Doc ID     : [dim](generated from title after planning)[/dim]")
    console.print(f"  Topic              : {topic}")
    console.print(f"  Interests          : {interests}")
    console.print(f"  Length             : {final_length}")
    console.print()

    # --- Run pipeline --------------------------------------------------------
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    work_dir = tempfile.mkdtemp(prefix="daskalo_work_", dir=output_dir)

    initial_state = {
        "book_id": book_id,
        "curriculum_chapter_id": chapter_id,
        "variant_id": variant_id,
        "chapter_order": chapter_order,
        "chapter_topic": topic,
        "student_interests": interests,
        "lesson_length": final_length,
        "chapter_title": "",
        "chapter_summary": "",
        "chapter_image_prompt": "",
        "passage": [],
        "vocabulary": [],
        "grammar_concept_outlines": [],
        "grammar_notes": [],
        "exercises": [],
        "image_prompts": [],
        "review_feedback": "",
        "generation_attempts": 0,
        "work_dir": work_dir,
        "audio_files": [],
        "sentence_audio_files": [],
        "image_files": [],
        "chapter_image_path": "",
        "output_zip_path": "",
    }

    console.print("[bold yellow]Running content generation pipeline…[/bold yellow]\n")

    from graph import build_graph

    graph = build_graph()
    final_state = graph.invoke(initial_state)

    zip_path = final_state.get("output_zip_path", "")
    if not zip_path or not Path(zip_path).exists():
        console.print("\n[bold red]Pipeline completed but no ZIP file was produced.[/bold red]")
        console.print("Check logs above for errors.")
        raise SystemExit(1)

    console.print(f"\n[bold green]ZIP created:[/bold green] [cyan]{zip_path}[/cyan]")

    generated_title = final_state.get("chapter_title", "")
    generated_variant_id = final_state.get("variant_id", "")
    generated_summary = final_state.get("chapter_summary", "")
    if generated_variant_id:
        console.print(f"\n  [bold]Variant Doc ID   :[/bold] [bold green]{generated_variant_id}[/bold green]")
    if generated_title:
        console.print(f"  [bold]Generated title  :[/bold] {generated_title}")
    if generated_summary:
        console.print(f"  [bold]Generated summary:[/bold] {generated_summary}")

    # --- Deliver to environment ----------------------------------------------
    if not local:
        console.print(
            "\n[bold yellow]Production mode:[/bold yellow] ZIP not uploaded automatically."
            "\nNext step: upload the ZIP to your GCS ingestion bucket to trigger backend ingestion."
            f"\n  Bucket: [cyan]gs://<your-ingestion-bucket>/{Path(zip_path).name}[/cyan]"
        )
        return

    from services.local_ingest import ingest_direct

    console.print("\n[bold yellow]Writing content directly to Firestore emulator…[/bold yellow]")
    try:
        chapter_id_written = ingest_direct(zip_path)
        console.print(
            f"\n[bold green]Done![/bold green] Chapter [cyan]{chapter_id_written}[/cyan] "
            "written directly to Firestore emulator."
        )
        console.print("Open the Firebase Emulator UI at [cyan]http://localhost:4001[/cyan] to inspect it.")
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[bold red]Direct ingest failed:[/bold red] {exc}")
        console.print("Make sure the Firebase Emulator Suite is running (dev.sh).")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# upload command
# ---------------------------------------------------------------------------


@cli.command("upload")
@click.argument("zip_path", type=click.Path(exists=True, dir_okay=False, readable=True))
def upload(zip_path: str) -> None:
    """Upload an existing ZIP file directly into the local Firestore emulator.

    ZIP_PATH is the path to a previously generated chapter ZIP file.
    """
    _check_env()

    if not zip_path.endswith(".zip"):
        raise click.BadParameter("File must be a .zip archive.", param_hint="ZIP_PATH")

    console.print(Panel(Text("Daskalo Content Upload", justify="center"), style="bold blue"))
    console.print()
    console.print(f"  ZIP file : [cyan]{zip_path}[/cyan]")
    console.print()

    from services.local_ingest import ingest_direct

    console.print("[bold yellow]Writing content to Firestore emulator…[/bold yellow]")
    try:
        chapter_id_written = ingest_direct(zip_path)
        console.print(
            f"\n[bold green]Done![/bold green] Chapter [cyan]{chapter_id_written}[/cyan] "
            "written directly to Firestore emulator."
        )
        console.print("Open the Firebase Emulator UI at [cyan]http://localhost:4001[/cyan] to inspect it.")
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[bold red]Direct ingest failed:[/bold red] {exc}")
        console.print("Make sure the Firebase Emulator Suite is running (dev.sh).")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# Pre-flight helpers
# ---------------------------------------------------------------------------


def _check_env() -> None:
    required = ["GOOGLE_CLOUD_PROJECT"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        console.print(f"[bold red]Error:[/bold red] Missing required env vars: {', '.join(missing)}")
        console.print("Copy [bold].env.example[/bold] to [bold].env[/bold] and fill in the values.")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
