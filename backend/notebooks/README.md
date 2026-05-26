# Research Notebooks

Notebooks in this directory are for **exploration and visualization only**.

## Rules

1. **Reusable logic belongs in modules** — `loaders/`, `statistical_testing/`, `alpha_validation/`, `feature_analysis/`, `experiments/`.
2. **No duplicated loading logic** — always use `DatasetLoader` from `loaders.dataset_loader`.
3. **No lookahead** — never use future bars, centered rolling windows, or full-sample fits for historical labels.
4. **No toy data in production paths** — use parquet tiers produced by `run_data_pipeline.py`.
5. **Log experiments** — persist parameters and metrics via `ExperimentTracker`.

## Setup

```bash
cd backend
pip install -r requirements-data.txt -r requirements-research.txt
python -m ipykernel install --user --name quant-research
```

## Workflow

See `example_research_workflow.ipynb` for a canonical end-to-end research session:

1. Load features tier via `DatasetLoader`
2. Run stationarity and distribution diagnostics
3. Bootstrap alpha validation
4. Feature importance (with causality disclaimer)
5. Track experiment metadata

## Data prerequisites

```bash
python run_data_pipeline.py --symbol "GC=F" --interval 1d --period 2y
```
