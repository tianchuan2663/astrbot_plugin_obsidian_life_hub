from __future__ import annotations

import re


def markdown_to_push_text(markdown: str) -> str:
    """Convert report Markdown to readable plain text for active push fallback."""
    lines: list[str] = []
    table_header: list[str] | None = None

    for raw_line in str(markdown or "").splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if _is_table_separator(line):
            continue
        if _is_table_row(line):
            cells = _table_cells(line)
            if table_header is None:
                table_header = cells
                continue
            if len(cells) == len(table_header):
                lines.append(_format_table_item(table_header, cells))
            else:
                lines.append("  ".join(cells))
            continue

        table_header = None
        lines.append(_format_non_table_line(line))

    return _compact_blank_lines("\n".join(lines)).strip()


def _is_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    if not _is_table_row(line):
        return False
    body = line.strip("|").replace(" ", "")
    return bool(body) and all(char in "-:|" for char in body)


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip("|").split("|")]


def _format_table_item(headers: list[str], cells: list[str]) -> str:
    pairs = [(header, cell) for header, cell in zip(headers, cells) if cell]
    if not pairs:
        return ""

    first_header, first_cell = pairs[0]
    rest = [f"{header}: {cell}" for header, cell in pairs[1:]]
    if first_header in {"内容", "计划", "范围"}:
        prefix = f"- {first_cell}"
    else:
        prefix = f"- {first_header}: {first_cell}"
    return f"{prefix}  {'  '.join(rest)}".rstrip()


def _format_non_table_line(line: str) -> str:
    heading_match = re.match(r"^(#{1,6})\s*(.+)$", line)
    if heading_match:
        level = len(heading_match.group(1))
        title = heading_match.group(2).strip()
        return title if level <= 2 else f"- {title}"
    if line.startswith("- "):
        return line
    return line


def _compact_blank_lines(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

