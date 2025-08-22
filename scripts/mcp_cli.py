#!/usr/bin/env python3
# clients/mcp_cli.py
import argparse
import json
import subprocess
import sys
import threading
import time
import uuid
from typing import Any

# ---------- JSON-RPC over stdio ----------


class JsonRpcStdioClient:
    def __init__(self, cmd: list[str]):
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line-buffered
        )
        self._lock = threading.Lock()
        self._responses: dict[str, Any] = {}
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                # If the server prints logs to stdout, surface them
                print(f"[cli] non-JSON from server stdout: {line}", file=sys.stderr)
                continue
            mid = str(msg.get("id"))
            with self._lock:
                self._responses[mid] = msg

    def call(self, method: str, params: dict[str, Any]) -> Any:
        msg_id = str(uuid.uuid4())
        req = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        payload = json.dumps(req) + "\n"
        assert self.proc.stdin is not None
        with self._lock:
            self.proc.stdin.write(payload)
            self.proc.stdin.flush()

        deadline = time.time() + 90
        while time.time() < deadline:
            with self._lock:
                if msg_id in self._responses:
                    resp = self._responses.pop(msg_id)
                    break
            time.sleep(0.01)
        else:
            raise TimeoutError(f"Timeout waiting for {method}")

        if "error" in resp:
            err = resp["error"]
            code = err.get("code", "UNKNOWN")
            msg = err.get("message", "Error")
            details = err.get("data") or err.get("details")
            raise RuntimeError(
                f"{method} failed [{code}]: {msg}\nDetails: {json.dumps(details, indent=2)}"
            )

        return resp.get("result")

    def close(self):
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
        except Exception:
            pass


# ---------- Command handlers ----------


def cmd_pubmed_search(client, a):
    res = client.call("pubmed.search", {"term": a.term, "limit": a.limit})
    print(json.dumps(res, indent=2))


def cmd_pubmed_get(client, a):
    res = client.call("pubmed.get", {"pmid": a.pmid})
    print(json.dumps(res, indent=2))


def cmd_pubmed_sync(client, a):
    params = {"term": a.term}
    if a.query_key:
        params["query_key"] = a.query_key
    if a.overlap_days is not None:
        params["overlap_days"] = a.overlap_days
    res = client.call("pubmed.sync", params)
    print(json.dumps(res, indent=2))


def cmd_pubmed_sync_incremental(client, a):
    params = {"query_key": a.query_key}
    if a.overlap_days is not None:
        params["overlap_days"] = a.overlap_days
    res = client.call("pubmed.sync.incremental", params)
    print(json.dumps(res, indent=2))


def cmd_ckpt_create(client, a):
    res = client.call(
        "corpus.checkpoint.create",
        {
            "checkpoint_id": a.checkpoint_id,
            "name": a.name,
            "description": a.description or "",
        },
    )
    print(json.dumps(res, indent=2))


def cmd_ckpt_get(client, a):
    res = client.call("corpus.checkpoint.get", {"checkpoint_id": a.checkpoint_id})
    print(json.dumps(res, indent=2))


def cmd_ckpt_list(client, a):
    res = client.call("corpus.checkpoint.list", {})
    print(json.dumps(res, indent=2))


def cmd_ckpt_delete(client, a):
    res = client.call("corpus.checkpoint.delete", {"checkpoint_id": a.checkpoint_id})
    print(json.dumps(res, indent=2))


def cmd_rag_search(client, a):
    res = client.call("rag.search", {"query": a.query, "top_k": a.top_k})
    print(json.dumps(res, indent=2))


def cmd_rag_get(client, a):
    res = client.call("rag.get", {"doc_id": a.doc_id})
    print(json.dumps(res, indent=2))


def cmd_raw(client, a):
    # Power-user escape hatch if schemas differ: pass any method/JSON params
    params = json.loads(a.params) if a.params else {}
    res = client.call(a.method, params)
    print(json.dumps(res, indent=2))


# ---------- CLI wiring ----------


def build_parser():
    p = argparse.ArgumentParser(
        description="Thin JSON-RPC stdio client for the bio-mcp server."
    )
    p.add_argument(
        "--server-cmd",
        default="python main.py",
        help="Command to start the MCP server (spawned per invocation).",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("pubmed.search", help="Search curated PubMed corpus")
    s.add_argument("--term", required=True)
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(func=cmd_pubmed_search)

    s = sub.add_parser("pubmed.get", help="Get one abstract by PMID")
    s.add_argument("--pmid", required=True)
    s.set_defaults(func=cmd_pubmed_get)

    s = sub.add_parser(
        "pubmed.sync", help="Run a sync (e.g., backfill or ad-hoc refresh)"
    )
    s.add_argument(
        "--term", required=True, help="PubMed term (use your compiler output)"
    )
    s.add_argument("--query-key", help="Name for checkpointing this corpus")
    s.add_argument("--overlap-days", type=int, default=5)
    s.set_defaults(func=cmd_pubmed_sync)

    s = sub.add_parser(
        "pubmed.sync.incremental", help="Incremental delta sync using checkpoint"
    )
    s.add_argument("--query-key", required=True)
    s.add_argument("--overlap-days", type=int, default=5)
    s.set_defaults(func=cmd_pubmed_sync_incremental)

    s = sub.add_parser("corpus.checkpoint.create", help="Create a research snapshot")
    s.add_argument("--checkpoint-id", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--description")
    s.set_defaults(func=cmd_ckpt_create)

    s = sub.add_parser("corpus.checkpoint.get", help="Get a snapshot by id")
    s.add_argument("--checkpoint-id", required=True)
    s.set_defaults(func=cmd_ckpt_get)

    s = sub.add_parser("corpus.checkpoint.list", help="List snapshots")
    s.set_defaults(func=cmd_ckpt_list)

    s = sub.add_parser("corpus.checkpoint.delete", help="Delete a snapshot")
    s.add_argument("--checkpoint-id", required=True)
    s.set_defaults(func=cmd_ckpt_delete)

    s = sub.add_parser("rag.search", help="Hybrid semantic + keyword search")
    s.add_argument("--query", required=True)
    s.add_argument("--top-k", type=int, default=10)
    s.set_defaults(func=cmd_rag_search)

    s = sub.add_parser("rag.get", help="Fetch a document (e.g., pmid:123)")
    s.add_argument("--doc-id", required=True)
    s.set_defaults(func=cmd_rag_get)

    # raw escape hatch
    s = sub.add_parser("raw", help="Call any method with JSON params")
    s.add_argument("--method", required=True, help="e.g., pubmed.search")
    s.add_argument("--params", help='JSON string: e.g., \'{"term":"x","limit":5}\'')
    s.set_defaults(func=cmd_raw)

    return p


def main():
    args = build_parser().parse_args()
    server_cmd = (
        args.server_cmd
        if isinstance(args.server_cmd, list)
        else args.server_cmd.split()
    )
    client = JsonRpcStdioClient(server_cmd)
    try:
        args.func(client, args)
    finally:
        client.close()


if __name__ == "__main__":
    main()
