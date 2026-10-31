# -*- coding: utf-8 -*-
"""RFC 8949 CBOR 编码器。

支持三种编码策略：

``default``
    最短整数编码 + 最短可无损还原的浮点宽度 + 定长容器，保持映射插入顺序。

``canonical=True``
    RFC 7049 规范形式：定长容器、最短整数、最短可无损还原的浮点，
    映射键按其规范编码的 **长度优先、再按字典序** 排序。

``ctap2=True``
    RFC 8949 §4.2.1 核心确定性编码（CTAP2 / WebAuthn 采用）：
    映射键按其确定性编码的**纯字节字典序**排序。

两者在少数真实数据上会产生不同结果，因此分别提供。
"""

from __future__ import annotations

import math
import struct
from typing import Any, Dict, List, Optional, Union

from .errors import CBOREncodeError
from .types import UNDEFINED, SimpleValue, Tag

__all__ = ["dumps", "canonical_dumps", "CBOREncoder"]

_MAX_UINT64 = (1 << 64) - 1
_FLOAT_MODES = ("auto", "16", "32", "64")


def _head(mt: int, n: int) -> bytes:
    """为 major type ``mt`` 与参数 ``n`` 生成最短头部字节。"""
    if n < 24:
        return bytes((mt << 5 | n,))
    if n < 0x100:
        return bytes((mt << 5 | 24, n))
    if n < 0x10000:
        return bytes((mt << 5 | 25,)) + n.to_bytes(2, "big")
    if n < 0x100000000:
        return bytes((mt << 5 | 26,)) + n.to_bytes(4, "big")
    if n <= _MAX_UINT64:
        return bytes((mt << 5 | 27,)) + n.to_bytes(8, "big")
    raise CBOREncodeError("argument out of range for major type %d: %d" % (mt, n))


def _shortest_float(value: float) -> bytes:
    """按 RFC 8949 §4.2.2 "preferred serialization" 选择最短可还原宽度。"""
    if math.isnan(value):
        # 首选序列化把 NaN 统一为 0x7e00
        return b"\xf9\x7e\x00"
    if value == 0.0:
        # 保留 ±0.0 的符号（Python 中 0.0 == -0.0，需单独判断）
        return b"\xf9\x80\x00" if math.copysign(1.0, value) < 0 else b"\xf9\x00\x00"
    try:
        packed = struct.pack(">e", value)
        if struct.unpack(">e", packed)[0] == value:
            return b"\xf9" + packed
    except (OverflowError, struct.error):
        pass
    try:
        packed = struct.pack(">f", value)
        if struct.unpack(">f", packed)[0] == value:
            return b"\xfa" + packed
    except (OverflowError, struct.error):
        pass
    return b"\xfb" + struct.pack(">d", value)


def _split_text_chunks(text: str, chunk_size: int) -> List[str]:
    """按 UTF-8 码点边界切分文本，保证每个分块自身是合法 UTF-8。"""
    if not text:
        return [""]
    chunks: List[str] = []
    current: List[str] = []
    size = 0
    for ch in text:
        width = len(ch.encode("utf-8"))
        if size + width > chunk_size and current:
            chunks.append("".join(current))
            current = []
            size = 0
        current.append(ch)
        size += width
    chunks.append("".join(current))
    return chunks


class CBOREncoder:
    """带选项的 CBOR 编码器。"""

    def __init__(
        self,
        canonical: bool = False,
        ctap2: bool = False,
        float_mode: str = "auto",
        indefinite: bool = False,
        chunk_size: int = 8,
    ) -> None:
        if float_mode not in _FLOAT_MODES:
            raise ValueError(
                "float_mode must be one of %s, got %r" % (_FLOAT_MODES, float_mode)
            )
        if (canonical or ctap2) and indefinite:
            raise CBOREncodeError(
                "canonical/CTAP2 encoding forbids indefinite-length items"
            )
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        self.canonical = canonical
        self.ctap2 = ctap2
        self.float_mode = float_mode
        self.indefinite = indefinite
        self.chunk_size = chunk_size
        self.deterministic = canonical or ctap2

    # -- 公开入口 ---------------------------------------------------------
    def encode(self, obj: Any) -> bytes:
        return self._encode(obj, 0)

    # -- 内部实现 ---------------------------------------------------------
    def _encode(self, obj: Any, depth: int, allow_indefinite: bool = True) -> bytes:
        if depth > 256:
            raise CBOREncodeError("object nesting too deep (>256)")

        if obj is None:
            return b"\xf6"
        if obj is UNDEFINED:
            return b"\xf7"
        if obj is True:
            return b"\xf5"
        if obj is False:
            return b"\xf4"
        if isinstance(obj, SimpleValue):
            return self._simple(obj)
        if isinstance(obj, Tag):
            return _head(6, obj.tag) + self._encode(
                obj.value, depth + 1, allow_indefinite
            )
        if isinstance(obj, bool):  # pragma: no cover - 已被 is True/False 覆盖
            return b"\xf5" if obj else b"\xf4"
        if isinstance(obj, int):
            return self._int(obj)
        if isinstance(obj, float):
            return self._float(obj)
        if isinstance(obj, str):
            return self._text(obj, allow_indefinite)
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return self._bytes(bytes(obj), allow_indefinite)
        if isinstance(obj, (list, tuple)):
            return self._array(list(obj), depth, allow_indefinite)
        if isinstance(obj, dict):
            return self._map(obj, depth, allow_indefinite)
        raise CBOREncodeError(
            "unsupported type for CBOR encoding: %r" % type(obj).__name__
        )

    def _simple(self, value: SimpleValue) -> bytes:
        n = int(value)
        if n < 24:
            return bytes((0xE0 | n,))
        return b"\xf8" + bytes((n,))

    def _int(self, value: int) -> bytes:
        if 0 <= value <= _MAX_UINT64:
            return _head(0, value)
        if -(_MAX_UINT64 + 1) <= value < 0:
            return _head(1, -1 - value)
        # 超出 64 位：退化为标签 2/3 大整数
        if value > 0:
            raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
            return _head(6, 2) + _head(2, len(raw)) + raw
        magnitude = -1 - value
        raw = magnitude.to_bytes((magnitude.bit_length() + 7) // 8, "big")
        return _head(6, 3) + _head(2, len(raw)) + raw

    def _float(self, value: float) -> bytes:
        if self.float_mode == "auto":
            return _shortest_float(value)
        if self.float_mode == "16":
            return b"\xf9" + struct.pack(">e", value)
        if self.float_mode == "32":
            return b"\xfa" + struct.pack(">f", value)
        return b"\xfb" + struct.pack(">d", value)

    def _text(self, value: str, allow_indefinite: bool = True) -> bytes:
        if self.indefinite and allow_indefinite:
            out = bytearray(b"\x7f")
            for piece in _split_text_chunks(value, self.chunk_size):
                raw = piece.encode("utf-8")
                out += _head(3, len(raw)) + raw
            out += b"\xff"
            return bytes(out)
        raw = value.encode("utf-8")
        return _head(3, len(raw)) + raw

    def _bytes(self, raw: bytes, allow_indefinite: bool = True) -> bytes:
        if self.indefinite and allow_indefinite:
            out = bytearray(b"\x5f")
            size = self.chunk_size
            for i in range(0, len(raw), size):
                piece = raw[i : i + size]
                out += _head(2, len(piece)) + piece
            out += b"\xff"
            return bytes(out)
        return _head(2, len(raw)) + raw

    def _array(
        self, items: List[Any], depth: int, allow_indefinite: bool = True
    ) -> bytes:
        if self.indefinite and allow_indefinite:
            out = bytearray(b"\x9f")
            for item in items:
                out += self._encode(item, depth + 1, allow_indefinite)
            out += b"\xff"
            return bytes(out)
        out = bytearray(_head(4, len(items)))
        for item in items:
            out += self._encode(item, depth + 1, allow_indefinite)
        return bytes(out)

    def _map(
        self, mapping: Dict[Any, Any], depth: int, allow_indefinite: bool = True
    ) -> bytes:
        items = list(mapping.items())
        if self.deterministic:
            items.sort(key=self._sort_key)
        if self.indefinite and allow_indefinite:
            out = bytearray(b"\xbf")
            for key, value in items:
                # 键必须始终为定长：不定长键会破坏确定性比较与排序
                out += self._encode(key, depth + 1, False)
                out += self._encode(value, depth + 1, allow_indefinite)
            out += b"\xff"
            return bytes(out)
        out = bytearray(_head(5, len(items)))
        for key, value in items:
            out += self._encode(key, depth + 1, False)
            out += self._encode(value, depth + 1, allow_indefinite)
        return bytes(out)

    def _sort_key(self, item: Any) -> Any:
        """确定性编码下的映射键排序键。

        RFC 7049 规范形式采用「长度优先、再字典序」；
        RFC 8949 / CTAP2 核心确定性编码采用纯字节字典序。
        """
        key, _value = item
        encoded = self._encode(key, 0, False)
        if self.ctap2:
            return (encoded,)
        return (len(encoded), encoded)


def dumps(
    obj: Any,
    *,
    canonical: bool = False,
    ctap2: bool = False,
    float_mode: str = "auto",
    indefinite: bool = False,
    chunk_size: int = 8,
) -> bytes:
    """把 Python 对象编码为 CBOR 字节串。

    :param canonical: 采用 RFC 7049 规范形式
    :param ctap2: 采用 RFC 8949 §4.2.1 核心确定性编码
    :param float_mode: ``auto``（最短可无损还原）/ ``16`` / ``32`` / ``64``
    :param indefinite: 使用不定长容器与分块字符串（不可与规范形式同用）
    :param chunk_size: 不定长字符串分块大小（字节）
    """
    return CBOREncoder(
        canonical=canonical,
        ctap2=ctap2,
        float_mode=float_mode,
        indefinite=indefinite,
        chunk_size=chunk_size,
    ).encode(obj)


def canonical_dumps(obj: Any, ctap2: bool = False) -> bytes:
    """等价于 :func:`dumps` 的确定性编码快捷方式。"""
    return dumps(obj, canonical=not ctap2, ctap2=ctap2)
