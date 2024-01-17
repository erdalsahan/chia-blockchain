from __future__ import annotations

import asyncio
import inspect
from contextlib import asynccontextmanager
from dataclasses import MISSING, Field, dataclass, field, fields
from typing import Any, AsyncIterator, Callable, Dict, Iterable, Optional, Protocol, Type, Union

import click
from typing_extensions import dataclass_transform

from chia.cmds.cmds_util import get_wallet_client
from chia.rpc.wallet_rpc_client import WalletRpcClient

SyncCmd = Callable[..., None]


class SyncChiaCommand(Protocol):
    def run(self) -> None:
        ...


class AsyncChiaCommand(Protocol):
    async def run(self) -> None:
        ...


ChiaCommand = Union[SyncChiaCommand, AsyncChiaCommand]


def option(*param_decls: str, **kwargs: Any) -> Any:
    return field(
        metadata=dict(
            is_command_option=True,
            param_decls=tuple(param_decls),
            **kwargs,
        ),
        default=kwargs["default"] if "default" in kwargs else MISSING,
    )


def _apply_options(cmd: SyncCmd, _fields: Iterable[Field[Any]]) -> SyncCmd:
    wrapped_cmd = cmd
    for _field in _fields:
        if "is_command_option" not in _field.metadata or not _field.metadata["is_command_option"]:
            continue
        wrapped_cmd = click.option(
            *_field.metadata["param_decls"],
            **{k: v for k, v in _field.metadata.items() if k not in ("param_decls", "is_command_option")},
        )(wrapped_cmd)

    return wrapped_cmd


@dataclass_transform()
def chia_command(cmd: click.Group, name: str, help: str) -> Callable[[Type[ChiaCommand]], Type[ChiaCommand]]:
    def _chia_command(cls: Type[ChiaCommand]) -> Type[ChiaCommand]:
        # The type ignores here are largely due to the fact that the class information is not preserved after being
        # passed through the dataclass wrapper.  Not sure what to do about this right now.
        wrapped_cls: Type[ChiaCommand] = dataclass(  # type: ignore[assignment]
            frozen=True,
            kw_only=True,
        )(cls)
        cls_fields = fields(wrapped_cls)  # type: ignore[arg-type]
        if inspect.iscoroutinefunction(cls.run):

            async def async_base_cmd(**kwargs: Any) -> None:
                await wrapped_cls(**kwargs).run()  # type: ignore[misc]

            def base_cmd(**kwargs: Any) -> None:
                coro = async_base_cmd(**kwargs)
                assert coro is not None
                asyncio.run(coro)

        else:

            def base_cmd(**kwargs: Any) -> None:
                wrapped_cls(**kwargs).run()

        marshalled_cmd = _apply_options(base_cmd, cls_fields)
        cmd.command(name, help=help)(marshalled_cmd)
        return wrapped_cls

    return _chia_command


@dataclass_transform()
def command_helper(cls: Type[Any]) -> Type[Any]:
    return dataclass(frozen=True, kw_only=True)(cls)


@dataclass(frozen=True)
class WalletClientInfo:
    client: WalletRpcClient
    fingerprint: int
    config: Dict[str, Any]


@command_helper
class NeedsWalletRPC:
    client_info: Optional[WalletClientInfo] = None
    wallet_rpc_port: Optional[int] = option(
        "-wp",
        "--wallet-rpc_port",
        help=(
            "Set the port where the Wallet is hosting the RPC interface."
            "See the rpc_port under wallet in config.yaml."
        ),
        type=int,
        default=None,
    )
    fingerprint: Optional[int] = option(
        "-f",
        "--fingerprint",
        help="Fingerprint of the wallet to use",
        type=int,
        default=None,
    )

    @asynccontextmanager
    async def wallet_rpc(self) -> AsyncIterator[WalletClientInfo]:
        if self.client_info is not None:
            yield self.client_info
        else:
            async with get_wallet_client(self.wallet_rpc_port, self.fingerprint) as (wallet_client, fp, config):
                yield WalletClientInfo(wallet_client, fp, config)
