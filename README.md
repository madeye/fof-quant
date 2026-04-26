# fof-quant

面向 **场内宽基指数基金（ETF）FOF 增强** 工作流的研究系统。

v1 版本是一条确定性的 CLI 与报告流水线：

- 基于 Tushare 的数据接入与本地缓存
- 股票穿透增强因子分析
- ETF 打分与 FOF 配置
- 历史回测
- Excel / HTML 报告
- 可选的 LLM 文字解读，仅用于报告叙述（不参与打分、加权或回测计算）

详见 [docs/PRD.md](docs/PRD.md)、[docs/ROADMAP.md](docs/ROADMAP.md)、[docs/TODO.md](docs/TODO.md)。

## 环境准备

```bash
uv sync --all-extras --dev
```

将 `.env.example` 复制为 `.env`，并在执行实盘数据刷新命令前设置 `TUSHARE_TOKEN`。
可选的 LLM 报告解读使用 `LLM_PROVIDER` 加 `LLM_API_KEY`，或使用具体厂商的密钥，例如
`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`MINIMAX_API_KEY`、`MOONSHOT_API_KEY`。
真实的 `.env` 文件与凭据目录已在 Git 中忽略。

## 常用命令

```bash
uv run fof-quant --help
uv run fof-quant config validate --config configs/example.yaml
uv run fof-quant pipeline run --config configs/example.yaml
uv run ruff check .
uv run mypy src tests
uv run pytest
```

## 提交前检查

每次提交前，请运行：

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest
```

## 许可证

本项目基于 [MIT License](LICENSE) 发布。

## 免责声明

本项目**仅供研究与学习使用**，不构成任何投资建议、要约、招揽，也不是对任何证券、基金或其他金融工具的买卖推荐。
回测结果、打分、配置方案以及 LLM 生成的任何文字解读，均为确定性研究流水线的示例性输出，
**不对未来收益作出任何预测或承诺**。市场数据可能存在缺失、延迟或错误，历史表现亦不代表未来表现。

使用本软件做出的任何决策，由您自行承担全部责任。作者及贡献者对因使用本软件
而产生的任何投资亏损、数据丢失、合规风险或其他损害均不承担任何责任。
通过本项目使用 Tushare、LLM 服务商或任何其他第三方服务，须遵守其各自的服务条款；
您有义务确保自身使用行为符合所在司法辖区的全部法律、法规与许可要求。
