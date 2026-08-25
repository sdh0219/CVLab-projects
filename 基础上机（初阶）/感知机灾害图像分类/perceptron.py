"""从零实现的二分类感知机，用于教学演示。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class Perceptron:
    def __init__(self, learning_rate: float = 0.1, max_epochs: int = 100):
        self.learning_rate = learning_rate
        self.max_epochs = max_epochs
        self.weights: np.ndarray | None = None
        self.bias = 0.0
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None
        self.history: list[int] = []

    def fit(self, x: np.ndarray, y: np.ndarray) -> "Perceptron":
        self.mean = x.mean(axis=0)
        self.std = x.std(axis=0)
        self.std[self.std < 1e-8] = 1.0
        xs = (x - self.mean) / self.std
        self.weights = np.zeros(xs.shape[1], dtype=float)
        self.bias = 0.0
        best_weights = self.weights.copy()
        best_bias = self.bias
        best_errors = len(y) + 1

        for _ in range(self.max_epochs):
            errors = 0
            for xi, yi in zip(xs, y):
                pred = int(np.dot(self.weights, xi) + self.bias >= 0)
                update = self.learning_rate * (int(yi) - pred)
                if update != 0:
                    self.weights += update * xi
                    self.bias += update
                    errors += 1
                # Pocket 感知机：对小样本、不完全线性可分的数据，
                # 保留训练期间误分最少的一组参数。
                current = (xs @ self.weights + self.bias >= 0).astype(int)
                current_errors = int(np.sum(current != y))
                if current_errors < best_errors:
                    best_errors = current_errors
                    best_weights = self.weights.copy()
                    best_bias = self.bias
            self.history.append(errors)
            if errors == 0:
                break
        self.weights = best_weights
        self.bias = best_bias
        return self

    def decision_function(self, x: np.ndarray) -> np.ndarray:
        if self.weights is None or self.mean is None or self.std is None:
            raise RuntimeError("模型尚未训练")
        return ((x - self.mean) / self.std) @ self.weights + self.bias

    def predict(self, x: np.ndarray) -> np.ndarray:
        return (self.decision_function(x) >= 0).astype(int)

    def save(self, path: str | Path) -> None:
        data = {
            "learning_rate": self.learning_rate,
            "max_epochs": self.max_epochs,
            "weights": self.weights.tolist(),
            "bias": self.bias,
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "history": self.history,
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Perceptron":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        model = cls(data["learning_rate"], data["max_epochs"])
        model.weights = np.asarray(data["weights"], dtype=float)
        model.bias = float(data["bias"])
        model.mean = np.asarray(data["mean"], dtype=float)
        model.std = np.asarray(data["std"], dtype=float)
        model.history = data.get("history", [])
        return model
