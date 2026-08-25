"""仅用Python标准库提供本地网页演示。"""
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from analyzer import EmergencyAnalyzer

analyzer = EmergencyAnalyzer()
EXAMPLE = "8月24日16时20分，滨海化工园区3号仓库冒出黄色烟雾，有明显刺鼻气味，2人受伤，当前东南风3级。"


def render_page(text=EXAMPLE, result=None):
    details = ""
    if result:
        advice = "".join(f"<li>{escape(item)}</li>" for item in result["advice"])
        people = "、".join(result["people"])
        details = f'''<div class="card"><h2>结构化研判</h2><div class="grid">
<div>事件类型：<b>{escape(result['event_type'])}</b></div><div>置信度：{result['confidence']:.1%}</div>
<div>风险程度：<span class="high">{result['severity']}</span></div><div>时间：{escape(result['time'])}</div>
<div>地点：{escape(result['location'])}</div><div>人员：{escape(people)}</div><div>风向：{escape(result['wind'])}</div></div>
<h3>建议处置</h3><ol>{advice}</ol><div class="warning">{escape(result['warning'])}</div></div>'''
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Transformer应急研判</title><style>
body{{font-family:Arial,"Microsoft YaHei";max-width:980px;margin:35px auto;background:#f3f6f9;color:#19324a}}
.card{{background:white;padding:24px;margin:16px 0;border-radius:12px;box-shadow:0 3px 14px #ccd5dd}}
textarea{{width:100%;height:120px;padding:12px;box-sizing:border-box;font-size:16px}}button{{background:#176b87;color:white;border:0;padding:11px 25px;border-radius:6px;font-size:16px}}
.high{{color:#c33;font-weight:bold}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.warning{{background:#fff5df;padding:12px;border-left:5px solid #ef9d22}}</style></head>
<body><h1>Transformer 应急事件自动研判</h1><div class="card"><form method="post"><textarea name="text">{escape(text)}</textarea><p><button>开始研判</button></p></form></div>{details}</body></html>'''


class Handler(BaseHTTPRequestHandler):
    def respond(self, html):
        data = html.encode("utf-8"); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self): self.respond(render_page())
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0)); form = parse_qs(self.rfile.read(length).decode("utf-8"))
        text = form.get("text", [""])[0].strip(); self.respond(render_page(text, analyzer.analyze(text) if text else None))
    def log_message(self, format, *args): return


if __name__ == "__main__":
    print("网页演示已启动: http://127.0.0.1:5000")
    HTTPServer(("127.0.0.1", 5000), Handler).serve_forever()
