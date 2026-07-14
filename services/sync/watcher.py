"""File system sync service for .weave.md files."""
import hashlib
from pathlib import Path
from typing import List, Optional, Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from services.parser.parser import WeaveParser
from services.graph.engine import GraphEngine
from services.shared.models import WeaveFile, Entry, Tag, SessionLocal


class WeaveEventHandler(FileSystemEventHandler):
    """Handle file system events for .weave.md files."""

    def __init__(self, parser: WeaveParser, on_change: Callable):
        self.parser = parser
        self.on_change = on_change
        self._file_hashes: dict = {}

    def _is_weave_file(self, path: str) -> bool:
        return path.endswith('.weave.md')

    def _get_hash(self, path: str) -> str:
        try:
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except (IOError, OSError):
            return ""

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory or not self._is_weave_file(event.src_path):
            return
        try:
            parsed = self.parser.parse_file(Path(event.src_path))
            self._file_hashes[event.src_path] = self._get_hash(event.src_path)
            self.on_change(parsed, event.src_path, 'created')
        except Exception as e:
            print(f"Error processing {event.src_path}: {e}")

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory or not self._is_weave_file(event.src_path):
            return
        new_hash = self._get_hash(event.src_path)
        if self._file_hashes.get(event.src_path) == new_hash:
            return
        try:
            parsed = self.parser.parse_file(Path(event.src_path))
            self._file_hashes[event.src_path] = new_hash
            self.on_change(parsed, event.src_path, 'modified')
        except Exception as e:
            print(f"Error processing {event.src_path}: {e}")

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory or not self._is_weave_file(event.src_path):
            return
        self._file_hashes.pop(event.src_path, None)
        self.on_change(None, event.src_path, 'deleted')


class WeaveSyncService:
    """Sync .weave.md files with the database."""

    def __init__(self, watch_dirs: List[str], parser: Optional[WeaveParser] = None):
        self.watch_dirs = [Path(d) for d in watch_dirs]
        self.parser = parser or WeaveParser()
        self.observer: Optional[Observer] = None

    def _upsert_file(self, parsed, file_path: str, event_type: str) -> int:
        """Upsert a weave file into the database."""
        db = SessionLocal()
        try:
            # Find existing file
            existing = db.query(WeaveFile).filter(WeaveFile.file_path == file_path).first()

            if existing:
                existing.project_name = parsed.project_name
                existing.status = parsed.status
                # Clear old entries
                db.query(Entry).filter(Entry.weave_file_id == existing.id).delete()
                db.flush()
                weave_file = existing
            else:
                weave_file = WeaveFile(
                    file_path=file_path,
                    project_name=parsed.project_name,
                    status=parsed.status,
                )
                db.add(weave_file)
                db.flush()

            # Add entries
            for parsed_entry in parsed.entries:
                entry = Entry(
                    weave_file_id=weave_file.id,
                    entry_type=parsed_entry.entry_type,
                    title=parsed_entry.title,
                    content=parsed_entry.content,
                    outcome=parsed_entry.outcome,
                    scope=parsed_entry.scope,
                    status=parsed_entry.status,
                    owner=parsed_entry.owner,
                    source_ref=parsed_entry.source_ref,
                )
                db.add(entry)
                db.flush()

                # Add tags
                for tag_name in parsed_entry.tags:
                    tag = db.query(Tag).filter(Tag.name == tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.add(tag)
                        db.flush()
                    entry.tags.append(tag)

            db.commit()

            return len(parsed.entries)

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def _delete_file(self, file_path: str) -> None:
        """Delete a weave file from the database."""
        db = SessionLocal()
        try:
            weave_file = db.query(WeaveFile).filter(WeaveFile.file_path == file_path).first()
            if weave_file:
                db.delete(weave_file)
                db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def initial_sync(self) -> int:
        """Sync all .weave.md files in watch directories."""
        count = 0
        for watch_dir in self.watch_dirs:
            if not watch_dir.exists():
                continue
            for file_path in watch_dir.rglob('*.weave.md'):
                try:
                    parsed = self.parser.parse_file(file_path)
                    self._upsert_file(parsed, str(file_path), 'initial')
                    count += 1
                except Exception as e:
                    print(f"Error syncing {file_path}: {e}")

        # SECOND PASS: resolve cross-file references after all files are in DB
        db = SessionLocal()
        try:
            graph = GraphEngine(db)
            for weave_file in db.query(WeaveFile).all():
                graph.resolve_references(str(weave_file.id))
        except Exception as e:
            print(f"Error resolving references: {e}")
        finally:
            db.close()

        return count

    def start(self) -> None:
        """Start file system watcher."""
        self.observer = Observer()
        handler = WeaveEventHandler(
            parser=self.parser,
            on_change=lambda p, fp, et: self._upsert_file(p, fp, et) if p else self._delete_file(fp),
        )

        for watch_dir in self.watch_dirs:
            if watch_dir.exists():
                self.observer.schedule(handler, str(watch_dir), recursive=True)

        self.observer.start()
        print(f"Weave sync watching {len(self.watch_dirs)} directories")

    def stop(self) -> None:
        """Stop file system watcher."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()