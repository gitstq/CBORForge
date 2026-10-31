<div align="center">

# 🔧 CBORForge

**零依赖 · 离线优先的 CBOR（RFC 8949）编解码、诊断表示法与规范性审计工具箱**

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#-核心特性)
[![RFC](https://img.shields.io/badge/RFC-8949-orange.svg)](https://www.rfc-editor.org/rfc/rfc8949)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**简体中文** · [繁體中文](README.zh-TW.md) · [English](README.en.md)

</div>

---

## 🎉 项目介绍

**CBORForge** 是一个完全自研的 CBOR（Concise Binary Object Representation）工具箱，严格实现 **RFC 8949**，并提供 **RFC 7049 规范形式** 与 **RFC 8949 §4.2.1 核心确定性编码（CTAP2 / WebAuthn）** 两种确定性编码策略。

### 它解决什么痛点？

CBOR 在物联网、WebAuthn / FIDO2 签名、COSE、区块链与嵌入式通信中被广泛使用，但开发者常常面临三个真实困境：

| 😖 痛点 | ❌ 现状 | ✅ CBORForge |
|---|---|---|
| **看不懂二进制** | 抓包拿到 `a26161016162820203`，只能靠猜 | `inspect` 直接给出带**偏移量**的结构树 + 十六进制转储 |
| **签名校验失败** | 同一份逻辑数据，因为编码差异导致哈希对不上 | `validate` 精确定位重复键、非最短编码、键序错误，并给出偏移量 |
| **环境装不上依赖** | 内网 / 嵌入式环境无法 `pip install` | **零第三方依赖**，纯标准库，单目录即可运行，完全离线 |

### 自研差异化亮点

- 🧩 **真正的零依赖**：仅用 `struct` / `base64` / `json` / `re` / `math` 等标准库，运行期零第三方包，可整体拷贝进任何项目。
- 🛡️ **严格良构性校验**：完整实现 RFC 8949 附录 C 的良构性检查（保留附加信息、不定长误用、非法 UTF-8、`break` 错位等 17 类畸形输入全部拒绝）。
- 🔍 **确定性编码审计**：10 条规则（CBF001–CBF010）覆盖非最短编码、浮点宽度、NaN 首选序列化、不定长、重复键、键序、不可哈希键、深层嵌套等，输出**偏移量 + 数据路径 + 修复建议**。
- 🔁 **无损双向桥接**：诊断表示法（RFC 8949 §8）与 JSON 桥接层均保证往返无损，字节串 / 标签 / 简单值 / `undefined` / NaN 都能完整保留。
- 🚪 **CI 就绪**：`validate` 发现 error 级问题即以退出码 `1` 结束，可直接作为流水线门禁。
- 🧪 **自带标准测试向量**：内置 RFC 8949 附录 A 共 **81 条**向量、**226 项**检查，`cborforge selftest` 一键验证。

> 灵感来源：RFC 8949 / RFC 7049 标准文本与 WebAuthn CTAP2 规范编码要求；实现为 100% 独立自研，未复用任何既有 CBOR 库的源码。

---

## ✨ 核心特性

- 🧠 **完整解码器** — major type 0–7 全覆盖，含不定长字节串 / 文本串 / 数组 / 映射、标签、半精度 / 单精度 / 双精度浮点、简单值、`undefined`。
- 📦 **多策略编码器** — 默认最短编码；`--canonical` 走 RFC 7049；`--ctap2` 走 RFC 8949 核心确定性编码；支持 `auto / 16 / 32 / 64` 四种浮点宽度策略。
- 🧾 **诊断表示法** — RFC 8949 §8 双向支持，含 `h'..'` / `b64'..'` 字节串、`0x1.8p+1` 十六进制浮点、`simple(n)`、`Infinity` / `NaN`，额外支持 `#` 注释与尾随逗号。
- 🔄 **JSON 无损桥接** — 用 `$bytes` / `$tag` / `$simple` / `$undefined` / `$float` / `$map` 标记保留 JSON 缺失的 CBOR 语义，往返不丢信息。
- 🔎 **结构可视化** — `inspect` 输出层级结构树，每个节点标注偏移量、长度、编码头部与取值预览，并附十六进制转储。
- 🛡️ **安全加固** — 默认 256 层嵌套深度上限、超大长度声明预检，抵御恶意构造输入导致的栈溢出与内存耗尽。
- 🐍 **Python API + CLI 双形态** — 既可作为库 `import cborforge`，也可 `python -m cborforge` 或安装后的 `cborforge` 命令使用。
- 📴 **完全离线** — 无网络请求、无遥测、无配置文件、无环境变量依赖。

---

## 🚀 快速开始

### 环境要求

| 项目 | 要求 |
|---|---|
| Python | **3.8 及以上**（推荐 3.11+） |
| 操作系统 | Windows / macOS / Linux 全平台 |
| 第三方依赖 | **无** |
| 网络 | **不需要** |

### 方式一：免安装，直接运行（推荐先试这个）

```bash
git clone https://github.com/gitstq/CBORForge.git
cd CBORForge

# 编码：JSON → CBOR（十六进制）
python -m cborforge encode '{"user": "ada", "id": 7, "tags": ["a", "b"], "score": 1.5}'
# a464757365726361646162696407647461677382616161626573636f7265f93e00

# 解码：CBOR → JSON
python -m cborforge decode a464757365726361646162696407647461677382616161626573636f7265f93e00
```

### 方式二：安装为命令行工具

```bash
pip install .          # 从源码安装（当前目录）
# 或
pip install -e .       # 可编辑模式，适合二次开发

cborforge --version
# cborforge 1.0.0
```

### 方式三：作为库引入

```python
import cborforge

raw = cborforge.dumps({"user": "ada", "score": 1.5})
print(raw.hex())                       # a26475736572636164616573636f7265f93e00
print(cborforge.loads(raw))            # {'user': 'ada', 'score': 1.5}
print(cborforge.to_diagnostic(cborforge.loads(raw)))
# {"user": "ada", "score": 1.5}
```

### 30 秒体验完整链路

```bash
# 1) 一段"不规范"的 CBOR：不定长映射 + 键序颠倒（"b" 在 "a" 前）
python -m cborforge validate bf61621901f4616101ff
# → CBF004 使用了不定长数据项 / CBF006 映射键未按确定性规则排序  (退出码 1)

# 2) 一键规范化
python -m cborforge canonical bf61621901f4616101ff
# a261610161621901f4

# 3) 再次审计：通过
python -m cborforge validate a261610161621901f4
# → 结论：通过 PASS（0 错误 / 0 警告 / 0 提示）  (退出码 0)

# 4) 运行标准测试向量自检
python -m cborforge selftest
# ✅ 全部通过：解码、诊断表示法往返与字节级重编码均一致。
```

---

## 📖 详细使用指南

### 命令行总览

```
cborforge [--version] <command> [options]

  encode     把 JSON / 诊断表示法编码为 CBOR
  decode     把 CBOR 解码为 JSON / 诊断表示法
  inspect    展示带偏移量的结构树与十六进制转储
  validate   规范性 / 确定性编码审计
  canonical  重新编码为规范 / 确定性形式
  selftest   运行内置 RFC 8949 测试向量自检
```

> 💡 **输入技巧**：位置参数优先按**文件路径**读取；若该路径不存在，则按**字面量**处理。
> 因此 `cborforge decode a1616101`（直接传十六进制）与 `cborforge decode data.cbor`（读文件）都能工作。
> 使用 `-` 或省略参数则从标准输入读取，方便管道串联。

#### 通用选项

| 选项 | 说明 | 默认值 |
|---|---|---|
| `--in-format` | 输入解释方式：`auto` / `hex` / `base64` / `bin` | `auto` |
| `-o, --output` | 输出文件，`-` 表示标准输出 | `-` |
| `-f, --format` | 输出表示（各子命令候选值不同） | 见下 |

---

### `encode` — 编码为 CBOR

```bash
# 从 JSON 编码（默认自动识别，也支持 --from diag 指定诊断表示法）
cborforge encode '{"a": 1}'                      # → a1616101
cborforge encode '{"a": 1}' -f base64            # → oWGBAQ==
cborforge encode '{"a": 1}' -f bin -o data.cbor  # → 写出二进制文件

# 从诊断表示法编码（可表达字节串 / 标签 / 简单值）
cborforge encode --from diag '{1: 2, "x": h'6161', "z": simple(42)}'
# → a301026178426161617af82a
```

| 选项 | 说明 | 默认 |
|---|---|---|
| `--from` | `auto` / `json` / `diag` | `auto` |
| `-f` | `hex` / `base64` / `bin` | `hex` |
| `--canonical` | RFC 7049 规范形式 | 关 |
| `--ctap2` | RFC 8949 核心确定性编码 | 关 |
| `--float-mode` | `auto` / `16` / `32` / `64` | `auto` |
| `--indefinite` | 使用不定长构造（用于互操作性测试） | 关 |
| `--chunk-size` | 不定长字符串分块字节数 | `8` |

---

### `decode` — 解码 CBOR

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
# 输出为诊断表示法（默认紧凑单行）
cborforge decode a464757365726361646162696407647461677382616161626573636f7265f93e00 -f diag
# {"user": "ada", "id": 7, "tags": ["a", "b"], "score": 1.5}

# 需要换行缩进时显式指定
cborforge decode a3616101616283010203 -f diag --indent 2
```

| 选项 | 说明 | 默认 |
|---|---|---|
| `-f` | `json` / `diag` | `json` |
| `--indent` | 缩进宽度；JSON 默认 `2`，诊断表示法默认紧凑 | `2` |
| `--hex-floats` | 诊断表示法使用十六进制浮点字面量 | 关 |
| `--bignum` | 把标签 2/3 大整数折叠为 Python `int` | 关 |

---

### `inspect` — 结构可视化

```bash
cborforge inspect a26161016162820203
```

```
🔍 CBORForge inspect — 9 字节
────────────────────────────────────────────────────────────────────────────────────────
路径                                 类型               偏移        长度     值
────────────────────────────────────────────────────────────────────────────────────────
$                                  map(2)           @0        9
  K .a                             text(1)          @1        2      "a"
  V .a                             uint             @3        1      1
  K .b                             text(1)          @4        2      "b"
  V .b                             array(2)         @6        3
    [0]                            uint             @7        1      2
    [1]                            uint             @8        1      3
────────────────────────────────────────────────────────────────────────────────────────
十六进制转储 / hex dump:
00000000  a2 61 61 01 61 62 82 02 03                       |.aa.ab...|
```

> `K` / `V` 表示映射的键与值；`∞` 标记表示该项为不定长编码。

| 选项 | 说明 | 默认 |
|---|---|---|
| `--max-bytes` | 字节串预览最大长度 | `24` |
| `--max-text` | 文本串预览最大长度 | `40` |
| `--dump-limit` | 十六进制转储最大字节数 | `256` |

---

### `validate` — 规范性审计

```bash
cborforge validate bf61621901f4616101ff
```

```
CBORForge 审计报告 / CBORForge Audit Report
────────────────────────────────────────────────────────────
  字节长度   : 10
  数据项数量 : 5
  最大嵌套   : 1
  确定性规则 : RFC 8949 §4.2.1 核心确定性编码（字节字典序）
  结论       : 未通过 FAIL（2 错误 / 0 警告 / 0 提示）
────────────────────────────────────────────────────────────
[CBF004] error   使用了不定长数据项
        偏移 0 (长度 10)  路径 $
        map 使用了不定长编码，无法得到确定性字节序列
        建议: 改写为定长形式以获得确定性编码
[CBF006] error   映射键未按确定性规则排序
        偏移 6 (长度 2)  路径 $
        键 'a' 排序在 'b' 之前，违反 RFC8949
        建议: 按键的确定性编码排序（RFC 8949 为纯字节字典序）
```

```bash
# 输出 JSON，便于接入流水线
cborforge validate 1801 -f json

# 作为 CI 门禁：有问题即失败
cborforge validate payload.cbor --in-format bin || exit 1
```

| 选项 | 说明 | 默认 |
|---|---|---|
| `--determinism` | `rfc8949` / `rfc7049` / `off` | `rfc8949` |
| `--depth-threshold` | 触发 CBF008 的嵌套深度阈值 | `32` |
| `--strict` | 存在任何级别问题即返回非零 | 关 |
| `-f` | `text` / `json` | `text` |

**退出码**

| 码 | 含义 |
|---|---|
| `0` | 未发现 error 级问题（`--strict` 时为无任何问题） |
| `1` | 发现 error 级问题（`--strict` 时为发现任何问题） |
| `2` | 用法 / IO / 解码或编码错误 |

#### 审计规则表

| 编码 | 级别 | 含义 | 修复建议 |
|---|---|---|---|
| `CBF000` | error | 数据不符合 RFC 8949 良构性要求 | 检查是否为截断 / 损坏的字节流 |
| `CBF001` | error | 参数 / 长度未使用最短编码 | 改用 `ai<24` / `24` / `25` / `26` / `27` |
| `CBF002` | error | 浮点未使用最短可无损还原宽度 | 按 §4.2.2 降级为半精度 / 单精度 |
| `CBF003` | error | NaN 未使用首选序列化 | 统一为 `0xf97e00` |
| `CBF004` | error | 使用了不定长数据项 | 改写为定长 |
| `CBF005` | error | 映射存在重复键 | ⚠️ 签名场景下可被用于绕过校验 |
| `CBF006` | error | 映射键未按确定性规则排序 | 按键的确定性编码排序 |
| `CBF007` | warning | 映射键不可哈希 | 改用标量键 |
| `CBF008` | warning | 嵌套深度超过阈值 | 降低层级，避免栈溢出 |
| `CBF009` | warning | 不定长字符串被拆为多个分块 | 合并为单分块可显著减小体积 |
| `CBF010` | info | 使用了未收录的标签号 | 确认标签号语义 |

---

### `canonical` — 规范化重编码

```bash
cborforge canonical bf61621901f4616101ff --report
# 规范化: 10 字节 -> 9 字节 (已重写)
# a261610161621901f4
```

`--report` 会向标准错误输出体积对比，方便在流水线中观察规范化收益。

---

### `selftest` — 标准向量自检

```bash
cborforge selftest
# 🧪 CBORForge selftest — RFC 8949 附录 A 测试向量
#   向量总数 : 81
#   检查项   : 226
#   通过     : 226
#   失败     : 0
# ✅ 全部通过：解码、诊断表示法往返与字节级重编码均一致。
```

---

### Python API

```python
import cborforge
from cborforge import Tag, SimpleValue, UNDEFINED

# ── 编解码 ───────────────────────────────────────────────
raw = cborforge.dumps({"a": 1, "b": [1, 2, 3]})
cborforge.loads(raw)                          # {'a': 1, 'b': [1, 2, 3]}

# 确定性编码
cborforge.dumps({1000: 1, True: 2}, canonical=True)   # RFC 7049：长度优先
cborforge.dumps({1000: 1, True: 2}, ctap2=True)       # RFC 8949：纯字节字典序

# 不定长构造 + 浮点宽度策略
cborforge.dumps([1, 2], indefinite=True)              # 9f0102ff
cborforge.dumps(1.5, float_mode="64")                 # fb3ff8000000000000

# ── CBOR 专属语义 ────────────────────────────────────────
cborforge.dumps(Tag(0, "2013-03-21T20:04:00Z")).hex()
cborforge.dumps(SimpleValue(42)).hex()                # f82a
cborforge.dumps(UNDEFINED).hex()                      # f7
cborforge.loads(b"\xc2\x42\x01\x00", bignum=True)     # 256（标签 2 折叠为 int）

# ── 诊断表示法 ───────────────────────────────────────────
cborforge.to_diagnostic({"a": 1}, indent=2)
cborforge.parse_diagnostic('{1: 2, "b": h'0102'} # 支持注释')

# ── JSON 无损桥接 ────────────────────────────────────────
cborforge.to_json_text({"k": b"\x01\x02"})
# {"k": {"$bytes": "AQI="}}
cborforge.from_json_text('{"k": {"$bytes": "AQI="}}')  # {'k': b'\x01\x02'}

# ── 审计 ─────────────────────────────────────────────────
report = cborforge.validate(bytes.fromhex("1801"))
report.ok          # False
report.counts      # {'error': 1, 'warning': 0, 'info': 0}
[f.code for f in report.findings]   # ['CBF001']
report.to_text()   # 人类可读报告
report.to_dict()   # 可 JSON 序列化的结构

# 解析树（带偏移量，可自行做二次分析）
node = cborforge.parse(bytes.fromhex("a26161016162820203"))
node.offset, node.end, node.entries  # 0, 9, [(key_node, value_node), ...]
```

---

### 典型使用场景

**场景一：WebAuthn / CTAP2 签名前的编码体检**

```bash
# 注册响应中的 authenticatorData 必须采用确定性编码
cborforge validate attestation.cbor --in-format bin --determinism rfc8949
cborforge canonical attestation.cbor --in-format bin --ctap2 -f bin -o fixed.cbor
```

**场景二：抓包排查 IoT 设备的 CBOR 报文**

```bash
cborforge inspect --in-format bin capture.bin | head -40
```

**场景三：CI 中防止不规范编码合入**

```yaml
- name: CBOR canonical check
  run: |
    for f in $(find . -name '*.cbor'); do
      cborforge validate "$f" --in-format bin || exit 1
    done
```

---

## 💡 设计思路与迭代规划

### 设计哲学

1. **零依赖优先** — 只依赖标准库，意味着它可以被 vendored 进任何项目、跑在任何受限环境里；也意味着没有供应链攻击面。
2. **严格优于宽容** — 解码器对良构性错误一律拒绝，而不是"尽力猜测"。模糊的解析结果是安全漏洞的温床（尤其是重复键）。
3. **可观测优先** — 每条审计结论都带**偏移量、长度、数据路径与修复建议**，而不是只说"不合规"。
4. **无损优先** — 诊断表示法与 JSON 桥接层都必须保证往返不丢语义，哪怕为此需要引入 `$` 前缀的显式标记。

### 技术选型

| 决策 | 选择 | 原因 |
|---|---|---|
| 语言 | 纯 Python | 零依赖目标下最务实；标准库已提供 `struct`（半精度浮点 `'>e'`）、`base64`、`json` |
| 浮点最短化 | `struct` 往返相等判定 | 无需引入 NumPy，即可精确判断某值能否被半/单精度无损承载 |
| 解析树 | 解码时同步构建 `CBORNode` | 一次解析同时服务解码、审计、可视化，避免重复遍历与逻辑分叉 |
| 键序策略 | 同时提供 RFC 7049 与 RFC 8949 | 两者在真实数据上确实会给出不同顺序，混用会导致签名不匹配 |
| 深度限制 | 默认 256 层 + 长度预检 | 抵御恶意构造输入导致的栈溢出与内存耗尽 |

### 迭代规划

- 🔜 **v1.1** — 增加 RFC 8742 / RFC 8949 §4.2.2 首选序列化的**自动改写**模式；补充更多 IANA 标签语义解读。
- 🔜 **v1.2** — 支持 CBOR 序列（RFC 8742）的流式解码与多数据项审计。
- 🔜 **v1.3** — 增加 SARIF 2.1.0 报告输出，直接接入 GitHub Code Scanning。
- 🔜 **v2.0** — 提供可选的标签语义层（日期、URI、bignum、十进制分数）自动解析。

### 社区贡献方向

- 补充更多真实世界的畸形样本与回归用例；
- 扩充 IANA 标签注册表子集；
- 翻译更多语言版本的 README（日语 / 韩语 / 西班牙语）。

---

## 📦 打包与部署指南

CBORForge 属于**工具库 / CLI 类项目**，无需编译产物，通过标准 Python 打包流程分发。

### 一键构建

```bash
./scripts/build.sh
```

脚本依次执行：清理 → 编译检查 → 单元测试 → 内置自检 → 构建发行包，全部离线完成。产物输出到 `dist/`：

```
dist/cborforge-1.0.0-py3-none-any.whl
```

### 手动构建

```bash
python -m build                 # 需要 build（PEP 517 标准方式）
# 或离线退化为：
python -m pip wheel --no-deps --no-build-isolation -w dist .
```

### Makefile 目标

```bash
make help       # 查看全部目标
make install    # 可编辑模式安装
make test       # 单元测试
make selftest   # RFC 8949 向量自检
make lint       # compileall 编译检查
make demo       # CLI 演示
make build      # 构建发行包
make clean      # 清理产物
```

### 部署方式

| 场景 | 做法 |
|---|---|
| **打包成 Wheel** | `./scripts/build.sh` → 分发 `dist/*.whl`，`pip install cborforge-1.0.0-py3-none-any.whl` |
| **整目录 vendored** | 直接把 `cborforge/` 拷入项目，`import cborforge` 即可，无需安装 |
| **单文件嵌入** | 将 `cborforge/` 打包进应用资源目录，用 `sys.path.append()` 引入 |
| **容器镜像** | `COPY cborforge/ /app/cborforge/`，无需 `pip install` 任何依赖 |
| **CLI 集成** | `pip install .` 后直接使用 `cborforge` 命令；或用 `python -m cborforge` 免安装调用 |

### 兼容环境

| 项目 | 说明 |
|---|---|
| Python | 3.8 / 3.9 / 3.10 / 3.11 / 3.12 |
| 操作系统 | Windows / macOS / Linux（纯 Python，无平台相关代码） |
| 架构 | x86_64 / ARM64 等全部支持 |
| 网络 | 完全不需要 |

---

## 🤝 贡献指南

- 提交信息请遵循 **Angular 规范**：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`。
- 提交 PR 前请确保 `make test` 与 `make selftest` 全部通过，并补充对应单元测试。
- **任何引入第三方运行期依赖的改动都不会被合并** —— 零依赖是本项目的第一原则。
- 新增审计规则时，请同步更新 `cborforge/validator.py` 的 `RULES` 表与三语 README 的规则表。

详细规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 📄 开源协议说明

本项目基于 **MIT License** 开源，详见 [LICENSE](LICENSE)。

- ✅ 允许商业使用、修改、分发、私有化部署与再许可；
- ✅ 允许用于闭源产品；
- ⚠️ 唯一要求：在副本或实质性部分中保留版权声明与许可声明；
- ❗ 软件按"原样"提供，不含任何明示或默示担保。

> 项目为 100% 独立自研实现，未复制任何既有 CBOR 库的源代码；所依据的 RFC 8949 / RFC 7049 标准文本属于公开标准文档。

---

<div align="center">

**CBORForge** — 让每一字节都可控、可解释、可验证。 🛠️

</div>
