<div align="center">

# 🔧 CBORForge

**Zero-dependency · offline-first CBOR (RFC 8949) toolkit: codec, diagnostic notation & canonical-encoding audit**

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#-features)
[![RFC](https://img.shields.io/badge/RFC-8949-orange.svg)](https://www.rfc-editor.org/rfc/rfc8949)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · **English**

</div>

---

## 🎉 Overview

**CBORForge** is a from-scratch CBOR (Concise Binary Object Representation) toolkit implementing **RFC 8949**, with first-class support for both **RFC 7049 canonical form** and the **RFC 8949 §4.2.1 core deterministic encoding** used by CTAP2 / WebAuthn.

### What problems does it solve?

CBOR is everywhere — IoT messaging, WebAuthn / FIDO2 signatures, COSE, blockchains, embedded links — yet developers keep hitting the same three walls:

| 😖 Pain | ❌ Today | ✅ With CBORForge |
|---|---|---|
| **Binary is unreadable** | You capture `a26161016162820203` and start guessing | `inspect` prints a structural tree with **byte offsets** plus a hex dump |
| **Signature verification fails** | Same logical data, different bytes, different hash | `validate` pinpoints duplicate keys, non-minimal encodings and key-order violations **by offset** |
| **Dependencies won't install** | Air-gapped / embedded targets have no `pip` | **Zero third-party dependencies**, pure stdlib, copy-and-run, fully offline |

### What makes it different

- 🧩 **Genuinely zero-dependency** — only `struct`, `base64`, `json`, `re`, `math` and friends. Nothing to install at runtime, so it vendors cleanly into any project.
- 🛡️ **Strict well-formedness** — implements the full RFC 8949 Appendix C checks; 17 distinct classes of malformed input are rejected rather than "best-guess" parsed.
- 🔍 **Deterministic-encoding audit** — 10 rules (`CBF001`–`CBF010`) covering non-minimal lengths, float width, NaN preferred serialization, indefinite items, duplicate keys, key ordering, unhashable keys and deep nesting. Every finding carries an **offset, a data path and a fix suggestion**.
- 🔁 **Lossless bridges** — both the diagnostic notation (RFC 8949 §8) and the JSON bridge round-trip without losing byte strings, tags, simple values, `undefined` or NaN.
- 🚪 **CI-ready** — `validate` exits `1` on any error-level finding, so it drops straight into a pipeline as a gate.
- 🧪 **Standard vectors built in** — 81 vectors from RFC 8949 Appendix A, 226 assertions, one command: `cborforge selftest`.

> Inspired by the RFC 8949 / RFC 7049 specifications and the CTAP2 canonical encoding rules. 100% independently implemented — no existing CBOR library source was reused.

---

## ✨ Features

- 🧠 **Complete decoder** — major types 0–7, including indefinite-length byte/text strings, arrays and maps, tags, half/single/double precision floats, simple values and `undefined`.
- 📦 **Multi-strategy encoder** — shortest-form by default; `--canonical` for RFC 7049; `--ctap2` for RFC 8949 core deterministic; four float-width policies (`auto` / `16` / `32` / `64`).
- 🧾 **Diagnostic notation** — bidirectional RFC 8949 §8 support: `h'..'` / `b64'..'` byte strings, `0x1.8p+1` hex floats, `simple(n)`, `Infinity` / `NaN`. Plus `#` comments and trailing commas.
- 🔄 **Lossless JSON bridge** — `$bytes`, `$tag`, `$simple`, `$undefined`, `$float` and `$map` markers preserve everything JSON cannot express natively.
- 🔎 **Structure visualisation** — `inspect` renders a tree with offset, length, encoded header and value preview per node, plus a hex dump.
- 🛡️ **Hardened** — 256-level nesting cap by default and pre-flight length checks, so hostile input cannot exhaust the stack or memory.
- 🐍 **Library *and* CLI** — `import cborforge`, or run `python -m cborforge`, or install and use the `cborforge` command.
- 📴 **Fully offline** — no network calls, no telemetry, no config files, no environment variables.

---

## 🚀 Quick start

### Requirements

| Item | Requirement |
|---|---|
| Python | **3.8+** (3.11+ recommended) |
| OS | Windows / macOS / Linux |
| Third-party deps | **none** |
| Network | **not required** |

### Option 1 — run it straight from the checkout

```bash
git clone https://github.com/gitstq/CBORForge.git
cd CBORForge

# Encode: JSON -> CBOR (hex)
python -m cborforge encode '{"user": "ada", "id": 7, "tags": ["a", "b"], "score": 1.5}'
# a464757365726361646162696407647461677382616161626573636f7265f93e00

# Decode: CBOR -> JSON
python -m cborforge decode a464757365726361646162696407647461677382616161626573636f7265f93e00
```

### Option 2 — install as a CLI

```bash
pip install .          # from a source checkout
# or
pip install -e .       # editable, for hacking on it

cborforge --version
# cborforge 1.0.0
```

### Option 3 — use it as a library

```python
import cborforge

raw = cborforge.dumps({"user": "ada", "score": 1.5})
print(raw.hex())                       # a26475736572636164616573636f7265f93e00
print(cborforge.loads(raw))            # {'user': 'ada', 'score': 1.5}
print(cborforge.to_diagnostic(cborforge.loads(raw)))
# {"user": "ada", "score": 1.5}
```

### The whole loop in 30 seconds

```bash
# 1) A "messy" CBOR item: indefinite-length map with keys out of order ("b" before "a")
python -m cborforge validate bf61621901f4616101ff
# -> CBF004 indefinite-length item / CBF006 map keys out of order  (exit 1)

# 2) Normalise it
python -m cborforge canonical bf61621901f4616101ff
# a261610161621901f4

# 3) Audit again: clean
python -m cborforge validate a261610161621901f4
# -> Result: PASS (0 errors / 0 warnings / 0 hints)  (exit 0)

# 4) Run the standard test vectors
python -m cborforge selftest
# ✅ All checks passed: decoding, diagnostic round-trip and byte-level re-encoding agree.
```

---

## 📖 Usage guide

### Command overview

```
cborforge [--version] <command> [options]

  encode     Encode JSON / diagnostic notation into CBOR
  decode     Decode CBOR into JSON / diagnostic notation
  inspect    Show an offset-annotated structure tree with hex dump
  validate   Canonical / deterministic encoding audit
  canonical  Re-encode into canonical / deterministic form
  selftest   Run the built-in RFC 8949 test vectors
```

> 💡 **Input tip:** the positional argument is first tried as a **file path**; if no such file exists it is treated as a **literal value**.
> So both `cborforge decode a1616101` (inline hex) and `cborforge decode data.cbor` (file) work.
> Use `-` or omit the argument to read from stdin, which makes piping easy.

#### Common options

| Option | Meaning | Default |
|---|---|---|
| `--in-format` | How to interpret input: `auto` / `hex` / `base64` / `bin` | `auto` |
| `-o, --output` | Output file, `-` for stdout | `-` |
| `-f, --format` | Output representation (varies per subcommand) | see below |

---

### `encode` — into CBOR

```bash
# From JSON (auto-detected; --from diag forces diagnostic notation)
cborforge encode '{"a": 1}'                      # -> a1616101
cborforge encode '{"a": 1}' -f base64            # -> oWGBAQ==
cborforge encode '{"a": 1}' -f bin -o data.cbor  # -> write raw bytes

# From diagnostic notation (can express byte strings, tags and simple values)
cborforge encode --from diag '{1: 2, "x": h'6161', "z": simple(42)}'
# -> a301026178426161617af82a
```

| Option | Meaning | Default |
|---|---|---|
| `--from` | `auto` / `json` / `diag` | `auto` |
| `-f` | `hex` / `base64` / `bin` | `hex` |
| `--canonical` | RFC 7049 canonical form | off |
| `--ctap2` | RFC 8949 core deterministic encoding | off |
| `--float-mode` | `auto` / `16` / `32` / `64` | `auto` |
| `--indefinite` | Emit indefinite-length constructs (interop testing) | off |
| `--chunk-size` | Chunk size in bytes for indefinite strings | `8` |

---

### `decode` — out of CBOR

```bash
cborforge decode a464757365726361646162696407647461677382616161626573636f7265f93e00
```

```json
{
  "user": "ada",
  "id": 7,
  "tags": [
    "a",
    "b"
  ],
  "score": 1.5
}
```

```bash
# Diagnostic notation (compact single line by default)
cborforge decode a464757365726361646162696407647461677382616161626573636f7265f93e00 -f diag
# {"user": "ada", "id": 7, "tags": ["a", "b"], "score": 1.5}

# Ask for indentation explicitly
cborforge decode a3616101616283010203 -f diag --indent 2
```

| Option | Meaning | Default |
|---|---|---|
| `-f` | `json` / `diag` | `json` |
| `--indent` | Indent width; JSON defaults to `2`, diagnostic stays compact | `2` |
| `--hex-floats` | Use hex float literals in diagnostic output | off |
| `--bignum` | Fold tag 2/3 bignums into Python `int` | off |

---

### `inspect` — structure visualisation

```bash
cborforge inspect a26161016162820203
```

```
🔍 CBORForge inspect — 9 bytes
────────────────────────────────────────────────────────────────────────────────────────
Path                                 Type             Offset    Length  Value
────────────────────────────────────────────────────────────────────────────────────────
$                                  map(2)           @0        9
  K .a                             text(1)          @1        2      "a"
  V .a                             uint             @3        1      1
  K .b                             text(1)          @4        2      "b"
  V .b                             array(2)         @6        3
    [0]                            uint             @7        1      2
    [1]                            uint             @8        1      3
────────────────────────────────────────────────────────────────────────────────────────
Hex dump:
00000000  a2 61 61 01 61 62 82 02 03                       |.aa.ab...|
```

> `K` / `V` mark a map's key and value; `∞` marks an indefinite-length item.

| Option | Meaning | Default |
|---|---|---|
| `--max-bytes` | Max byte-string preview length | `24` |
| `--max-text` | Max text-string preview length | `40` |
| `--dump-limit` | Max bytes in the hex dump | `256` |

---

### `validate` — canonical audit

```bash
cborforge validate bf61621901f4616101ff
```

```
CBORForge Audit Report
────────────────────────────────────────────────────────────
  Size          : 10 bytes
  Item count    : 5
  Max depth     : 1
  Determinism   : RFC 8949 §4.2.1 core deterministic (bytewise lexicographic)
  Result        : FAIL (2 errors / 0 warnings / 0 hints)
────────────────────────────────────────────────────────────
[CBF004] error   Indefinite-length data item
        offset 0 (length 10)  path $
        map uses indefinite-length encoding, so no deterministic byte sequence exists
        Hint: rewrite as a definite-length item
[CBF006] error   Map keys are not in deterministic order
        offset 6 (length 2)  path $
        key 'a' sorts before 'b', violating RFC8949
        Hint: sort keys by their deterministic encodings
```

```bash
# JSON output for pipeline consumption
cborforge validate 1801 -f json

# Use it as a CI gate
cborforge validate payload.cbor --in-format bin || exit 1
```

| Option | Meaning | Default |
|---|---|---|
| `--determinism` | `rfc8949` / `rfc7049` / `off` | `rfc8949` |
| `--depth-threshold` | Depth that triggers CBF008 | `32` |
| `--strict` | Fail on any finding, at any severity | off |
| `-f` | `text` / `json` | `text` |

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | No error-level findings (with `--strict`: no findings at all) |
| `1` | Error-level findings present (with `--strict`: any finding) |
| `2` | Usage / IO / decode or encode error |

#### Rule table

| Code | Severity | Meaning | Fix |
|---|---|---|---|
| `CBF000` | error | Data is not well-formed per RFC 8949 | Check for a truncated or corrupt byte stream |
| `CBF001` | error | Argument/length is not minimally encoded | Use `ai<24` / `24` / `25` / `26` / `27` |
| `CBF002` | error | Float is wider than needed to round-trip | Downgrade to half/single per §4.2.2 |
| `CBF003` | error | NaN is not the preferred serialization | Use `0xf97e00` |
| `CBF004` | error | Indefinite-length item | Rewrite as definite-length |
| `CBF005` | error | Duplicate map key | ⚠️ Can be exploited to bypass signature checks |
| `CBF006` | error | Map keys are not in deterministic order | Sort by each key's deterministic encoding |
| `CBF007` | warning | Unhashable map key | Use scalar keys |
| `CBF008` | warning | Nesting deeper than the threshold | Reduce depth to avoid stack exhaustion |
| `CBF009` | warning | Indefinite string split into multiple chunks | One chunk is materially smaller |
| `CBF010` | info | Tag number is not in the built-in registry | Confirm the tag's semantics |

---

### `canonical` — re-encode deterministically

```bash
cborforge canonical bf61621901f4616101ff --report
# Canonicalised: 10 bytes -> 9 bytes (rewritten)
# a261610161621901f4
```

`--report` prints the size delta to stderr, which is handy for watching the savings in CI.

---

### `selftest` — standard vectors

```bash
cborforge selftest
# 🧪 CBORForge selftest — RFC 8949 Appendix A test vectors
#   Vectors    : 81
#   Assertions : 226
#   Passed     : 226
#   Failed     : 0
# ✅ All checks passed: decoding, diagnostic round-trip and byte-level re-encoding agree.
```

---

### Python API

```python
import cborforge
from cborforge import Tag, SimpleValue, UNDEFINED

# ── Codec ────────────────────────────────────────────────
raw = cborforge.dumps({"a": 1, "b": [1, 2, 3]})
cborforge.loads(raw)                          # {'a': 1, 'b': [1, 2, 3]}

# Deterministic encoding
cborforge.dumps({1000: 1, True: 2}, canonical=True)   # RFC 7049: length-first
cborforge.dumps({1000: 1, True: 2}, ctap2=True)       # RFC 8949: bytewise lexicographic

# Indefinite constructs + float width policy
cborforge.dumps([1, 2], indefinite=True)              # 9f0102ff
cborforge.dumps(1.5, float_mode="64")                 # fb3ff8000000000000

# ── CBOR-only semantics ──────────────────────────────────
cborforge.dumps(Tag(0, "2013-03-21T20:04:00Z")).hex()
cborforge.dumps(SimpleValue(42)).hex()                # f82a
cborforge.dumps(UNDEFINED).hex()                      # f7
cborforge.loads(b"\xc2\x42\x01\x00", bignum=True)     # 256 (tag 2 folded into int)

# ── Diagnostic notation ──────────────────────────────────
cborforge.to_diagnostic({"a": 1}, indent=2)
cborforge.parse_diagnostic('{1: 2, "b": h'0102'} # comments supported')

# ── Lossless JSON bridge ─────────────────────────────────
cborforge.to_json_text({"k": b"\x01\x02"})
# {"k": {"$bytes": "AQI="}}
cborforge.from_json_text('{"k": {"$bytes": "AQI="}}')  # {'k': b'\x01\x02'}

# ── Audit ────────────────────────────────────────────────
report = cborforge.validate(bytes.fromhex("1801"))
report.ok          # False
report.counts      # {'error': 1, 'warning': 0, 'info': 0}
[f.code for f in report.findings]   # ['CBF001']
report.to_text()   # human-readable report
report.to_dict()   # JSON-serialisable structure

# Parse tree with offsets, for custom analysis
node = cborforge.parse(bytes.fromhex("a26161016162820203"))
node.offset, node.end, node.entries  # 0, 9, [(key_node, value_node), ...]
```

---

### Typical scenarios

**1. Pre-signature check for WebAuthn / CTAP2**

```bash
# authenticatorData must use the deterministic encoding
cborforge validate attestation.cbor --in-format bin --determinism rfc8949
cborforge canonical attestation.cbor --in-format bin --ctap2 -f bin -o fixed.cbor
```

**2. Debugging a captured IoT CBOR message**

```bash
cborforge inspect --in-format bin capture.bin | head -40
```

**3. Keeping non-canonical encodings out of the repo**

```yaml
- name: CBOR canonical check
  run: |
    for f in $(find . -name '*.cbor'); do
      cborforge validate "$f" --in-format bin || exit 1
    done
```

---

## 💡 Design notes & roadmap

### Philosophy

1. **Zero dependencies first.** Stdlib only means it vendors into anything, runs in air-gapped environments, and carries no supply-chain surface.
2. **Strict beats lenient.** The decoder rejects well-formedness errors instead of guessing. Ambiguous parses are where security bugs live — duplicate map keys being the classic case.
3. **Observability first.** Every finding carries an **offset, a length, a data path and a fix hint**, not just "not canonical".
4. **Losslessness first.** The diagnostic and JSON bridges must round-trip perfectly, even if that requires explicit `$`-prefixed markers.

### Technical choices

| Decision | Choice | Why |
|---|---|---|
| Language | Pure Python | The pragmatic route to zero dependencies; stdlib already provides `struct` (half-precision `'>e'`), `base64`, `json` |
| Float minimisation | `struct` round-trip equality | Decides whether a value survives half/single precision without pulling in NumPy |
| Parse tree | `CBORNode` built during decode | One pass feeds decoding, auditing and visualisation — no duplicated traversal or divergent logic |
| Key ordering | Both RFC 7049 and RFC 8949 | They genuinely differ on real data; mixing them breaks signatures |
| Depth limit | 256 levels + length pre-checks | Keep hostile input from exhausting the stack or memory |

### Roadmap

- 🔜 **v1.1** — auto-rewrite mode for the RFC 8949 §4.2.2 preferred serialization; richer IANA tag interpretation.
- 🔜 **v1.2** — streaming decode and multi-item auditing for CBOR sequences (RFC 8742).
- 🔜 **v1.3** — SARIF 2.1.0 output for direct GitHub Code Scanning integration.
- 🔜 **v2.0** — optional tag-semantics layer (dates, URIs, bignums, decimal fractions).

### How to help

- Add real-world malformed samples and regression cases.
- Expand the IANA tag registry subset.
- Translate the README into more languages (Japanese, Korean, Spanish).

---

## 📦 Packaging & deployment

CBORForge is a **library / CLI project** — there is nothing to compile, and distribution follows the standard Python packaging flow.

### One-shot build

```bash
./scripts/build.sh
```

The script runs clean → compile check → unit tests → built-in self-test → build, entirely offline. Artefacts land in `dist/`:

```
dist/cborforge-1.0.0-py3-none-any.whl
```

### Manual build

```bash
python -m build                 # requires build (PEP 517)
# or, fully offline:
python -m pip wheel --no-deps --no-build-isolation -w dist .
```

### Makefile targets

```bash
make help       # list all targets
make install    # editable install
make test       # unit tests
make selftest   # RFC 8949 vector self-test
make lint       # compileall check
make demo       # CLI demo
make build      # build distributions
make clean      # remove artefacts
```

### Deployment options

| Scenario | How |
|---|---|
| **Ship a wheel** | `./scripts/build.sh`, then `pip install cborforge-1.0.0-py3-none-any.whl` |
| **Vendor the package** | Copy `cborforge/` into your project and `import cborforge` — no install step |
| **Bundle in an app** | Drop `cborforge/` into your resources and add it with `sys.path.append()` |
| **Container image** | `COPY cborforge/ /app/cborforge/` — no `pip install` needed |
| **CLI integration** | `pip install .` then run `cborforge`; or `python -m cborforge` with no install at all |

### Compatibility

| Item | Notes |
|---|---|
| Python | 3.8 / 3.9 / 3.10 / 3.11 / 3.12 |
| OS | Windows / macOS / Linux (pure Python, no platform-specific code) |
| Architecture | x86_64, ARM64 and everything else |
| Network | Not required at all |

---

## 🤝 Contributing

- Commit messages follow the **Angular convention**: `feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`.
- Before opening a PR, make sure `make test` and `make selftest` pass, and add tests for the behaviour you changed.
- **Pull requests that add a third-party runtime dependency will not be merged** — zero dependencies is the project's first principle.
- When adding an audit rule, update the `RULES` table in `cborforge/validator.py` and the rule tables in all three READMEs.

Full details in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 License

Released under the **MIT License** — see [LICENSE](LICENSE).

- ✅ Commercial use, modification, distribution, private deployment and relicensing are all permitted.
- ✅ Usable inside closed-source products.
- ⚠️ The only requirement: keep the copyright and licence notice in copies or substantial portions.
- ❗ The software is provided "as is", without warranty of any kind.

> This is a 100% independent implementation; no existing CBOR library source was copied. The RFC 8949 / RFC 7049 specifications it follows are public standard documents.

---

<div align="center">

**CBORForge** — every byte explained, verified and under control. 🛠️

</div>
