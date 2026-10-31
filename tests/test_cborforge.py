# -*- coding: utf-8 -*-
"""CBORForge 单元测试。

运行::

    python -m unittest discover -s tests -v
    # 或
    make test

全部测试仅依赖 Python 标准库，离线运行，无网络访问。
"""

from __future__ import annotations

import base64
import binascii
import json
import math
import os
import sys
import tempfile
import unittest
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cborforge
from cborforge import (
    UNDEFINED,
    SimpleValue,
    Tag,
    dumps,
    from_json_text,
    loads,
    parse_diagnostic,
    safe_validate,
    to_diagnostic,
    to_json_text,
    validate,
)
from cborforge.cli import main
from cborforge.decoder import parse
from cborforge.errors import (
    CBORDecodeError,
    CBOREncodeError,
    DiagnosticError,
)
from cborforge.types import Break
from cborforge.vectors import NON_ROUNDTRIP, VECTORS


def hx(text: str) -> bytes:
    return binascii.unhexlify(text)


def _readf(path: str) -> str:
    """读取文本文件（显式关闭句柄，避免 ResourceWarning）。"""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# ==========================================================================
# 解码器
# ==========================================================================


class TestDecoderVectors(unittest.TestCase):
    """RFC 8949 附录 A 测试向量的解码正确性。"""

    def test_all_vectors_decode(self) -> None:
        for hex_text, diag in VECTORS:
            with self.subTest(hex=hex_text):
                actual = loads(hx(hex_text))
                self.assertEqual(type(actual), type(parse_diagnostic(diag)))
                self.assertTrue(
                    _same(actual, parse_diagnostic(diag)),
                    "解码结果不符: %s -> %r" % (hex_text, actual),
                )

    def test_trailing_data_is_rejected(self) -> None:
        with self.assertRaises(CBORDecodeError):
            loads(hx("0101"))

    def test_bignum_folding(self) -> None:
        self.assertEqual(loads(hx("c2420100"), bignum=True), 256)
        self.assertEqual(loads(hx("c3420100"), bignum=True), -257)
        self.assertIsInstance(loads(hx("c2420100")), Tag)

    def test_indefinite_text_chunks_are_validated(self) -> None:
        # 分块文本串中某个分块不是合法 UTF-8 → 必须报错
        with self.assertRaises(CBORDecodeError):
            loads(hx("7f62c328ff"))

    def test_depth_limit(self) -> None:
        with self.assertRaises(CBORDecodeError):
            loads(b"\x81" * 400 + b"\x01")
        # 放宽上限后应可正常解码
        self.assertEqual(loads(b"\x81" * 400 + b"\x01", max_depth=512), _nest(400))


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, float) and isinstance(right, float):
        if math.isnan(left) and math.isnan(right):
            return True
        return left == right and math.copysign(1.0, left) == math.copysign(1.0, right)
    if isinstance(left, Tag) and isinstance(right, Tag):
        return left.tag == right.tag and _same(left.value, right.value)
    if isinstance(left, SimpleValue) and isinstance(right, SimpleValue):
        return int(left) == int(right)
    if left is UNDEFINED or right is UNDEFINED:
        return left is right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _same(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return list(left.keys()) == list(right.keys()) and all(
            _same(left[k], right[k]) for k in left
        )
    return type(left) is type(right) and left == right


def _nest(depth: int) -> Any:
    value: Any = 1
    for _ in range(depth):
        value = [value]
    return value


class TestDecoderMalformed(unittest.TestCase):
    """RFC 8949 附录 C 良构性错误必须被拒绝。"""

    CASES = {
        "reserved_ai_28": "1c",
        "reserved_ai_29": "1d",
        "reserved_ai_30": "1e",
        "indefinite_uint": "1f",
        "indefinite_tag": "df00",
        "nested_indefinite_bytes": "5f5f4100ffff",
        "indefinite_bytes_with_int_chunk": "5f01ff",
        "invalid_utf8_text": "62c328",
        "break_at_top_level": "ff",
        "simple_two_byte_reserved": "f800",
        "truncated_8byte_arg": "1b0000",
        "truncated_array": "81",
        "truncated_map": "a1",
        "unterminated_indefinite_array": "9f01",
        "oversized_array_length": "9bffffffffffffffff",
        "oversized_map_length": "bbffffffffffffffff",
        "oversized_byte_string": "44ffff",
    }

    def test_malformed_cases(self) -> None:
        for name, hex_text in self.CASES.items():
            with self.subTest(case=name):
                with self.assertRaises(CBORDecodeError):
                    loads(hx(hex_text))

    def test_empty_input(self) -> None:
        with self.assertRaises(CBORDecodeError):
            loads(b"")


# ==========================================================================
# 编码器
# ==========================================================================


class TestEncoder(unittest.TestCase):
    def test_roundtrip_vectors(self) -> None:
        for hex_text, _diag in VECTORS:
            if hex_text in NON_ROUNDTRIP:
                continue
            with self.subTest(hex=hex_text):
                self.assertEqual(dumps(loads(hx(hex_text))).hex(), hex_text)

    def test_shortest_integer(self) -> None:
        self.assertEqual(dumps(0).hex(), "00")
        self.assertEqual(dumps(23).hex(), "17")
        self.assertEqual(dumps(24).hex(), "1818")
        self.assertEqual(dumps(255).hex(), "18ff")
        self.assertEqual(dumps(256).hex(), "190100")
        self.assertEqual(dumps(65536).hex(), "1a00010000")
        self.assertEqual(dumps(4294967296).hex(), "1b0000000100000000")

    def test_negative_integers(self) -> None:
        self.assertEqual(dumps(-1).hex(), "20")
        self.assertEqual(dumps(-24).hex(), "37")
        self.assertEqual(dumps(-25).hex(), "3818")
        self.assertEqual(dumps(-256).hex(), "38ff")

    def test_bignum_roundtrip(self) -> None:
        big = 2 ** 70 + 12345
        encoded = dumps(big)
        self.assertEqual(encoded[0], 0xC2)
        self.assertEqual(loads(encoded, bignum=True), big)
        negative = -(2 ** 70) - 1
        self.assertEqual(loads(dumps(negative), bignum=True), negative)

    def test_float_preferred_serialization(self) -> None:
        self.assertEqual(dumps(1.0).hex(), "f93c00")
        self.assertEqual(dumps(0.0).hex(), "f90000")
        self.assertEqual(dumps(-0.0).hex(), "f98000")
        self.assertEqual(dumps(1.1).hex(), "fb3ff199999999999a")
        self.assertEqual(dumps(float("nan")).hex(), "f97e00")
        self.assertEqual(dumps(float("inf")).hex(), "f97c00")
        self.assertEqual(dumps(float("-inf")).hex(), "f9fc00")

    def test_float_modes(self) -> None:
        self.assertEqual(dumps(1.5, float_mode="64").hex(), "fb3ff8000000000000")
        self.assertEqual(dumps(1.5, float_mode="32").hex(), "fa3fc00000")
        self.assertEqual(dumps(1.5, float_mode="16").hex(), "f93e00")

    def test_simple_values(self) -> None:
        self.assertEqual(dumps(SimpleValue(16)).hex(), "f0")
        self.assertEqual(dumps(SimpleValue(255)).hex(), "f8ff")
        with self.assertRaises(ValueError):
            SimpleValue(256)

    def test_indefinite_containers(self) -> None:
        self.assertEqual(dumps([1, 2], indefinite=True).hex(), "9f0102ff")
        self.assertEqual(dumps({"a": 1}, indefinite=True).hex(), "bf616101ff")
        self.assertEqual(dumps(b"ab", indefinite=True).hex(), "5f426162ff")
        self.assertEqual(dumps("ab", indefinite=True).hex(), "7f626162ff")
        # 不定长形式仍可正确解码
        self.assertEqual(loads(dumps([1, 2], indefinite=True)), [1, 2])

    def test_indefinite_text_keeps_utf8_boundaries(self) -> None:
        encoded = dumps("水abc", indefinite=True, chunk_size=1)
        self.assertEqual(loads(encoded), "水abc")

    def test_canonical_and_ctap2_ordering_differ(self) -> None:
        obj = {1000: 1, True: 2}
        # RFC 7049：长度优先 → true(1B) 排在 1000(3B) 之前
        self.assertEqual(dumps(obj, canonical=True).hex(), "a2f5021903e801")
        # RFC 8949：纯字节字典序 → 0x19 < 0xf5 → 1000 在前
        self.assertEqual(dumps(obj, ctap2=True).hex(), "a21903e801f502")

    def test_canonical_rejects_indefinite(self) -> None:
        with self.assertRaises(CBOREncodeError):
            dumps([1], canonical=True, indefinite=True)

    def test_unsupported_type(self) -> None:
        with self.assertRaises(CBOREncodeError):
            dumps(object())

    def test_tag_number_range(self) -> None:
        with self.assertRaises(ValueError):
            Tag(-1, 1)


# ==========================================================================
# 诊断表示法
# ==========================================================================


class TestDiagnostic(unittest.TestCase):
    def test_dump_basic(self) -> None:
        self.assertEqual(to_diagnostic(0), "0")
        self.assertEqual(to_diagnostic(-1), "-1")
        self.assertEqual(to_diagnostic(1.5), "1.5")
        self.assertEqual(to_diagnostic(True), "true")
        self.assertEqual(to_diagnostic(None), "null")
        self.assertEqual(to_diagnostic(UNDEFINED), "undefined")
        self.assertEqual(to_diagnostic(b"\x01\x02"), "h'0102'")
        self.assertEqual(to_diagnostic("a"), '"a"')
        self.assertEqual(to_diagnostic([1, 2]), "[1, 2]")
        self.assertEqual(to_diagnostic({1: 2}), "{1: 2}")
        self.assertEqual(to_diagnostic(Tag(1, 0)), "1(0)")
        self.assertEqual(to_diagnostic(SimpleValue(42)), "simple(42)")

    def test_parse_basic(self) -> None:
        self.assertEqual(parse_diagnostic("0"), 0)
        self.assertEqual(parse_diagnostic("-1"), -1)
        self.assertEqual(parse_diagnostic("1.5"), 1.5)
        self.assertEqual(parse_diagnostic("true"), True)
        self.assertEqual(parse_diagnostic("null"), None)
        self.assertEqual(parse_diagnostic("undefined"), UNDEFINED)
        self.assertEqual(parse_diagnostic("h'0102'"), b"\x01\x02")
        self.assertEqual(parse_diagnostic("b64'AQI='"), b"\x01\x02")
        self.assertEqual(parse_diagnostic("[1, 2]"), [1, 2])
        self.assertEqual(parse_diagnostic('{"a": 1}'), {"a": 1})
        self.assertEqual(parse_diagnostic("1(1363896240)"), Tag(1, 1363896240))
        self.assertEqual(parse_diagnostic("simple(42)"), SimpleValue(42))
        self.assertEqual(parse_diagnostic("Infinity"), math.inf)
        self.assertEqual(parse_diagnostic("-Infinity"), -math.inf)
        self.assertTrue(math.isnan(parse_diagnostic("NaN")))

    def test_comments_and_trailing_commas(self) -> None:
        text = "[1, 2, 3,] # 尾随逗号与注释\n"
        self.assertEqual(parse_diagnostic(text), [1, 2, 3])

    def test_hex_float_literals(self) -> None:
        self.assertEqual(parse_diagnostic("0x1.8p+1"), 3.0)
        self.assertEqual(parse_diagnostic("0x10"), 16)

    def test_escapes(self) -> None:
        self.assertEqual(parse_diagnostic(r'"a\"b\\c\n"'), 'a"b\\c\n')
        self.assertEqual(parse_diagnostic(r'"水"'), "水")

    def test_roundtrip_all_vectors(self) -> None:
        for hex_text, diag in VECTORS:
            with self.subTest(hex=hex_text):
                value = loads(hx(hex_text))
                self.assertTrue(_same(parse_diagnostic(to_diagnostic(value)), value))

    def test_errors(self) -> None:
        with self.assertRaises(DiagnosticError):
            parse_diagnostic("[1, 2")
        with self.assertRaises(DiagnosticError):
            parse_diagnostic("nope")
        with self.assertRaises(DiagnosticError):
            parse_diagnostic("'abc'")

    def test_pretty_indent(self) -> None:
        text = to_diagnostic({"a": [1, 2]}, indent=2)
        self.assertIn("\n", text)
        self.assertTrue(_same(parse_diagnostic(text), {"a": [1, 2]}))

    def test_truncation(self) -> None:
        self.assertIn("…", to_diagnostic(b"\x00" * 64, max_bytes=8))
        self.assertIn("…", to_diagnostic("x" * 64, max_text=8))


# ==========================================================================
# JSON 桥接
# ==========================================================================


class TestJsonBridge(unittest.TestCase):
    CASES = [
        0,
        -1,
        1.5,
        True,
        False,
        None,
        UNDEFINED,
        "",
        "水",
        b"\x00\x01\xff",
        [],
        [1, [2, 3]],
        {"a": 1, "b": [1, 2]},
        Tag(0, "2013-03-21T20:04:00Z"),
        Tag(23, b"\x01\x02\x03\x04"),
        SimpleValue(42),
        float("nan"),
        float("inf"),
        float("-inf"),
        {1: "int key", 2: [3, 4]},
    ]

    def test_lossless_roundtrip(self) -> None:
        for value in self.CASES:
            with self.subTest(value=repr(value)):
                text = to_json_text(value)
                restored = from_json_text(text)
                self.assertTrue(
                    _same(restored, value),
                    "往返失败: %r -> %s -> %r" % (value, text, restored),
                )

    def test_marker_shapes(self) -> None:
        self.assertEqual(json.loads(to_json_text(b"\x01")), {"$bytes": base64.b64encode(b"\x01").decode()})
        self.assertEqual(json.loads(to_json_text(Tag(1, 2))), {"$tag": 1, "$value": 2})
        self.assertEqual(json.loads(to_json_text(UNDEFINED)), {"$undefined": True})
        self.assertEqual(json.loads(to_json_text(float("nan"))), {"$float": "NaN"})
        self.assertEqual(json.loads(to_json_text(SimpleValue(7))), {"$simple": 7})

    def test_non_string_keys_use_map_wrapper(self) -> None:
        payload = json.loads(to_json_text({1: 2}))
        self.assertEqual(payload, {"$map": [[1, 2]]})
        payload = json.loads(to_json_text({"$weird": 1}))
        self.assertEqual(payload, {"$map": [["$weird", 1]]})

    def test_reserved_key_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            from_json_text('{"$nope": 1}')
        with self.assertRaises(ValueError):
            from_json_text('{"$tag": -1, "$value": 1}')


# ==========================================================================
# 审计引擎
# ==========================================================================


class TestValidator(unittest.TestCase):
    def test_clean_canonical_input(self) -> None:
        report = validate(hx("a201020304"))
        self.assertTrue(report.ok)
        self.assertEqual(report.findings, [])
        self.assertEqual(report.counts["error"], 0)

    def test_cbf001_non_minimal_int(self) -> None:
        report = validate(hx("1801"))
        self.assertFalse(report.ok)
        self.assertIn("CBF001", [f.code for f in report.findings])

    def test_cbf002_float_width(self) -> None:
        report = validate(hx("fb3ff0000000000000"))
        self.assertIn("CBF002", [f.code for f in report.findings])

    def test_cbf003_nan(self) -> None:
        report = validate(hx("fb7ff8000000000000"))
        codes = [f.code for f in report.findings]
        self.assertIn("CBF003", codes)
        self.assertNotIn("CBF002", codes)

    def test_cbf004_indefinite(self) -> None:
        report = validate(hx("9f01ff"))
        self.assertIn("CBF004", [f.code for f in report.findings])

    def test_cbf005_duplicate_key(self) -> None:
        report = validate(hx("a201020102"))
        self.assertIn("CBF005", [f.code for f in report.findings])

    def test_cbf006_key_order(self) -> None:
        report = validate(hx("a202010102"))
        self.assertIn("CBF006", [f.code for f in report.findings])
        # 关闭顺序检查后不应再报
        report = validate(hx("a202010102"), determinism="off")
        self.assertNotIn("CBF006", [f.code for f in report.findings])

    def test_cbf007_unhashable_key(self) -> None:
        report = validate(hx("a18001"))
        self.assertIn("CBF007", [f.code for f in report.findings])

    def test_cbf008_deep_nesting(self) -> None:
        report = validate(b"\x81" * 40 + b"\x01")
        self.assertIn("CBF008", [f.code for f in report.findings])

    def test_cbf009_fragmented_string(self) -> None:
        report = validate(hx("5f41014102ff"))
        self.assertIn("CBF009", [f.code for f in report.findings])

    def test_cbf010_unknown_tag(self) -> None:
        report = validate(hx("c601"))
        self.assertIn("CBF010", [f.code for f in report.findings])
        # 已收录标签不应提示
        report = validate(hx("c101"))
        self.assertNotIn("CBF010", [f.code for f in report.findings])

    def test_safe_validate_reports_decode_failure(self) -> None:
        report = safe_validate(hx("1c"))
        self.assertFalse(report.ok)
        self.assertEqual(report.findings[0].code, "CBF000")

    def test_canonical_output_is_clean(self) -> None:
        messy = loads(hx("bf61610161629f0203ffff"))
        report = validate(dumps(messy, canonical=True))
        self.assertTrue(report.ok, "规范编码后不应再有问题: %s" % report.to_text())

    def test_report_json_is_serialisable(self) -> None:
        report = validate(hx("1801"))
        payload = json.loads(json.dumps(report.to_dict()))
        self.assertEqual(payload["counts"]["error"], 1)

    def test_bad_determinism(self) -> None:
        with self.assertRaises(ValueError):
            validate(hx("00"), determinism="nope")


# ==========================================================================
# 命令行
# ==========================================================================


class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()

    def _out(self, name: str = "out.bin") -> str:
        return os.path.join(self.tmp, name)

    def test_encode_hex(self) -> None:
        target = self._out()
        self.assertEqual(main(["encode", '{"a": 1}', "-o", target]), 0)
        self.assertEqual(_readf(target).strip(), "a1616101")

    def test_encode_base64(self) -> None:
        target = self._out()
        self.assertEqual(main(["encode", "1", "-f", "base64", "-o", target]), 0)
        self.assertEqual(_readf(target).strip(), base64.b64encode(b"\x01").decode())

    def test_decode_json_and_diag(self) -> None:
        target = self._out()
        self.assertEqual(main(["decode", "a1616101", "-o", target]), 0)
        self.assertEqual(json.loads(_readf(target)), {"a": 1})
        target2 = self._out("d.txt")
        self.assertEqual(main(["decode", "a1616101", "-f", "diag", "-o", target2]), 0)
        self.assertEqual(_readf(target2).strip(), '{"a": 1}')

    def test_roundtrip_through_cli(self) -> None:
        cbor = self._out("a.cbor")
        back = self._out("b.json")
        self.assertEqual(main(["encode", '{"x": [1, 2, 3]}', "-f", "bin", "-o", cbor]), 0)
        self.assertEqual(
            main(["decode", cbor, "--in-format", "bin", "-o", back]), 0
        )
        self.assertEqual(
            json.loads(_readf(back)), {"x": [1, 2, 3]}
        )

    def test_inspect(self) -> None:
        target = self._out("i.txt")
        self.assertEqual(main(["inspect", "a26161016162820203", "-o", target]), 0)
        text = _readf(target)
        self.assertIn("map(2)", text)
        self.assertIn("hex dump", text)

    def test_validate_exit_codes(self) -> None:
        self.assertEqual(main(["validate", "a201020304", "-o", self._out()]), 0)
        self.assertEqual(main(["validate", "1801", "-o", self._out()]), 1)
        # --strict：连 info 级问题也视为失败
        self.assertEqual(
            main(["validate", "c601", "--strict", "-o", self._out()]), 1
        )
        self.assertEqual(main(["validate", "c601", "-o", self._out()]), 0)

    def test_validate_json_output(self) -> None:
        target = self._out("v.json")
        self.assertEqual(main(["validate", "1801", "-f", "json", "-o", target]), 1)
        payload = json.loads(_readf(target))
        self.assertEqual(payload["findings"][0]["code"], "CBF001")

    def test_canonical_rewrites_indefinite(self) -> None:
        target = self._out()
        self.assertEqual(main(["canonical", "bf61610161629f0203ffff", "-o", target]), 0)
        self.assertEqual(_readf(target).strip(), "a26161016162820203")

    def test_selftest(self) -> None:
        self.assertEqual(main(["selftest", "-o", self._out("s.txt")]), 0)

    def test_decode_error_exit_code(self) -> None:
        self.assertEqual(main(["decode", "1c"]), 2)

    def test_stdin_input(self) -> None:
        target = self._out()
        import io

        original = sys.stdin
        sys.stdin = io.TextIOWrapper(io.BytesIO(b"a1616101"))
        try:
            code = main(["decode", "-o", target])
        finally:
            sys.stdin = original
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(_readf(target)), {"a": 1})


# ==========================================================================
# 包级 API
# ==========================================================================


class TestPackageApi(unittest.TestCase):
    def test_public_api_surface(self) -> None:
        for name in (
            "dumps",
            "loads",
            "parse",
            "to_diagnostic",
            "parse_diagnostic",
            "to_json_text",
            "from_json_text",
            "validate",
            "safe_validate",
            "Tag",
            "SimpleValue",
            "UNDEFINED",
            "CBORDecodeError",
        ):
            self.assertTrue(hasattr(cborforge, name), "缺少公开 API: %s" % name)

    def test_version(self) -> None:
        self.assertRegex(cborforge.__version__, r"^\d+\.\d+\.\d+$")

    def test_parse_tree_offsets(self) -> None:
        node = parse(hx("a26161016162820203"))
        self.assertEqual(node.offset, 0)
        self.assertEqual(node.end, 9)
        self.assertEqual(len(node.entries), 2)
        key_node, value_node = node.entries[1]
        self.assertEqual(key_node.offset, 4)
        self.assertEqual(value_node.mt, 4)

    def test_break_is_not_exported_value(self) -> None:
        self.assertIsInstance(Break(), Break)


if __name__ == "__main__":
    unittest.main(verbosity=2)
