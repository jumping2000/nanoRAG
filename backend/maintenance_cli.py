from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime

from config import get_settings
from maintenance import (
    delete_kb_totally,
    purge_orphan_qdrant_points,
    rebuild_kb_from_sparse_chunks,
    reset_all_state,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="nanoRAG maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    delete_kb_parser = subparsers.add_parser("delete-kb", help="Delete one knowledge base across all stores")
    delete_kb_parser.add_argument("kb_id")

    rebuild_kb_parser = subparsers.add_parser(
        "rebuild-kb",
        help="Rebuild metadata catalog entries for one KB from the sparse chunk store",
    )
    rebuild_kb_parser.add_argument("kb_id")

    subparsers.add_parser(
        "purge-qdrant-orphans",
        help="Delete Qdrant points missing kb_id payloads",
    )

    reset_all_parser = subparsers.add_parser(
        "reset-all",
        help="Reset local metadata, graph store, uploads, sparse store and Qdrant collection",
    )
    reset_all_parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup copies for metadata and sparse files before reset",
    )

    args = parser.parse_args()
    settings = get_settings()

    if args.command == "delete-kb":
        return _print(delete_kb_totally(settings, args.kb_id).model_dump())

    if args.command == "rebuild-kb":
        return _print(rebuild_kb_from_sparse_chunks(settings, args.kb_id))

    if args.command == "purge-qdrant-orphans":
        return _print({"deleted_orphan_points": purge_orphan_qdrant_points(settings)})

    if args.command == "reset-all":
        backups = [] if args.no_backup else _backup_local_state(settings)
        summary = reset_all_state(settings)
        payload = asdict(summary)
        payload["backups"] = backups
        return _print(payload)

    raise ValueError(f"Unknown maintenance command: {args.command}")


def _backup_local_state(settings) -> list[str]:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backups: list[str] = []
    for path in (
        settings.knowledge_bases_store_path,
        settings.documents_store_path,
        settings.chunks_store_path,
    ):
        if not path.exists():
            continue
        target = path.with_name(f"{path.stem}.{timestamp}.bak{path.suffix}")
        shutil.copy2(path, target)
        backups.append(str(target))
    return backups


def _print(payload: object) -> int:
    serializable = asdict(payload) if is_dataclass(payload) else payload
    print(json.dumps(serializable, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())