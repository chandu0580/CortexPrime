from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Dict, Optional

_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> Callable:
    def decorator(fn: Callable) -> Callable:
        tool_name = name or fn.__name__
        sig = inspect.signature(fn)
        param_schema = parameters or _infer_params(sig)

        _TOOL_REGISTRY[tool_name] = {
            "name": tool_name,
            "description": description or fn.__doc__ or "",
            "parameters": param_schema,
            "fn": fn,
        }

        @wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)

        wrapper._is_cortex_tool = True
        wrapper._tool_name = tool_name
        wrapper._tool_spec = _TOOL_REGISTRY[tool_name]
        return wrapper

    return decorator


def _infer_params(sig: inspect.Signature) -> Dict[str, Any]:
    properties = {}
    required = []
    for name, param in sig.parameters.items():
        if name == "self" or name == "context":
            continue
        param_type = "string"
        if param.annotation is not inspect.Parameter.empty:
            origin = getattr(param.annotation, "__origin__", None)
            if origin is dict:
                param_type = "object"
            elif origin is list:
                param_type = "array"
            elif origin is int or param.annotation is int:
                param_type = "integer"
            elif origin is float or param.annotation is float:
                param_type = "number"
            elif origin is bool or param.annotation is bool:
                param_type = "boolean"
        properties[name] = {"type": param_type, "description": ""}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


def get_registered_tools() -> Dict[str, Dict[str, Any]]:
    return dict(_TOOL_REGISTRY)


def clear_registry() -> None:
    _TOOL_REGISTRY.clear()
