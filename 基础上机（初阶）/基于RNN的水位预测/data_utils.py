import csv
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


def load_water_levels(path):
    timestamps, levels = [], []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, skipinitialspace=True)
        for row in reader:
            try:
                timestamp = datetime.strptime(row["Date Time"].strip(), "%Y-%m-%d %H:%M")
                level = float(row["Water Level"].strip())
            except (KeyError, ValueError):
                continue
            timestamps.append(timestamp)
            levels.append(level)
    if len(levels) < 100:
        raise RuntimeError("可用水位数据太少")
    return timestamps, np.asarray(levels, dtype=np.float32)


def check_hourly_continuity(timestamps):
    return [
        (timestamps[i - 1], timestamps[i])
        for i in range(1, len(timestamps))
        if timestamps[i] - timestamps[i - 1] != timedelta(hours=1)
    ]


class SequenceDataset(Dataset):
    def __init__(self, values, sequence_length=24):
        self.values = torch.as_tensor(values, dtype=torch.float32)
        self.sequence_length = sequence_length

    def __len__(self):
        return len(self.values) - self.sequence_length

    def __getitem__(self, index):
        x = self.values[index : index + self.sequence_length].unsqueeze(-1)
        y = self.values[index + self.sequence_length]
        return x, y

