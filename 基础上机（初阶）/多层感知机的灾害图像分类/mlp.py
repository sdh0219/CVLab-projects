"""仅使用 NumPy 实现的两隐藏层 MLP：ReLU + Sigmoid + BCE + 反向传播。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class MLP:
    def __init__(self, input_size=3, hidden1=8, hidden2=4, learning_rate=0.03, seed=42):
        self.learning_rate = learning_rate
        rng = np.random.default_rng(seed)
        # He 初始化适合 ReLU。
        self.w1 = rng.normal(0, np.sqrt(2 / input_size), (input_size, hidden1))
        self.b1 = np.zeros((1, hidden1))
        self.w2 = rng.normal(0, np.sqrt(2 / hidden1), (hidden1, hidden2))
        self.b2 = np.zeros((1, hidden2))
        self.w3 = rng.normal(0, np.sqrt(2 / hidden2), (hidden2, 1))
        self.b3 = np.zeros((1, 1))
        self.mean = np.zeros(input_size)
        self.std = np.ones(input_size)
        self.history: list[float] = []

    @staticmethod
    def relu(x):
        return np.maximum(0.0, x)

    @staticmethod
    def sigmoid(x):
        x = np.clip(x, -50, 50)
        return 1.0 / (1.0 + np.exp(-x))

    def _forward(self, x):
        z1 = x @ self.w1 + self.b1
        h1 = self.relu(z1)
        z2 = h1 @ self.w2 + self.b2
        h2 = self.relu(z2)
        probability = self.sigmoid(h2 @ self.w3 + self.b3)
        return z1, h1, z2, h2, probability

    @staticmethod
    def binary_cross_entropy(y, probability):
        p = np.clip(probability, 1e-8, 1 - 1e-8)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    def fit(self, x, y, epochs=1500, batch_size=4, seed=42):
        self.mean = x.mean(axis=0)
        self.std = x.std(axis=0)
        self.std[self.std < 1e-8] = 1.0
        xs = (x - self.mean) / self.std
        y = y.reshape(-1, 1).astype(float)
        rng = np.random.default_rng(seed)

        for _ in range(epochs):
            order = rng.permutation(len(xs))
            for start in range(0, len(xs), batch_size):
                index = order[start : start + batch_size]
                xb, yb = xs[index], y[index]
                z1, h1, z2, h2, p = self._forward(xb)
                m = len(xb)

                # BCE 与 Sigmoid 组合后，输出层梯度简化为 (p-y)/m。
                dz3 = (p - yb) / m
                dw3, db3 = h2.T @ dz3, dz3.sum(axis=0, keepdims=True)
                dh2 = dz3 @ self.w3.T
                dz2 = dh2 * (z2 > 0)
                dw2, db2 = h1.T @ dz2, dz2.sum(axis=0, keepdims=True)
                dh1 = dz2 @ self.w2.T
                dz1 = dh1 * (z1 > 0)
                dw1, db1 = xb.T @ dz1, dz1.sum(axis=0, keepdims=True)

                for parameter, gradient in (
                    (self.w1, dw1), (self.b1, db1), (self.w2, dw2),
                    (self.b2, db2), (self.w3, dw3), (self.b3, db3)
                ):
                    parameter -= self.learning_rate * gradient
            self.history.append(self.binary_cross_entropy(y, self._forward(xs)[-1]))
        return self

    def predict_proba(self, x):
        xs = (x - self.mean) / self.std
        return self._forward(xs)[-1].ravel()

    def predict(self, x, threshold=0.5):
        return (self.predict_proba(x) >= threshold).astype(int)

    def save(self, path: str | Path):
        data = {name: getattr(self, name).tolist() for name in
                ("w1", "b1", "w2", "b2", "w3", "b3", "mean", "std")}
        data["learning_rate"] = self.learning_rate
        data["history"] = self.history
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        model = cls(len(data["mean"]), len(data["b1"][0]), len(data["b2"][0]), data["learning_rate"])
        for name in ("w1", "b1", "w2", "b2", "w3", "b3", "mean", "std"):
            setattr(model, name, np.asarray(data[name], dtype=float))
        model.history = data.get("history", [])
        return model

