from pathlib import Path

import yaml


AGENT_TYPE_MAP = {
    "classifier": "agents7.agents.Classifier",
    "labeler": "agents7.agents.Labeler",
    "detector": "agents7.agents.Detector",
    "regressor": "agents7.agents.Regressor",
}


def import_class(dotted_path: str):
    import importlib

    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _load_config(config_file: Path) -> tuple[dict, str]:
    """Load a YAML config file and return (parsed dict, raw text)."""
    with open(config_file, encoding="utf-8") as f:
        raw_yaml = f.read()
    cfg: dict = yaml.safe_load(raw_yaml)
    return cfg, raw_yaml


def _load_output_schema(
    cfg: dict,
) -> tuple[dict | None, set[str]]:
    """Resolve output model from cfg and return (schema, field names)."""
    output_model_path = cfg.get("output_model")
    if not output_model_path:
        return None, set()
    try:
        from agents7.agents.utils import import_from_path

        model_cls = import_from_path(output_model_path)
        schema: dict = model_cls.model_json_schema()
        return schema, set(schema.get("properties", {}).keys())
    except (ImportError, AttributeError):
        return None, set()
