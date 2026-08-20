from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "dpf"
PNG_PATH = OUTPUT_DIR / "gbdt_principle_flowchart_hd.png"
PDF_PATH = OUTPUT_DIR / "gbdt_principle_flowchart_hd.pdf"


def configure_matplotlib() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 180
    plt.rcParams["savefig.dpi"] = 360


def add_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    lines: list[str],
    color: str,
    title_size: float = 15,
    body_size: float = 10.5,
) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.016,rounding_size=0.018",
            linewidth=1.8,
            edgecolor=color,
            facecolor="#FFFFFF",
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (x + 0.012, y + h - 0.062),
            w - 0.024,
            0.046,
            boxstyle="round,pad=0.01,rounding_size=0.014",
            linewidth=0,
            facecolor=color,
            alpha=0.96,
        )
    )
    ax.text(
        x + w / 2,
        y + h - 0.039,
        title,
        ha="center",
        va="center",
        fontsize=title_size,
        color="white",
        weight="bold",
    )
    for idx, line in enumerate(lines):
        ax.text(
            x + 0.025,
            y + h - 0.095 - idx * 0.042,
            line,
            ha="left",
            va="center",
            fontsize=body_size,
            color="#263747",
        )


def add_arrow(ax, start: tuple[float, float], end: tuple[float, float], color: str = "#3E4C59") -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=24,
            lw=2.3,
            color=color,
            shrinkA=5,
            shrinkB=5,
        )
    )


def draw_flowchart() -> None:
    configure_matplotlib()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(18, 10), facecolor="white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.955,
        "梯度提升树模型原理流程图",
        ha="center",
        va="center",
        fontsize=30,
        weight="bold",
        color="#1c304d",
    )
    ax.text(
        0.5,
        0.908,
        "核心思想：多棵弱决策树按顺序训练，后一棵树重点修正前一轮的预测误差，最终加权集成得到预测结果",
        ha="center",
        va="center",
        fontsize=15,
        color="#5A6573",
    )

    add_box(
        ax,
        0.035,
        0.67,
        0.22,
        0.17,
        "1. 输入训练数据",
        [
            "X：灾害强度、损失、GDP、产业结构等特征",
            "y：恢复周期类别 0-4",
            "样本：地震事件 + 区域年份经济表现",
        ],
        "#2E86AB",
    )
    add_box(
        ax,
        0.305,
        0.67,
        0.18,
        0.17,
        "2. 初始预测",
        [
            "先给出一个基础预测 F0",
            "分类任务通常来自类别先验概率",
            "后续每轮都在此基础上修正",
        ],
        "#6A994E",
    )
    add_box(
        ax,
        0.535,
        0.67,
        0.20,
        0.17,
        "3. 计算误差方向",
        [
            "比较真实标签和当前预测",
            "得到损失函数的负梯度",
            "可理解为“下一步该往哪里改”",
        ],
        "#F18F01",
    )
    add_box(
        ax,
        0.785,
        0.67,
        0.18,
        0.17,
        "4. 训练第 m 棵树",
        [
            "用一棵小决策树拟合误差",
            "树深较浅，单棵树是弱学习器",
            "重点学习上一轮没学好的样本",
        ],
        "#C73E1D",
    )

    add_box(
        ax,
        0.135,
        0.34,
        0.22,
        0.17,
        "5. 更新模型",
        [
            "把新树加入已有模型",
            "学习率控制每棵树的贡献",
            "公式：Fm(x) = Fm-1(x) + η hm(x)",
        ],
        "#5B8C5A",
    )
    add_box(
        ax,
        0.405,
        0.34,
        0.20,
        0.17,
        "6. 多轮迭代提升",
        [
            "重复计算误差、训练新树、更新模型",
            "本项目使用 300 轮迭代",
            "模型逐步降低预测误差",
        ],
        "#7B5EA7",
    )
    add_box(
        ax,
        0.655,
        0.34,
        0.22,
        0.17,
        "7. 最终集成输出",
        [
            "所有树的结果累加形成强模型",
            "输出恢复周期类别和预测概率",
            "同时可计算特征重要性",
        ],
        "#3C7A89",
    )

    add_box(
        ax,
        0.07,
        0.10,
        0.25,
        0.12,
        "适合本项目的原因",
        [
            "中小规模表格数据表现稳定",
            "能处理非线性关系和特征交互",
        ],
        "#4472C4",
        title_size=14,
        body_size=10.2,
    )
    add_box(
        ax,
        0.375,
        0.10,
        0.25,
        0.12,
        "关键参数",
        [
            "n_estimators=300，learning_rate=0.05",
            "max_depth=3，subsample=0.85",
        ],
        "#ED7D31",
        title_size=14,
        body_size=10.2,
    )
    add_box(
        ax,
        0.68,
        0.10,
        0.25,
        0.12,
        "预测结果解释",
        [
            "恢复趋势预测图",
            "影响因素排序图与政策情景对比图",
        ],
        "#70AD47",
        title_size=14,
        body_size=10.2,
    )

    add_arrow(ax, (0.258, 0.755), (0.303, 0.755))
    add_arrow(ax, (0.488, 0.755), (0.533, 0.755))
    add_arrow(ax, (0.738, 0.755), (0.782, 0.755))
    add_arrow(ax, (0.875, 0.665), (0.765, 0.515), "#6B7280")
    add_arrow(ax, (0.655, 0.425), (0.608, 0.425))
    add_arrow(ax, (0.405, 0.425), (0.358, 0.425))
    add_arrow(ax, (0.245, 0.335), (0.405, 0.255), "#6B7280")
    add_arrow(ax, (0.505, 0.335), (0.655, 0.255), "#6B7280")

    ax.text(
        0.5,
        0.585,
        "逐步纠错：每一轮都关注上一轮的残差或负梯度",
        ha="center",
        va="center",
        fontsize=16,
        color="#1c304d",
        weight="bold",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#EEF4FF", edgecolor="#B8C7E6"),
    )
    ax.text(
        0.5,
        0.035,
        "一句话理解：梯度提升树不是让很多树独立投票，而是让树按顺序接力修正错误，最后组合成更强的预测模型。",
        ha="center",
        va="center",
        fontsize=13,
        color="#5A6573",
    )

    plt.tight_layout(pad=1.0)
    fig.savefig(PNG_PATH, dpi=360, bbox_inches="tight", facecolor="white")
    fig.savefig(PDF_PATH, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    draw_flowchart()
    print(f"Saved PNG: {PNG_PATH}")
    print(f"Saved PDF: {PDF_PATH}")
