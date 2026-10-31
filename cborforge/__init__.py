# -*- coding: utf-8 -*-
"""CBORForge —— 零依赖·离线优先的 CBOR (RFC 8949) 工具箱。

提供完整的编解码、诊断表示法（RFC 8949 §8）、JSON 无损桥接、
规范性/确定性编码审计与命令行工具，全部仅依赖 Python 标准库。

快速上手::

    import cborforge

    raw = cborforge.dumps({"a": 1, "b": [1, 2, 3]})
    cborforge.loads(raw)                       # {'a': 1, 'b': [1, 2, 3]}
    cborforge.to_diagnostic(cborforge.loads(raw))
    cborforge.validate(raw).ok                 # True

命令行::

    python -m cborforge encode   '{"a": 1}'            # a1616101
    python -m cborforge decode   a1616101
    python -m cborforge inspect  a1616101
    python -m cborforge validate a1616101
    python -m cborforge selftest
"""

from __future__ import annotations

from .decoder import CBORNode, Decoder, loads, parse
from .diagnostic import parse_diagnostic, to_diagnostic
from .encoder import dumps
from .errors import (
    CBORDecodeError,
    CBOREncodeError,
    CBORError,
    DiagnosticError,
    ValidationError,
)
from .jsonio import (
    from_json_text,
    from_json_value,
    to_json_text,
    to_json_value,
)
from .types import UNDEFINED, SimpleValue, Tag
from .validator import (
    KNOWN_TAGS,
    RULES,
    DETERMINISM_CHOICES,
    Finding,
    Report,
    safe_validate,
    validate,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    # 编解码
    "dumps",
    "loads",
    "parse",
    "CBORNode",
    "Decoder",
    # 诊断表示法
    "to_diagnostic",
    "parse_diagnostic",
    # JSON 桥接
    "to_json_value",
    "from_json_value",
    "to_json_text",
    "from_json_text",
    # 审计
    "validate",
    "safe_validate",
    "Report",
    "Finding",
    "RULES",
    "KNOWN_TAGS",
    "DETERMINISM_CHOICES",
    # 类型
    "Tag",
    "SimpleValue",
    "UNDEFINED",
    # 异常
    "CBORError",
    "CBORDecodeError",
    "CBOREncodeError",
    "DiagnosticError",
    "ValidationError",
]
