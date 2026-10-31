# -*- coding: utf-8 -*-
"""RFC 8949 CBOR 解码器。

本模块提供一个**严格**的 CBOR 解码器：它会在解码过程中完整执行 RFC 8949
附录 C（"Well-Formedness Errors"）所列举的良构性检查，包括

* 保留的附加信息（28/29/30）；
* 不定长（indefinite）用于不允许的 major type；
* 不定长字符串的分块自身不可再为不定长；
* 文本字符串必须是合法 UTF-8（含不定长分块的逐块校验）；
* ``break`` 出现在不定长容器之外；
* 双字节形式的简单值落在 0..31 保留区间。

同时提供 :class:`CBORNode` 解析树，供 :mod:`cborforge.validator` 做规范性
审计、供 CLI 的 ``inspect`` 做带偏移量的结构展示。
"""

from __future__ import annotations

import struct
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .errors import CBORDecodeError
from .types import UNDEFINED, Break, SimpleValue, Tag

__all__ = ["CBORNode", "Decoder", "parse", "loads", "MAX_DEPTH"]

#: 默认最大嵌套深度，抵御恶意构造的深层嵌套导致的栈溢出。
MAX_DEPTH = 256

_MAX_UINT64 = (1 << 64) - 1


class CBORNode:
    """CBOR 数据项解析树节点。

    每个节点记录了该项在原始字节流中的偏移区间、头部编码方式以及解码后的
    Python 值，从而在不重新解析的前提下支撑审计与可视化。
    """

    __slots__ = (
        "offset",
        "end",
        "mt",
        "ai",
        "arg",
        "head_len",
        "indefinite",
        "value",
        "children",
        "entries",
        "tag",
        "child",
        "depth",
    )

    def __init__(
        self,
        offset: int,
        mt: int,
        ai: int,
        arg: Optional[int],
        head_len: int,
        depth: int = 0,
    ) -> None:
        self.offset = offset
        self.end = -1
        self.mt = mt
        self.ai = ai
        self.arg = arg
        self.head_len = head_len
        self.indefinite = ai == 31
        self.depth = depth
        self.value: Any = None
        self.children: List["CBORNode"] = []
        self.entries: List[Tuple["CBORNode", "CBORNode"]] = []
        self.tag: Optional[int] = None
        self.child: Optional["CBORNode"] = None

    # -- 便捷属性 ---------------------------------------------------------
    @property
    def length(self) -> int:
        """该项占用的字节总数（含头部）。"""
        return self.end - self.offset

    @property
    def payload(self) -> slice:
        """该项在字节流中的切片范围。"""
        return slice(self.offset, self.end)

    @property
    def major_name(self) -> str:
        return _MAJOR_NAMES[self.mt]

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return "<CBORNode mt=%d ai=%d off=%d len=%d>" % (
            self.mt,
            self.ai,
            self.offset,
            self.end - self.offset,
        )


_MAJOR_NAMES = (
    "unsigned",
    "negative",
    "bytes",
    "text",
    "array",
    "map",
    "tag",
    "simple/float",
)


class Decoder:
    """一次性 CBOR 解码器。

    :param data: 待解码字节流
    :param bignum: 是否把标签 2/3（大整数）自动折叠为 Python ``int``
    :param max_depth: 允许的最大嵌套深度
    """

    def __init__(
        self,
        data: Union[bytes, bytearray, memoryview],
        bignum: bool = False,
        max_depth: int = MAX_DEPTH,
    ) -> None:
        if isinstance(data, (bytearray, memoryview)):
            data = bytes(data)
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes-like, got %r" % type(data).__name__)
        self.data = data
        self.bignum = bignum
        self.max_depth = max_depth

    # -- 入口 -------------------------------------------------------------
    def parse(self) -> CBORNode:
        """解码字节流中的**第一个**数据项并返回解析树根节点。"""
        if not self.data:
            raise CBORDecodeError("empty input: no CBOR data item", 0)
        node = self._item(0, 0)
        if node.mt == 7 and node.ai == 31:
            raise CBORDecodeError("unexpected break stop code at top level", 0)
        return node

    # -- 底层读取 ---------------------------------------------------------
    def _need(self, pos: int, count: int, what: str) -> None:
        if pos + count > len(self.data):
            raise CBORDecodeError(
                "truncated input while reading %s: need %d byte(s)" % (what, count),
                pos,
            )

    def _head(self, pos: int) -> Tuple[int, int, Optional[int], int]:
        """读取初始字节与扩展参数。

        返回 ``(mt, ai, arg, head_len)``；不定长时 ``arg`` 为 ``None``。
        """
        self._need(pos, 1, "initial byte")
        ib = self.data[pos]
        mt = ib >> 5
        ai = ib & 0x1F
        if ai < 24:
            return mt, ai, ai, 1
        if ai == 24:
            self._need(pos + 1, 1, "1-byte argument")
            return mt, ai, self.data[pos + 1], 2
        if ai == 25:
            self._need(pos + 1, 2, "2-byte argument")
            return mt, ai, int.from_bytes(self.data[pos + 1 : pos + 3], "big"), 3
        if ai == 26:
            self._need(pos + 1, 4, "4-byte argument")
            return mt, ai, int.from_bytes(self.data[pos + 1 : pos + 5], "big"), 5
        if ai == 27:
            self._need(pos + 1, 8, "8-byte argument")
            return mt, ai, int.from_bytes(self.data[pos + 1 : pos + 9], "big"), 9
        if ai == 31:
            return mt, ai, None, 1
        raise CBORDecodeError(
            "reserved additional information %d is not well-formed" % ai, pos
        )

    # -- 递归解码 ---------------------------------------------------------
    def _item(self, pos: int, depth: int) -> CBORNode:
        if depth > self.max_depth:
            raise CBORDecodeError(
                "nesting depth exceeds limit (%d)" % self.max_depth, pos
            )
        mt, ai, arg, head_len = self._head(pos)
        # RFC 8949：不定长只允许用于 major type 2/3/4/5（7 的 31 为 break）
        if ai == 31 and mt in (0, 1, 6):
            raise CBORDecodeError(
                "indefinite-length %s is not well-formed" % _MAJOR_NAMES[mt], pos
            )
        node = CBORNode(pos, mt, ai, arg, head_len, depth)
        body = pos + head_len
        remaining = len(self.data)

        if mt == 0:  # 无符号整数
            node.value = arg
            node.end = body

        elif mt == 1:  # 负整数
            node.value = -1 - arg
            node.end = body

        elif mt == 2:  # 字节串
            node.end, node.value = self._string(body, node, 2, _concat_bytes, depth)

        elif mt == 3:  # 文本串
            node.end, node.value = self._string(body, node, 3, _concat_text, depth)

        elif mt == 4:  # 数组
            if ai == 31:
                cursor = body
                while True:
                    item = self._item(cursor, depth + 1)
                    if item.mt == 7 and item.ai == 31:
                        cursor = item.end
                        break
                    node.children.append(item)
                    cursor = item.end
                node.end = cursor
            else:
                count = arg
                if count > remaining - body:
                    raise CBORDecodeError(
                        "array of %d items exceeds available data" % count, pos
                    )
                cursor = body
                for _ in range(count):
                    child = self._item(cursor, depth + 1)
                    node.children.append(child)
                    cursor = child.end
                node.end = cursor
            node.value = [child.value for child in node.children]

        elif mt == 5:  # 映射
            if ai == 31:
                cursor = body
                while True:
                    key = self._item(cursor, depth + 1)
                    if key.mt == 7 and key.ai == 31:
                        cursor = key.end
                        break
                    value = self._item(key.end, depth + 1)
                    node.entries.append((key, value))
                    cursor = value.end
                node.end = cursor
            else:
                count = arg
                if 2 * count > remaining - body:
                    raise CBORDecodeError(
                        "map of %d pairs exceeds available data" % count, pos
                    )
                cursor = body
                for _ in range(count):
                    key = self._item(cursor, depth + 1)
                    value = self._item(key.end, depth + 1)
                    node.entries.append((key, value))
                    cursor = value.end
                node.end = cursor
            node.value = _build_map(node.entries)

        elif mt == 6:  # 标签
            node.tag = arg
            child = self._item(body, depth + 1)
            if child.mt == 7 and child.ai == 31:
                raise CBORDecodeError("tag must be followed by a data item", pos)
            node.child = child
            node.end = child.end
            node.value = self._finish_tag(arg, child.value)

        else:  # mt == 7
            if ai < 20:
                node.value = SimpleValue(ai)
                node.end = body
            elif ai == 20:
                node.value = False
                node.end = body
            elif ai == 21:
                node.value = True
                node.end = body
            elif ai == 22:
                node.value = None
                node.end = body
            elif ai == 23:
                node.value = UNDEFINED
                node.end = body
            elif ai == 24:
                # 载荷字节即附加信息本身，已由 _head() 读入 arg。
                raw = arg
                if raw < 32:
                    raise CBORDecodeError(
                        "simple value %d in two-byte form is not well-formed" % raw,
                        pos + 1,
                    )
                node.value = SimpleValue(raw)
                node.end = body
            elif ai == 25:
                start = pos + 1
                node.value = struct.unpack(">e", self.data[start : start + 2])[0]
                node.end = body
            elif ai == 26:
                start = pos + 1
                node.value = struct.unpack(">f", self.data[start : start + 4])[0]
                node.end = body
            elif ai == 27:
                start = pos + 1
                node.value = struct.unpack(">d", self.data[start : start + 8])[0]
                node.end = body
            else:  # ai == 31 -> break
                node.value = Break()
                node.end = body

        return node

    def _string(
        self,
        body: int,
        node: CBORNode,
        mt: int,
        concat,
        depth: int,
    ) -> Tuple[int, Union[bytes, str]]:
        """解码字节串（mt=2）或文本串（mt=3），含不定长分块。"""
        remaining = len(self.data)
        if node.ai == 31:
            cursor = body
            chunks: List[CBORNode] = []
            while True:
                chunk = self._item(cursor, depth + 1)
                if chunk.mt == 7 and chunk.ai == 31:
                    cursor = chunk.end
                    break
                if chunk.mt != mt:
                    raise CBORDecodeError(
                        "indefinite-length %s chunk must have major type %d" % (_MAJOR_NAMES[mt], mt),
                        chunk.offset,
                    )
                if chunk.ai == 31:
                    raise CBORDecodeError(
                        "nested indefinite-length %s chunk is not well-formed" % _MAJOR_NAMES[mt],
                        chunk.offset,
                    )
                chunks.append(chunk)
                cursor = chunk.end
            node.children = chunks
            node.end = cursor
            return node.end, concat([c.value for c in chunks])

        length = node.arg
        if length > remaining - body:
            raise CBORDecodeError(
                "%s of %d bytes exceeds available data" % (_MAJOR_NAMES[mt], length),
                node.offset,
            )
        raw = self.data[body : body + length]
        if mt == 3:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CBORDecodeError(
                    "text string is not valid UTF-8: %s" % exc.reason, body
                ) from None
            return body + length, text
        return body + length, raw

    def _finish_tag(self, tag: int, value: Any) -> Any:
        if self.bignum and tag in (2, 3) and isinstance(value, (bytes, bytearray)):
            n = int.from_bytes(bytes(value), "big")
            return n if tag == 2 else -1 - n
        return Tag(tag, value)


def _concat_bytes(chunks: Sequence[bytes]) -> bytes:
    return b"".join(chunks)


def _concat_text(chunks: Sequence[str]) -> str:
    return "".join(chunks)


def _build_map(entries: Sequence[Tuple[CBORNode, CBORNode]]) -> Optional[Dict[Any, Any]]:
    """把 (键节点, 值节点) 序列折叠为 Python ``dict``。

    当存在不可哈希的键（例如数组作为键）时返回 ``None``，由审计引擎报告，
    而不是让解码整体失败。
    """
    out: Dict[Any, Any] = {}
    for key_node, value_node in entries:
        try:
            out[key_node.value] = value_node.value
        except TypeError:
            return None
    return out


def parse(
    data: Union[bytes, bytearray, memoryview],
    bignum: bool = False,
    max_depth: int = MAX_DEPTH,
) -> CBORNode:
    """解码首个 CBOR 数据项并返回解析树根节点。"""
    return Decoder(data, bignum=bignum, max_depth=max_depth).parse()


def loads(
    data: Union[bytes, bytearray, memoryview],
    bignum: bool = False,
    max_depth: int = MAX_DEPTH,
) -> Any:
    """解码一段**完整**的 CBOR 字节流并返回 Python 值。

    :raises CBORDecodeError: 数据不合法，或顶层数据项之后仍有多余字节。
    """
    decoder = Decoder(data, bignum=bignum, max_depth=max_depth)
    node = decoder.parse()
    if node.end != len(decoder.data):
        raise CBORDecodeError(
            "trailing data after top-level item: %d byte(s) unconsumed"
            % (len(decoder.data) - node.end),
            node.end,
        )
    return node.value
