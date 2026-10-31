# -*- coding: utf-8 -*-
"""CBORForge 异常类型定义。

所有异常均继承自 :class:`CBORError`，便于调用方统一捕获。
"""

from __future__ import annotations


class CBORError(Exception):
    """CBORForge 所有异常的基类。"""


class CBORDecodeError(CBORError):
    """CBOR 解码失败（数据不符合 RFC 8949 良构性要求）。

    :param message: 人类可读的错误描述
    :param offset: 出错位置在输入字节流中的偏移量，可为 ``None``
    """

    def __init__(self, message: str, offset: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.offset = offset

    def __str__(self) -> str:  # pragma: no cover - 简单格式化
        if self.offset is None:
            return self.message
        return "%s (offset %d)" % (self.message, self.offset)


class CBOREncodeError(CBORError):
    """CBOR 编码失败（对象类型不受支持或数值越界）。"""


class DiagnosticError(CBORError):
    """诊断表示法（RFC 8949 §8）解析或生成失败。"""

    def __init__(self, message: str, position: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.position = position

    def __str__(self) -> str:  # pragma: no cover - 简单格式化
        if self.position is None:
            return self.message
        return "%s (position %d)" % (self.message, self.position)


class ValidationError(CBORError):
    """规范性校验过程中出现无法继续的结构性错误。"""
