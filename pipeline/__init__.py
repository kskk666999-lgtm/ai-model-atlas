"""AI Model Atlas 数据流水线。

纯确定性数据处理：HTTP 抓取 → 校验 → 规范化 → 排名 → 静态 JSON。
全程不调用任何生成式大模型 API。
"""

__version__ = "0.1.0"
