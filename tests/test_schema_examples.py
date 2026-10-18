import importlib
import inspect
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import app
from pydantic import BaseModel


def _models_with_examples() -> Iterator[type[BaseModel]]:
    app_path = Path(app.__file__).parent
    for path in app_path.rglob("*.py"):
        if "json_schema_extra" not in path.read_text(encoding="utf-8"):
            continue
        relative_module = path.relative_to(app_path.parent).with_suffix("")
        module_name = ".".join(relative_module.parts)
        module = importlib.import_module(module_name)
        for _, model in inspect.getmembers(module, inspect.isclass):
            if (
                model is not BaseModel
                and issubclass(model, BaseModel)
                and model.__module__ == module_name
                and isinstance(model.model_config.get("json_schema_extra"), dict)
                and "example" in model.model_config["json_schema_extra"]
            ):
                yield model


def _null_paths(value: Any, path: str = "example") -> list[str]:
    if value is None:
        return [path]
    if isinstance(value, dict):
        return [
            null_path
            for key, item in value.items()
            for null_path in _null_paths(item, f"{path}.{key}")
        ]
    if isinstance(value, list):
        return [
            null_path
            for index, item in enumerate(value)
            for null_path in _null_paths(item, f"{path}[{index}]")
        ]
    return []


def test_json_schema_examples_are_complete_valid_and_non_null() -> None:
    models = list(_models_with_examples())

    assert models, "No se encontraron schemas con ejemplos para validar."
    for model in models:
        example = model.model_config["json_schema_extra"]["example"]

        assert isinstance(example, dict), f"{model.__name__}.example debe ser un objeto."
        assert set(example) == set(model.model_fields), (
            f"{model.__name__}.example no representa exactamente todos sus campos."
        )
        assert not _null_paths(example), (
            f"{model.__name__}.example contiene valores nulos: {_null_paths(example)}"
        )
        model.model_validate(example)
