# -*- coding: utf-8 -*-
"""CBORForge 命令行接口。

提供六个子命令：``encode`` / ``decode`` / ``inspect`` / ``validate`` /
``canonical`` / ``selftest``，全部离线运行、无第三方依赖。

退出码
------

====== ===============================================
0      执行成功（审计类命令：未发现 error 级问题）
1      审计发现 error 级问题（``--strict`` 下含 warning/info）
2      用法、IO、解码或编码错误
====== ===============================================
"""

from __future__ import annotations

import argparse
import base64
import binascii
import math
import os
import re
import sys
from typing import Any, List, Optional, Sequence, Tuple

from . import __version__
from .decoder import loads, parse
from .diagnostic import parse_diagnostic, to_diagnostic
from .encoder import dumps
from .errors import CBORDecodeError, CBOREncodeError, DiagnosticError
from .jsonio import from_json_text, to_json_text
from .types import UNDEFINED, SimpleValue, Tag
from .validator import DETERMINISM_CHOICES, safe_validate, validate
from .vectors import NON_ROUNDTRIP, VECTORS

__all__ = ["main", "build_parser"]

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

_HEX_RE = re.compile(r"\A[0-9a-fA-F]*\Z")


class CliError(Exception):
    """命令行层面的可恢复错误。"""


# --------------------------------------------------------------------------
# 输入 / 输出工具
# --------------------------------------------------------------------------


def _read_source(source: Optional[str]) -> bytes:
    """读取输入。

    优先按文件路径读取；当给定值不是已存在的文件时，按**字面量**处理，
    从而支持 ``cborforge decode a1616101`` 这类直接传值的用法。
    """
    if source is None or source == "-":
        return sys.stdin.buffer.read()
    if os.path.exists(source):
        with open(source, "rb") as handle:
            return handle.read()
    return source.encode("utf-8")


def _read_text(source: Optional[str]) -> str:
    return _read_source(source).decode("utf-8")


def _as_cbor_bytes(raw: bytes, fmt: str) -> bytes:
    """按 ``hex`` / ``base64`` / ``bin`` / ``auto`` 解释输入字节。"""
    if fmt == "bin":
        return raw
    text = raw.decode("utf-8").strip()
    if text[:2].lower() == "0x":
        text = text[2:]
    text = re.sub(r"\s+", "", text)
    if not text:
        return b""
    if fmt == "hex":
        try:
            return binascii.unhexlify(text)
        except binascii.Error as exc:
            raise CliError("十六进制输入无法解析: %s" % exc) from None
    if fmt == "base64":
        try:
            return base64.b64decode(text + "=" * ((-len(text)) % 4))
        except (binascii.Error, ValueError) as exc:
            raise CliError("Base64 输入无法解析: %s" % exc) from None
    # auto：优先按十六进制（含 0x 前缀或纯十六进制且长度为偶数），否则 Base64
    if _HEX_RE.match(text) and len(text) % 2 == 0:
        try:
            return binascii.unhexlify(text)
        except binascii.Error:
            pass
    try:
        return base64.b64decode(text + "=" * ((-len(text)) % 4), validate=True)
    except (binascii.Error, ValueError):
        raise CliError(
            "无法判定输入格式（既非纯十六进制也非合法 Base64），请使用 --in-format 指定"
        ) from None


def _emit_text(text: str, target: Optional[str]) -> None:
    if not text.endswith("\n"):
        text += "\n"
    if target is None or target == "-":
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.flush()
        return
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)


def _emit_bytes(data: bytes, target: Optional[str], trailing_newline: bool = False) -> None:
    if target is None or target == "-":
        sys.stdout.buffer.write(data)
        if trailing_newline:
            sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
        return
    with open(target, "wb") as handle:
        handle.write(data)


def _format_bytes(data: bytes, fmt: str) -> bytes:
    if fmt == "hex":
        return data.hex().encode("ascii")
    if fmt == "base64":
        return base64.b64encode(data)
    return data


# --------------------------------------------------------------------------
# inspect 渲染
# --------------------------------------------------------------------------


def _clip(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _type_label(node: Any) -> str:
    mt = node.mt
    ai = node.ai
    if mt == 0:
        return "uint"
    if mt == 1:
        return "nint"
    if mt == 2:
        return "bytes(%d)" % len(node.value)
    if mt == 3:
        return "text(%d)" % len(node.value)
    if mt == 4:
        return "array(%d)%s" % (len(node.children), " ∞" if ai == 31 else "")
    if mt == 5:
        return "map(%d)%s" % (len(node.entries), " ∞" if ai == 31 else "")
    if mt == 6:
        return "tag(%d)" % node.tag
    if ai < 20:
        return "simple"
    if ai == 20:
        return "false"
    if ai == 21:
        return "true"
    if ai == 22:
        return "null"
    if ai == 23:
        return "undefined"
    if ai == 24:
        return "simple"
    if ai in (25, 26, 27):
        return "float%d" % {25: 16, 26: 32, 27: 64}[ai]
    return "break"


def _preview(node: Any, max_bytes: Optional[int], max_text: Optional[int]) -> str:
    if node.mt in (4, 5, 6):
        return ""
    if node.value is None:
        return ""
    try:
        return _clip(
            to_diagnostic(node.value, max_bytes=max_bytes, max_text=max_text), 48
        )
    except Exception:  # pragma: no cover - 防御性
        return ""


def _key_label(key: Any) -> str:
    if isinstance(key, str):
        return ".%s" % key
    return _clip("[%s]" % to_diagnostic(key, max_bytes=8, max_text=12), 20)


def _emit_node(
    lines: List[str],
    node: Any,
    path: str,
    role: str,
    depth: int,
    max_bytes: Optional[int],
    max_text: Optional[int],
) -> None:
    head = "  " * depth + role + path
    lines.append(
        "%-34s %-16s @%-8d %-6d %s"
        % (
            _clip(head, 34),
            _type_label(node),
            node.offset,
            node.length,
            _preview(node, max_bytes, max_text),
        )
    )
    if node.mt == 6 and node.child is not None:
        _emit_node(lines, node.child, path, "  ", depth + 1, max_bytes, max_text)
    elif node.mt == 4:
        for index, child in enumerate(node.children):
            _emit_node(
                lines, child, "[%d]" % index, "", depth + 1, max_bytes, max_text
            )
    elif node.mt == 5:
        for key_node, value_node in node.entries:
            label = _key_label(key_node.value)
            _emit_node(lines, key_node, label, "K ", depth + 1, max_bytes, max_text)
            _emit_node(lines, value_node, label, "V ", depth + 1, max_bytes, max_text)


def _hexdump(data: bytes, limit: int = 256) -> List[str]:
    out: List[str] = []
    shown = data[:limit]
    for index in range(0, len(shown), 16):
        chunk = shown[index : index + 16]
        hexpart = " ".join("%02x" % byte for byte in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append("%08x  %-47s  |%s|" % (index, hexpart, ascii_part))
    if len(data) > limit:
        out.append("... 其余 %d 字节已省略（共 %d 字节）" % (len(data) - limit, len(data)))
    return out


# --------------------------------------------------------------------------
# 子命令实现
# --------------------------------------------------------------------------


def cmd_encode(args: argparse.Namespace) -> int:
    text = _read_text(args.input)
    source = args.src
    if source == "auto":
        try:
            value = from_json_text(text)
        except Exception:
            value = parse_diagnostic(text)
    elif source == "json":
        value = from_json_text(text)
    else:
        value = parse_diagnostic(text)
    encoded = dumps(
        value,
        canonical=args.canonical,
        ctap2=args.ctap2,
        float_mode=args.float_mode,
        indefinite=args.indefinite,
        chunk_size=args.chunk_size,
    )
    _emit_bytes(
        _format_bytes(encoded, args.format),
        args.output,
        trailing_newline=args.format in ("hex", "base64"),
    )
    return EXIT_OK


def cmd_decode(args: argparse.Namespace) -> int:
    raw = _as_cbor_bytes(_read_source(args.input), args.in_format)
    value = loads(raw, bignum=args.bignum)
    if args.format == "json":
        indent = 2 if args.indent < 0 else (args.indent or None)
        text = to_json_text(value, indent=indent)
    else:
        # 诊断表示法默认紧凑单行，显式传入 --indent 才换行缩进
        indent = None if args.indent < 0 else (args.indent or None)
        text = to_diagnostic(value, indent=indent, hex_floats=args.hex_floats)
    _emit_text(text, args.output)
    return EXIT_OK


def cmd_inspect(args: argparse.Namespace) -> int:
    raw = _as_cbor_bytes(_read_source(args.input), args.in_format)
    node = parse(raw)
    lines: List[str] = []
    lines.append("🔍 CBORForge inspect — %d 字节" % len(raw))
    lines.append("─" * 88)
    lines.append(
        "%-34s %-16s %-9s %-6s %s" % ("路径", "类型", "偏移", "长度", "值")
    )
    lines.append("─" * 88)
    _emit_node(lines, node, "$", "", 0, args.max_bytes, args.max_text)
    lines.append("─" * 88)
    lines.append("十六进制转储 / hex dump:")
    lines.extend(_hexdump(raw, args.dump_limit))
    _emit_text("\n".join(lines), args.output)
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    raw = _as_cbor_bytes(_read_source(args.input), args.in_format)
    report = safe_validate(
        raw,
        determinism=args.determinism,
        depth_threshold=args.depth_threshold,
    )
    if args.format == "json":
        import json

        _emit_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2), args.output
        )
    else:
        _emit_text(report.to_text(), args.output)
    if args.strict:
        return EXIT_OK if not report.findings else EXIT_FINDINGS
    return EXIT_OK if report.ok else EXIT_FINDINGS


def cmd_canonical(args: argparse.Namespace) -> int:
    raw = _as_cbor_bytes(_read_source(args.input), args.in_format)
    value = loads(raw, bignum=args.bignum)
    encoded = dumps(value, canonical=not args.ctap2, ctap2=args.ctap2)
    if args.report:
        after = encoded
        sys.stderr.write(
            "规范化: %d 字节 -> %d 字节 (%s)\n"
            % (len(raw), len(after), "一致" if raw == after else "已重写")
        )
    _emit_bytes(
        _format_bytes(encoded, args.format),
        args.output,
        trailing_newline=args.format in ("hex", "base64"),
    )
    return EXIT_OK


# -- selftest --------------------------------------------------------------


def _deep_equal(left: Any, right: Any) -> bool:
    if isinstance(left, float) and isinstance(right, float):
        if math.isnan(left) and math.isnan(right):
            return True
        return left == right and math.copysign(1.0, left) == math.copysign(1.0, right)
    if isinstance(left, Tag) and isinstance(right, Tag):
        return left.tag == right.tag and _deep_equal(left.value, right.value)
    if isinstance(left, SimpleValue) and isinstance(right, SimpleValue):
        return int(left) == int(right)
    if left is UNDEFINED or right is UNDEFINED:
        return left is right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _deep_equal(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        if list(left.keys()) != list(right.keys()):
            return False
        return all(_deep_equal(left[k], right[k]) for k in left)
    return type(left) is type(right) and left == right


def _selftest_results() -> Tuple[int, int, List[str]]:
    passed = 0
    failed = 0
    problems: List[str] = []
    for hex_text, diag in VECTORS:
        raw = binascii.unhexlify(hex_text)
        expected = parse_diagnostic(diag)
        try:
            actual = loads(raw)
        except CBORDecodeError as exc:
            failed += 1
            problems.append("解码失败 %s: %s" % (hex_text, exc))
            continue
        if not _deep_equal(actual, expected):
            failed += 1
            problems.append("值不匹配 %s: %r != %r" % (hex_text, actual, expected))
            continue
        passed += 1

        # 诊断表示法往返
        try:
            if not _deep_equal(parse_diagnostic(to_diagnostic(actual)), actual):
                failed += 1
                problems.append("诊断表示法往返失败: %s" % hex_text)
                continue
        except DiagnosticError as exc:
            failed += 1
            problems.append("诊断表示法往返异常 %s: %s" % (hex_text, exc))
            continue
        passed += 1

        # 字节级重编码（仅限期望可还原的向量）
        if hex_text in NON_ROUNDTRIP:
            continue
        try:
            rebuilt = dumps(actual)
        except CBOREncodeError as exc:
            failed += 1
            problems.append("重编码失败 %s: %s" % (hex_text, exc))
            continue
        if rebuilt != raw:
            failed += 1
            problems.append(
                "重编码字节不一致 %s: 得到 %s" % (hex_text, rebuilt.hex())
            )
            continue
        passed += 1
    return passed, failed, problems


def cmd_selftest(args: argparse.Namespace) -> int:
    passed, failed, problems = _selftest_results()
    lines: List[str] = []
    lines.append("🧪 CBORForge selftest — RFC 8949 附录 A 测试向量")
    lines.append("─" * 60)
    lines.append("  向量总数 : %d" % len(VECTORS))
    lines.append("  检查项   : %d" % (passed + failed))
    lines.append("  通过     : %d" % passed)
    lines.append("  失败     : %d" % failed)
    lines.append("─" * 60)
    for problem in problems:
        lines.append("  ✗ %s" % problem)
    if not problems:
        lines.append("  ✅ 全部通过：解码、诊断表示法往返与字节级重编码均一致。")
    _emit_text("\n".join(lines), args.output)
    return EXIT_OK if failed == 0 else EXIT_FINDINGS


# --------------------------------------------------------------------------
# 解析器
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cborforge",
        description="零依赖·离线优先的 CBOR (RFC 8949) 编解码与规范性审计工具箱",
    )
    parser.add_argument(
        "--version", action="version", version="cborforge %s" % __version__
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    # encode
    p = sub.add_parser("encode", help="把 JSON / 诊断表示法编码为 CBOR")
    p.add_argument("input", nargs="?", default="-", help="输入文件，'-' 或省略表示标准输入")
    p.add_argument(
        "--from", dest="src", choices=("auto", "json", "diag"), default="auto",
        help="输入文本格式（默认自动判定）",
    )
    p.add_argument("-f", "--format", choices=("hex", "base64", "bin"), default="hex",
                   help="CBOR 输出表示（默认 hex）")
    p.add_argument("-o", "--output", default="-", help="输出文件，'-' 表示标准输出")
    p.add_argument("--canonical", action="store_true", help="使用 RFC 7049 规范形式")
    p.add_argument("--ctap2", action="store_true", help="使用 RFC 8949 核心确定性编码")
    p.add_argument("--float-mode", choices=("auto", "16", "32", "64"), default="auto")
    p.add_argument("--indefinite", action="store_true", help="使用不定长构造")
    p.add_argument("--chunk-size", type=int, default=8, help="不定长字符串分块字节数")
    p.set_defaults(handler=cmd_encode)

    # decode
    p = sub.add_parser("decode", help="把 CBOR 解码为 JSON / 诊断表示法")
    p.add_argument("input", nargs="?", default="-")
    p.add_argument("--in-format", choices=("auto", "hex", "base64", "bin"), default="auto")
    p.add_argument("-f", "--format", choices=("json", "diag"), default="json")
    p.add_argument(
        "--indent", type=int, default=-1,
        help="缩进宽度；JSON 默认 2，诊断表示法默认紧凑（0 亦为紧凑）",
    )
    p.add_argument("--hex-floats", action="store_true", help="诊断表示法使用十六进制浮点")
    p.add_argument("--bignum", action="store_true", help="把标签 2/3 折叠为 Python int")
    p.add_argument("-o", "--output", default="-")
    p.set_defaults(handler=cmd_decode)

    # inspect
    p = sub.add_parser("inspect", help="展示带偏移量的结构树与十六进制转储")
    p.add_argument("input", nargs="?", default="-")
    p.add_argument("--in-format", choices=("auto", "hex", "base64", "bin"), default="auto")
    p.add_argument("--max-bytes", type=int, default=24, help="字节串预览最大长度")
    p.add_argument("--max-text", type=int, default=40, help="文本串预览最大长度")
    p.add_argument("--dump-limit", type=int, default=256, help="十六进制转储最大字节数")
    p.add_argument("-o", "--output", default="-")
    p.set_defaults(handler=cmd_inspect)

    # validate
    p = sub.add_parser("validate", help="规范性 / 确定性编码审计")
    p.add_argument("input", nargs="?", default="-")
    p.add_argument("--in-format", choices=("auto", "hex", "base64", "bin"), default="auto")
    p.add_argument("--determinism", choices=DETERMINISM_CHOICES, default="rfc8949")
    p.add_argument("--depth-threshold", type=int, default=32)
    p.add_argument("--strict", action="store_true", help="存在任何问题即返回非零")
    p.add_argument("-f", "--format", choices=("text", "json"), default="text")
    p.add_argument("-o", "--output", default="-")
    p.set_defaults(handler=cmd_validate)

    # canonical
    p = sub.add_parser("canonical", help="重新编码为规范 / 确定性形式")
    p.add_argument("input", nargs="?", default="-")
    p.add_argument("--in-format", choices=("auto", "hex", "base64", "bin"), default="auto")
    p.add_argument("--ctap2", action="store_true", help="使用 RFC 8949 核心确定性编码")
    p.add_argument("-f", "--format", choices=("hex", "base64", "bin"), default="hex")
    p.add_argument("--report", action="store_true", help="向标准输出打印体积对比")
    p.add_argument("--bignum", action="store_true")
    p.add_argument("-o", "--output", default="-")
    p.set_defaults(handler=cmd_canonical)

    # selftest
    p = sub.add_parser("selftest", help="运行内置 RFC 8949 测试向量自检")
    p.add_argument("-o", "--output", default="-")
    p.set_defaults(handler=cmd_selftest)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """命令行入口，返回进程退出码。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except CliError as exc:
        sys.stderr.write("cborforge: 错误: %s\n" % exc)
        return EXIT_ERROR
    except (CBORDecodeError, CBOREncodeError, DiagnosticError) as exc:
        sys.stderr.write("cborforge: 错误: %s\n" % exc)
        return EXIT_ERROR
    except (OSError, ValueError, binascii.Error) as exc:
        sys.stderr.write("cborforge: 错误: %s\n" % exc)
        return EXIT_ERROR
