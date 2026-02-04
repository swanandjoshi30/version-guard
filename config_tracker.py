#!/usr/bin/env python3
import sys
import time
from pathlib import Path
from collections import deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import difflib
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.syntax import Syntax
from rich.text import Text

console = Console()


class FolderWatcher(FileSystemEventHandler):
    def __init__(self, files_to_track, history=1, encoding='utf-8'):
        """
        files_to_track: list of Path objects
        """
        self.files_to_track = {f.resolve(): deque(maxlen=history + 1) for f in files_to_track}
        self.encoding = encoding

        # Read initial content
        for path in self.files_to_track:
            if path.exists():
                self.files_to_track[path].append(path.read_text(encoding=self.encoding))
            else:
                self.files_to_track[path].append("")

    def on_modified(self, event):
        self._handle_event(event)

    def on_created(self, event):
        self._handle_event(event)

    def _handle_event(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path).resolve()
        if path not in self.files_to_track:
            return

        old = self.files_to_track[path][-1] if self.files_to_track[path] else ""
        try:
            new = path.read_text(encoding=self.encoding)
        except Exception as e:
            new = f"[error reading file: {e}]"

        if new != old:
            self.files_to_track[path].append(new)
            self.print_diff(path, old, new)

    def print_diff(self, path, old, new):
        old_lines = old.splitlines()
        new_lines = new.splitlines()
        diff = list(difflib.ndiff(old_lines, new_lines))

        left = []
        right = []
        for line in diff:
            code = line[:2]
            text = line[2:]
            if code == "- ":
                left.append(Text(f"- {text}", style="bold red"))
            elif code == "+ ":
                right.append(Text(f"+ {text}", style="bold green"))
            elif code == "? ":
                continue
            else:   
                left.append(Text(f"  {text}"))
                right.append(Text(f"  {text}"))

        left_panel = Panel(
            Syntax("\n".join(t.plain for t in left), "text", theme="monokai", line_numbers=False),
            title="Before",
            border_style="red",
        )
        right_panel = Panel(
            Syntax("\n".join(t.plain for t in right), "text", theme="monokai", line_numbers=False),
            title="After",
            border_style="green",
        )

        header = Text.assemble(("File changed: ", "bold"), (str(path), "italic"))
        console.rule(header)
        console.print(Columns([left_panel, right_panel]))
        console.rule()


def main():
    if len(sys.argv) < 2:
        console.print("[red]Usage: python config_tracker.py file1 [file2 ...][/red]")
        sys.exit(1)

    files = [Path(p).resolve() for p in sys.argv[1:]]
    folder_map = {}
    for f in files:
        folder_map.setdefault(f.parent.resolve(), []).append(f)

    observer = Observer()

    # Create one FolderWatcher per unique folder
    for folder, files_in_folder in folder_map.items():
        watcher = FolderWatcher(files_in_folder)
        observer.schedule(watcher, str(folder), recursive=False)

    observer.start()
    console.print(f"Watching {len(files)} files for changes. Press Ctrl+C to quit.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("Stopping watcher...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()