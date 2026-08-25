import torch
from torch import nn


class EventTransformer(nn.Module):
    def __init__(self, vocab_size, num_classes, max_length=128, d_model=64, nhead=4, layers=2):
        super().__init__(); self.max_length = max_length
        self.token_embedding = nn.Embedding(vocab_size, d_model, padding_idx=0)
        self.position_embedding = nn.Embedding(max_length, d_model)
        layer = nn.TransformerEncoderLayer(d_model, nhead, dim_feedforward=128, dropout=0.1, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, num_layers=layers)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, tokens):
        positions = torch.arange(tokens.size(1), device=tokens.device).unsqueeze(0)
        x = self.token_embedding(tokens) + self.position_embedding(positions)
        padding = tokens.eq(0); encoded = self.encoder(x, src_key_padding_mask=padding)
        mask = (~padding).unsqueeze(-1); pooled = (encoded * mask).sum(1) / mask.sum(1).clamp(min=1)
        return self.classifier(pooled)

