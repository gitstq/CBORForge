#!/usr/bin/env bash
#
# CBORForge 一键构建脚本
# ---------------------------------------------------------------------------
# 依次执行：清理 → 编译检查 → 单元测试 → 内置自检 → 构建 sdist / wheel。
# 优先使用 PEP 517 标准的 `python -m build`；若当前环境没有安装 build，
# 则退化为 `pip wheel --no-build-isolation`，全程不需要联网。
#
# 用法: ./scripts/build.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

echo "▶ [1/5] 清理旧产物"
rm -rf dist build ./*.egg-info

echo "▶ [2/5] 编译检查"
"$PYTHON" -m compileall -q cborforge tests

echo "▶ [3/5] 单元测试"
"$PYTHON" -m unittest discover -s tests -t . -q

echo "▶ [4/5] RFC 8949 内置自检"
"$PYTHON" -m cborforge selftest | tail -3

echo "▶ [5/5] 构建发行包"
mkdir -p dist
if "$PYTHON" -m build --help >/dev/null 2>&1; then
    "$PYTHON" -m build
else
    echo "  (未检测到 build，退化为 pip wheel --no-build-isolation)"
    "$PYTHON" -m pip wheel --no-deps --no-build-isolation -w dist .
fi

echo "✅ 构建完成，产物位于 dist/:"
ls -1 dist
