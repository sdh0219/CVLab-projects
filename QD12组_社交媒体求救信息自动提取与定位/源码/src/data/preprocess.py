"""文本清洗: 处理微博/评论风格噪声。

清洗规则:
  - 去除 URL (http/https)
  - 去除 @用户 (保留@后面的提及, 因为本任务关注求救内容本身)
  - 规范化 #话题# -> 去掉井号, 保留话题词 (话题常含地点/灾种关键词)
  - 去除 emoji / 控制字符 / 多余空白
  - 繁简转换 -> 简体 (用 opencc)

注意: 本任务中部分实体(如电话号码)需要保留, 因此不能粗暴去除所有数字/符号。
"""
from __future__ import annotations

import re

# 延迟导入 opencc (可选)
_t2s = None
try:
    from opencc import OpenCC
    _t2s = OpenCC("t2s")  # 繁体 -> 简体
except Exception:  # pragma: no cover
    _t2s = None

# 正则模式
URL_RE = re.compile(r"https?://\S+|www\.\S+")
AT_RE = re.compile(r"@[^\s@:：]+")           # @用户名
HASH_RE = re.compile(r"#([^#]+)#")           # #话题# -> 话题词
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # 表情符号
    "\U0001F300-\U0001F5FF"  # 符号和象形文字
    "\U0001F680-\U0001F6FF"  # 交通和地图符号
    "\U0001F1E0-\U0001F1FF"  # 旗帜
    "\U00002700-\U000027BF"  # 装饰符号
    "\U0001F900-\U0001F9FF"  # 补充表情符号
    "\U00002600-\U000026FF"  # 杂项符号
    "]"
)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")  # 控制字符
WHITESPACE_RE = re.compile(r"\s+")                          # 多空白合一
# 重复标点压缩: 把 "！！！！" -> "！" (保留语气, 但不超过2个)
REPEAT_PUNCT_RE = re.compile(r"([!?。！？，,]){3,}")


def clean_text(text: str, keep_at: bool = False) -> str:
    """清洗单条文本。

    Args:
        text: 原始文本
        keep_at: 是否保留 @用户 (默认 False, 求救信息通常不依赖@)
    Returns:
        清洗后的文本
    """
    if not text:
        return ""

    # 1. URL
    text = URL_RE.sub(" ", text)
    # 2. @用户
    if not keep_at:
        text = AT_RE.sub(" ", text)
    # 3. #话题# -> 话题词 (保留关键词, 对实体抽取有帮助)
    text = HASH_RE.sub(lambda m: m.group(1), text)
    # 4. emoji
    text = EMOJI_RE.sub(" ", text)
    # 5. 控制字符
    text = CONTROL_RE.sub("", text)
    # 6. 繁简转换
    if _t2s is not None:
        text = _t2s.convert(text)
    # 7. 压缩重复标点
    text = REPEAT_PUNCT_RE.sub(lambda m: m.group(1) * 2, text)
    # 8. 多空白合一, 去首尾空白
    text = WHITESPACE_RE.sub(" ", text).strip()

    return text


def normalize_whitespace(text: str) -> str:
    """仅做空白归一化, 不改动其他字符 (轻量版, 用于已经干净的文本)。"""
    return WHITESPACE_RE.sub(" ", text).strip()


if __name__ == "__main__":
    # 简单自测
    test_cases = [
        "救命! https://t.co/abc @人民日报 #郑州暴雨# 我们在郑州京广路隧道被淹 🆘🚨",
        "紧急求助!!   雅安芦山县地震了！！！",
    ]
    for t in test_cases:
        print(f"原始: {t}")
        print(f"清洗: {clean_text(t)}")
        print("-" * 40)
