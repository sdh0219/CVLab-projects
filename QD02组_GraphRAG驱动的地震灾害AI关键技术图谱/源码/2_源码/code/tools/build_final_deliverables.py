from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


PACKAGE_NAME = "地震灾害AI防灾减灾关键技术图谱构建_提交包"

INCLUDE_PATHS = [
    "README.md",
    ".env.example",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "next.config.ts",
    "vite.config.ts",
    "eslint.config.mjs",
    "postcss.config.mjs",
    "config",
    "data/corpus",
    "docs",
    "graphrag_atlas",
    "tools",
    "app",
    "public/atlas",
    "public/favicon.svg",
    "outputs/graphrag_index",
]

EXCLUDE_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "llm_cache",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build final non-PPTX deliverables and clean submission package.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", default="outputs/final_deliverables")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = (root / args.output_dir).resolve()
    export_dir = root / "outputs" / "graphrag_index" / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    context = load_context(root, export_dir)
    report_md = build_final_report(context)
    report_path = output_dir / "final_report.md"
    report_path.write_text(report_md, encoding="utf-8")
    html_path = output_dir / "final_report.html"
    html_path.write_text(markdown_to_html(report_md), encoding="utf-8")
    checklist_path = output_dir / "submission_checklist.md"
    checklist_path.write_text(build_submission_checklist(context), encoding="utf-8")

    package_dir = output_dir / PACKAGE_NAME
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    copied_files = copy_submission_files(root, package_dir)
    extra_docs_dir = package_dir / "docs" / "final"
    extra_docs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(report_path, extra_docs_dir / "final_report.md")
    shutil.copy2(html_path, extra_docs_dir / "final_report.html")
    shutil.copy2(checklist_path, extra_docs_dir / "submission_checklist.md")

    package_manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "package_name": PACKAGE_NAME,
        "source_root": str(root),
        "summary": context["summary"],
        "included_file_count": len(copied_files) + 3,
        "included_roots": INCLUDE_PATHS,
        "excluded": sorted(EXCLUDE_PARTS | {"node_modules", ".wrangler", ".idea", "dist", "build", "dev-server*.log"}),
        "notes": [
            "未生成PPTX。",
            "专家审核表为待审核结构，不能表述为已完成人工专家评审。",
            "提交包排除了依赖缓存、IDE配置、运行缓存和日志。",
        ],
    }
    (package_dir / "SUBMISSION_PACKAGE_MANIFEST.json").write_text(
        json.dumps(package_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (package_dir / "SUBMISSION_README.md").write_text(build_package_readme(context), encoding="utf-8")

    zip_path = output_dir / f"{PACKAGE_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    zip_directory(package_dir, zip_path)

    result = {
        "final_report": str(report_path),
        "final_report_html": str(html_path),
        "checklist": str(checklist_path),
        "package_dir": str(package_dir),
        "zip_path": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "included_file_count": package_manifest["included_file_count"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def load_context(root: Path, export_dir: Path) -> dict[str, Any]:
    summary = read_json(root / "outputs" / "graphrag_index" / "index_summary.json")
    quality = read_json(export_dir / "atlas_quality_report.json")
    tech_assessment = read_json(export_dir / "key_technology_assessment.json")
    uncertainty = read_json(export_dir / "uncertainty_report.json")
    submission = read_json(export_dir / "submission_manifest.json")
    topology = read_json(export_dir / "topology_communities.json")
    qa_results = read_json(export_dir / "qa_evaluation_results.json")
    export_files = sorted(path for path in export_dir.iterdir() if path.is_file())
    return {
        "summary": summary,
        "quality": quality,
        "tech_assessment": tech_assessment,
        "uncertainty": uncertainty,
        "submission": submission,
        "topology": topology,
        "qa_results": qa_results,
        "export_files": export_files,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_final_report(context: dict[str, Any]) -> str:
    summary = context["summary"]
    quality = context["quality"]
    tech_rows = context["tech_assessment"]
    uncertainty = context["uncertainty"]
    topology = context["topology"]
    qa_results = context["qa_results"]
    qa_passed = sum(1 for item in qa_results if item.get("status") == "passed")
    high_uncertainty = sum(1 for item in uncertainty.get("items", []) if item.get("risk_level") == "high")
    lines = [
        "# 地震灾害AI防灾减灾关键技术图谱构建最终成果报告",
        "",
        f"生成时间：{context['generated_at']}",
        "",
        "## 1. 项目目标",
        "",
        "本项目构建一个可运行的 GraphRAG 风格工程原型，并将研究尺度统一到地震灾害案例。系统从论文、专利、项目、政策、地震案例、标准和报告中抽取地震早期预警、震后损毁评估、应急调度、生命线风险传播和证据链问答等关键技术、应用场景、证据关系和待复核问题，形成可追溯、可问答、可更新的地震灾害关键技术图谱。",
        "",
        "## 2. 已完成成果",
        "",
        f"- 语料规模：{summary.get('documents')} 篇地震专题整理语料，覆盖 7 类来源。",
        f"- 图谱规模：{summary.get('entities')} 个实体节点，{summary.get('relations')} 条证据关系，{summary.get('claims')} 条声明。",
        f"- 社区结果：{summary.get('communities')} 个技术社区，{len(topology)} 个拓扑社区。",
        f"- 评测结果：{len(qa_results)} 条问答评测问题，其中 {qa_passed} 条通过当前覆盖度检查。",
        f"- 风险筛查：{len(uncertainty.get('items', []))} 个不确定性复核项，其中 {high_uncertainty} 个高优先级。",
        "",
        "## 3. 关键技术评分",
        "",
        "| 排名 | 技术 | 分数 | 成熟度 | 证据来源 | 缺口 |",
        "|---:|---|---:|---|---:|---|",
    ]
    for index, row in enumerate(tech_rows, start=1):
        lines.append(
            f"| {index} | {row['name']} | {row['key_tech_score']} | {row['maturity_level']} | "
            f"{row['evidence_doc_count']} | {row.get('missing_evidence') or '无规则缺口'} |"
        )
    lines.extend(
        [
            "",
            "## 4. 技术缺口",
            "",
        ]
    )
    gaps = quality.get("technology_gaps", [])
    if gaps:
        for item in gaps:
            lines.append(f"- {item['technology']}：{'；'.join(item['missing'])}")
    else:
        lines.append("- 当前规则检查未发现核心证据缺口。")
    lines.extend(
        [
            "",
            "## 5. 拓扑社区",
            "",
            "| 社区 | 标题 | 成员数 | 关系数 | 摘要 |",
            "|---|---|---:|---:|---|",
        ]
    )
    for item in topology:
        lines.append(
            f"| {item['topology_community_id']} | {item['title']} | {item['member_count']} | "
            f"{item['relation_count']} | {item['summary']} |"
        )
    lines.extend(
        [
            "",
            "## 6. 可复现命令",
            "",
            "```bash",
            "npm.cmd run atlas:refresh",
            "npm.cmd run lint",
            "npm.cmd run build",
            "npm.cmd run atlas:package",
            "```",
            "",
            "## 7. 边界说明",
            "",
            "- 当前专家审核表和专家预审优先级表是待审核结构，不代表已完成人工专家评审。",
        "- 当前社区报告以规则化证据聚合为主，拓扑社区为加权标签传播结果，后续可接入正式 Leiden 或 Microsoft GraphRAG 社区发现。",
            "- 语料正文为面向抽取的中文整理稿，不是原文全文转载；正式论文或报告引用时应回到 `corpus_manifest.csv` 中的来源 URL 核对。",
            "- Neo4j 导入文件已经生成，但仍需在真实 Neo4j 实例中执行和验收。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_submission_checklist(context: dict[str, Any]) -> str:
    summary = context["summary"]
    lines = [
        "# 提交前检查清单",
        "",
        "- [x] 规则索引已生成。",
        f"- [x] 文档数量为 {summary.get('documents')}。",
        f"- [x] 实体节点为 {summary.get('entities')}。",
        f"- [x] 证据关系为 {summary.get('relations')}。",
        "- [x] 前端快照已生成。",
        "- [x] Neo4j CSV、GraphML、可视化 JSON 已生成。",
        "- [x] 关键技术评分、QA 评测和不确定性报告已生成。",
        "- [x] 未生成 PPTX。",
        "- [ ] 如需正式提交，请确认教师是否要求 Word/PDF 报告。",
        "- [ ] 如需声称专家评审完成，请先人工填写 `expert_review_log.csv`。",
        "- [ ] 如需声称 Neo4j 已部署，请先在真实 Neo4j 实例执行 `neo4j_import.cypher` 并截图留证。",
        "",
    ]
    return "\n".join(lines)


def build_package_readme(context: dict[str, Any]) -> str:
    summary = context["summary"]
    return "\n".join(
        [
            "# 地震灾害AI防灾减灾关键技术图谱构建提交包",
            "",
            "本提交包为自动整理后的干净成果目录，不包含 `node_modules`、构建缓存、IDE配置和运行日志。",
            "",
            "## 快速复现",
            "",
            "```bash",
            "npm.cmd install",
            "npm.cmd run atlas:refresh",
            "npm.cmd run build",
            "```",
            "",
            "## 当前规模",
            "",
            f"- 文档：{summary.get('documents')}",
            f"- 实体：{summary.get('entities')}",
            f"- 声明：{summary.get('claims')}",
            f"- 关系：{summary.get('relations')}",
            f"- 技术社区：{summary.get('communities')}",
            "",
            "## 重点查看",
            "",
            "- `docs/final/final_report.md`",
            "- `outputs/graphrag_index/exports/submission_manifest.md`",
            "- `outputs/graphrag_index/exports/key_technology_assessment.md`",
            "- `outputs/graphrag_index/exports/uncertainty_report.md`",
            "- `outputs/graphrag_index/exports/atlas.graphml`",
            "",
        ]
    )


def markdown_to_html(markdown: str) -> str:
    body_lines = []
    in_code = False
    in_ul = False
    table_buffer: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            if in_code:
                body_lines.append("</code></pre>")
                in_code = False
            else:
                close_list(body_lines, in_ul)
                in_ul = False
                body_lines.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            body_lines.append(html.escape(line))
            continue
        if line.startswith("|"):
            table_buffer.append(line)
            continue
        flush_table(body_lines, table_buffer)
        if line.startswith("# "):
            close_list(body_lines, in_ul)
            in_ul = False
            body_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            close_list(body_lines, in_ul)
            in_ul = False
            body_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not in_ul:
                body_lines.append("<ul>")
                in_ul = True
            body_lines.append(f"<li>{html.escape(line[2:])}</li>")
        elif not line:
            close_list(body_lines, in_ul)
            in_ul = False
        else:
            close_list(body_lines, in_ul)
            in_ul = False
            body_lines.append(f"<p>{html.escape(line)}</p>")
    flush_table(body_lines, table_buffer)
    close_list(body_lines, in_ul)
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>地震灾害AI防灾减灾关键技术图谱构建最终成果报告</title>",
            "<style>",
            "body{font-family:Arial,'Microsoft YaHei',sans-serif;line-height:1.75;color:#172026;max-width:1120px;margin:32px auto;padding:0 24px;background:#fff}",
            "h1{font-size:30px} h2{font-size:22px;margin-top:28px} table{border-collapse:collapse;width:100%;margin:14px 0} th,td{border:1px solid #d7ded8;padding:8px;vertical-align:top} th{background:#eef4ef} code,pre{background:#f6f8f7} pre{padding:12px;overflow:auto}",
            "</style>",
            "</head>",
            "<body>",
            *body_lines,
            "</body>",
            "</html>",
        ]
    )


def flush_table(body_lines: list[str], table_buffer: list[str]) -> None:
    if not table_buffer:
        return
    rows = [parse_markdown_table_row(line) for line in table_buffer if not set(line.replace("|", "").strip()) <= {"-", ":"}]
    if rows:
        body_lines.append("<table>")
        for row_index, row in enumerate(rows):
            tag = "th" if row_index == 0 else "td"
            body_lines.append("<tr>" + "".join(f"<{tag}>{html.escape(cell)}</{tag}>" for cell in row) + "</tr>")
        body_lines.append("</table>")
    table_buffer.clear()


def parse_markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def close_list(body_lines: list[str], in_ul: bool) -> None:
    if in_ul:
        body_lines.append("</ul>")


def copy_submission_files(root: Path, package_dir: Path) -> list[Path]:
    copied: list[Path] = []
    for relative in INCLUDE_PATHS:
        source = root / relative
        if not source.exists():
            continue
        target = package_dir / relative
        if source.is_dir():
            for path in source.rglob("*"):
                if path.is_file() and not should_exclude(path):
                    dest = target / path.relative_to(source)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, dest)
                    copied.append(dest)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(target)
    return copied


def should_exclude(path: Path) -> bool:
    return any(part in EXCLUDE_PARTS for part in path.parts)


def zip_directory(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir.parent))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
