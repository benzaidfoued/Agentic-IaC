"""Private local run store. Hashes prevent accidental edits, not hostile local users."""

import contextlib
import fcntl
import json
import os
import re
import time
import uuid
from pathlib import Path

from .core import ForgeError


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    temporary.replace(path)


class Store:
    def __init__(self, root=".forgeiac"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)

    def path(self, run_id):
        if not re.fullmatch(r"[a-f0-9]{16}", run_id):
            raise ForgeError("Invalid run ID")
        path = self.root / "runs" / run_id
        if not path.is_dir() or path.is_symlink():
            raise ForgeError("Run not found")
        return path

    def create(self, proposal):
        run_id = uuid.uuid4().hex[:16]
        path = self.root / "runs" / run_id
        path.mkdir(parents=True, mode=0o700)
        write_json(path / "proposal.json", proposal)
        name = "main.tf.json" if proposal["engine"] == "terraform" else "resource.json"
        write_json(path / name, proposal["artifact"])
        self.event(run_id, "proposed", {"blueprint": proposal["blueprint"]})
        return run_id

    def read(self, run_id, name):
        path = self.path(run_id) / name
        if not path.is_file():
            raise ForgeError(f"Run has no {name}; complete the preceding step")
        return json.loads(path.read_text())

    @contextlib.contextmanager
    def lock(self, run_id):
        with (self.path(run_id) / ".lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ForgeError("Another operation is active on this run") from exc
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def event(self, run_id, action, data=None):
        with (self.path(run_id) / "events.jsonl").open("a") as stream:
            os.chmod(stream.name, 0o600)
            stream.write(
                json.dumps({"time": time.time(), "action": action, "data": data or {}}) + "\n"
            )
