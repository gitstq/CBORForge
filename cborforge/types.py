# -*- coding: utf-8 -*-
"""CBOR 数据模型中 Python 侧没有原生对应物的类型。

CBOR 拥有若干 JSON 不存在的语义单元：标签（tag）、简单值（simple value）
以及 ``undefined``。本模块为它们提供轻量的 Python 表达。
"""

from __future__ import annotations

_MAX_UINT64 = (1 << 64) - 1

__all__ = ["Tag", "SimpleValue", "Undefined", "UNDEFINED", "Break"]


class Tag:
    """CBOR 标签（major type 6）。

    标签由一个无符号整数标签号与一个被标注的数据项组成，例如
    ``Tag(0, "2013-03-21T20:04:00Z")`` 表示一个标准日期时间字符串。
    """

    __slots__ = ("tag", "value")

    def __init__(self, tag: int, value: object) -> None:
        if not isinstance(tag, int) or isinstance(tag, bool):
            raise TypeError("tag number must be an int, got %r" % type(tag).__name__)
        if tag < 0 or tag > _MAX_UINT64:
            raise ValueError("tag number out of range [0, 2**64-1]: %d" % tag)
        self.tag = tag
        self.value = value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Tag):
            return self.tag == other.tag and self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("cborforge.Tag", self.tag, self.value))

    def __repr__(self) -> str:
        return "Tag(%d, %r)" % (self.tag, self.value)


class SimpleValue(int):
    """CBOR 简单值（major type 7，非 true/false/null/undefined）。

    以 :class:`int` 为基类，因此可直接参与数值比较；同时保留独立类型，
    便于编解码时与整数区分。取值范围 0..255，其中 0..19 与 32..255
    为可用区间，20..23 由布尔/空值占用，24..31 为保留区间。
    """

    __slots__ = ()

    def __new__(cls, value: int) -> "SimpleValue":
        ivalue = int(value)
        if ivalue < 0 or ivalue > 255:
            raise ValueError("simple value out of range [0, 255]: %d" % ivalue)
        return super().__new__(cls, ivalue)

    def __repr__(self) -> str:
        return "simple(%d)" % int(self)

    @property
    def is_reserved(self) -> bool:
        """简单值落在 RFC 8949 保留区间（24..31）。"""
        return 24 <= int(self) <= 31


class Undefined:
    """CBOR ``undefined``（0xf7）单例。"""

    _instance: "Undefined | None" = None

    def __new__(cls) -> "Undefined":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "undefined"

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Undefined)

    def __hash__(self) -> int:
        return hash("cborforge.Undefined")


UNDEFINED = Undefined()


class Break:
    """不定长容器结束标记（0xff）的内部占位类型。"""

    _instance: "Break | None" = None

    def __new__(cls) -> "Break":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - 内部使用
        return "break"

    def __bool__(self) -> bool:
        return False
