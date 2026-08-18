"""Pure-Python frozen linear Communication Opportunity Value predictor."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping


class FrozenOpportunityPredictor:
    def __init__(self, manifest: Mapping[str, object]) -> None:
        self.features = tuple(str(item) for item in manifest["feature_names"])
        self.imputer = tuple(float(item) for item in manifest["imputer_median"])
        self.mean = tuple(float(item) for item in manifest["standardizer_mean"])
        self.scale = tuple(float(item) for item in manifest["standardizer_scale"])
        self.coefficients = tuple(float(item) for item in manifest["coefficients"])
        self.intercept = float(manifest["intercept"])
        self.threshold = float(manifest["decision_threshold"])
        lengths = {len(self.features), len(self.imputer), len(self.mean),
                   len(self.scale), len(self.coefficients)}
        if len(lengths) != 1 or not self.features:
            raise ValueError("inconsistent opportunity model dimensions")
        if any(value <= 0 for value in self.scale) or not 0 < self.threshold < 1:
            raise ValueError("invalid opportunity model normalization or threshold")

    @classmethod
    def from_path(cls, path: Path) -> "FrozenOpportunityPredictor":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def probability(self, feature_values: Mapping[str, float]) -> float:
        values = []
        for index, feature in enumerate(self.features):
            value = float(feature_values[feature])
            if not math.isfinite(value):
                value = self.imputer[index]
            values.append((value - self.mean[index]) / self.scale[index])
        logit = self.intercept + sum(weight * value for weight, value in zip(self.coefficients, values))
        if logit >= 0:
            return 1.0 / (1.0 + math.exp(-logit))
        exp_value = math.exp(logit)
        return exp_value / (1.0 + exp_value)

    def send(self, feature_values: Mapping[str, float]) -> bool:
        return self.probability(feature_values) >= self.threshold

