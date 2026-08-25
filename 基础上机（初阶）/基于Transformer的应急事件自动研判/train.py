import json
import random
from pathlib import Path
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from model import EventTransformer

ROOT = Path("."); LABELS = ["fire", "flood", "earthquake", "chemical_leak", "landslide", "other"]


class TextDataset(Dataset):
    def __init__(self, rows, vocab, max_length=128): self.rows, self.vocab, self.max_length = rows, vocab, max_length
    def __len__(self): return len(self.rows)
    def __getitem__(self, index):
        row = self.rows[index]; ids = [self.vocab.get(char, 1) for char in row["text"][:self.max_length]]
        ids += [0] * (self.max_length - len(ids))
        return torch.tensor(ids), torch.tensor(LABELS.index(row["label"]))


def main():
    random.seed(42); torch.manual_seed(42)
    rows = [json.loads(line) for line in (ROOT / "data/events.jsonl").read_text(encoding="utf-8").splitlines()]
    random.shuffle(rows); split = int(len(rows) * 0.8); train_rows, val_rows = rows[:split], rows[split:]
    chars = sorted(set("".join(row["text"] for row in train_rows))); vocab = {char: i + 2 for i, char in enumerate(chars)}
    train_loader = DataLoader(TextDataset(train_rows, vocab), batch_size=32, shuffle=True)
    val_loader = DataLoader(TextDataset(val_rows, vocab), batch_size=64)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = EventTransformer(len(vocab) + 2, len(LABELS)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01); criterion = nn.CrossEntropyLoss()
    best_acc = 0.0
    for epoch in range(1, 16):
        model.train(); total_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device); optimizer.zero_grad(); loss = criterion(model(x), y)
            loss.backward(); optimizer.step(); total_loss += loss.item() * len(y)
        model.eval(); correct = total = 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device); correct += (model(x).argmax(1) == y).sum().item(); total += len(y)
        acc = correct / total
        if acc > best_acc:
            best_acc = acc; torch.save({"model_state": model.state_dict(), "vocab": vocab, "labels": LABELS,
                "max_length": 128, "d_model": 64, "nhead": 4, "layers": 2}, ROOT / "event_transformer.pt")
        print(f"Epoch {epoch:02d}/15 | train loss={total_loss/len(train_rows):.4f} | val acc={acc:.2%}")
    print(f"\n数据: {len(rows)}条 | 设备: {device} | 最佳验证准确率: {best_acc:.2%}")


if __name__ == "__main__": main()

