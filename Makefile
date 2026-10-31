# CBORForge —— 一键构建 / 测试 / 打包脚本
# 全部目标均离线可用，无需联网。

PYTHON  ?= python3
PKG     := cborforge
DIST    := dist

.PHONY: help install test selftest lint build dist demo clean

help:                                   ## 显示可用目标
	@printf "CBORForge 可用目标:\n"
	@printf "  make install    以可编辑模式安装到当前环境\n"
	@printf "  make test       运行单元测试套件\n"
	@printf "  make selftest   运行内置 RFC 8949 测试向量自检\n"
	@printf "  make lint       使用 compileall 做语法/编译检查\n"
	@printf "  make demo       运行 CLI 演示（编解码 / 审计）\n"
	@printf "  make build      构建 sdist 与 wheel 到 %s/\n" "$(DIST)"
	@printf "  make dist       clean + build\n"
	@printf "  make clean      清理构建产物与缓存\n"

install:                                ## 可编辑模式安装
	$(PYTHON) -m pip install -e .

test:                                   ## 单元测试
	$(PYTHON) -m unittest discover -s tests -t . -v

selftest:                               ## RFC 8949 测试向量自检
	$(PYTHON) -m $(PKG) selftest

lint:                                   ## 编译检查（零依赖，无需额外工具）
	$(PYTHON) -m compileall -q $(PKG) tests

demo:                                   ## CLI 演示
	@echo '--- encode ---';      $(PYTHON) -m $(PKG) encode '{"a": 1, "b": [1, 2, 3], "t": 1.5}'
	@echo '--- decode ---';      $(PYTHON) -m $(PKG) decode a36161016162830102036174f93e00
	@echo '--- inspect ---';     $(PYTHON) -m $(PKG) inspect a26161016162820203 | head -8
	@echo '--- validate ok ---'; $(PYTHON) -m $(PKG) validate a201020304 | tail -4
	@echo '--- validate bad -'; $(PYTHON) -m $(PKG) validate 1801 | tail -6

build:                                  ## 构建发行包
	./scripts/build.sh

dist: clean build                       ## 清理后重新构建

clean:                                  ## 清理
	rm -rf $(DIST) build ./*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.py[co]' -delete 2>/dev/null || true
