# -*- coding: utf-8 -*-
"""CBOR 与 JSON 之间的**无损**桥接层。

JSON 缺少字节串、标签、简单值、``undefined`` 与非字符串键等 CBOR 语义，
因此本模块定义了一套显式的类型标记（全部以 ``$`` 开头）：

============================ ==========================================
CBOR 语义                     JSON 表达
============================ ==========================================
字节串                        ``{"$bytes": "<base64>"}``
标签                          ``{"$tag": 1, "$value": <被标注值>}``
简单值                        ``{"$simple": 42}``
undefined                     ``{"$undefined": true}``
NaN / ±Infinity               ``{"$float": "NaN"}``
含非字符串键的映射            ``{"$map": [[<键>, <值>], ...]}``
============================ ==========================================

为避免歧义，**以 ``$`` 开头的字符串键被视为保留键**：编码时若映射中含有
此类键，该映射会整体退化为 ``$map`` 形式，从而保证往返无损。
"""

from __future__ import annotations

import base64
import json
import math
from typing import Any, Dict, List, Tuple, Union

from .types import UNDEFINED, SimpleValue, Tag

__all__ = ["to_json_value", "from_json_value", "to_json_text", "from_json_text"]

_MARKER_BYTES = "$bytes"
_MARKER_TAG = "$tag"
_MARKER_SIMPLE = "$simple"
_MARKER_UNDEFINED = "$undefined"
_MARKER_FLOAT = "$float"
_MARKER_MAP = "$map"
_MARKER_VALUE = "$value"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def to_json_value(obj: Any) -> Any:
    """把 CBOR 值转换为 JSON 可序列化的 Python 值。"""
    if obj is None or obj is True or obj is False:
        return obj
    if obj is UNDEFINED:
        return {_MARKER_UNDEFINED: True}
    if isinstance(obj, Tag):
        return {_MARKER_TAG: obj.tag, _MARKER_VALUE: to_json_value(obj.value)}
    if isinstance(obj, SimpleValue):
        return {_MARKER_SIMPLE: int(obj)}
    if isinstance(obj, float):
        if math.isnan(obj):
            return {_MARKER_FLOAT: "NaN"}
        if math.isinf(obj):
            return {_MARKER_FLOAT: "Infinity" if obj > 0 else "-Infinity"}
        return obj
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return {_MARKER_BYTES: _b64(bytes(obj))}
    if isinstance(obj, (list, tuple)):
        return [to_json_value(item) for item in obj]
    if isinstance(obj, dict):
        return _map_to_json(obj)
    raise TypeError("cannot convert to JSON: %r" % type(obj).__name__)


def _map_to_json(mapping: Dict[Any, Any]) -> Any:
    keys = list(mapping.keys())
    plain = all(isinstance(key, str) for key in keys) and not any(
        isinstance(key, str) and key.startswith("$") for key in keys
    )
    if plain:
        return {
            key: to_json_value(value) for key, value in mapping.items()  # type: ignore[misc]
        }
    return {
        _MARKER_MAP: [
            [to_json_value(key), to_json_value(value)]
            for key, value in mapping.items()
        ]
    }


def from_json_value(obj: Any) -> Any:
    """把桥接层表达的 JSON 值还原为 CBOR 值。"""
    if obj is None or obj is True or obj is False:
        return obj
    if isinstance(obj, str) or isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return obj
    if isinstance(obj, list):
        return [from_json_value(item) for item in obj]
    if isinstance(obj, dict):
        return _object_from_json(obj)
    raise TypeError("cannot convert from JSON: %r" % type(obj).__name__)


def _object_from_json(obj: Dict[str, Any]) -> Any:
    keys = set(obj.keys())
    if keys == {_MARKER_BYTES}:
        payload = obj[_MARKER_BYTES]
        if not isinstance(payload, str):
            raise ValueError("$bytes payload must be a base64 string")
        return base64.b64decode(payload)
    if keys == {_MARKER_TAG, _MARKER_VALUE}:
        tag = obj[_MARKER_TAG]
        if not isinstance(tag, int) or isinstance(tag, bool) or tag < 0:
            raise ValueError("$tag must be a non-negative integer")
        return Tag(tag, from_json_value(obj[_MARKER_VALUE]))
    if keys == {_MARKER_SIMPLE}:
        return SimpleValue(obj[_MARKER_SIMPLE])
    if keys == {_MARKER_UNDEFINED}:
        return UNDEFINED
    if keys == {_MARKER_FLOAT}:
        name = obj[_MARKER_FLOAT]
        table = {"NaN": math.nan, "Infinity": math.inf, "-Infinity": -math.inf}
        if name not in table:
            raise ValueError("unknown $float value: %r" % name)
        return table[name]
    if keys == {_MARKER_MAP}:
        pairs = obj[_MARKER_MAP]
        if not isinstance(pairs, list):
            raise ValueError("$map must contain a list of [key, value] pairs")
        out: Dict[Any, Any] = {}
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError("$map entries must be [key, value] pairs")
            out[from_json_value(pair[0])] = from_json_value(pair[1])
        return out
    if any(isinstance(key, str) and key.startswith("$") for key in keys):
        raise ValueError(
            "object keys starting with '$' are reserved by the CBORForge JSON bridge"
        )
    return {key: from_json_value(value) for key, value in obj.items()}


def to_json_text(obj: Any, *, indent: Union[int, None] = 2) -> str:
    """把 CBOR 值序列化为 JSON 文本。"""
    return json.dumps(
        to_json_value(obj), ensure_ascii=False, indent=indent, allow_nan=False
    )


def from_json_text(text: str) -> Any:
    """把 JSON 文本解析为 CBOR 值。"""
    return from_json_value(json.loads(text))
