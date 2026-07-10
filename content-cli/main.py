"""
Daskalo Content Generation CLI — operator entrypoint.

Usage:
    uv run daskalo generate [OPTIONS]
    uv run daskalo generate-practice [OPTIONS]

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

    # Upload an existing ZIP directly to production GCP (Firestore + GCS):
    uv run daskalo upload --remote output/b1_c2_boxing.zip

    # Generate a Practice Set from an existing chapter ZIP:
    uv run daskalo generate-practice output/b1_c2_boxing.zip

    # Generate a Practice Set and write directly to production:
    uv run daskalo generate-practice --no-local output/b1_c2_boxing.zip
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Resolve all filesystem paths relative to this package directory, not the
# process's current working directory (IMP-CC-05) — `.env`, `output/`, and the
# `shared` curriculum package must be found the same way no matter where the
# `daskalo` command is invoked from.
_PACKAGE_DIR = Path(__file__).parent
_repo_root = _PACKAGE_DIR.parent

load_dotenv(_PACKAGE_DIR / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logging.getLogger("google_genai.models").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()

# Ensure shared package is importable.
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from shared.data.curriculum_loader import load_curriculum  # noqa: E402


def _slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _get_curriculum_data() -> dict:
    return load_curriculum(_repo_root)


def _prompt_index(label: str, count: int) -> int:
    """Prompt for a 1-based index and validate it against `count` items.

    Re-prompts on out-of-range input (CC-06) instead of silently wrapping via
    negative indexing (entering "0") or crashing with an unhandled IndexError.
    """
    while True:
        raw = click.prompt(label, type=int)
        if 1 <= raw <= count:
            return raw - 1
        console.print(f"[red]Please enter a number between 1 and {count}.[/red]")


def _prompt_for_chapter() -> tuple[dict, dict]:
    """Interactive prompt for curriculum chapter selection."""
    data = _get_curriculum_data()

    console.print("\n[bold]Select a Book:[/bold]")
    for i, book in enumerate(data["books"], 1):
        console.print(f"  {i}. {book['title']} ({book['level']})")

    book_idx = _prompt_index("Book number", len(data["books"]))
    book = data["books"][book_idx]

    console.print(f"\n[bold]Select a Chapter in '{book['title']}':[/bold]")
    for i, ch in enumerate(book["chapters"], 1):
        console.print(f"  {i}. Chapter {book['order']}.{ch['order']} ({ch['id']}) - {ch['suggested_length']}")

    ch_idx = _prompt_index("Chapter number", len(book["chapters"]))
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
@click.option(
    "--keep-work-dir",
    is_flag=True,
    default=False,
    help="Keep the temporary output/daskalo_work_* directory after a successful run (for debugging).",
)
def generate(
    curriculum_chapter: str | None,
    topic: str,
    interests: str,
    length: str | None,
    local: bool,
    keep_work_dir: bool,
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
    # IMP-CC-01: thread_id is a stable hash of the inputs that fully determine this
    # generation run. Re-running the exact same command recomputes the same
    # thread_id, so a failed run's checkpoint can be found and resumed.
    thread_id = _compute_thread_id(chapter_id, topic, final_length)

    from graph import build_graph

    graph = build_graph(thread_id=thread_id)
    graph_config = {"configurable": {"thread_id": thread_id}}
    resuming = bool(graph.get_state(graph_config).next)

    if resuming:
        console.print(
            f"[bold yellow]Resuming previous incomplete run[/bold yellow] "
            f"(thread_id=[cyan]{thread_id}[/cyan]) from the last completed step…\n"
        )
        initial_state = None
    else:
        output_dir = _PACKAGE_DIR / "output"
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
            "audio_assets": [],
            "passage_audio_path": "",
            "sentence_audio_files": [],
            "image_files": [],
            "chapter_image_path": "",
            "output_zip_path": "",
        }

    console.print("[bold yellow]Running content generation pipeline…[/bold yellow]\n")

    try:
        final_state = graph.invoke(initial_state, config=graph_config)
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[bold red]Pipeline failed:[/bold red] {exc}")
        console.print(
            "\n[bold yellow]Re-running the exact same command will resume from the last "
            f"completed step[/bold yellow] (progress is checkpointed under thread_id=[cyan]{thread_id}[/cyan])."
        )
        raise SystemExit(1) from exc

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
        # IMP-CC-06: ZIP is left in place for manual upload — this is the "success"
        # state for --no-local, so the work dir can be cleaned up now.
        _cleanup_work_dir(final_state.get("work_dir", ""), keep_work_dir)
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
        # IMP-CC-06: only clean up once ingest has actually succeeded — if it
        # failed, the work dir is left in place in case it's useful for debugging.
        _cleanup_work_dir(final_state.get("work_dir", ""), keep_work_dir)
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[bold red]Direct ingest failed:[/bold red] {exc}")
        console.print("Make sure the Firebase Emulator Suite is running (dev.sh).")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# generate-practice command
# ---------------------------------------------------------------------------


@cli.command("generate-practice")
@click.argument("chapter_zip", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--practice-id",
    default=None,
    help=("Override the generated practice set document ID. Defaults to {chapter_id}_ps_01 (incrementing if needed)."),
)
@click.option(
    "--local/--no-local",
    default=True,
    show_default=True,
    help=("Target the local Firebase Emulator Suite (default). Use --no-local to produce the ZIP only."),
)
@click.option(
    "--keep-work-dir",
    is_flag=True,
    default=False,
    help="Keep the temporary output/daskalo_practice_* directory after a successful run (for debugging).",
)
def generate_practice(chapter_zip: str, practice_id: str | None, local: bool, keep_work_dir: bool) -> None:
    """Generate a Practice Set for an existing chapter ZIP.

    Reads the chapter ZIP to extract context (topic, vocabulary, existing audio),
    runs the LLM to generate 10-12 exercises, generates new media assets,
    and delivers the resulting practice-set ZIP to the configured environment.

    CHAPTER_ZIP is the path to a previously generated chapter ZIP file.
    """
    _check_env()

    console.print(Panel(Text("Daskalo Practice Set Generator", justify="center"), style="bold blue"))
    console.print()

    zip_path_obj = Path(chapter_zip)
    console.print(f"  Source ZIP  : [cyan]{chapter_zip}[/cyan]")

    # --- Read chapter context from ZIP ---
    zip_bytes = zip_path_obj.read_bytes()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        try:
            descriptor = json.loads(zf.read("descriptor.json"))
        except KeyError as exc:
            raise click.BadParameter("ZIP is missing descriptor.json", param_hint="CHAPTER_ZIP") from exc

        chapter = descriptor.get("chapter", {})
        chapter_id: str = chapter.get("id", "")
        book_id: str = descriptor.get("bookId", "")
        curriculum_chapter_id: str = chapter.get("curriculumChapterId", "")
        chapter_order: int = chapter.get("order", 0)
        chapter_topic: str = chapter.get("topic", "")
        chapter_title: str = chapter.get("title", "")
        chapter_summary: str = chapter.get("summary", "")

        if not chapter_id:
            raise click.UsageError("Could not determine chapter ID from descriptor.json")

        # Build vocabulary list from descriptor
        from models.content_models import VocabularyItem

        raw_vocab = chapter.get("vocabulary", [])
        vocabulary = [VocabularyItem(greek=v["greek"], english=v["english"]) for v in raw_vocab if v.get("greek")]

        # Extract existing audio into work_dir so we can reuse it
        output_dir = _PACKAGE_DIR / "output"
        output_dir.mkdir(exist_ok=True)
        work_dir = tempfile.mkdtemp(prefix="daskalo_practice_", dir=output_dir)

        existing_audio: dict[str, str] = {}
        for zip_name in zf.namelist():
            if zip_name.startswith("assets/audio/") and zip_name.endswith(".mp3"):
                # Skip conversation and grammar audio — not needed for practice sets
                if "/conversation/" in zip_name or "/grammar/" in zip_name or "/sentences/" in zip_name:
                    continue
                audio_bytes = zf.read(zip_name)
                local_path = str(Path(work_dir) / Path(zip_name).name)
                Path(local_path).write_bytes(audio_bytes)
                # Map the audio by the greek text extracted from the filename heuristic
                # (best-effort; generate_practice_media will fall back to fresh TTS if not found)

        # For vocab-to-path mapping, use vocab audioPath if present
        for v in raw_vocab:
            audio_path = v.get("audioPath")
            if audio_path:
                local_path = str(Path(work_dir) / Path(audio_path).name)
                if Path(local_path).exists():
                    tts_text = re.split(r"\s*/\s*|\s+-\s*", v["greek"])[0].strip()
                    existing_audio[tts_text] = local_path

    # Determine practice set ID (CC-07: real auto-increment based on existing ZIPs in output/,
    # instead of a hardcoded "_ps_01" that silently overwrote any prior practice set on re-run).
    final_practice_id = practice_id or _next_practice_id(output_dir, chapter_id)

    env_label = "[cyan]local emulators[/cyan]" if local else "[yellow]production[/yellow]"
    console.print(f"  Target env  : {env_label}")
    console.print(f"  Chapter ID  : [dim]{chapter_id}[/dim]")
    console.print(f"  Practice ID : [bold green]{final_practice_id}[/bold green]")
    console.print(f"  Vocab words : {len(vocabulary)}")
    console.print(f"  Reused audio: {len(existing_audio)} files")
    console.print()

    # --- Run practice pipeline ---
    # IMP-CC-01: same checkpoint/resume mechanism as `generate` (see graph.py / build_graph).
    thread_id = _compute_thread_id(chapter_id, final_practice_id)

    from practice_graph import build_practice_graph

    graph = build_practice_graph(thread_id=thread_id)
    graph_config = {"configurable": {"thread_id": thread_id}}
    resuming = bool(graph.get_state(graph_config).next)

    if resuming:
        console.print(
            f"[bold yellow]Resuming previous incomplete run[/bold yellow] "
            f"(thread_id=[cyan]{thread_id}[/cyan]) from the last completed step…\n"
        )
        initial_state: dict | None = None
    else:
        initial_state = {
            "book_id": book_id,
            "curriculum_chapter_id": curriculum_chapter_id,
            "chapter_id": chapter_id,
            "practice_set_id": final_practice_id,
            "chapter_order": chapter_order,
            "chapter_topic": chapter_topic,
            "chapter_title": chapter_title,
            "chapter_summary": chapter_summary,
            "vocabulary": vocabulary,
            "existing_audio": existing_audio,
            "exercises": [],
            "image_prompts": [],
            "chapter_image_prompt": "",
            "work_dir": work_dir,
            "audio_files": [],
            "image_files": [],
            "chapter_image_path": "",
            "output_zip_path": "",
        }

    console.print("[bold yellow]Running practice set generation pipeline…[/bold yellow]\n")

    try:
        final_state = graph.invoke(initial_state, config=graph_config)
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[bold red]Pipeline failed:[/bold red] {exc}")
        console.print(
            "\n[bold yellow]Re-running the exact same command will resume from the last "
            f"completed step[/bold yellow] (progress is checkpointed under thread_id=[cyan]{thread_id}[/cyan])."
        )
        raise SystemExit(1) from exc

    practice_zip_path = final_state.get("output_zip_path", "")
    if not practice_zip_path or not Path(practice_zip_path).exists():
        console.print("\n[bold red]Pipeline completed but no ZIP file was produced.[/bold red]")
        raise SystemExit(1)

    console.print(f"\n[bold green]Practice ZIP created:[/bold green] [cyan]{practice_zip_path}[/cyan]")

    if not local:
        _cleanup_work_dir(final_state.get("work_dir", ""), keep_work_dir)
        console.print(
            "\n[bold yellow]Production mode:[/bold yellow] ZIP not uploaded automatically."
            f"\n  Next step: upload manually — [cyan]uv run daskalo upload --remote {practice_zip_path}[/cyan]"
        )
        return

    from services.local_ingest import ingest_direct

    console.print("\n[bold yellow]Writing practice set to Firestore emulator…[/bold yellow]")
    try:
        practice_id_written = ingest_direct(practice_zip_path)
        console.print(
            f"\n[bold green]Done![/bold green] Practice set [cyan]{practice_id_written}[/cyan] "
            "written to Firestore emulator."
        )
        _cleanup_work_dir(final_state.get("work_dir", ""), keep_work_dir)
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[bold red]Direct ingest failed:[/bold red] {exc}")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# upload command
# ---------------------------------------------------------------------------


@cli.command("upload")
@click.argument("zip_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--remote",
    is_flag=True,
    default=False,
    help=(
        "Write directly to production GCP (Firestore + GCS) instead of the local emulator. "
        "Reads project config from infra/terraform.tfvars. "
        "Requires Application Default Credentials (gcloud auth application-default login)."
    ),
)
def upload(zip_path: str, remote: bool) -> None:
    """Upload an existing ZIP file into Firestore and GCS.

    By default targets the local Firebase Emulator Suite.
    Pass --remote to write directly to production GCP.

    ZIP_PATH is the path to a previously generated chapter ZIP file.
    """
    # CC-10: local (default) ingest hardcodes the demo-daskalo project and never
    # touches GOOGLE_CLOUD_PROJECT, so only --remote actually requires it.
    _check_env(require_gcp_project=remote)

    if not zip_path.endswith(".zip"):
        raise click.BadParameter("File must be a .zip archive.", param_hint="ZIP_PATH")

    console.print(Panel(Text("Daskalo Content Upload", justify="center"), style="bold blue"))
    console.print()
    console.print(f"  ZIP file : [cyan]{zip_path}[/cyan]")

    if remote:
        _upload_remote(zip_path)
    else:
        _upload_local(zip_path)


# ---------------------------------------------------------------------------
# users command group
# ---------------------------------------------------------------------------


@cli.group("users")
def users() -> None:
    """Manage student activation and curriculum initialization."""


@users.command("list")
@click.option(
    "--status",
    "status_filter",
    type=click.Choice(["pending", "active", "all"]),
    default="pending",
    show_default=True,
    help="Which users to list.",
)
@click.option(
    "--remote",
    is_flag=True,
    default=False,
    help="List production users instead of local emulator users.",
)
def users_list(status_filter: str, remote: bool) -> None:
    """List users with activation-relevant metadata."""
    fs_client = _get_users_firestore_client(remote)

    query_ref = fs_client.collection("users")
    if status_filter != "all":
        query_ref = query_ref.where("status", "==", status_filter)

    rows = []
    for snap in query_ref.stream():
        data = snap.to_dict() or {}
        curriculum = data.get("curriculum", {})
        rows.append((snap.id, data, bool(curriculum.get("initializedAt"))))

    rows.sort(key=lambda row: _timestamp_sort_key(row[1].get("createdAt")))

    table = Table(title=f"Daskalo users ({'production' if remote else 'local'}, status={status_filter})")
    table.add_column("UID")
    table.add_column("Email")
    table.add_column("Display name")
    table.add_column("Status")
    table.add_column("Created")
    table.add_column("Last active")
    table.add_column("Curriculum")

    for uid, data, initialized in rows:
        table.add_row(
            uid,
            str(data.get("email", "")),
            str(data.get("displayName", "")),
            str(data.get("status", "")),
            _format_timestamp(data.get("createdAt")),
            _format_timestamp(data.get("lastActive")),
            "yes" if initialized else "no",
        )

    console.print(table)


@users.command("activate")
@click.argument("uid")
@click.option(
    "--remote",
    is_flag=True,
    default=False,
    help="Activate the user in production Firestore instead of the local emulator.",
)
def users_activate(uid: str, remote: bool) -> None:
    """Activate a user and initialize/refresh automatic curriculum selections."""
    fs_client = _get_users_firestore_client(remote)
    result = _activate_user(fs_client, uid)

    console.print(Panel(Text("Daskalo User Activation", justify="center"), style="bold blue"))
    console.print(f"  Target      : [{'bold red' if remote else 'cyan'}]{'production' if remote else 'local emulators'}[/]")
    console.print(f"  UID         : [cyan]{uid}[/cyan]")
    console.print(f"  Status      : {result['old_status']} -> {result['new_status']}")
    console.print(f"  Initialized : {'yes' if result['initialized'] else 'already initialized'}")
    console.print(f"  Rows written: {result['selected_count']}")
    if result["manual_count"]:
        console.print(f"  Manual kept : {result['manual_count']}")
    if result["repair_needed"]:
        console.print("\n[bold yellow]Repair needed for manual selections:[/bold yellow]")
        for slot, chapter_id in result["repair_needed"].items():
            console.print(f"  {slot}: selected chapter not readable ([cyan]{chapter_id}[/cyan])")


def _get_users_firestore_client(remote: bool):
    from google.cloud import firestore

    if remote:
        from services.remote_ingest import get_remote_config

        config = get_remote_config()
        return firestore.Client(project=config["project_id"], database=config["db_name"])

    from services.local_ingest import LOCAL_PROJECT_ID, _configure_emulator_env

    _configure_emulator_env()
    return firestore.Client(project=LOCAL_PROJECT_ID)


def _activate_user(fs_client, uid: str) -> dict:
    user_ref = fs_client.collection("users").document(uid)
    user_snap = user_ref.get()
    if not user_snap.exists:
        raise click.UsageError(f"User '{uid}' not found.")

    user = user_snap.to_dict() or {}
    old_status = str(user.get("status", ""))
    if old_status not in {"pending", "active"}:
        raise click.UsageError(f"User '{uid}' has unsupported status {old_status!r}.")

    selected, repair_needed = _build_curriculum_selection(fs_client, user)
    curriculum = user.get("curriculum", {})
    initialized = not bool(curriculum.get("initializedAt"))
    now = datetime.now(UTC)

    update = {
        "status": "active",
        "curriculum.selectedChapterIdsByCurriculumChapterId": selected,
        "curriculum.updatedAt": now,
    }
    if initialized:
        update["curriculum.initializedAt"] = now

    user_ref.update(update)

    return {
        "old_status": old_status,
        "new_status": "active",
        "initialized": initialized,
        "selected_count": len(selected),
        "manual_count": len(curriculum.get("manualSelectionsByCurriculumChapterId", {}) or {}),
        "repair_needed": repair_needed,
    }


def _build_curriculum_selection(fs_client, user: dict) -> tuple[dict[str, str], dict[str, str]]:
    curriculum = user.get("curriculum", {}) or {}
    existing = dict(curriculum.get("selectedChapterIdsByCurriculumChapterId", {}) or {})
    manual = dict(curriculum.get("manualSelectionsByCurriculumChapterId", {}) or {})

    selectable_by_slot: dict[str, list[tuple[datetime, str]]] = {}
    readable_by_slot: dict[str, set[str]] = {}
    readable_ids: set[str] = set()
    for snap in fs_client.collection("chapters").stream():
        chapter = snap.to_dict() or {}
        slot = chapter.get("curriculumChapterId")
        if not slot:
            continue
        readable_ids.add(snap.id)
        readable_by_slot.setdefault(slot, set()).add(snap.id)
        if chapter.get("isSelectableAlternative") is False:
            continue
        selectable_by_slot.setdefault(slot, []).append((_generated_at_key(chapter.get("generatedAt")), snap.id))

    selected: dict[str, str] = {}
    repair_needed: dict[str, str] = {}
    for slot, variants in selectable_by_slot.items():
        variants.sort(key=lambda item: (item[0], item[1]), reverse=True)
        newest_id = variants[0][1]
        existing_id = existing.get(slot)
        if slot in manual and existing_id:
            selected[slot] = existing_id
            if existing_id not in readable_ids:
                repair_needed[slot] = existing_id
        else:
            selected[slot] = newest_id

    # Preserve selected hidden variants for slots whose selectable variants were all hidden/deleted.
    for slot, selected_id in existing.items():
        if slot not in selected and selected_id in readable_by_slot.get(slot, set()):
            selected[slot] = selected_id
        if slot in manual and slot not in selected:
            selected[slot] = selected_id
            if selected_id not in readable_ids:
                repair_needed[slot] = selected_id

    return selected, repair_needed


def _generated_at_key(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)
    return datetime.min.replace(tzinfo=UTC)


def _timestamp_sort_key(value) -> datetime:
    return _generated_at_key(value)


def _format_timestamp(value) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M")
    return ""


def _upload_local(zip_path: str) -> None:
    """Ingest ZIP into the local Firebase Emulator Suite."""
    console.print("  Target   : [cyan]local emulators[/cyan]")
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


def _upload_remote(zip_path: str) -> None:
    """Ingest ZIP directly into production GCP (Firestore + GCS)."""
    from services.remote_ingest import get_remote_config, ingest_remote

    # Load and display config so the operator knows exactly what will be targeted.
    try:
        config = get_remote_config()
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"\n[bold red]Config error:[/bold red] {exc}")
        raise SystemExit(1) from exc

    console.print("  Target   : [bold red]PRODUCTION[/bold red]")
    console.print(f"  Project  : [cyan]{config['project_id']}[/cyan]")
    console.print(f"  Bucket   : [cyan]{config['public_assets_bucket_name']}[/cyan]")
    console.print(f"  Database : [cyan]{config['db_name']}[/cyan]")
    console.print()

    # Require explicit confirmation before touching production.
    confirmed = click.confirm(
        "You are about to write to PRODUCTION Firestore and GCS. Continue?",
        default=False,
    )
    if not confirmed:
        console.print("[yellow]Aborted.[/yellow]")
        raise SystemExit(0)

    console.print()
    console.print("[bold yellow]Writing content to production Firestore and GCS…[/bold yellow]")
    try:
        chapter_id_written = ingest_remote(zip_path)
        console.print(
            f"\n[bold green]Done![/bold green] Chapter [cyan]{chapter_id_written}[/cyan] "
            f"written to production Firestore (db=[cyan]{config['db_name']}[/cyan])."
        )
        console.print(
            f"Assets uploaded to [cyan]gs://{config['public_assets_bucket_name']}/chapters/{chapter_id_written}/[/cyan]"
        )
        console.print(
            f"ZIP archived at [cyan]gs://{config['public_assets_bucket_name']}/archives/{chapter_id_written}.zip[/cyan]"
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[bold red]Remote ingest failed:[/bold red] {exc}")
        console.print("Ensure you are authenticated: [cyan]gcloud auth application-default login[/cyan]")
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# Pre-flight helpers
# ---------------------------------------------------------------------------


def _check_env(require_gcp_project: bool = True) -> None:
    """Validate required environment variables are present.

    `require_gcp_project` gates the GOOGLE_CLOUD_PROJECT check (CC-10): local
    `upload` (the default) hardcodes the `demo-daskalo` project for the
    Firebase emulators and never reads GOOGLE_CLOUD_PROJECT, so only
    `--remote` ingestion and the generation commands (which call Vertex AI /
    Cloud TTS against the real project regardless of --local/--no-local)
    actually need it.
    """
    required = ["GOOGLE_CLOUD_PROJECT"] if require_gcp_project else []
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        console.print(f"[bold red]Error:[/bold red] Missing required env vars: {', '.join(missing)}")
        console.print("Copy [bold].env.example[/bold] to [bold].env[/bold] and fill in the values.")
        raise SystemExit(1)


def _compute_thread_id(*parts: str) -> str:
    """Compute a stable LangGraph checkpoint thread_id from the inputs that fully
    determine a generation run (IMP-CC-01). Re-running the exact same CLI
    invocation recomputes the same parts, hence the same thread_id, hence the
    same checkpoint file — which is what makes "just re-run the command" an
    accurate resume instruction.
    """
    joined = ":".join(str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _cleanup_work_dir(work_dir: str, keep_work_dir: bool) -> None:
    """Remove the temporary work directory after a successful run (IMP-CC-06).

    The final .zip always lives in `output/`, one level above `work_dir` — it
    is never inside the directory being removed here. No-ops if
    `--keep-work-dir` was passed. A cleanup failure is logged as a warning
    rather than failing the command; it never affects whether generation or
    ingest succeeded.
    """
    if not work_dir:
        return
    if keep_work_dir:
        console.print(f"[dim]Keeping work directory (--keep-work-dir): {work_dir}[/dim]")
        return
    try:
        shutil.rmtree(work_dir)
        logger.debug("Removed work directory: %s", work_dir)
    except OSError as exc:
        logger.warning("Could not remove work directory %s: %s", work_dir, exc)


def _next_practice_id(output_dir: Path, chapter_id: str) -> str:
    """Return the next free `{chapter_id}_ps_NN` practice-set ID (CC-07).

    Real auto-increment, replacing the previously hardcoded `_ps_01` (which
    silently overwrote any existing practice set for the chapter on re-run
    despite the docstring's claim of auto-increment). Scans `output/` for
    previously produced `{chapter_id}_ps_NN.zip` files — the ZIP filename is
    the authoritative local record of a previously generated practice set,
    available whether or not the emulator is currently running.

    Known limitation: this is a local-filesystem counter. If `output/` is
    cleared (e.g. a fresh checkout/CI run) while the corresponding practice
    sets still exist in Firestore, the counter can restart at 01 and collide
    with a document ID that already exists remotely (a merge-write, so it
    would silently overwrite rather than error).
    """
    pattern = re.compile(rf"^{re.escape(chapter_id)}_ps_(\d+)\.zip$")
    max_suffix = 0
    if output_dir.exists():
        for path in output_dir.iterdir():
            match = pattern.match(path.name)
            if match:
                max_suffix = max(max_suffix, int(match.group(1)))
    return f"{chapter_id}_ps_{max_suffix + 1:02d}"


if __name__ == "__main__":
    cli()
