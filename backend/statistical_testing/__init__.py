"""Statistical testing utilities for quantitative research."""

from statistical_testing.autocorrelation_tests import (
    AutocorrelationDiagnostics,
    LjungBoxResult,
    run_autocorrelation_diagnostics,
    run_ljung_box,
)
from statistical_testing.distribution_tests import (
    DistributionDiagnostics,
    run_distribution_diagnostics,
)
from statistical_testing.hypothesis_tests import (
    BootstrapSignificanceResult,
    ConfidenceIntervalResult,
    TTestResult,
    bootstrap_significance,
    confidence_interval,
    run_ttest,
)
from statistical_testing.stationarity_tests import (
    StationarityAssessment,
    run_stationarity_suite,
)

__all__ = [
    "AutocorrelationDiagnostics",
    "BootstrapSignificanceResult",
    "ConfidenceIntervalResult",
    "DistributionDiagnostics",
    "LjungBoxResult",
    "StationarityAssessment",
    "bootstrap_significance",
    "confidence_interval",
    "run_autocorrelation_diagnostics",
    "run_distribution_diagnostics",
    "run_ljung_box",
    "run_stationarity_suite",
    "run_ttest",
    "TTestResult",
]
