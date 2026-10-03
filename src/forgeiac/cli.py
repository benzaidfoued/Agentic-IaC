"""Command line interface. All mutation approvals stay outside the model boundary."""

import argparse
import json
import os
import sys
import time

from . import __version__
from .ai import select
from .core import ForgeError, default_catalog, load_catalog, propose
from .engine import apply, export_gitops, plan, status
from .knowledge import index_docs, search
from .store import Store, write_json


def fields(values):
    result = {}
    for value in values:
        key, separator, raw = value.partition("=")
        if not separator or not key:
            raise ForgeError("Parameters use --set key=value")
        try:
            result[key] = json.loads(raw)
        except ValueError:
            result[key] = raw
    return result


def parser():
    cli = argparse.ArgumentParser(description="ForgeIaC · intent → review → infrastructure")
    cli.add_argument("--version", action="version", version=__version__)
    cli.add_argument("--catalog", default=default_catalog())
    cli.add_argument("--home", default=".forgeiac", help="Private persistent run/state directory")
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="List trusted infrastructure blueprints")
    request = commands.add_parser("request", help="Create a proposal; no infrastructure changes")
    request.add_argument("prompt", nargs="?", default="")
    request.add_argument("--blueprint", help="Deterministic mode: no model or API key required")
    request.add_argument("--model", default=os.getenv("FORGEIAC_MODEL"))
    request.add_argument("--engine", choices=["terraform", "crossplane"])
    request.add_argument("--set", action="append", default=[])
    revise = commands.add_parser(
        "revise", help="Update an existing run while retaining Terraform state"
    )
    revise.add_argument("run")
    revise.add_argument("--set", action="append", default=[], required=True)
    show = commands.add_parser("show", help="Inspect generated IaC and its parameters")
    show.add_argument("run")
    planning = commands.add_parser("plan", help="Validate and produce an approval-bound plan")
    planning.add_argument("run")
    planning.add_argument("--context", help="Required explicit kube context for Crossplane")
    execution = commands.add_parser("apply", help="Apply the exact reviewed plan")
    execution.add_argument("run")
    execution.add_argument("--approve", required=True, help="Full approval digest from plan")
    execution.add_argument(
        "--direct", action="store_true", help="Opt in to non-GitOps Crossplane apply"
    )
    export = commands.add_parser("export", help="Export Crossplane resource + Kustomization")
    export.add_argument("run")
    export.add_argument("--approve", required=True)
    export.add_argument("--destination", required=True)
    observe = commands.add_parser("status")
    observe.add_argument("run")
    observe.add_argument("--wait", type=int, default=0, metavar="SECONDS")
    index = commands.add_parser("index", help="Index approved Markdown docs locally for RAG")
    index.add_argument("directory")
    query = commands.add_parser("search")
    query.add_argument("query")
    commands.add_parser("doctor", help="Check local prerequisites, without cloud calls")
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    os.umask(0o077)
    try:
        store = Store(args.home)
        database = store.root / "knowledge.db"
        if args.command == "catalog":
            result = [
                {
                    "id": e["id"],
                    "engine": e["engine"],
                    "description": e["description"],
                    "parameters": e["parameters"],
                }
                for e in load_catalog(args.catalog).values()
            ]
        elif args.command == "request":
            catalog = load_catalog(args.catalog)
            citations = []
            supplied = fields(args.set)
            if args.blueprint:
                choice = {"blueprint": args.blueprint, "parameters": supplied}
            else:
                if not args.model or not args.prompt:
                    raise ForgeError(
                        "Supply --blueprint, or a request text and --model provider:model"
                    )
                evidence = search(database, args.prompt)
                citations = [item["source"] for item in evidence]
                choice = select(catalog, args.prompt, args.model, args.engine, evidence)
                choice["parameters"].update(supplied)
            proposal = propose(catalog, choice["blueprint"], choice["parameters"])
            if args.engine and proposal["engine"] != args.engine:
                raise ForgeError("Blueprint does not match requested engine")
            proposal["citations"] = citations
            run_id = store.create(proposal)
            result = {
                "run": run_id,
                "engine": proposal["engine"],
                "status": "proposed",
                "citations": citations,
                "next": f"forgeiac show {run_id}; forgeiac plan {run_id}",
            }
        elif args.command == "revise":
            with store.lock(args.run):
                old = store.read(args.run, "proposal.json")
                params = old["parameters"] | fields(args.set)
                proposal = propose(load_catalog(args.catalog), old["blueprint"], params)
                # A blueprint keeps one stable infrastructure identity per run.
                identity_fields = ("name", "namespace", "subscription_id")
                if any(
                    old["parameters"].get(k) != proposal["parameters"].get(k)
                    for k in identity_fields
                ):
                    raise ForgeError("Identity fields cannot change; create a separate run")
                path = store.path(args.run)
                write_json(path / "proposal.json", proposal)
                filename = "main.tf.json" if proposal["engine"] == "terraform" else "resource.json"
                write_json(path / filename, proposal["artifact"])
                (path / "plan.json").unlink(missing_ok=True)
                store.event(args.run, "revised")
                result = {
                    "run": args.run,
                    "status": "revised",
                    "next": "Create and review a new plan",
                }
        elif args.command == "show":
            result = store.read(args.run, "proposal.json")
        elif args.command == "plan":
            result = plan(store, args.run, args.context)
        elif args.command == "apply":
            result = apply(store, args.run, args.approve, args.direct)
        elif args.command == "export":
            result = export_gitops(store, args.run, args.approve, args.destination)
        elif args.command == "status":
            deadline = time.monotonic() + max(0, args.wait)
            while True:
                result = status(store, args.run)
                if result["status"] in ("ready", "applied", "failed") or not args.wait:
                    break
                if time.monotonic() >= deadline:
                    raise ForgeError(
                        "Readiness deadline exceeded; inspect status and controller events"
                    )
                time.sleep(min(5, max(0, deadline - time.monotonic())))
        elif args.command == "index":
            result = {"indexed_chunks": index_docs(args.directory, database)}
        elif args.command == "search":
            result = search(database, args.query)
        else:
            import shutil

            result = {name: bool(shutil.which(name)) for name in ("terraform", "kubectl", "git")}
            result["python"] = sys.version.split()[0]
        print(json.dumps(result, indent=2))
        return 0
    except (ForgeError, OSError, ValueError, KeyError) as exc:
        print(f"forgeiac: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
