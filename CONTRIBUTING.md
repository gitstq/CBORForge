# 🤝 贡献指南

感谢你愿意让 CBORForge 变得更好！本项目的第一原则是 **零依赖、离线优先**，
因此任何引入第三方运行期依赖的改动都不会被合并。

## 开发环境

```bash
git clone <your-fork-url>
cd cborforge
make install      # 可编辑模式安装（不引入任何第三方包）
make test         # 单元测试
make selftest     # RFC 8949 测试向量自检
```

要求 **Python 3.8+**，无需联网、无需额外依赖。

## 提交规范

提交信息遵循 [Angular 规范](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)：

```
feat: 新增 CBF011 规则以检测未对齐的字节串分块
fix: 修复不定长文本串在码点边界处的切分错误
docs: 补充繁體中文 README 的打包章节
refactor: 将审计规则表抽离为独立模块
test: 为 canonical/ctap2 键序差异补充回归用例
chore: 更新 .gitignore
```

允许的 type：`feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `perf` / `ci`。

## Pull Request 检查清单

- [ ] `make test` 与 `make selftest` 全部通过
- [ ] 新增或修改的行为都有对应单元测试
- [ ] 未引入任何第三方运行期依赖
- [ ] 若新增审计规则，已同步更新 `cborforge/validator.py` 的 `RULES` 表与三语 README
- [ ] 若改动公开 API，已同步更新 `cborforge/__init__.py` 的 `__all__` 与三语 README

## Issue 反馈

提交 Issue 时请尽量附带：

1. 触发问题的 **十六进制 CBOR 字节串**（可用 `cborforge inspect` 导出）；
2. 期望行为与实际行为；
3. Python 版本与操作系统。

涉及安全问题的报告请优先说明是否可被外部输入触发。

## 行为准则

保持友善、就事论事。任何人身攻击或无关争论都将被移除。

---

By contributing, you agree that your contributions will be licensed under the MIT License.
