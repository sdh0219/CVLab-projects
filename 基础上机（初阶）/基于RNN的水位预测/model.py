import torch
from torch import nn


class WaterLevelRNN(nn.Module):
    """输入过去 sequence_length 个小时的水位，预测下一小时。"""

    def __init__(self, hidden_size=32, num_layers=1, dropout=0.0):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.rnn = nn.RNN(
            input_size=1,
            hidden_size=hidden_size,
            num_layers=num_layers,
            nonlinearity="tanh",
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.output = nn.Linear(hidden_size, 1)

    def forward(self, x):
        sequence_output, _ = self.rnn(x)
        return self.output(sequence_output[:, -1, :]).squeeze(1)

