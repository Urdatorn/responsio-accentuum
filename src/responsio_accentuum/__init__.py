"""Top-level exports for responsio_accentuum.

Re-exports public names from each top-level module in this package.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Iterable

_export_names: set[str] = set()


def _export_from_module(module: ModuleType) -> None:
	module_all = getattr(module, "__all__", None)
	if module_all is None:
		names = [name for name in module.__dict__ if not name.startswith("_")]
	else:
		names = list(module_all)

	for name in names:
		globals()[name] = getattr(module, name)
		_export_names.add(name)


def _iter_module_names(package_paths: Iterable[str]) -> Iterable[str]:
	for module_info in pkgutil.iter_modules(package_paths):
		if module_info.ispkg:
			continue

		yield module_info.name


def _export_from_package(package_name: str) -> None:
	package = importlib.import_module(f"{__name__}.{package_name}")
	globals()[package_name] = package
	_export_names.add(package_name)

	for module_name in _iter_module_names(package.__path__):
		module = importlib.import_module(f"{package.__name__}.{module_name}")
		_export_from_module(module)


for module_name in _iter_module_names(__path__):
	module = importlib.import_module(f"{__name__}.{module_name}")
	_export_from_module(module)

for package_name in ("utils", "plot"):
	_export_from_package(package_name)

__all__ = sorted(_export_names)
