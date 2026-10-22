"""Render actual order models/macros for bounded offline and opt-in native tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "dbt"


def render_order_sql(
    relative: str,
    *,
    ref: Callable[[str], str] = lambda name: name,
    config: Callable[..., str] | None = None,
) -> str:
    jinja = pytest.importorskip("jinja2")
    environment = jinja.Environment(undefined=jinja.StrictUndefined)
    context = {"ref": ref}
    if config is not None:
        context["config"] = config
    module = environment.from_string(
        (PROJECT / "macros/order_components.sql").read_text("utf-8")
    ).make_module(context)
    return environment.from_string((PROJECT / relative).read_text("utf-8")).render(
        **context, order_components=module.order_components
    )


def render_order_model(name: str, ref: Callable[[str], str] = lambda name: name) -> str:
    return render_order_sql(f"models/marts/{name}.sql", ref=ref)
