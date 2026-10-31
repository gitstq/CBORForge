# -*- coding: utf-8 -*-
"""CBOR 规范性 / 确定性编码审计引擎。

引擎在解码得到的 :class:`~cborforge.decoder.CBORNode` 解析树上做静态分析，
输出带偏移量的审计结论，可用于

* 检查数据是否符合 RFC 7049 规范形式 / RFC 8949 §4.2 核心确定性编码；
* 发现重复键、非最短编码等会在签名校验场景下引发安全问题的隐患；
* 作为 CI 门禁（``--strict`` 下发现问题即以非零退出码结束）。

规则表
------

====== ======== ==================================================
编码    严重级别  含义
====== ======== ==================================================
CBF000 error    数据不符合 RFC 8949 良构性要求（解码失败）
CBF001 error    参数/长度未使用最短编码
CBF002 error    浮点数未使用最短可无损还原的宽度
CBF003 error    NaN 未使用首选序列化 ``0xf97e00``
CBF004 error    使用了不定长数据项
CBF005 error    映射存在重复键
CBF006 error    映射键未按所选确定性规则排序
CBF007 warning  映射键不可哈希，无法无损转换为 Python ``dict``
CBF008 warning  嵌套深度超过阈值
CBF009 warning  不定长字符串被拆分为多个分块
CBF010 info     使用了内置注册表未收录的标签号
====== ======== ==================================================
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .decoder import Decoder, parse
from .encoder import _shortest_float
from .errors import CBORDecodeError
from .types import UNDEFINED, SimpleValue, Tag

__all__ = [
    "Finding",
    "Report",
    "RULES",
    "validate",
    "safe_validate",
    "KNOWN_TAGS",
    "DETERMINISM_CHOICES",
]

# IANA CBOR 标签注册表常用子集（仅用于提示，未收录不代表错误）
KNOWN_TAGS: Set[int] = set(
    list(range(0, 6))
    + list(range(21, 31))
    + list(range(32, 49))
    + list(range(50, 62))
    + list(range(64, 88))
    + list(range(128, 137))
    + [22098, 55799, 1530973434432]
)

RULES: Dict[str, Tuple[str, str, str]] = {
    "CBF000": (
        "数据不符合 RFC 8949 良构性要求",
        "error",
        "修正数据源或检查是否为截断/损坏的 CBOR 字节流",
    ),
    "CBF001": (
        "参数/长度未使用最短编码",
        "error",
        "改用最短形式：ai<24、24(1B)、25(2B)、26(4B)、27(8B)",
    ),
    "CBF002": (
        "浮点数未使用最短可无损还原的宽度",
        "error",
        "按 RFC 8949 §4.2.2 首选序列化降级为半精度/单精度",
    ),
    "CBF003": (
        "NaN 未使用首选序列化",
        "error",
        "统一编码为 0xf97e00",
    ),
    "CBF004": (
        "使用了不定长数据项",
        "error",
        "改写为定长形式以获得确定性编码",
    ),
    "CBF005": (
        "映射存在重复键",
        "error",
        "删除重复键，签名校验场景下重复键可被用于绕过验证",
    ),
    "CBF006": (
        "映射键未按确定性规则排序",
        "error",
        "按键的确定性编码排序（RFC 8949 为纯字节字典序）",
    ),
    "CBF007": (
        "映射键不可哈希",
        "warning",
        "改用标量键，否则无法无损转换为 Python dict",
    ),
    "CBF008": (
        "嵌套深度超过阈值",
        "warning",
        "降低嵌套层级，避免解码器栈溢出",
    ),
    "CBF009": (
        "不定长字符串被拆分为多个分块",
        "warning",
        "合并为单个定长分块可显著减少字节数",
    ),
    "CBF010": (
        "使用了未收录的标签号",
        "info",
        "确认该标签号语义；自定义标签建议使用 24 或大于 2^32 的数值",
    ),
}

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


class Finding:
    """一条审计结论。"""

    __slots__ = ("code", "severity", "message", "offset", "length", "path")

    def __init__(
        self,
        code: str,
        severity: str,
        message: str,
        offset: int,
        length: int = 0,
        path: str = "$",
    ) -> None:
        self.code = code
        self.severity = severity
        self.message = message
        self.offset = offset
        self.length = length
        self.path = path

    def to_dict(self) -> Dict[str, Any]:
        title, _severity, hint = RULES.get(
            self.code, (self.code, self.severity, "")
        )
        return {
            "code": self.code,
            "title": title,
            "severity": self.severity,
            "message": self.message,
            "hint": hint,
            "offset": self.offset,
            "length": self.length,
            "path": self.path,
        }

    def __str__(self) -> str:
        return "[%s] %-7s %s" % (self.code, self.severity, self.message)


class Report:
    """审计结果汇总。"""

    __slots__ = ("findings", "determinism", "size", "item_count", "max_depth")

    def __init__(
        self,
        findings: List[Finding],
        determinism: str,
        size: int,
        item_count: int,
        max_depth: int,
    ) -> None:
        self.findings = findings
        self.determinism = determinism
        self.size = size
        self.item_count = item_count
        self.max_depth = max_depth

    # -- 汇总视图 ---------------------------------------------------------
    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def infos(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "info"]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def counts(self) -> Dict[str, int]:
        out = {"error": 0, "warning": 0, "info": 0}
        for finding in self.findings:
            out[finding.severity] = out.get(finding.severity, 0) + 1
        return out

    def to_dict(self) -> Dict[str, Any]:
        counts = self.counts
        return {
            "tool": "cborforge",
            "determinism": self.determinism,
            "size": self.size,
            "item_count": self.item_count,
            "max_depth": self.max_depth,
            "ok": self.ok,
            "counts": counts,
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_text(self, *, show_hint: bool = True) -> str:
        counts = self.counts
        lines: List[str] = []
        lines.append("CBORForge 审计报告 / CBORForge Audit Report")
        lines.append("─" * 60)
        lines.append("  字节长度   : %d" % self.size)
        lines.append("  数据项数量 : %d" % self.item_count)
        lines.append("  最大嵌套   : %d" % self.max_depth)
        lines.append("  确定性规则 : %s" % _DETERMINISM_LABELS.get(
            self.determinism, self.determinism
        ))
        lines.append(
            "  结论       : %s（%d 错误 / %d 警告 / %d 提示）"
            % (
                "通过 PASS" if self.ok else "未通过 FAIL",
                counts["error"],
                counts["warning"],
                counts["info"],
            )
        )
        lines.append("─" * 60)
        if not self.findings:
            lines.append("  未发现任何问题。✨")
            return "\n".join(lines)
        ordered = sorted(
            self.findings,
            key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9), f.offset, f.code),
        )
        for finding in ordered:
            title, _severity, hint = RULES.get(
                finding.code, (finding.code, finding.severity, "")
            )
            lines.append(
                "[%s] %-7s %s" % (finding.code, finding.severity, title)
            )
            lines.append(
                "        偏移 %d (长度 %d)  路径 %s"
                % (finding.offset, finding.length, finding.path)
            )
            lines.append("        %s" % finding.message)
            if show_hint and hint:
                lines.append("        建议: %s" % hint)
        return "\n".join(lines)


_DETERMINISM_LABELS = {
    "rfc8949": "RFC 8949 §4.2.1 核心确定性编码（字节字典序）",
    "rfc7049": "RFC 7049 规范形式（长度优先 + 字节字典序）",
    "off": "不检查键顺序",
}

_DETERMINISM_CHOICES = ("rfc8949", "rfc7049", "off")

#: 受支持的确定性规则取值（供 CLI 与调用方复用）。
DETERMINISM_CHOICES = _DETERMINISM_CHOICES


def _minimal_ai(n: int) -> int:
    """返回承载参数 ``n`` 所需的最小附加信息值。"""
    if n < 24:
        return n
    if n < 0x100:
        return 24
    if n < 0x10000:
        return 25
    if n < 0x100000000:
        return 26
    return 27


def _sort_key(encoded: bytes, determinism: str) -> Tuple[Any, ...]:
    if determinism == "rfc7049":
        return (len(encoded), encoded)
    return (encoded,)


class _Auditor:
    def __init__(
        self,
        data: bytes,
        determinism: str,
        depth_threshold: int,
        known_tags: Set[int],
    ) -> None:
        self.data = data
        self.determinism = determinism
        self.depth_threshold = depth_threshold
        self.known_tags = known_tags
        self.findings: List[Finding] = []
        self.item_count = 0
        self.max_depth = 0
        self._deep_reported = False

    def add(self, code: str, message: str, node, path: str) -> None:
        severity = RULES[code][1]
        self.findings.append(
            Finding(
                code,
                severity,
                message,
                node.offset,
                node.end - node.offset,
                path,
            )
        )

    def run(self) -> None:
        root = parse(self.data)
        self._walk(root, "$")

    # -- 遍历 -------------------------------------------------------------
    def _walk(self, node, path: str) -> None:
        self.item_count += 1
        self.max_depth = max(self.max_depth, node.depth)
        if node.depth > self.depth_threshold and not self._deep_reported:
            self._deep_reported = True
            self.add(
                "CBF008",
                "嵌套深度 %d 超过阈值 %d" % (node.depth, self.depth_threshold),
                node,
                path,
            )

        mt = node.mt
        ai = node.ai

        # CBF001：非最短参数/长度编码（浮点与简单值不适用）
        if mt in (0, 1, 2, 3, 4, 5, 6) and ai != 31:
            expected = _minimal_ai(node.arg)
            if ai != expected:
                self.add(
                    "CBF001",
                    "major type %d 的参数 %d 使用 ai=%d，最短应为 ai=%d"
                    % (mt, node.arg, ai, expected),
                    node,
                    path,
                )

        # CBF002 / CBF003：浮点宽度与 NaN 首选序列化
        if mt == 7 and ai in (25, 26, 27):
            value = node.value
            actual_len = node.end - node.offset
            if isinstance(value, float) and math.isnan(value):
                if not (ai == 25 and self.data[node.offset : node.end] == b"\xf9\x7e\x00"):
                    self.add(
                        "CBF003",
                        "NaN 编码为 %s，首选序列化应为 f97e00"
                        % self.data[node.offset : node.end].hex(),
                        node,
                        path,
                    )
            else:
                shortest_len = len(_shortest_float(float(value)))
                if actual_len != shortest_len:
                    self.add(
                        "CBF002",
                        "浮点值 %r 占用 %d 字节，最短可无损还原仅需 %d 字节"
                        % (value, actual_len, shortest_len),
                        node,
                        path,
                    )

        # CBF004：不定长数据项
        if ai == 31 and mt in (2, 3, 4, 5):
            self.add(
                "CBF004",
                "%s 使用了不定长编码，无法得到确定性字节序列"
                % node.major_name,
                node,
                path,
            )

        # CBF009：不定长字符串多分块
        if ai == 31 and mt in (2, 3) and len(node.children) > 1:
            self.add(
                "CBF009",
                "不定长 %s 被拆分为 %d 个分块"
                % (node.major_name, len(node.children)),
                node,
                path,
            )

        # CBF010：未收录标签号
        if mt == 6:
            if node.tag not in self.known_tags:
                self.add(
                    "CBF010",
                    "标签号 %d 不在内置注册表中" % node.tag,
                    node,
                    path,
                )
            self._walk(node.child, "%s#%d" % (path, node.tag))
            return

        if mt == 4:
            for index, child in enumerate(node.children):
                self._walk(child, "%s[%d]" % (path, index))
            return

        if mt == 5:
            self._audit_map(node, path)
            for key_node, value_node in node.entries:
                self._walk(key_node, _key_path(path, key_node.value))
                self._walk(value_node, _key_path(path, key_node.value))
            return

    def _audit_map(self, node, path: str) -> None:
        encoded_keys = [
            self.data[key.offset : key.end] for key, _value in node.entries
        ]

        # CBF005：重复键
        seen: Dict[bytes, int] = {}
        for index, raw in enumerate(encoded_keys):
            key_node = node.entries[index][0]
            if raw in seen:
                self.add(
                    "CBF005",
                    "重复键 %s（首次出现于偏移 %d）"
                    % (_short_repr(key_node.value), seen[raw]),
                    key_node,
                    path,
                )
            else:
                seen[raw] = key_node.offset

        # CBF006：键顺序
        if self.determinism in ("rfc8949", "rfc7049"):
            for index in range(len(encoded_keys) - 1):
                left = _sort_key(encoded_keys[index], self.determinism)
                right = _sort_key(encoded_keys[index + 1], self.determinism)
                if left > right:
                    key_node = node.entries[index + 1][0]
                    self.add(
                        "CBF006",
                        "键 %s 排序在 %s 之前，违反 %s"
                        % (
                            _short_repr(node.entries[index + 1][0].value),
                            _short_repr(node.entries[index][0].value),
                            self.determinism.upper(),
                        ),
                        key_node,
                        path,
                    )

        # CBF007：不可哈希键
        if node.value is None and node.entries:
            self.add(
                "CBF007",
                "映射包含不可哈希的键，解码后无法构造 Python dict",
                node,
                path,
            )


def _short_repr(value: Any, limit: int = 32) -> str:
    try:
        text = repr(value)
    except Exception:  # pragma: no cover - 极端防御
        text = "<unrepresentable>"
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def _key_path(path: str, key: Any) -> str:
    if isinstance(key, str):
        return "%s.%s" % (path, key)
    return "%s[%s]" % (path, _short_repr(key, 24))


def validate(
    data: bytes,
    *,
    determinism: str = "rfc8949",
    depth_threshold: int = 32,
    known_tags: Optional[Set[int]] = None,
) -> Report:
    """审计一段 CBOR 字节流并返回 :class:`Report`。

    :param determinism: ``rfc8949`` / ``rfc7049`` / ``off``
    :param depth_threshold: 触发 CBF008 的嵌套深度阈值
    :param known_tags: 自定义已知标签号集合，缺省使用 :data:`KNOWN_TAGS`
    :raises CBORDecodeError: 数据不符合 RFC 8949 良构性要求
    """
    if determinism not in _DETERMINISM_CHOICES:
        raise ValueError(
            "determinism must be one of %s" % (_DETERMINISM_CHOICES,)
        )
    if isinstance(data, (bytearray, memoryview)):
        data = bytes(data)
    auditor = _Auditor(
        data,
        determinism,
        depth_threshold,
        set(known_tags) if known_tags is not None else KNOWN_TAGS,
    )
    auditor.run()
    return Report(
        auditor.findings,
        determinism,
        len(data),
        auditor.item_count,
        auditor.max_depth,
    )


def safe_validate(data: bytes, **kwargs: Any) -> Report:
    """同 :func:`validate`，但把解码失败包装为 CBF000 结论而不抛异常。"""
    try:
        return validate(data, **kwargs)
    except CBORDecodeError as exc:
        report = Report(
            [
                Finding(
                    "CBF000",
                    "error",
                    str(exc),
                    exc.offset if exc.offset is not None else 0,
                )
            ],
            kwargs.get("determinism", "rfc8949"),
            len(data),
            0,
            0,
        )
        return report
