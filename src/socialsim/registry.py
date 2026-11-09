"""Command registry: handlers register themselves with a decorator; the CLI builds argparse from it."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from socialsim.validation import Field


@dataclass
class Cmd:
    group: str | None  # None => top-level command
    name: str
    fn: Callable[..., Any]
    help: str
    example: str
    id_arg: str | None = None  # metavar of the positional id, if any
    payload: str | None = None  # None | "required" | "optional"
    flags: tuple[str, ...] = ()  # confirm | full | sql | limit | table | format | out
    spec: dict[str, Field] | None = None  # documented payload fields (for `commands`)


REGISTRY: list[Cmd] = []


def command(
    group: str | None,
    name: str,
    *,
    help: str,
    example: str,
    id_arg: str | None = None,
    payload: str | None = None,
    flags: tuple[str, ...] = (),
    spec: dict[str, Field] | None = None,
):
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        REGISTRY.append(Cmd(group, name, fn, help, example, id_arg, payload, flags, spec))
        return fn

    return deco
