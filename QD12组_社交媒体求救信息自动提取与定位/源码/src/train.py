"""训练脚本: 训练 BERT NER 模型。

流程:
  1. 加载 train/dev 数据集
  2. 构建 BertNER 模型 (BERT + Linear + CRF)
  3. 训练: AdamW + warmup, 每个 epoch 在 dev 上评估
  4. 保存 dev F1 最高的 checkpoint

训练过程全程记录:
  - 终端实时输出 (tqdm + 每 epoch 汇总)
  - 日志文件 outputs/reports/train_log.txt (永久保存, 含时间戳)
  - 训练历史 outputs/reports/train_history.json (便于画曲线)
  - 训练曲线图 outputs/reports/training_curve.png (直接放 PPT)

用法:
    python -m src.train                 # 用 config.py 默认参数
    python -m src.train --epochs 5      # 自定义
    python -m src.train --no_crf        # 不使用 CRF (对比实验)
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.config import (
    BEST_CKPT_DIR, BERT_MODEL_NAME, DEV_FILE, DEVICE, EVAL_BATCH,
    GRAD_CLIP, LEARNING_RATE, MAX_LEN, NUM_EPOCHS, REPORTS_DIR, SEED,
    TRAIN_BATCH, TRAIN_FILE, USE_CRF, WEIGHT_DECAY, WARMUP_RATIO,
    ensure_dirs, print_config,
)
from src.data.dataset import Collater, NERDataset
from src.evaluate import compute_metrics


# ==================================================================
# 日志系统: 同时输出到终端和文件
# ==================================================================
LOG_FILE = REPORTS_DIR / "train_log.txt"
HISTORY_FILE = REPORTS_DIR / "train_history.json"
CURVE_FILE = REPORTS_DIR / "training_curve.png"
TB_DIR = REPORTS_DIR / "tensorboard"  # TensorBoard 日志目录


def setup_logger() -> logging.Logger:
    """配置 logger: 同时输出到终端和文件。"""
    ensure_dirs()
    logger = logging.getLogger("train")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("[%(asctime)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # 终端
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 文件 (追加模式, 保留多次训练历史)
    fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def to_native(obj):
    """递归把 numpy 类型转成 Python 原生类型, 以便 JSON 序列化。

    seqeval 返回的 support 等字段是 numpy.int64, 标准 json.dump 不支持。
    """
    import numpy as _np
    if isinstance(obj, dict):
        return {k: to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_native(x) for x in obj]
    if isinstance(obj, _np.integer):
        return int(obj)
    if isinstance(obj, _np.floating):
        return float(obj)
    if isinstance(obj, _np.ndarray):
        return to_native(obj.tolist())
    return obj


def evaluate(model, loader, device) -> dict:
    model.eval()
    all_preds, all_golds = [], []
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items()}
        pred_ids = model.decode(batch["input_ids"], batch["attention_mask"],
                                batch.get("token_type_ids"))
        for i, preds in enumerate(pred_ids):
            gold_ids = batch["labels"][i].tolist()
            gold_seq = [g for g in gold_ids if g != -100]
            n = min(len(preds), len(gold_seq))
            all_preds.append(preds[:n])
            all_golds.append(gold_seq[:n])
    return compute_metrics(all_preds, all_golds)


def get_linear_warmup_scheduler(optimizer, num_warmup, num_total):
    from torch.optim.lr_scheduler import LambdaLR
    def lr_lambda(cur):
        if cur < num_warmup:
            return float(cur) / float(max(1, num_warmup))
        return max(0.0, float(num_total - cur) / float(max(1, num_total - num_warmup)))
    return LambdaLR(optimizer, lr_lambda)


def plot_training_curve(history: list[dict], save_path: Path) -> None:
    """画训练曲线图: loss + dev F1 (双 Y 轴)。"""
    try:
        import matplotlib
        matplotlib.use("Agg")  # 无界面后端
        import matplotlib.pyplot as plt
    except ImportError:
        print("[!] matplotlib 未安装, 跳过画图")
        return

    # 中文字体 (Windows: 微软雅黑 / SimHei)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei",
                                        "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    epochs = [h["epoch"] for h in history]
    losses = [h["train_loss"] for h in history]
    f1s = [h["dev_f1"] for h in history]
    ps = [h["dev_precision"] for h in history]
    rs = [h["dev_recall"] for h in history]

    fig, ax1 = plt.subplots(figsize=(9, 5))

    color_loss = "#1f77b4"
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("训练 Loss", color=color_loss)
    ax1.plot(epochs, losses, color=color_loss, marker="o",
             label="Train Loss", linewidth=2)
    ax1.tick_params(axis="y", labelcolor=color_loss)
    ax1.set_xticks(epochs)

    ax2 = ax1.twinx()
    ax2.set_ylabel("Dev 指标", color="#d62728")
    ax2.plot(epochs, f1s, color="#d62728", marker="s",
             label="Dev F1", linewidth=2)
    ax2.plot(epochs, ps, color="#2ca02c", marker="^",
             label="Dev Precision", linestyle="--", alpha=0.7)
    ax2.plot(epochs, rs, color="#ff7f0e", marker="v",
             label="Dev Recall", linestyle="--", alpha=0.7)
    ax2.tick_params(axis="y", labelcolor="#d62728")

    # 标记最佳 F1
    if f1s:
        best_idx = int(np.argmax(f1s))
        ax2.annotate(f"Best F1={f1s[best_idx]:.4f}",
                     xy=(epochs[best_idx], f1s[best_idx]),
                     xytext=(epochs[best_idx], max(f1s[best_idx] - 0.08, 0.0)),
                     arrowprops=dict(color="black", shrink=0.05),
                     fontsize=10, ha="center",
                     bbox=dict(boxstyle="round,pad=0.3",
                               fc="yellow", alpha=0.5))

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="center right")
    plt.title(f"训练曲线 (BERT{'+CRF' if USE_CRF else ''} NER)")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()


def train(args) -> None:
    ensure_dirs()
    set_seed(SEED)
    logger = setup_logger()

    # 训练会话分隔 (便于在日志文件里区分多次运行)
    logger.info("=" * 70)
    logger.info("新训练会话开始 / New training session")
    logger.info("=" * 70)
    print_config()
    logger.info(f"参数: epochs={args.epochs} batch={args.batch_size} "
                f"lr={args.lr} no_crf={args.no_crf}")

    # ---- TensorBoard 初始化 ----
    from torch.utils.tensorboard import SummaryWriter
    # 每次 run 一个独立子目录 (带时间戳), 便于多次实验对比
    import datetime
    run_subdir = datetime.datetime.now().strftime("run_%Y%m%d_%H%M%S")
    if args.no_crf:
        run_subdir += "_nocrf"
    tb_run_dir = TB_DIR / run_subdir
    tb_run_dir.mkdir(parents=True, exist_ok=True)
    writer = SummaryWriter(log_dir=str(tb_run_dir))
    logger.info(f"    TensorBoard 日志: {tb_run_dir}")
    # 记录训练配置到 TensorBoard TEXT
    writer.add_text("config/epochs", str(args.epochs))
    writer.add_text("config/batch_size", str(args.batch_size))
    writer.add_text("config/learning_rate", str(args.lr))
    writer.add_text("config/use_crf", str((not args.no_crf) and USE_CRF))
    writer.add_text("config/seed", str(SEED))
    writer.add_text("config/model", BERT_MODEL_NAME)

    # ---- 1. tokenizer + 数据 ----
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(BERT_MODEL_NAME)

    logger.info(f"[1] 加载数据: train={TRAIN_FILE}, dev={DEV_FILE}")
    train_ds = NERDataset(TRAIN_FILE, tokenizer, MAX_LEN)
    dev_ds = NERDataset(DEV_FILE, tokenizer, MAX_LEN)
    logger.info(f"    train={len(train_ds)}, dev={len(dev_ds)}")
    writer.add_text("data/train_size", str(len(train_ds)))
    writer.add_text("data/dev_size", str(len(dev_ds)))

    collate = Collater(tokenizer)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size,
                              shuffle=True, collate_fn=collate)
    dev_loader = DataLoader(dev_ds, batch_size=EVAL_BATCH,
                            shuffle=False, collate_fn=collate)

    # ---- 2. 模型 ----
    from src.models.bert_ner import BertNER
    use_crf = (not args.no_crf) and USE_CRF
    logger.info(f"[2] 构建模型 (use_crf={use_crf})")
    model = BertNER(use_crf=use_crf).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"    可训练参数: {n_params/1e6:.2f}M")
    writer.add_text("config/num_params_M", f"{n_params/1e6:.2f}")
    # 记录模型计算图 (用一个样本)
    try:
        sample = next(iter(train_loader))
        sample = {k: v.to(DEVICE) for k, v in sample.items()}
        writer.add_graph(model, input=(sample["input_ids"][:2],
                                       sample["attention_mask"][:2]),
                         verbose=False)
    except Exception as e:
        logger.info(f"    [跳过] 模型图记录失败 (CRF 不支持 trace): {e}")


    # ---- 3. 优化器 ----
    no_decay = ["bias", "LayerNorm.weight"]
    grouped = [
        {"params": [p for n, p in model.named_parameters()
                    if not any(nd in n for nd in no_decay)],
         "weight_decay": WEIGHT_DECAY},
        {"params": [p for n, p in model.named_parameters()
                    if any(nd in n for nd in no_decay)],
         "weight_decay": 0.0},
    ]
    optimizer = torch.optim.AdamW(grouped, lr=args.lr)
    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * WARMUP_RATIO)
    scheduler = get_linear_warmup_scheduler(optimizer, warmup_steps, total_steps)
    logger.info(f"    总 steps={total_steps}, warmup={warmup_steps}")

    # ---- 4. 训练循环 ----
    best_f1 = 0.0
    history: list[dict] = []   # 每个 epoch 的指标, 用于画曲线
    logger.info(f"[3] 开始训练 (device={DEVICE}, epochs={args.epochs})")

    global_step = 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0 = time.time()
        total_loss = 0.0
        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{args.epochs}",
                    ncols=90)
        for batch in pbar:
            batch = {k: v.to(DEVICE) for k, v in batch.items()}
            loss = model.loss(batch["input_ids"], batch["attention_mask"],
                              batch["labels"], batch.get("token_type_ids"))
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optimizer.step()
            scheduler.step()
            total_loss += loss.item()
            pbar.set_postfix(loss=f"{loss.item():.4f}")
            # TensorBoard: 每个 step 记录 loss 和学习率 (实时曲线)
            writer.add_scalar("train/loss_step", loss.item(), global_step)
            writer.add_scalar("train/learning_rate",
                              scheduler.get_last_lr()[0], global_step)
            global_step += 1
        avg_loss = total_loss / len(train_loader)

        # ---- 评估 ----
        metrics = evaluate(model, dev_loader, DEVICE)
        dt = time.time() - t0
        logger.info(
            f"Epoch {epoch:2d}/{args.epochs}: loss={avg_loss:.4f} | "
            f"dev P={metrics['precision']:.4f} R={metrics['recall']:.4f} "
            f"F1={metrics['f1']:.4f}  ({dt:.1f}s)"
        )
        # 分类型细节 (INFO 级, 文件里看得到)
        for t, m in metrics["per_type"].items():
            logger.info(f"           {t}: P={m['P']:.4f} R={m['R']:.4f} "
                        f"F1={m['F1']:.4f} support={m['support']}")

        # ---- TensorBoard: 每 epoch 记录指标 ----
        writer.add_scalar("train/loss_epoch", avg_loss, epoch)
        writer.add_scalar("dev/precision", metrics["precision"], epoch)
        writer.add_scalar("dev/recall", metrics["recall"], epoch)
        writer.add_scalar("dev/f1", metrics["f1"], epoch)
        for t, m in metrics["per_type"].items():
            writer.add_scalar(f"dev_f1_by_type/{t}", m["F1"], epoch)
            writer.add_scalar(f"dev_precision_by_type/{t}", m["P"], epoch)
            writer.add_scalar(f"dev_recall_by_type/{t}", m["R"], epoch)

        # 记录历史
        history.append({
            "epoch": epoch,
            "train_loss": avg_loss,
            "dev_precision": metrics["precision"],
            "dev_recall": metrics["recall"],
            "dev_f1": metrics["f1"],
            "per_type": metrics["per_type"],
            "time_sec": dt,
        })
        # 每轮都写一次 history (防止中断丢失)
        with HISTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(to_native({"config": {"epochs": args.epochs, "lr": args.lr,
                                  "batch_size": args.batch_size,
                                  "use_crf": use_crf, "seed": SEED},
                       "history": history}),
                      f, ensure_ascii=False, indent=2)
        # 每轮都画一次曲线 (增量更新)
        plot_training_curve(history, CURVE_FILE)

        # ---- 保存最佳 ----
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            model.save(BEST_CKPT_DIR)
            tokenizer.save_pretrained(BEST_CKPT_DIR)
            with (BEST_CKPT_DIR / "train_config.json").open("w", encoding="utf-8") as f:
                json.dump({"use_crf": use_crf, "epochs": args.epochs,
                           "lr": args.lr, "batch_size": args.batch_size,
                           "best_f1": best_f1, "best_epoch": epoch,
                           "seed": SEED}, f, ensure_ascii=False, indent=2)
            logger.info(f"  ** 新最佳 dev F1={best_f1:.4f}, "
                        f"已保存到 {BEST_CKPT_DIR}")

    # ---- 训练结束汇总 ----
    # TensorBoard: 记录超参 + 最终指标 (HPARAMS 面板, 便于多次实验对比)
    writer.add_hparams(
        hparam_dict={"lr": args.lr, "batch_size": args.batch_size,
                     "epochs": args.epochs, "use_crf": use_crf},
        metric_dict={"hparam/best_dev_f1": best_f1},
    )
    writer.add_text("result/best_dev_f1", f"{best_f1:.4f}")
    writer.add_text("result/global_steps", str(global_step))
    writer.close()

    logger.info("=" * 70)
    logger.info(f"训练完成! 最佳 dev F1 = {best_f1:.4f}")
    logger.info(f"  历史记录: {HISTORY_FILE}")
    logger.info(f"  训练曲线: {CURVE_FILE}")
    logger.info(f"  完整日志: {LOG_FILE}")
    logger.info(f"  TensorBoard: {tb_run_dir}")
    logger.info(f"  查看方法: tensorboard --logdir \"{TB_DIR}\"")
    logger.info(f"  最佳模型: {BEST_CKPT_DIR}")
    logger.info("=" * 70)


def parse_args():
    p = argparse.ArgumentParser(description="训练 BERT NER 模型")
    p.add_argument("--epochs", type=int, default=NUM_EPOCHS)
    p.add_argument("--batch_size", type=int, default=TRAIN_BATCH)
    p.add_argument("--lr", type=float, default=LEARNING_RATE)
    p.add_argument("--no_crf", action="store_true",
                   help="不使用 CRF (用于对比实验)")
    return p.parse_args()


if __name__ == "__main__":
    train(parse_args())
