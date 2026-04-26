# fof-quant

ETF FOF research system for 场内宽基指数基金增强 workflows.

The v1 product is a deterministic CLI and report pipeline:

- Tushare-backed data ingestion and local cache
- 股票穿透增强 factor analysis
- ETF scoring and FOF allocation
- Historical backtesting
- Excel/HTML reports
- Optional LLM explanations for narrative review only

See [docs/PRD.md](docs/PRD.md), [docs/ROADMAP.md](docs/ROADMAP.md), and [docs/TODO.md](docs/TODO.md).

## Setup

```bash
uv sync --all-extras --dev
```

Copy `.env.example` to `.env` and set `TUSHARE_TOKEN` before live data refresh commands.
Optional LLM report explanations use `LLM_PROVIDER` plus `LLM_API_KEY`, or provider-specific
keys such as `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MINIMAX_API_KEY`, and `MOONSHOT_API_KEY`.
Real `.env` files and credential directories are ignored by Git.

## Common Commands

```bash
uv run fof-quant --help
uv run fof-quant config validate --config configs/example.yaml
uv run ruff check .
uv run mypy src tests
uv run pytest
```

## Development Gate

Before every commit, run:

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest
```
