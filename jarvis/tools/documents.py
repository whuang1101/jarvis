from __future__ import annotations

import json


def _join_source(source: object) -> str:
    if isinstance(source, list):
        return "".join(source)
    return str(source)


def _render_outputs(outputs: object) -> str:
    if not isinstance(outputs, list):
        return ""
    parts: list[str] = []
    for out in outputs:
        if not isinstance(out, dict):
            continue
        output_type = out.get("output_type")
        if output_type == "stream":
            parts.append(_join_source(out.get("text", "")))
        elif output_type in ("execute_result", "display_data"):
            data = out.get("data", {})
            if isinstance(data, dict) and "text/plain" in data:
                parts.append(_join_source(data["text/plain"]))
    return "".join(parts).rstrip("\n")


def render_notebook(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            notebook = json.load(f)
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except json.JSONDecodeError as e:
        return f"Error: {path} is not valid notebook JSON: {e}"
    except OSError as e:
        return f"Error reading {path}: {e}"

    if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list):
        return f"Error: {path} is not a valid notebook (missing 'cells')"

    blocks: list[str] = []
    for cell in notebook["cells"]:
        if not isinstance(cell, dict) or "cell_type" not in cell or "source" not in cell:
            return f"Error: {path} has a malformed cell (missing cell_type/source)"

        cell_type = cell["cell_type"]
        block = f"# %% [{cell_type}]\n{_join_source(cell['source'])}"

        if cell_type == "code":
            out_text = _render_outputs(cell.get("outputs", []))
            if out_text:
                block += f"\n# Out:\n{out_text}"

        blocks.append(block)

    return "\n\n".join(blocks)
