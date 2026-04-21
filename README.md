# PDF_Parser

中文 | [Description](#description)

用于解析 PDF 的工具库：**文本提取**、**表格识别（含跨页合并）**、**图片 OCR**、**签章检测与解析**。针对以文本/线条为主的表格效果较好，可合并跨页表格为连贯结构，图片OCR可根据个人情况选择ocr工具或视觉模型，签章识别还只是初步的调试，后续未过多关注。

---

## Description

`PDF_Parser` extracts text, detects and parses tables (including cross-page merging), runs image OCR, and optionally detects stamps/seals. It is oriented toward **text-heavy / vector-style tables**; scanned PDFs or purely image-based documents depend more on OCR quality and model configuration.

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 文本 | 按页提取正文，支持页眉页脚移除与智能裁剪 |
| 表格 | PyMuPDF 坐标与规则解析，跨页表格检测与行合并 |
| 图片 | 从页面提取嵌入图片，可走视觉模型做 OCR |
| 签章 | 可选：候选检测、相似去重、签章区域 OCR（受 `Config` 开关控制） |

---

## 环境要求

- **Python** 3.10+（建议）
- 依赖列表见：`File_handle/requirements.txt`

---

## 安装

```bash
git clone https://github.com/FengAiXing/PDF_Parser.git
cd PDF_Parser

pip install -r File_handle/requirements.txt
```

在项目根目录运行脚本时，需保证能解析到 `File_handle` 包（可参考仓库中的 `test.py` 通过 `sys.path` 加入项目根目录）。

---

## 快速开始

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from File_handle import FileProcessor

processor = FileProcessor(
    vision_model="doubao-seed-1-6-vision-250815",  # 可按你的视觉模型服务替换
    max_workers=8,
)

result = processor.process_pdf_full(
    pdf_path="your_file.pdf",
    output_dir="output_complete",
)

if result["success"]:
    text = result["final_content"]
    print(text[:500])
else:
    print(result.get("error"))
```

更完整的命令行示例见仓库根目录 **`test.py`**（将其中 `PDF_PATH` 改为你的文件路径）。

---

## `FileProcessor.process_pdf_full` 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `pdf_path` | `str` | （必填） | PDF 文件路径 |
| `output_dir` | `str` | `"output_complete"` | 输出根目录 |
| `save_table_images` | `bool` | `True` | 是否保存表格截图（仍受 `Config` 总开关约束） |
| `save_single_table_results` | `bool` | `True` | 是否保存每张表格的识别文本文件 |
| `remove_header_footer` | `bool` | `True` | 是否移除页眉页脚 |
| `use_smart_removal` | `bool` | `True` | 是否使用基于位置的智能页眉页脚移除 |
| `enable_stamp_detection` | `bool` | `True` | 是否做签章检测（还与 `Config.ENABLE_STAMP_*` 同时生效） |
| `stamp_similarity_threshold` | `float` | `0.95` | 签章相似度阈值，用于去重 |

构造函数 **`FileProcessor(vision_model=..., max_workers=...)`** 中，`vision_model` 为视觉 OCR 使用的模型名（需与你的后端实现一致）；`max_workers` 为并发上限，请按机器性能与接口限流调整，不宜盲目拉大。

---

## 返回值

成功时 `success` 为 `True`，主要字段如下：

| 字段 | 说明 |
|------|------|
| `success` | 是否解析成功 |
| `final_content` | 合并后的完整文本（按页组织后的整篇内容） |
| `final_output` | 最终 `.txt` 结果路径（若允许保存） |
| `tables_dir` | 表格图片目录 |
| `images_dir` | 提取图片目录 |
| `single_table_results_dir` | 单张表格识别结果目录 |
| `image_ocr_results_dir` | 单张图片 OCR 结果目录（若有） |
| `stamps_dir` | 签章图片目录（若启用且存在签章） |
| `stamp_detection` | 签章检测详细结果（若启用） |
| `statistics` | 耗时、页数、表格数、图片数及签章统计等 |
| `error` | 失败时的错误信息字符串 |

失败时 `success` 为 `False`，请查看 `error`。

---

## 功能与保存开关（`Config`）

全局开关在 **`File_handle/config/config.py`** 的 `Config` 类中，例如：

- **功能**：`ENABLE_TABLE_PARSING`、`ENABLE_IMAGE_PARSING`、`ENABLE_STAMP_DETECTION`、`ENABLE_STAMP_PARSING`
- **保存**：`ENABLE_ALL_SAVES` 为总开关；另有 `SAVE_FINAL_RESULT`、`SAVE_TABLE_IMAGES` 等分项

典型搭配：

| 需求 | 建议 |
|------|------|
| 只要文本 | 关闭表格/图片/签章相关功能开关 |
| 文本 + 表格 | 仅开启 `ENABLE_TABLE_PARSING` |
| 文本 + 图片 OCR | 开启 `ENABLE_IMAGE_PARSING`，按需关闭签章 |
| 识别签章但不 OCR 签章内容 | `ENABLE_STAMP_DETECTION=True`，`ENABLE_STAMP_PARSING=False` |

修改后无需改业务代码即可影响 `FileProcessor` 行为。

---

## 异步接口

若在 **已有 asyncio 事件循环** 的环境（如 Jupyter、部分 Web 框架）中调用，`process_pdf_full` 会报错并提示使用异步版本。请改为在同一循环中 **`await processor.process_pdf_full_async(...)`**，参数与 `process_pdf_full` 一致。

---

## 项目结构（节选）

```
PDF_Parser/
├── test.py                 # 示例入口
├── README.md
└── File_handle/
    ├── requirements.txt
    ├── config/             # Config 与功能/保存开关
    ├── parsers/            # 粗解析、表格、视觉解析
    ├── table/              # 跨页表格合并等
    ├── image/              # 图片提取、签章检测
    ├── utils/              # 文档拼装、PDF/文本工具
    ├── file_processor.py   # 一站式完整流程
    └── main_parser.py      # 粗解析 / 视觉解析等组合接口
```

---

## 安全与隐私

- 默认的 `vision_model` 名称仅表示一种模型 ID 占位，**请在自有环境中替换为实际服务支持的模型名**，并自行对接合规的 AI 服务。

---

## 许可证

本项目采用 **MIT License**，完整条文见仓库根目录 [`LICENSE`](LICENSE)。

- 允许商业与非商业使用、复制、修改、合并、发布、再许可及销售。
- 分发时须保留版权声明与许可全文；软件按「原样」提供，作者不承担任何担保或赔偿责任。

---

## 贡献与反馈

欢迎通过 [Issues](https://github.com/FengAiXing/PDF_Parser/issues) 反馈缺陷或需求；