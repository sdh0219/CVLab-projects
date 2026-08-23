from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_PPTX = ROOT / "outputs" / "manual-ppt" / "test.pptx"
OUT = ROOT / "ppt" / "基于LSTM的洪水水位预测.pptx"
PREDICTION_PLOT = ROOT / "outputs" / "prediction_plot.png"
RISK_PLOT = ROOT / "outputs" / "risk_plot.png"

EMU = 914400
SLIDE_CX = 12192000
SLIDE_CY = 6858000

C = {
    "navy": "0B1F33",
    "blue": "1261A6",
    "sky": "E8F3FA",
    "teal": "0F766E",
    "green": "16A34A",
    "orange": "F59E0B",
    "red": "DC2626",
    "ink": "172033",
    "muted": "607085",
    "line": "D8E3EA",
    "white": "FFFFFF",
    "pale": "F7FBFD",
    "cyan": "C7F9FF",
}


def emu(inches: float) -> int:
    return int(round(inches * EMU))


def esc(text: str) -> str:
    return html.escape(text, quote=True)


@dataclass
class SlideBuilder:
    shapes: list[str] = field(default_factory=list)
    rels: list[tuple[str, str]] = field(default_factory=list)
    shape_id: int = 2

    def next_id(self) -> int:
        current = self.shape_id
        self.shape_id += 1
        return current

    def rect(self, x: float, y: float, w: float, h: float, fill: str = "FFFFFF", line: str | None = None, name: str = "Shape") -> None:
        sid = self.next_id()
        ln = "<a:ln><a:noFill/></a:ln>" if line is None else f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
        self.shapes.append(
            f"""
            <p:sp>
              <p:nvSpPr><p:cNvPr id="{sid}" name="{esc(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
              <p:spPr>
                <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                <a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>
                {ln}
              </p:spPr>
            </p:sp>
            """
        )

    def text(self, body: str, x: float, y: float, w: float, h: float, size: int = 20, color: str = "172033", bold: bool = False, align: str = "l") -> None:
        sid = self.next_id()
        b = ' b="1"' if bold else ""
        paragraphs = []
        for line in body.split("\n"):
            paragraphs.append(
                f"""
                <a:p>
                  <a:pPr algn="{align}"/>
                  <a:r>
                    <a:rPr lang="zh-CN" sz="{size * 100}"{b}>
                      <a:solidFill><a:srgbClr val="{color}"/></a:solidFill>
                      <a:latin typeface="Microsoft YaHei"/>
                      <a:ea typeface="Microsoft YaHei"/>
                      <a:cs typeface="Microsoft YaHei"/>
                    </a:rPr>
                    <a:t>{esc(line)}</a:t>
                  </a:r>
                </a:p>
                """
            )
        self.shapes.append(
            f"""
            <p:sp>
              <p:nvSpPr><p:cNvPr id="{sid}" name="TextBox {sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
              <p:spPr>
                <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                <a:noFill/>
                <a:ln><a:noFill/></a:ln>
              </p:spPr>
              <p:txBody>
                <a:bodyPr wrap="square" lIns="45720" rIns="45720" tIns="22860" bIns="22860"/>
                <a:lstStyle/>
                {''.join(paragraphs)}
              </p:txBody>
            </p:sp>
            """
        )

    def metric(self, label: str, value: str, note: str, x: float, y: float, accent: str) -> None:
        self.rect(x, y, 2.55, 1.18, C["white"], C["line"])
        self.rect(x, y, 0.08, 1.18, accent, None)
        self.text(label, x + 0.22, y + 0.14, 2.1, 0.24, 13, C["muted"], True)
        self.text(value, x + 0.22, y + 0.40, 2.1, 0.38, 26, C["navy"], True)
        self.text(note, x + 0.22, y + 0.86, 2.1, 0.22, 11, C["muted"])

    def bullet(self, body: str, x: float, y: float, w: float) -> None:
        self.rect(x, y + 0.16, 0.07, 0.07, C["teal"], None)
        self.text(body, x + 0.18, y, w - 0.18, 0.55, 18, C["ink"])

    def image(self, media_name: str, x: float, y: float, w: float, h: float, rel_id: str) -> None:
        sid = self.next_id()
        self.rels.append((rel_id, f"../media/{media_name}"))
        self.shapes.append(
            f"""
            <p:pic>
              <p:nvPicPr><p:cNvPr id="{sid}" name="{esc(media_name)}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
              <p:blipFill>
                <a:blip r:embed="{rel_id}"/>
                <a:stretch><a:fillRect/></a:stretch>
              </p:blipFill>
              <p:spPr>
                <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
              </p:spPr>
            </p:pic>
            """
        )

    def header(self, title: str, page: int) -> None:
        self.text("项目5 · 基于 LSTM 的洪水水位预测", 0.58, 0.28, 5.6, 0.3, 14, C["teal"], True)
        self.text(title, 0.58, 0.62, 9.8, 0.52, 28, C["navy"], True)
        self.rect(0.58, 1.25, 12.15, 0.02, C["line"], None)
        self.text("数据来源：USGS Water Services · 站点 05464500", 0.58, 7.05, 6.2, 0.22, 10, C["muted"])
        self.text(f"{page:02d}", 12.1, 7.05, 0.55, 0.22, 10, C["muted"], align="r")

    def xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
               xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
               xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
          <p:cSld>
            <p:spTree>
              <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
              <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
              {''.join(self.shapes)}
            </p:spTree>
          </p:cSld>
          <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
        </p:sld>
        """

    def rel_xml(self) -> str:
        entries = "\n".join(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"/>'
            for rid, target in self.rels
        )
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          {entries}
        </Relationships>
        """


def build_slides() -> list[SlideBuilder]:
    slides: list[SlideBuilder] = []

    s = SlideBuilder()
    s.rect(0, 0, 13.333, 7.5, C["pale"], None)
    s.rect(0, 0, 4.85, 7.5, C["navy"], None)
    s.text("项目5", 0.70, 0.80, 2.4, 0.36, 22, "B9E6F2", True)
    s.text("基于 LSTM 的\n洪水水位预测", 0.70, 1.55, 4.0, 1.45, 38, C["white"], True)
    s.text("监测预警模块 · 真实 USGS 水文站数据", 0.72, 3.25, 3.7, 0.35, 17, "D6F2F7")
    s.text("研究对象：Cedar River at Cedar Rapids, IA\n站点编号：USGS 05464500\n预测目标：未来 24 小时水位", 0.72, 4.50, 3.75, 1.0, 18, C["white"])
    s.metric("小时级记录", "161,663", "2008-2026", 5.65, 1.55, C["blue"])
    s.metric("历史最高水位", "31.12 ft", "2008-06-13", 8.60, 1.55, C["red"])
    s.metric("预测步长", "24 h", "滑动窗口 72 h", 5.65, 3.20, C["teal"])
    s.metric("第24小时 R²", "0.973", "RMSE 0.312 ft", 8.60, 3.20, C["green"])
    s.text("真实数据 · LSTM 模型 · 误差评价 · 风险等级", 5.70, 5.55, 5.6, 0.38, 20, C["navy"], True)
    slides.append(s)

    s = SlideBuilder()
    s.header("研究区域与问题定义", 2)
    s.rect(0.65, 1.70, 5.35, 4.30, C["sky"], C["line"])
    s.text("研究区域", 0.95, 2.00, 2.4, 0.34, 22, C["navy"], True)
    s.bullet("Cedar River 位于美国 Iowa 州，Cedar Rapids 市沿河分布。", 1.0, 2.65, 4.3)
    s.bullet("2008 年发生极端洪水，站点峰值水位达到 31.12 ft。", 1.0, 3.45, 4.3)
    s.bullet("单一水文站数据易获取、易复现，适合课程项目汇报。", 1.0, 4.25, 4.3)
    s.rect(6.75, 1.70, 5.35, 4.30, C["white"], C["line"])
    s.text("预测任务", 7.05, 2.00, 2.4, 0.34, 22, C["navy"], True)
    s.text("输入", 7.25, 2.80, 0.8, 0.3, 18, C["teal"], True)
    s.text("过去 72 小时水位 + 流量", 8.35, 2.78, 3.0, 0.35, 20, C["ink"], True)
    s.text("输出", 7.25, 4.00, 0.8, 0.3, 18, C["orange"], True)
    s.text("未来 24 小时水位", 8.35, 3.98, 3.0, 0.35, 20, C["ink"], True)
    s.text("目标：提前识别水位上涨趋势，为洪水监测预警提供量化依据。", 7.1, 5.10, 4.2, 0.55, 18, C["navy"], True)
    slides.append(s)

    s = SlideBuilder()
    s.header("真实数据来源与字段", 3)
    s.metric("数据平台", "USGS", "Water Services API", 0.75, 1.75, C["blue"])
    s.metric("站点编号", "05464500", "Cedar River", 3.65, 1.75, C["teal"])
    s.metric("时间范围", "2008-2026", "小时级序列", 6.55, 1.75, C["green"])
    s.metric("最大流量", "140k cfs", "2008 洪水期", 9.45, 1.75, C["red"])
    s.rect(0.95, 3.75, 11.4, 2.20, C["white"], C["line"])
    s.text("建模字段", 1.25, 4.02, 2.2, 0.34, 22, C["navy"], True)
    s.text("00065", 1.50, 4.75, 1.2, 0.3, 20, C["blue"], True)
    s.text("Gage height（水位），单位 ft；同时换算为 m", 2.90, 4.74, 7.2, 0.3, 19)
    s.text("00060", 1.50, 5.25, 1.2, 0.3, 20, C["teal"], True)
    s.text("Discharge（流量），单位 ft³/s；作为辅助特征", 2.90, 5.24, 7.2, 0.3, 19)
    slides.append(s)

    s = SlideBuilder()
    s.header("数据处理与样本构造", 4)
    for i, (num, title, note) in enumerate([
        ("1", "下载瞬时观测", "按年请求 USGS API"),
        ("2", "小时聚合", "按 1h 计算均值"),
        ("3", "缺失处理", "线性插值补齐"),
        ("4", "归一化", "MinMaxScaler"),
        ("5", "滑动窗口", "72h 输入 → 24h 输出"),
    ]):
        x = 0.75 + i * 2.38
        s.rect(x, 2.30, 1.85, 2.15, C["sky"] if i % 2 == 0 else C["white"], C["line"])
        s.rect(x + 0.18, 2.55, 0.42, 0.42, C["teal"], None)
        s.text(num, x + 0.22, 2.61, 0.34, 0.22, 16, C["white"], True, "ctr")
        s.text(title, x + 0.18, 3.20, 1.45, 0.3, 17, C["navy"], True)
        s.text(note, x + 0.18, 3.70, 1.45, 0.45, 13, C["muted"])
        if i < 4:
            s.text("→", x + 1.90, 3.12, 0.3, 0.3, 24, C["blue"], True, "ctr")
    s.text("样本形式：X ∈ R^(72×2)，y ∈ R^24", 1.65, 5.35, 4.4, 0.34, 21, C["navy"], True)
    s.text("两个输入特征分别为水位 stage_ft 与流量 discharge_cfs。", 6.10, 5.40, 5.2, 0.3, 17, C["muted"])
    slides.append(s)

    s = SlideBuilder()
    s.header("LSTM 模型结构", 5)
    for i, (a, b) in enumerate([("输入层", "72×2"), ("LSTM", "64 units"), ("Dropout", "0.2"), ("LSTM", "32 units"), ("Dense", "32 ReLU"), ("输出层", "24 h")]):
        x = 0.85 + i * 1.95
        s.rect(x, 2.55, 1.45, 1.10, C["navy"] if i == 5 else C["white"], C["navy"] if i == 5 else C["line"])
        s.text(a, x + 0.12, 2.78, 1.2, 0.28, 17, C["white"] if i == 5 else C["navy"], True, "ctr")
        s.text(b, x + 0.12, 3.22, 1.2, 0.25, 15, C["cyan"] if i == 5 else C["teal"], True, "ctr")
        if i < 5:
            s.text("→", x + 1.50, 2.95, 0.35, 0.3, 24, C["blue"], True, "ctr")
    s.rect(1.20, 4.90, 10.85, 1.00, C["sky"], C["line"])
    s.text("训练策略", 1.50, 5.13, 1.4, 0.3, 19, C["navy"], True)
    s.text("损失函数采用 MSE，优化器采用 Adam；测试集比例 20%，用 MAE、RMSE、R² 评价预测精度。", 3.05, 5.12, 8.0, 0.38, 18)
    slides.append(s)

    s = SlideBuilder()
    s.header("模型预测效果", 6)
    s.rect(0.62, 1.62, 8.16, 4.76, C["white"], C["line"])
    s.image("prediction_plot.png", 0.65, 1.65, 8.10, 4.70, "rId1")
    s.rect(9.10, 1.72, 3.15, 4.45, C["white"], C["line"])
    s.text("测试集指标", 9.40, 2.00, 2.0, 0.3, 22, C["navy"], True)
    s.text("第 1 小时", 9.42, 2.72, 1.2, 0.25, 15, C["muted"], True)
    s.text("R² 0.992\nMAE 0.101 ft", 9.42, 3.03, 2.3, 0.7, 22, C["blue"], True)
    s.text("第 24 小时", 9.42, 4.13, 1.5, 0.25, 15, C["muted"], True)
    s.text("R² 0.973\nRMSE 0.312 ft", 9.42, 4.45, 2.4, 0.7, 22, C["teal"], True)
    s.text("结论：LSTM 能较好跟踪水位峰谷变化，短时预测精度更高。", 9.35, 5.55, 2.55, 0.45, 15, C["ink"], True)
    slides.append(s)

    s = SlideBuilder()
    s.header("未来 24 小时水位与风险等级", 7)
    s.rect(0.62, 1.62, 8.06, 4.76, C["white"], C["line"])
    s.image("risk_plot.png", 0.65, 1.65, 8.00, 4.70, "rId1")
    s.rect(8.95, 1.70, 3.35, 4.55, C["white"], C["line"])
    s.text("风险阈值", 9.25, 2.00, 1.6, 0.3, 22, C["navy"], True)
    for i, (name, rng, color) in enumerate([("normal", "< 10 ft", C["green"]), ("action", "10-12 ft", "EAB308"), ("minor", "12-14 ft", C["orange"]), ("moderate", "14-16 ft", C["red"]), ("major", "≥ 16 ft", "7F1D1D")]):
        y = 2.65 + i * 0.45
        s.rect(9.32, y + 0.06, 0.13, 0.13, color, None)
        s.text(name, 9.62, y, 1.1, 0.25, 15, C["ink"], True)
        s.text(rng, 10.82, y, 1.0, 0.25, 15, C["muted"])
    s.text("未来 24 小时预测约 6.04-6.16 ft，风险等级为 normal。", 9.30, 5.35, 2.45, 0.55, 16, C["navy"], True)
    slides.append(s)

    s = SlideBuilder()
    s.header("结论与项目交付", 8)
    s.rect(0.80, 1.75, 5.35, 4.25, C["sky"], C["line"])
    s.text("主要结论", 1.12, 2.05, 2.0, 0.34, 22, C["navy"], True)
    s.bullet("USGS 数据开放、字段稳定，适合课程项目复现。", 1.15, 2.75, 4.2)
    s.bullet("水位 + 流量的多变量 LSTM 可完成 24 小时短时水位预测。", 1.15, 3.55, 4.2)
    s.bullet("预测曲线可接入阈值规则，形成洪水风险等级输出。", 1.15, 4.35, 4.2)
    s.rect(6.85, 1.75, 5.35, 4.25, C["white"], C["line"])
    s.text("已生成成果", 7.18, 2.05, 2.2, 0.34, 22, C["navy"], True)
    s.text("data/cedar_rapids_stage_hourly.csv\nsrc/download_usgs.py\nsrc/train_lstm.py\noutputs/prediction_plot.png\noutputs/risk_plot.png\ndocs/技术方案.md", 7.25, 2.75, 4.2, 1.95, 17, C["ink"])
    s.text("后续可加入 NASA GPM 或 ERA5 降雨数据，增强对暴雨驱动洪峰的解释能力。", 7.25, 5.25, 4.1, 0.52, 15, C["teal"], True)
    slides.append(s)

    return slides


def replace_content_types(text: str, count: int) -> str:
    text = re.sub(r'<Override PartName="/ppt/slides/slide\d+\.xml"[^>]*/>', "", text)
    insert = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, count + 1)
    )
    return text.replace("</Types>", f"{insert}</Types>")


def replace_presentation(text: str, count: int) -> str:
    slide_ids = "".join(
        f'<p:sldId id="{255 + i}" r:id="rIdSlide{i}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        for i in range(1, count + 1)
    )
    return re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>", f"<p:sldIdLst>{slide_ids}</p:sldIdLst>", text, flags=re.S)


def replace_presentation_rels(text: str, count: int) -> str:
    text = re.sub(
        r'<Relationship\b(?=[^>]*Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide")(?=[^>]*Target="[^"]*slides/slide\d+\.xml")[^>]*/>',
        "",
        text,
    )
    slide_rels = "\n".join(
        f'<Relationship Id="rIdSlide{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, count + 1)
    )
    return text.replace("</Relationships>", f"{slide_rels}</Relationships>")


def build() -> None:
    if not BASE_PPTX.exists():
        raise FileNotFoundError(f"Base PPTX not found: {BASE_PPTX}")

    slides = build_slides()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BASE_PPTX, "r") as zin, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
        skip_prefixes = ("ppt/slides/slide", "ppt/slides/_rels/slide")
        for item in zin.infolist():
            if item.filename.startswith(skip_prefixes):
                continue
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = replace_content_types(data.decode("utf-8"), len(slides)).encode("utf-8")
            elif item.filename == "ppt/presentation.xml":
                data = replace_presentation(data.decode("utf-8"), len(slides)).encode("utf-8")
            elif item.filename == "ppt/_rels/presentation.xml.rels":
                data = replace_presentation_rels(data.decode("utf-8"), len(slides)).encode("utf-8")
            zout.writestr(item, data)

        for i, slide in enumerate(slides, start=1):
            zout.writestr(f"ppt/slides/slide{i}.xml", slide.xml())
            zout.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide.rel_xml())

        zout.writestr("ppt/media/prediction_plot.png", PREDICTION_PLOT.read_bytes())
        zout.writestr("ppt/media/risk_plot.png", RISK_PLOT.read_bytes())

    print(OUT)


if __name__ == "__main__":
    build()
