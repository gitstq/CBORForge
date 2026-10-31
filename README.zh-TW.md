<div align="center">

# 🔧 CBORForge

**零依賴 · 離線優先的 CBOR（RFC 8949）編解碼、診斷表示法與規範性稽核工具箱**

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#-核心特色)
[![RFC](https://img.shields.io/badge/RFC-8949-orange.svg)](https://www.rfc-editor.org/rfc/rfc8949)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[简体中文](README.md) · **繁體中文** · [English](README.en.md)

</div>

---

## 🎉 專案介紹

**CBORForge** 是一套完全自研的 CBOR（Concise Binary Object Representation）工具箱，嚴格實作 **RFC 8949**，並同時提供 **RFC 7049 規範形式**與 **RFC 8949 §4.2.1 核心確定性編碼（CTAP2 / WebAuthn）**兩種確定性編碼策略。

### 它解決什麼痛點？

CBOR 廣泛應用於物聯網、WebAuthn / FIDO2 簽章、COSE、區塊鏈與嵌入式通訊，但開發者經常面臨三個真實困境：

| 😖 痛點 | ❌ 現況 | ✅ CBORForge |
|---|---|---|
| **二進位看不懂** | 擷取到封包 `a26161016162820203`，只能靠猜 | `inspect` 直接給出帶**偏移量**的結構樹 + 十六進位傾印 |
| **簽章驗證失敗** | 同一份邏輯資料，卻因編碼差異導致雜湊對不上 | `validate` 精確定位重複鍵、非最短編碼、鍵序錯誤，並附上偏移量 |
| **環境裝不上依賴** | 內網 / 嵌入式環境無法 `pip install` | **零第三方依賴**，純標準函式庫，整個目錄複製即可執行，完全離線 |

### 自研差異化亮點

- 🧩 **真正的零依賴**：僅使用 `struct` / `base64` / `json` / `re` / `math` 等標準函式庫，執行期不引入任何第三方套件，可整包 vendor 進任何專案。
- 🛡️ **嚴格良構性校驗**：完整實作 RFC 8949 附錄 C 的良構性檢查（保留附加資訊、不定長誤用、非法 UTF-8、`break` 錯位等 17 類畸形輸入全部拒絕）。
- 🔍 **確定性編碼稽核**：10 條規則（CBF001–CBF010）涵蓋非最短編碼、浮點寬度、NaN 首選序列化、不定長、重複鍵、鍵序、不可雜湊鍵、深層嵌套等，輸出**偏移量 + 資料路徑 + 修復建議**。
- 🔁 **無損雙向橋接**：診斷表示法（RFC 8949 §8）與 JSON 橋接層皆保證往返無損，位元組串 / 標籤 / 簡單值 / `undefined` / NaN 都能完整保留。
- 🚪 **CI 就緒**：`validate` 發現 error 級問題即以結束碼 `1` 收尾，可直接當作管線關卡。
- 🧪 **內建標準測試向量**：收錄 RFC 8949 附錄 A 共 **81 條**向量、**226 項**檢查，`cborforge selftest` 一鍵驗證。

> 靈感來源：RFC 8949 / RFC 7049 標準文本與 WebAuthn CTAP2 規範編碼要求；實作為 100% 獨立自研，未複用任何既有 CBOR 函式庫的原始碼。

---

## ✨ 核心特色

- 🧠 **完整解碼器** — major type 0–7 全覆蓋，含不定長位元組串 / 文字串 / 陣列 / 映射、標籤、半精度 / 單精度 / 雙精度浮點、簡單值、`undefined`。
- 📦 **多策略編碼器** — 預設最短編碼；`--canonical` 走 RFC 7049；`--ctap2` 走 RFC 8949 核心確定性編碼；支援 `auto / 16 / 32 / 64` 四種浮點寬度策略。
- 🧾 **診斷表示法** — RFC 8949 §8 雙向支援，含 `h'..'` / `b64'..'` 位元組串、`0x1.8p+1` 十六進位浮點、`simple(n)`、`Infinity` / `NaN`，額外支援 `#` 註解與尾隨逗號。
- 🔄 **JSON 無損橋接** — 以 `$bytes` / `$tag` / `$simple` / `$undefined` / `$float` / `$map` 標記保留 JSON 缺失的 CBOR 語意，往返不丟資訊。
- 🔎 **結構視覺化** — `inspect` 輸出層級結構樹，每個節點標註偏移量、長度、編碼頭部與取值預覽，並附十六進位傾印。
- 🛡️ **安全強化** — 預設 256 層嵌套深度上限、超大長度宣告預檢，抵禦惡意構造輸入導致的堆疊溢位與記憶體耗盡。
- 🐍 **Python API + CLI 雙型態** — 既可作為套件 `import cborforge`，也可 `python -m cborforge` 或安裝後的 `cborforge` 指令使用。
- 📴 **完全離線** — 無網路請求、無遙測、無設定檔、無環境變數依賴。

---

## 🚀 快速開始

### 環境需求

| 項目 | 需求 |
|---|---|
| Python | **3.8 以上**（建議 3.11+） |
| 作業系統 | Windows / macOS / Linux 全平台 |
| 第三方依賴 | **無** |
| 網路 | **不需要** |

### 方式一：免安裝，直接執行（建議先試這個）

```bash
git clone https://github.com/gitstq/CBORForge.git
cd CBORForge

# 編碼：JSON → CBOR（十六進位）
python -m cborforge encode '{"user": "ada", "id": 7, "tags": ["a", "b"], "score": 1.5}'
# a464757365726361646162696407647461677382616161626573636f7265f93e00

# 解碼：CBOR → JSON
python -m cborforge decode a464757365726361646162696407647461677382616161626573636f7265f93e00
```

### 方式二：安裝為命令列工具

```bash
pip install .          # 從原始碼安裝（目前目錄）
# 或
pip install -e .       # 可編輯模式，適合二次開發

cborforge --version
# cborforge 1.0.0
```

### 方式三：作為函式庫引入

```python
import cborforge

raw = cborforge.dumps({"user": "ada", "score": 1.5})
print(raw.hex())                       # a26475736572636164616573636f7265f93e00
print(cborforge.loads(raw))            # {'user': 'ada', 'score': 1.5}
print(cborforge.to_diagnostic(cborforge.loads(raw)))
# {"user": "ada", "score": 1.5}
```

### 30 秒體驗完整鏈路

```bash
# 1) 一段「不規範」的 CBOR：不定長映射 + 鍵序顛倒（"b" 在 "a" 前）
python -m cborforge validate bf61621901f4616101ff
# → CBF004 使用了不定長資料項 / CBF006 映射鍵未按確定性規則排序  (結束碼 1)

# 2) 一鍵規範化
python -m cborforge canonical bf61621901f4616101ff
# a261610161621901f4

# 3) 再次稽核：通過
python -m cborforge validate a261610161621901f4
# → 結論：通過 PASS（0 錯誤 / 0 警告 / 0 提示）  (結束碼 0)

# 4) 執行標準測試向量自檢
python -m cborforge selftest
# ✅ 全部通過：解碼、診斷表示法往返與位元組級重編碼均一致。
```

---

## 📖 詳細使用指南

### 命令列總覽

```
cborforge [--version] <command> [options]

  encode     把 JSON / 診斷表示法編碼為 CBOR
  decode     把 CBOR 解碼為 JSON / 診斷表示法
  inspect    展示帶偏移量的結構樹與十六進位傾印
  validate   規範性 / 確定性編碼稽核
  canonical  重新編碼為規範 / 確定性形式
  selftest   執行內建 RFC 8949 測試向量自檢
```

> 💡 **輸入技巧**：位置參數優先按**檔案路徑**讀取；若該路徑不存在，則按**字面量**處理。
> 因此 `cborforge decode a1616101`（直接給十六進位）與 `cborforge decode data.cbor`（讀檔）都能運作。
> 使用 `-` 或省略參數則從標準輸入讀取，方便以管線串接。

#### 通用選項

| 選項 | 說明 | 預設值 |
|---|---|---|
| `--in-format` | 輸入解釋方式：`auto` / `hex` / `base64` / `bin` | `auto` |
| `-o, --output` | 輸出檔案，`-` 表示標準輸出 | `-` |
| `-f, --format` | 輸出表示（各子命令候選值不同） | 見下 |

---

### `encode` — 編碼為 CBOR

```bash
# 從 JSON 編碼（預設自動識別，也可用 --from diag 指定診斷表示法）
cborforge encode '{"a": 1}'                      # → a1616101
cborforge encode '{"a": 1}' -f base64            # → oWGBAQ==
cborforge encode '{"a": 1}' -f bin -o data.cbor  # → 寫出二進位檔

# 從診斷表示法編碼（可表達位元組串 / 標籤 / 簡單值）
cborforge encode --from diag '{1: 2, "x": h'6161', "z": simple(42)}'
# → a301026178426161617af82a
```

| 選項 | 說明 | 預設 |
|---|---|---|
| `--from` | `auto` / `json` / `diag` | `auto` |
| `-f` | `hex` / `base64` / `bin` | `hex` |
| `--canonical` | RFC 7049 規範形式 | 關 |
| `--ctap2` | RFC 8949 核心確定性編碼 | 關 |
| `--float-mode` | `auto` / `16` / `32` / `64` | `auto` |
| `--indefinite` | 使用不定長構造（用於互通性測試） | 關 |
| `--chunk-size` | 不定長字串分塊位元組數 | `8` |

---

### `decode` — 解碼 CBOR

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
# 輸出為診斷表示法（預設緊湊單行）
cborforge decode a464757365726361646162696407647461677382616161626573636f7265f93e00 -f diag
# {"user": "ada", "id": 7, "tags": ["a", "b"], "score": 1.5}

# 需要換行縮排時明確指定
cborforge decode a3616101616283010203 -f diag --indent 2
```

| 選項 | 說明 | 預設 |
|---|---|---|
| `-f` | `json` / `diag` | `json` |
| `--indent` | 縮排寬度；JSON 預設 `2`，診斷表示法預設緊湊 | `2` |
| `--hex-floats` | 診斷表示法使用十六進位浮點字面量 | 關 |
| `--bignum` | 把標籤 2/3 大整數摺疊為 Python `int` | 關 |

---

### `inspect` — 結構視覺化

```bash
cborforge inspect a26161016162820203
```

```
🔍 CBORForge inspect — 9 位元組
────────────────────────────────────────────────────────────────────────────────────────
路徑                                 類型               偏移        長度     值
────────────────────────────────────────────────────────────────────────────────────────
$                                  map(2)           @0        9
  K .a                             text(1)          @1        2      "a"
  V .a                             uint             @3        1      1
  K .b                             text(1)          @4        2      "b"
  V .b                             array(2)         @6        3
    [0]                            uint             @7        1      2
    [1]                            uint             @8        1      3
────────────────────────────────────────────────────────────────────────────────────────
十六進位傾印 / hex dump:
00000000  a2 61 61 01 61 62 82 02 03                       |.aa.ab...|
```

> `K` / `V` 表示映射的鍵與值；`∞` 標記表示該項為不定長編碼。

| 選項 | 說明 | 預設 |
|---|---|---|
| `--max-bytes` | 位元組串預覽最大長度 | `24` |
| `--max-text` | 文字串預覽最大長度 | `40` |
| `--dump-limit` | 十六進位傾印最大位元組數 | `256` |

---

### `validate` — 規範性稽核

```bash
cborforge validate bf61621901f4616101ff
```

```
CBORForge 稽核報告 / CBORForge Audit Report
────────────────────────────────────────────────────────────
  位元組長度 : 10
  資料項數量 : 5
  最大嵌套   : 1
  確定性規則 : RFC 8949 §4.2.1 核心確定性編碼（位元組字典序）
  結論       : 未通過 FAIL（2 錯誤 / 0 警告 / 0 提示）
────────────────────────────────────────────────────────────
[CBF004] error   使用了不定長資料項
        偏移 0 (長度 10)  路徑 $
        map 使用了不定長編碼，無法得到確定性位元組序列
        建議: 改寫為定長形式以獲得確定性編碼
[CBF006] error   映射鍵未按確定性規則排序
        偏移 6 (長度 2)  路徑 $
        鍵 'a' 排序在 'b' 之前，違反 RFC8949
        建議: 按鍵的確定性編碼排序（RFC 8949 為純位元組字典序）
```

```bash
# 輸出 JSON，便於接入管線
cborforge validate 1801 -f json

# 作為 CI 關卡：有問題即失敗
cborforge validate payload.cbor --in-format bin || exit 1
```

| 選項 | 說明 | 預設 |
|---|---|---|
| `--determinism` | `rfc8949` / `rfc7049` / `off` | `rfc8949` |
| `--depth-threshold` | 觸發 CBF008 的嵌套深度門檻 | `32` |
| `--strict` | 存在任何層級問題即回傳非零 | 關 |
| `-f` | `text` / `json` | `text` |

**結束碼**

| 碼 | 意義 |
|---|---|
| `0` | 未發現 error 級問題（`--strict` 時為無任何問題） |
| `1` | 發現 error 級問題（`--strict` 時為發現任何問題） |
| `2` | 用法 / IO / 解碼或編碼錯誤 |

#### 稽核規則表

| 編碼 | 層級 | 意義 | 修復建議 |
|---|---|---|---|
| `CBF000` | error | 資料不符合 RFC 8949 良構性要求 | 檢查是否為截斷 / 損壞的位元組流 |
| `CBF001` | error | 參數 / 長度未使用最短編碼 | 改用 `ai<24` / `24` / `25` / `26` / `27` |
| `CBF002` | error | 浮點未使用最短可無損還原寬度 | 按 §4.2.2 降級為半精度 / 單精度 |
| `CBF003` | error | NaN 未使用首選序列化 | 統一為 `0xf97e00` |
| `CBF004` | error | 使用了不定長資料項 | 改寫為定長 |
| `CBF005` | error | 映射存在重複鍵 | ⚠️ 簽章情境下可被用於繞過驗證 |
| `CBF006` | error | 映射鍵未按確定性規則排序 | 按鍵的確定性編碼排序 |
| `CBF007` | warning | 映射鍵不可雜湊 | 改用純量鍵 |
| `CBF008` | warning | 嵌套深度超過門檻 | 降低層級，避免堆疊溢位 |
| `CBF009` | warning | 不定長字串被拆為多個分塊 | 合併為單分塊可顯著縮小體積 |
| `CBF010` | info | 使用了未收錄的標籤號 | 確認標籤號語意 |

---

### `canonical` — 規範化重編碼

```bash
cborforge canonical bf61621901f4616101ff --report
# 規範化: 10 位元組 -> 9 位元組 (已重寫)
# a261610161621901f4
```

`--report` 會向標準錯誤輸出體積對比，方便在管線中觀察規範化效益。

---

### `selftest` — 標準向量自檢

```bash
cborforge selftest
# 🧪 CBORForge selftest — RFC 8949 附錄 A 測試向量
#   向量總數 : 81
#   檢查項   : 226
#   通過     : 226
#   失敗     : 0
# ✅ 全部通過：解碼、診斷表示法往返與位元組級重編碼均一致。
```

---

### Python API

```python
import cborforge
from cborforge import Tag, SimpleValue, UNDEFINED

# ── 編解碼 ───────────────────────────────────────────────
raw = cborforge.dumps({"a": 1, "b": [1, 2, 3]})
cborforge.loads(raw)                          # {'a': 1, 'b': [1, 2, 3]}

# 確定性編碼
cborforge.dumps({1000: 1, True: 2}, canonical=True)   # RFC 7049：長度優先
cborforge.dumps({1000: 1, True: 2}, ctap2=True)       # RFC 8949：純位元組字典序

# 不定長構造 + 浮點寬度策略
cborforge.dumps([1, 2], indefinite=True)              # 9f0102ff
cborforge.dumps(1.5, float_mode="64")                 # fb3ff8000000000000

# ── CBOR 專屬語意 ────────────────────────────────────────
cborforge.dumps(Tag(0, "2013-03-21T20:04:00Z")).hex()
cborforge.dumps(SimpleValue(42)).hex()                # f82a
cborforge.dumps(UNDEFINED).hex()                      # f7
cborforge.loads(b"\xc2\x42\x01\x00", bignum=True)     # 256（標籤 2 摺疊為 int）

# ── 診斷表示法 ───────────────────────────────────────────
cborforge.to_diagnostic({"a": 1}, indent=2)
cborforge.parse_diagnostic('{1: 2, "b": h'0102'} # 支援註解')

# ── JSON 無損橋接 ────────────────────────────────────────
cborforge.to_json_text({"k": b"\x01\x02"})
# {"k": {"$bytes": "AQI="}}
cborforge.from_json_text('{"k": {"$bytes": "AQI="}}')  # {'k': b'\x01\x02'}

# ── 稽核 ─────────────────────────────────────────────────
report = cborforge.validate(bytes.fromhex("1801"))
report.ok          # False
report.counts      # {'error': 1, 'warning': 0, 'info': 0}
[f.code for f in report.findings]   # ['CBF001']
report.to_text()   # 人類可讀報告
report.to_dict()   # 可 JSON 序列化的結構

# 解析樹（帶偏移量，可自行做二次分析）
node = cborforge.parse(bytes.fromhex("a26161016162820203"))
node.offset, node.end, node.entries  # 0, 9, [(key_node, value_node), ...]
```

---

### 典型使用情境

**情境一：WebAuthn / CTAP2 簽章前的編碼體檢**

```bash
# 註冊回應中的 authenticatorData 必須採用確定性編碼
cborforge validate attestation.cbor --in-format bin --determinism rfc8949
cborforge canonical attestation.cbor --in-format bin --ctap2 -f bin -o fixed.cbor
```

**情境二：擷取封包排查 IoT 裝置的 CBOR 訊息**

```bash
cborforge inspect --in-format bin capture.bin | head -40
```

**情境三：在 CI 中防止不規範編碼被合入**

```yaml
- name: CBOR canonical check
  run: |
    for f in $(find . -name '*.cbor'); do
      cborforge validate "$f" --in-format bin || exit 1
    done
```

---

## 💡 設計思路與迭代規劃

### 設計哲學

1. **零依賴優先** — 只依賴標準函式庫，意味著它能被 vendor 進任何專案、跑在任何受限環境；也意味著沒有供應鏈攻擊面。
2. **嚴格優於寬容** — 解碼器對良構性錯誤一律拒絕，而不是「盡力猜測」。模糊的解析結果是安全漏洞的溫床（尤其是重複鍵）。
3. **可觀測優先** — 每條稽核結論都帶**偏移量、長度、資料路徑與修復建議**，而不是只說「不合規」。
4. **無損優先** — 診斷表示法與 JSON 橋接層都必須保證往返不丟語意，即便為此需要引入 `$` 前綴的顯式標記。

### 技術選型

| 決策 | 選擇 | 原因 |
|---|---|---|
| 語言 | 純 Python | 零依賴目標下最務實；標準函式庫已提供 `struct`（半精度浮點 `'>e'`）、`base64`、`json` |
| 浮點最短化 | `struct` 往返相等判定 | 無需引入 NumPy，即可精確判斷某值能否被半 / 單精度無損承載 |
| 解析樹 | 解碼時同步建構 `CBORNode` | 一次解析同時服務解碼、稽核、視覺化，避免重複走訪與邏輯分叉 |
| 鍵序策略 | 同時提供 RFC 7049 與 RFC 8949 | 兩者在真實資料上確實會給出不同順序，混用會導致簽章不匹配 |
| 深度限制 | 預設 256 層 + 長度預檢 | 抵禦惡意構造輸入導致的堆疊溢位與記憶體耗盡 |

### 迭代規劃

- 🔜 **v1.1** — 增加 RFC 8949 §4.2.2 首選序列化的**自動改寫**模式；補充更多 IANA 標籤語意解讀。
- 🔜 **v1.2** — 支援 CBOR 序列（RFC 8742）的串流解碼與多資料項稽核。
- 🔜 **v1.3** — 增加 SARIF 2.1.0 報告輸出，直接接入 GitHub Code Scanning。
- 🔜 **v2.0** — 提供可選的標籤語意層（日期、URI、bignum、十進位分數）自動解析。

### 社群貢獻方向

- 補充更多真實世界的畸形樣本與回歸案例；
- 擴充 IANA 標籤註冊表子集；
- 翻譯更多語言版本的 README（日語 / 韓語 / 西班牙語）。

---

## 📦 打包與部署指南

CBORForge 屬於**工具函式庫 / CLI 類專案**，無需編譯產物，透過標準 Python 打包流程分發。

### 一鍵建置

```bash
./scripts/build.sh
```

腳本依序執行：清理 → 編譯檢查 → 單元測試 → 內建自檢 → 建置發行包，全部離線完成。產物輸出到 `dist/`：

```
dist/cborforge-1.0.0-py3-none-any.whl
```

### 手動建置

```bash
python -m build                 # 需要 build（PEP 517 標準方式）
# 或離線退化為：
python -m pip wheel --no-deps --no-build-isolation -w dist .
```

### Makefile 目標

```bash
make help       # 查看全部目標
make install    # 可編輯模式安裝
make test       # 單元測試
make selftest   # RFC 8949 向量自檢
make lint       # compileall 編譯檢查
make demo       # CLI 示範
make build      # 建置發行包
make clean      # 清理產物
```

### 部署方式

| 情境 | 做法 |
|---|---|
| **打包成 Wheel** | `./scripts/build.sh` → 分發 `dist/*.whl`，`pip install cborforge-1.0.0-py3-none-any.whl` |
| **整目錄 vendor** | 直接把 `cborforge/` 複製進專案，`import cborforge` 即可，無需安裝 |
| **單檔嵌入** | 將 `cborforge/` 放進應用資源目錄，用 `sys.path.append()` 引入 |
| **容器映像** | `COPY cborforge/ /app/cborforge/`，無需 `pip install` 任何依賴 |
| **CLI 整合** | `pip install .` 後直接使用 `cborforge` 指令；或用 `python -m cborforge` 免安裝呼叫 |

### 相容環境

| 項目 | 說明 |
|---|---|
| Python | 3.8 / 3.9 / 3.10 / 3.11 / 3.12 |
| 作業系統 | Windows / macOS / Linux（純 Python，無平台相關程式碼） |
| 架構 | x86_64 / ARM64 等全部支援 |
| 網路 | 完全不需要 |

---

## 🤝 貢獻指南

- 提交訊息請遵循 **Angular 規範**：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`。
- 送出 PR 前請確保 `make test` 與 `make selftest` 全部通過，並補上對應的單元測試。
- **任何引入第三方執行期依賴的改動都不會被合併** —— 零依賴是本專案的第一原則。
- 新增稽核規則時，請同步更新 `cborforge/validator.py` 的 `RULES` 表與三語 README 的規則表。

詳細規則見 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 📄 開源授權說明

本專案以 **MIT License** 開源，詳見 [LICENSE](LICENSE)。

- ✅ 允許商業使用、修改、散佈、私有化部署與再授權；
- ✅ 允許用於閉源產品；
- ⚠️ 唯一要求：在副本或實質性部分中保留版權聲明與授權聲明；
- ❗ 軟體依「原樣」提供，不含任何明示或默示擔保。

> 專案為 100% 獨立自研實作，未複製任何既有 CBOR 函式庫的原始碼；所依據的 RFC 8949 / RFC 7049 標準文本屬於公開標準文件。

---

<div align="center">

**CBORForge** — 讓每一位元組都可掌控、可解釋、可驗證。 🛠️

</div>
