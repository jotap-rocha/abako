"""CLI ``python -m config.agent_policies generate|check``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config.agent_policies.contract import AgentPoliciesContract

DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / "agent-policies.yaml"


def main(argv: list[str] | None = None) -> int:
    """Entry point da CLI agent-policies."""
    parser = argparse.ArgumentParser(
        prog="python -m config.agent_policies",
        description="Kernel agent-policies: check contrato e generate artefatos dual-runtime",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser("check", help="Valida agent-policies.yaml")
    check_p.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_CONTRACT,
        help="Path do contrato YAML (default: raiz do repo)",
    )

    gen_p = sub.add_parser(
        "generate",
        help="Gera permissions.deny Claude + hooks Cursor a partir do catálogo",
    )
    gen_p.add_argument("--path", type=Path, default=DEFAULT_CONTRACT)
    gen_p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Diretório de saída (default: stdout JSON resumido / cwd relativo)",
    )
    gen_p.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="Path opcional de .harness/policies/project_profile.yaml",
    )
    gen_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Imprime artefatos sem escrever arquivos",
    )

    args = parser.parse_args(argv)

    if args.command == "check":
        return _cmd_check(args.path)
    if args.command == "generate":
        from config.agent_policies.generate import generate_artifacts, write_artifacts

        try:
            result = generate_artifacts(
                contract_path=args.path,
                profile_path=args.profile,
            )
        except Exception as exc:  # noqa: BLE001 — boundary CLI
            print(f"generate failed: {exc}", file=sys.stderr)
            return 1
        if args.dry_run or args.out_dir is None:
            print(result.to_summary())
            return 0
        write_artifacts(result, args.out_dir)
        print(f"wrote artifacts under {args.out_dir}")
        return 0
    return 2


def _cmd_check(path: Path) -> int:
    try:
        contract = AgentPoliciesContract.load(path)
    except Exception as exc:  # noqa: BLE001 — boundary CLI
        print(f"check failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"ok: version={contract.version} "
        f"core={len(contract.core_families)} "
        f"families={len(contract.families)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
