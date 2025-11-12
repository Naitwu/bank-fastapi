import importlib
import os
import pathlib

from backend.app.core.logging import get_logger

logger = get_logger()


def discover_models() -> list[str]:
    models_modules = []
    root_path = pathlib.Path(__file__).parent.parent

    logger.debug(f"Starting model discovery in the root path: {root_path}")

    for dirpath, dirnames, filenames in os.walk(root_path):
        if any(excluded in dirpath for excluded in ["__pycache__", ".venv"]):
            continue

        if "models.py" in filenames:
            relative_path = os.path.relpath(dirpath, root_path)
            module_path = relative_path.replace(os.path.sep, ".")

            if module_path == ".":
                module_path = "backend.app.core.models"
            else:
                module_path = f"backend.app.{module_path}.models"
            logger.debug(f"Discovered models file in : {module_path}")
            models_modules.append(module_path)
    return models_modules


def load_models() -> None:
    modules = discover_models()
    for module_name in modules:
        try:
            importlib.import_module(module_name)
            logger.debug(f"Successfully imported models module: {module_name}")
        except Exception as e:
            logger.error(f"Failed to import models module {module_name}: {e}")
