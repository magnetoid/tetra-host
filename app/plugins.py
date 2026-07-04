from dataclasses import dataclass
from typing import Protocol

from fastapi import FastAPI


@dataclass(frozen=True)
class PluginMeta:
    name: str
    label: str
    description: str
    nav_label: str
    nav_href: str
    enabled: bool = True
    # When true, this plugin's nav entry is only shown to platform admins
    # (filtered in inject_core_context by the current admin's role).
    platform_admin_only: bool = False


class TetraPlugin(Protocol):
    meta: PluginMeta

    def register(self, app: FastAPI) -> None:
        ...


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: list[TetraPlugin] = []

    def add(self, plugin: TetraPlugin) -> None:
        self._plugins.append(plugin)

    def register_all(self, app: FastAPI) -> None:
        for plugin in self._plugins:
            if plugin.meta.enabled:
                plugin.register(app)

    def nav_items(self) -> list[PluginMeta]:
        return [p.meta for p in self._plugins if p.meta.enabled and p.meta.nav_href]

    def plugins(self) -> list[TetraPlugin]:
        return list(self._plugins)

    def clear(self) -> None:
        self._plugins.clear()


registry = PluginRegistry()
