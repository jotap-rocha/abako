"""Parser YAML mínimo para ``waivers.yaml`` (lista de mappings).

O ``MinimalYaml`` do git-hygiene não cobre itens de lista com campos
aninhados (``- rule_id:`` + ``owner:`` / ``expiry:``). Este módulo isola
esse subset sem expandir o loader compartilhado nem puxar PyYAML.
"""

from __future__ import annotations

from typing import Any


class WaiversYamlError(ValueError):
    """Documento de waiver fora do subset suportado."""


def parse_waivers_document(text: str) -> list[dict[str, Any]]:
    """Retorna a lista sob ``waivers:``; ``[]`` / ausente → lista vazia."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        indent = _indent(raw)
        if indent != 0:
            raise WaiversYamlError(f"conteúdo inesperado fora da raiz (linha {i + 1})")
        if stripped in {"waivers: []", "waivers:[]"}:
            return []
        if stripped == "waivers:":
            return _parse_waiver_list(lines, i + 1)
        if stripped.startswith("waivers:"):
            rest = stripped.split(":", 1)[1].strip()
            if rest in {"[]", ""}:
                return []
            raise WaiversYamlError(
                f"waivers inline não suportado além de [] (linha {i + 1})"
            )
        raise WaiversYamlError(f"chave raiz esperada 'waivers:' (linha {i + 1})")
    return []


def _parse_waiver_list(lines: list[str], start: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    i = start
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        indent = _indent(raw)
        if indent == 0:
            break
        if indent != 2 or not stripped.startswith("-"):
            raise WaiversYamlError(
                f"item de waiver deve ser '- ...' com indent 2 (linha {i + 1})"
            )
        item_token = stripped[1:].strip()
        item: dict[str, Any] = {}
        if item_token:
            _assign_field(item, item_token, i + 1)
        i += 1
        while i < len(lines):
            nested_raw = lines[i]
            nested_stripped = nested_raw.strip()
            if not nested_stripped or nested_stripped.startswith("#"):
                i += 1
                continue
            nested_indent = _indent(nested_raw)
            if nested_indent <= 2:
                break
            if nested_indent != 4:
                raise WaiversYamlError(
                    f"campo de waiver deve ter indent 4 (linha {i + 1})"
                )
            _assign_field(item, nested_stripped, i + 1)
            i += 1
        items.append(item)
    return items


def _assign_field(target: dict[str, Any], token: str, line_no: int) -> None:
    if ":" not in token:
        raise WaiversYamlError(f"esperado 'chave: valor' na linha {line_no}")
    key, _, rest = token.partition(":")
    key = key.strip()
    rest = rest.strip()
    if not key:
        raise WaiversYamlError(f"chave vazia na linha {line_no}")
    target[key] = _scalar(rest)


def _scalar(token: str) -> Any:
    if token == "":
        return ""
    if token.startswith(("'", '"')) and len(token) >= 2 and token[-1] == token[0]:
        return token[1:-1]
    lowered = token.lower()
    if lowered in {"null", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return token


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))
