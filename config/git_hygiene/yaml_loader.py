"""Carregador mínimo de YAML (subset) — só stdlib, sem PyYAML.

Suporta o schema de git-hygiene.yaml: mapeamentos aninhados, listas `-`,
strings entre aspas, escalares simples e blocos `>` / `|`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class MinimalYamlError(ValueError):
    """YAML fora do subset suportado ou sintaxe inválida."""


def load_mapping(path: Path) -> dict[str, Any]:
    """Carrega um documento YAML cujo root é um mapping."""
    text = path.read_text(encoding="utf-8")
    root = _parse_block(text.splitlines(), 0, 0)[0]
    if not isinstance(root, dict):
        raise MinimalYamlError(f"root deve ser mapping: {path}")
    return root


def _parse_block(
    lines: list[str],
    start: int,
    indent: int,
) -> tuple[Any, int]:
    i = start
    mapping: dict[str, Any] = {}
    sequence: list[Any] | None = None

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        current_indent = len(raw) - len(raw.lstrip(" "))
        if current_indent < indent:
            break
        if current_indent > indent and sequence is None and not mapping:
            raise MinimalYamlError(f"indentação inesperada na linha {i + 1}")
        if current_indent > indent:
            break

        if stripped.startswith("- "):
            if mapping:
                raise MinimalYamlError(f"lista misturada com mapping na linha {i + 1}")
            if sequence is None:
                sequence = []
            item_text = stripped[2:].strip()
            value, i = _parse_value(lines, i, item_text)
            sequence.append(value)
            continue

        if sequence is not None:
            break

        if ":" not in stripped:
            raise MinimalYamlError(f"esperado 'chave:' na linha {i + 1}")

        key, _, rest = stripped.partition(":")
        key = key.strip()
        rest = rest.strip()
        if not key:
            raise MinimalYamlError(f"chave vazia na linha {i + 1}")

        if rest in (">", "|"):
            value, i = _parse_folded(lines, i + 1, current_indent + 2, rest)
            mapping[key] = value
            continue

        if rest == "":
            # Filho indentado (mapping ou lista)
            child, i = _parse_block(lines, i + 1, current_indent + 2)
            mapping[key] = child
            continue

        value, i = _parse_value(lines, i, rest)
        mapping[key] = value

    if sequence is not None:
        return sequence, i
    return mapping, i


def _parse_value(
    lines: list[str],
    index: int,
    token: str,
) -> tuple[Any, int]:
    del lines  # API simétrica com outros parsers; escalares não consomem linhas extras
    if token.startswith(("'", '"')):
        return _unquote(token), index + 1

    if token.endswith(":"):
        raise MinimalYamlError(f"valor inválido na linha {index + 1}")

    lowered = token.lower()
    if lowered == "true":
        return True, index + 1
    if lowered == "false":
        return False, index + 1
    if lowered in {"null", "~"}:
        return None, index + 1
    if _is_int(token):
        return int(token), index + 1

    return token, index + 1


def _parse_folded(
    lines: list[str],
    start: int,
    indent: int,
    style: str,
) -> tuple[str, int]:
    chunks: list[str] = []
    i = start
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.strip().startswith("#"):
            # linha em branco dentro do bloco: preserva separação
            if raw.strip().startswith("#"):
                i += 1
                continue
            if chunks:
                chunks.append("")
            i += 1
            continue
        current_indent = len(raw) - len(raw.lstrip(" "))
        if current_indent < indent:
            break
        chunks.append(raw[indent:] if current_indent >= indent else raw.strip())
        i += 1

    if style == ">":
        # folded: newlines → espaço; blocos vazios → newline
        text = " ".join(part.strip() for part in chunks if part.strip())
        return text.strip(), i

    return "\n".join(chunks).strip(), i


def _unquote(token: str) -> str:
    if len(token) < 2 or token[0] not in ("'", '"') or token[-1] != token[0]:
        raise MinimalYamlError(f"string sem aspas balanceadas: {token!r}")
    quote = token[0]
    body = token[1:-1]
    if quote == '"':
        return (
            body.replace("\\\\", "\\")
            .replace("\\n", "\n")
            .replace('\\"', '"')
        )
    return body.replace("''", "'")


def _is_int(token: str) -> bool:
    if token.startswith("-"):
        return token[1:].isdigit()
    return token.isdigit()
