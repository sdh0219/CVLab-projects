from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "osm_disaster_pipeline.example.json"


class PipelineGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("救援路径规划一键生成工具")
        self.geometry("1080x760")
        self.minsize(940, 660)

        self.config_path = tk.StringVar(value=str(DEFAULT_CONFIG))
        self.scenario_id = tk.StringVar(value="-")
        self.scenario_name = tk.StringVar(value="-")
        self.disaster_type = tk.StringVar(value="-")
        self.start_target = tk.StringVar(value="-")
        self.output_hint = tk.StringVar(value="-")

        self.overwrite = tk.BooleanVar(value=False)
        self.no_cache = tk.BooleanVar(value=False)
        self.skip_fetch = tk.BooleanVar(value=False)
        self.skip_planning = tk.BooleanVar(value=False)
        self.skip_visual = tk.BooleanVar(value=False)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None
        self.worker: threading.Thread | None = None

        self._build_ui()
        self._load_config_preview()
        self.after(150, self._drain_log_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        title = ttk.Label(self, text="真实路网 + 历史灾害 + Dijkstra 流水线", font=("Microsoft YaHei UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w", padx=24, pady=(20, 6))

        subtitle = ttk.Label(
            self,
            text="选择一个 JSON 配置文件后，一键抓取 OSM 路网、生成数据、运行 Dijkstra，并输出用于汇报的摘要和路线图。",
            foreground="#4B5563",
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=24, pady=(0, 16))

        config_frame = ttk.LabelFrame(self, text="配置文件")
        config_frame.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        config_frame.columnconfigure(0, weight=1)

        config_entry = ttk.Entry(config_frame, textvariable=self.config_path)
        config_entry.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=12)
        config_entry.bind("<FocusOut>", lambda _event: self._load_config_preview())
        config_entry.bind("<Return>", lambda _event: self._load_config_preview())

        ttk.Button(config_frame, text="选择...", command=self._choose_config).grid(row=0, column=1, padx=(0, 8), pady=12)
        ttk.Button(config_frame, text="重新读取", command=self._load_config_preview).grid(row=0, column=2, padx=(0, 12), pady=12)

        preview_frame = ttk.LabelFrame(self, text="当前场景预览")
        preview_frame.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.columnconfigure(3, weight=1)

        self._preview_row(preview_frame, 0, "场景 ID", self.scenario_id, "灾害类型", self.disaster_type)
        self._preview_row(preview_frame, 1, "场景名称", self.scenario_name, "起点终点", self.start_target)
        ttk.Label(preview_frame, text="输出位置").grid(row=2, column=0, sticky="w", padx=(12, 8), pady=(4, 12))
        ttk.Label(preview_frame, textvariable=self.output_hint, foreground="#374151").grid(
            row=2, column=1, columnspan=3, sticky="w", padx=(0, 12), pady=(4, 12)
        )

        middle = ttk.Frame(self)
        middle.grid(row=4, column=0, sticky="nsew", padx=24, pady=(0, 12))
        middle.columnconfigure(0, weight=0)
        middle.columnconfigure(1, weight=1)
        middle.rowconfigure(0, weight=1)

        options = ttk.LabelFrame(middle, text="运行选项")
        options.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        ttk.Checkbutton(options, text="允许覆盖已有同名场景", variable=self.overwrite).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 6)
        )
        ttk.Checkbutton(options, text="强制重新抓取 OSM 数据", variable=self.no_cache).grid(
            row=1, column=0, sticky="w", padx=12, pady=6
        )
        ttk.Checkbutton(options, text="只使用本地缓存", variable=self.skip_fetch).grid(
            row=2, column=0, sticky="w", padx=12, pady=6
        )
        ttk.Checkbutton(options, text="只生成数据，不跑 Dijkstra", variable=self.skip_planning).grid(
            row=3, column=0, sticky="w", padx=12, pady=6
        )
        ttk.Checkbutton(options, text="不生成路线图", variable=self.skip_visual).grid(
            row=4, column=0, sticky="w", padx=12, pady=6
        )

        ttk.Separator(options).grid(row=5, column=0, sticky="ew", padx=12, pady=12)
        self.run_button = ttk.Button(options, text="开始生成", command=self._start_pipeline)
        self.run_button.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.stop_button = ttk.Button(options, text="停止运行", command=self._stop_pipeline, state="disabled")
        self.stop_button.grid(row=7, column=0, sticky="ew", padx=12, pady=(0, 8))
        ttk.Button(options, text="打开数据目录", command=self._open_data_dir).grid(row=8, column=0, sticky="ew", padx=12, pady=(12, 8))
        ttk.Button(options, text="打开结果目录", command=self._open_output_dir).grid(row=9, column=0, sticky="ew", padx=12, pady=(0, 8))
        ttk.Button(options, text="打开路线图", command=self._open_visual).grid(row=10, column=0, sticky="ew", padx=12, pady=(0, 12))

        log_frame = ttk.LabelFrame(middle, text="运行日志")
        log_frame.grid(row=0, column=1, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, wrap="word", height=20, bg="#0F172A", fg="#E5E7EB", insertbackground="#E5E7EB")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        footer = ttk.Label(
            self,
            text="提示：本界面不会保存任何 API Key。OSM 抓取需要联网；如果只想用缓存，请先勾选“只使用本地缓存”。",
            foreground="#6B7280",
        )
        footer.grid(row=5, column=0, sticky="w", padx=24, pady=(0, 16))

    def _preview_row(
        self,
        parent: ttk.Frame,
        row: int,
        label_a: str,
        value_a: tk.StringVar,
        label_b: str,
        value_b: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label_a).grid(row=row, column=0, sticky="w", padx=(12, 8), pady=(12 if row == 0 else 4, 4))
        ttk.Label(parent, textvariable=value_a, foreground="#374151").grid(
            row=row, column=1, sticky="w", padx=(0, 16), pady=(12 if row == 0 else 4, 4)
        )
        ttk.Label(parent, text=label_b).grid(row=row, column=2, sticky="w", padx=(0, 8), pady=(12 if row == 0 else 4, 4))
        ttk.Label(parent, textvariable=value_b, foreground="#374151").grid(
            row=row, column=3, sticky="w", padx=(0, 12), pady=(12 if row == 0 else 4, 4)
        )

    def _choose_config(self) -> None:
        path = filedialog.askopenfilename(
            title="选择流水线配置文件",
            initialdir=str(ROOT / "configs"),
            filetypes=[("JSON 配置", "*.json"), ("所有文件", "*.*")],
        )
        if path:
            self.config_path.set(path)
            self._load_config_preview()

    def _read_config(self) -> dict:
        path = Path(self.config_path.get())
        if not path.is_absolute():
            path = ROOT / path
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_config_preview(self) -> None:
        try:
            config = self._read_config()
            scenario_id = str(config.get("scenario_id", "-"))
            start = config.get("start", {})
            target = config.get("target", {})
            disaster = config.get("disaster", {})
            self.scenario_id.set(scenario_id)
            self.scenario_name.set(str(config.get("scenario_name", scenario_id)))
            self.disaster_type.set(str(disaster.get("type", "-")))
            self.start_target.set(f"{start.get('name', 'START')} -> {target.get('name', 'TARGET')}")
            self.output_hint.set(f"data\\{scenario_id}    outputs\\{scenario_id}")
        except Exception as exc:
            self.scenario_id.set("-")
            self.scenario_name.set("-")
            self.disaster_type.set("-")
            self.start_target.set("-")
            self.output_hint.set("-")
            self._append_log(f"[warn] 配置预览读取失败：{exc}\n")

    def _build_command(self) -> list[str]:
        python_exe = ROOT / ".venv" / "Scripts" / "python.exe"
        if not python_exe.exists():
            python_exe = Path(sys.executable)

        config_path = Path(self.config_path.get())
        if not config_path.is_absolute():
            config_path = ROOT / config_path

        command = [
            str(python_exe),
            "-u",
            str(ROOT / "tools" / "run_osm_disaster_pipeline.py"),
            "--config",
            str(config_path),
        ]
        if self.overwrite.get():
            command.append("--overwrite")
        if self.no_cache.get():
            command.append("--no-cache")
        if self.skip_fetch.get():
            command.append("--skip-fetch")
        if self.skip_planning.get():
            command.append("--skip-planning")
        if self.skip_visual.get():
            command.append("--skip-visual")
        return command

    def _start_pipeline(self) -> None:
        if self.process is not None:
            messagebox.showinfo("正在运行", "当前已经有流水线在运行。")
            return
        try:
            self._read_config()
        except Exception as exc:
            messagebox.showerror("配置错误", f"配置文件无法读取：\n{exc}")
            return

        command = self._build_command()
        self._append_log("\n" + "=" * 76 + "\n")
        self._append_log("[cmd] " + " ".join(command) + "\n")
        self._set_running(True)
        self.worker = threading.Thread(target=self._run_worker, args=(command,), daemon=True)
        self.worker.start()

    def _run_worker(self, command: list[str]) -> None:
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.log_queue.put(line)
            return_code = self.process.wait()
            if return_code == 0:
                self.log_queue.put("\n[ok] 生成完成。\n")
            else:
                self.log_queue.put(f"\n[error] 运行失败，退出码：{return_code}\n")
        except Exception as exc:
            self.log_queue.put(f"\n[error] 无法启动流水线：{exc}\n")
        finally:
            self.process = None
            self.log_queue.put("__PIPELINE_DONE__")

    def _stop_pipeline(self) -> None:
        if self.process is None:
            return
        if messagebox.askyesno("停止运行", "确定要停止当前流水线吗？"):
            self.process.terminate()
            self._append_log("\n[warn] 已请求停止当前运行。\n")

    def _set_running(self, running: bool) -> None:
        self.run_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item == "__PIPELINE_DONE__":
                    self._set_running(False)
                else:
                    self._append_log(item)
        except queue.Empty:
            pass
        self.after(150, self._drain_log_queue)

    def _append_log(self, text: str) -> None:
        self.log_text.insert("end", text)
        self.log_text.see("end")

    def _scenario_path(self, parent: str) -> Path | None:
        try:
            config = self._read_config()
            scenario_id = str(config["scenario_id"])
            return ROOT / parent / scenario_id
        except Exception as exc:
            messagebox.showerror("配置错误", f"无法读取场景 ID：\n{exc}")
            return None

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            messagebox.showwarning("文件不存在", f"还没有生成：\n{path}")
            return
        os.startfile(str(path))

    def _open_data_dir(self) -> None:
        path = self._scenario_path("data")
        if path:
            self._open_path(path)

    def _open_output_dir(self) -> None:
        path = self._scenario_path("outputs")
        if path:
            self._open_path(path)

    def _open_visual(self) -> None:
        path = self._scenario_path("outputs")
        if not path:
            return
        visual = path / "route_map_abstract.png"
        self._open_path(visual)


def main() -> None:
    app = PipelineGui()
    app.mainloop()


if __name__ == "__main__":
    main()
