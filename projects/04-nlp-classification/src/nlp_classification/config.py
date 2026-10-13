"""Configuration for the NLP classification project (playbook §Config).

All tunables live in this pydantic model so a run is fully described by one
validated object; nothing is hard-coded in library code.
"""

from pathlib import Path

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field


class HPOConfig(PortfolioBaseModel):
    """Search space + budget for the Optuna study over the fine-tuning loop."""

    n_trials: int = Field(default=12, ge=2)
    lr_min: float = Field(default=1e-5, gt=0.0)
    lr_max: float = Field(default=5e-5, gt=0.0)
    warmup_max: float = Field(default=0.2, ge=0.0, lt=1.0)
    weight_decay_max: float = Field(default=0.1, ge=0.0)
    epochs_min: int = Field(default=2, ge=1)
    epochs_max: int = Field(default=4, ge=2)
    startup_trials: int = Field(default=5, ge=1, description="MedianPruner n_startup_trials.")
    pruner_warmup_epochs: int = Field(
        default=1, ge=0, description="Epochs reported before the pruner may fire."
    )


class HPOBest(PortfolioBaseModel):
    """Winning hyperparameters, written back into params.yaml by the hpo stage."""

    learning_rate: float = Field(gt=0.0)
    warmup_ratio: float = Field(ge=0.0, lt=1.0)
    weight_decay: float = Field(ge=0.0)
    epochs: int = Field(ge=1)
    best_val_f1_macro: float = Field(description="Validation macro-F1 of the best trial.")


class HPOMultiSeed(PortfolioBaseModel):
    """Budget for the seed-variance study (small trials per seed, CPU-bounded)."""

    seeds: list[int] = Field(default_factory=lambda: [42, 43, 44], min_length=2)
    n_trials: int = Field(default=6, ge=2)
    epochs_max: int = Field(default=3, ge=2, description="Tighter epoch cap to fit the budget.")
    startup_trials: int = Field(default=2, ge=1)


class NLPConfig(PortfolioBaseModel):
    """Bounded run configuration for AG News text classification."""

    # Reproducibility
    seed: int = Field(default=42, description="Global seed for subsampling and training.")

    # Data (bounded: 4000 train / 1000 test, stratified, seeded — see DESIGN.md)
    dataset_name: str = Field(default="fancyzhx/ag_news")
    dataset_source: str = Field(default="https://huggingface.co/datasets/fancyzhx/ag_news")
    dataset_license: str = Field(
        default="unknown",  # per the HF dataset card (AG News has no SPDX license)
    )
    train_samples: int = Field(default=4000, ge=100)
    test_samples: int = Field(default=1000, ge=100)
    val_fraction: float = Field(
        default=0.1,
        gt=0.0,
        lt=0.5,
        description="Stratified fraction carved out of the train subsample.",
    )

    # Tokenization / model
    model_name: str = Field(default="distilbert-base-uncased")
    encoder_b_name: str = Field(
        default="roberta-base",
        description="Second candidate encoder (WordPiece/BPE, no sentencepiece).",
    )
    max_length: int = Field(default=128, ge=8, le=512)

    # Hand-written training loop
    batch_size: int = Field(default=32, ge=1)
    epochs: int = Field(default=2, ge=1)
    learning_rate: float = Field(default=2e-5, gt=0.0)
    weight_decay: float = Field(default=0.01, ge=0.0)
    warmup_ratio: float = Field(
        default=0.1, ge=0.0, lt=1.0, description="Fraction of total steps with linear LR warmup."
    )
    early_stop_patience: int = Field(default=1, ge=1)

    # Baseline (same bounded subsample — apples-to-apples comparison)
    tfidf_max_features: int = Field(default=8000, ge=100)

    # HPO (search space defaults; ``hpo_best`` is filled by the hpo stage)
    hpo: HPOConfig = Field(default_factory=HPOConfig)
    hpo_best: HPOBest | None = None
    hpo_seeds: HPOMultiSeed = Field(default_factory=HPOMultiSeed)

    # Locations (relative to the project working directory)
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")

    @property
    def train_dir(self) -> Path:
        """Prepared train split directory."""
        return self.data_dir / "train"

    @property
    def val_dir(self) -> Path:
        """Prepared validation split directory."""
        return self.data_dir / "val"

    @property
    def test_dir(self) -> Path:
        """Prepared test split directory."""
        return self.data_dir / "test"

    @property
    def models_dir(self) -> Path:
        """Directory holding fitted model artifacts."""
        return self.reports_dir / "models"

    @property
    def history_path(self) -> Path:
        """JSON training history of the fine-tuned model."""
        return self.reports_dir / "history.json"

    @property
    def study_path(self) -> Path:
        """JSON summary of the Optuna study."""
        return self.reports_dir / "hpo_study.json"

    @property
    def selection_path(self) -> Path:
        """JSON record of the tuned-vs-wave2 model selection decision."""
        return self.reports_dir / "selection.json"
