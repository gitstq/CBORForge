# -*- coding: utf-8 -*-
"""CBOR 诊断表示法（RFC 8949 §8 "Diagnostic Notation"）解析与生成。

诊断表示法是一种人类可读、可无损往返的 CBOR 文本表达，例如::

    {1: 1363896240, "name": h'646566', "ok": true, "ratio": 1.5}

本模块同时提供

* :func:`to_diagnostic` —— 把 Python/CBOR 值渲染为诊断表示法；
* :func:`parse_diagnostic` —— 把诊断表示法解析回 Python 值。

解析器额外支持 ``#`` 行注释与尾随逗号，便于手写配置文件。
"""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from .errors import DiagnosticError
from .types import UNDEFINED, SimpleValue, Tag

__all__ = ["to_diagnostic", "parse_diagnostic"]

# --------------------------------------------------------------------------
# 词法分析
# --------------------------------------------------------------------------

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SIGNED_IDENT_RE = re.compile(r"[+-][A-Za-z_][A-Za-z0-9_]*")
_NUM_RE = re.compile(
    r"[+-]?(?:"
    r"0[xX](?:[0-9a-fA-F]+(?:\.[0-9a-fA-F]*)?|[0-9a-fA-F]*\.[0-9a-fA-F]+)"
    r"(?:[pP][+-]?[0-9]+)?"
    r"|[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?"
    r"|\.[0-9]+(?:[eE][+-]?[0-9]+)?"
    r")"
)
_PUNCT = "[]{}(),:"
_MAX_UINT64 = (1 << 64) - 1

_SPECIAL_IDENTS = {
    "true": True,
    "false": False,
    "null": None,
    "undefined": UNDEFINED,
    "Infinity": math.inf,
    "-Infinity": -math.inf,
    "NaN": math.nan,
    "-NaN": math.nan,
}


class _Token:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind: str, value: Any, pos: int) -> None:
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return "<%s %r@%d>" % (self.kind, self.value, self.pos)


def _decode_b64(payload: str, pos: int) -> bytes:
    text = payload.replace("-", "+").replace("_", "/")
    padding = (-len(text)) % 4
    text += "=" * padding
    try:
        return base64.b64decode(text, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise DiagnosticError("invalid base64 byte string: %s" % exc, pos) from None


def _lex(text: str) -> List[_Token]:
    tokens: List[_Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if ch == "#":
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if ch in _PUNCT:
            tokens.append(_Token("punct", ch, i))
            i += 1
            continue
        if ch == '"':
            end = i + 1
            buf: List[str] = []
            while end < n and text[end] != '"':
                if text[end] == "\\":
                    if end + 1 >= n:
                        raise DiagnosticError("unterminated escape in string", end)
                    nxt = text[end + 1]
                    mapping = {
                        "n": "\n",
                        "t": "\t",
                        "r": "\r",
                        "b": "\b",
                        "f": "\f",
                        '"': '"',
                        "\\": "\\",
                        "/": "/",
                    }
                    if nxt in mapping:
                        buf.append(mapping[nxt])
                        end += 2
                        continue
                    if nxt == "u":
                        hexpart = text[end + 2 : end + 6]
                        if len(hexpart) != 4:
                            raise DiagnosticError("truncated \\u escape", end)
                        try:
                            buf.append(chr(int(hexpart, 16)))
                        except ValueError:
                            raise DiagnosticError(
                                "invalid \\u escape: %r" % hexpart, end
                            ) from None
                        end += 6
                        continue
                    raise DiagnosticError("unknown escape: \\%s" % nxt, end)
                buf.append(text[end])
                end += 1
            if end >= n:
                raise DiagnosticError("unterminated string", i)
            tokens.append(_Token("string", "".join(buf), i))
            i = end + 1
            continue
        if ch == "'":
            raise DiagnosticError(
                "byte strings must be written as h'..' or b64'..'", i
            )
        signed = _SIGNED_IDENT_RE.match(text, i)
        if signed:
            tokens.append(_Token("ident", signed.group(0), i))
            i = signed.end()
            continue
        ident = _IDENT_RE.match(text, i)
        if ident:
            word = ident.group(0)
            end = ident.end()
            if word in ("h", "b64") and end < n and text[end] == "'":
                close = text.find("'", end + 1)
                if close < 0:
                    raise DiagnosticError("unterminated byte string", i)
                payload = text[end + 1 : close]
                if word == "h":
                    try:
                        raw = binascii.unhexlify(payload)
                    except binascii.Error as exc:
                        raise DiagnosticError(
                            "invalid hex byte string: %s" % exc, i
                        ) from None
                else:
                    raw = _decode_b64(payload, i)
                tokens.append(_Token("bytes", raw, i))
                i = close + 1
                continue
            tokens.append(_Token("ident", word, i))
            i = end
            continue
        num = _NUM_RE.match(text, i)
        if num:
            raw = num.group(0)
            tokens.append(_Token("number", raw, i))
            i = num.end()
            continue
        raise DiagnosticError("unexpected character %r" % ch, i)
    tokens.append(_Token("eof", None, n))
    return tokens


def _number_to_value(raw: str, pos: int) -> Union[int, float]:
    lowered = raw.lower()
    if lowered.startswith(("0x", "-0x", "+0x")):
        sign = -1 if raw.startswith("-") else 1
        body = raw[3:] if raw[0] in "+-" else raw[2:]
        if "p" in lowered:
            try:
                return sign * float.fromhex("0x" + body)
            except ValueError:
                raise DiagnosticError("invalid hex float: %s" % raw, pos) from None
        try:
            return sign * int(body, 16)
        except ValueError:
            raise DiagnosticError("invalid hex integer: %s" % raw, pos) from None
    if any(c in lowered for c in ".e"):
        try:
            return float(raw)
        except ValueError:
            raise DiagnosticError("invalid float literal: %s" % raw, pos) from None
    try:
        return int(raw)
    except ValueError:
        raise DiagnosticError("invalid integer literal: %s" % raw, pos) from None


# --------------------------------------------------------------------------
# 语法分析
# --------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: List[_Token]) -> None:
        self.tokens = tokens
        self.index = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def advance(self) -> _Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def expect_punct(self, char: str) -> None:
        token = self.current
        if token.kind != "punct" or token.value != char:
            raise DiagnosticError("expected %r" % char, token.pos)
        self.index += 1

    def parse(self) -> Any:
        value = self.value()
        if self.current.kind != "eof":
            raise DiagnosticError("unexpected trailing input", self.current.pos)
        return value

    def value(self) -> Any:
        token = self.current

        if token.kind == "punct" and token.value == "[":
            return self.array()
        if token.kind == "punct" and token.value == "{":
            return self.mapping()
        if token.kind == "string":
            self.advance()
            return token.value
        if token.kind == "bytes":
            self.advance()
            return token.value
        if token.kind == "number":
            self.advance()
            number = _number_to_value(token.value, token.pos)
            if self.current.kind == "punct" and self.current.value == "(":
                if not isinstance(number, int) or isinstance(number, bool):
                    raise DiagnosticError(
                        "tag number must be an integer", token.pos
                    )
                if number < 0 or number > _MAX_UINT64:
                    raise DiagnosticError("tag number out of range", token.pos)
                self.advance()
                inner = self.value()
                self.expect_punct(")")
                return Tag(number, inner)
            return number
        if token.kind == "ident":
            self.advance()
            word = token.value
            if word == "simple":
                self.expect_punct("(")
                inner = self.current
                if inner.kind != "number":
                    raise DiagnosticError(
                        "simple() requires a numeric argument", inner.pos
                    )
                self.advance()
                number = _number_to_value(inner.value, inner.pos)
                self.expect_punct(")")
                if not isinstance(number, int):
                    raise DiagnosticError("simple value must be an integer", inner.pos)
                return SimpleValue(number)
            if word in _SPECIAL_IDENTS:
                return _SPECIAL_IDENTS[word]
            raise DiagnosticError("unknown identifier %r" % word, token.pos)

        raise DiagnosticError(
            "unexpected %s token" % token.kind, token.pos
        )

    def array(self) -> List[Any]:
        self.expect_punct("[")
        items: List[Any] = []
        if self.current.kind == "punct" and self.current.value == "]":
            self.advance()
            return items
        while True:
            items.append(self.value())
            if self.current.kind == "punct" and self.current.value == ",":
                self.advance()
                if self.current.kind == "punct" and self.current.value == "]":
                    break
                continue
            break
        self.expect_punct("]")
        return items

    def mapping(self) -> Dict[Any, Any]:
        self.expect_punct("{")
        out: Dict[Any, Any] = {}
        if self.current.kind == "punct" and self.current.value == "}":
            self.advance()
            return out
        while True:
            key = self.value()
            self.expect_punct(":")
            out[key] = self.value()
            if self.current.kind == "punct" and self.current.value == ",":
                self.advance()
                if self.current.kind == "punct" and self.current.value == "}":
                    break
                continue
            break
        self.expect_punct("}")
        return out


def parse_diagnostic(text: str) -> Any:
    """把诊断表示法文本解析为 Python 值。"""
    if not isinstance(text, str):
        raise TypeError("diagnostic notation must be a str")
    return _Parser(_lex(text)).parse()


# --------------------------------------------------------------------------
# 生成
# --------------------------------------------------------------------------


class _Dumper:
    def __init__(
        self,
        indent: Optional[int],
        hex_floats: bool,
        max_bytes: Optional[int],
        max_text: Optional[int],
    ) -> None:
        self.indent = indent
        self.hex_floats = hex_floats
        self.max_bytes = max_bytes
        self.max_text = max_text

    def dump(self, obj: Any, level: int = 0) -> str:
        if obj is None:
            return "null"
        if obj is UNDEFINED:
            return "undefined"
        if obj is True:
            return "true"
        if obj is False:
            return "false"
        if isinstance(obj, Tag):
            return "%d(%s)" % (obj.tag, self.dump(obj.value, level))
        if isinstance(obj, SimpleValue):
            return "simple(%d)" % int(obj)
        if isinstance(obj, float):
            return self._float(obj)
        if isinstance(obj, int):
            return str(int(obj))
        if isinstance(obj, str):
            return self._text(obj)
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return self._bytes(bytes(obj))
        if isinstance(obj, (list, tuple)):
            return self._array(list(obj), level)
        if isinstance(obj, dict):
            return self._map(obj, level)
        raise DiagnosticError("cannot render type %r" % type(obj).__name__)

    def _float(self, value: float) -> str:
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if self.hex_floats:
            return value.hex()
        text = repr(value)
        if "." not in text and "e" not in text and "E" not in text:
            text += ".0"
        return text

    def _text(self, value: str) -> str:
        if self.max_text is not None and len(value) > self.max_text:
            value = value[: self.max_text] + "…"
        return json.dumps(value, ensure_ascii=False)

    def _bytes(self, raw: bytes) -> str:
        truncated = False
        if self.max_bytes is not None and len(raw) > self.max_bytes:
            raw = raw[: self.max_bytes]
            truncated = True
        out = "h'" + raw.hex() + "'"
        if truncated:
            out += "…"
        return out

    def _wrap(self, parts: List[str], open_ch: str, close_ch: str, level: int) -> str:
        if self.indent is None:
            return open_ch + ", ".join(parts) + close_ch
        if not parts:
            return open_ch + close_ch
        pad = " " * (self.indent * (level + 1))
        closing = " " * (self.indent * level)
        body = (",\n").join(pad + part for part in parts)
        return "%s\n%s\n%s%s" % (open_ch, body, closing, close_ch)

    def _array(self, items: List[Any], level: int) -> str:
        parts = [self.dump(item, level + 1) for item in items]
        return self._wrap(parts, "[", "]", level)

    def _map(self, mapping: Dict[Any, Any], level: int) -> str:
        parts = [
            "%s: %s" % (self.dump(key, level + 1), self.dump(value, level + 1))
            for key, value in mapping.items()
        ]
        return self._wrap(parts, "{", "}", level)


def to_diagnostic(
    obj: Any,
    *,
    indent: Optional[int] = None,
    hex_floats: bool = False,
    max_bytes: Optional[int] = None,
    max_text: Optional[int] = None,
) -> str:
    """把 Python/CBOR 值渲染为 RFC 8949 §8 诊断表示法。

    :param indent: 为 ``None`` 时输出紧凑单行；为整数时按该宽度缩进换行
    :param hex_floats: 使用十六进制浮点字面量（如 ``0x1.8p+1``）
    :param max_bytes: 字节串最大展示长度，超出以 ``…`` 截断
    :param max_text: 文本串最大展示长度，超出以 ``…`` 截断
    """
    return _Dumper(indent, hex_floats, max_bytes, max_text).dump(obj)
