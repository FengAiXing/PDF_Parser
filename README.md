# PDF 解析工具

PDF 完整解析：文本提取 + 表格识别（含跨页）+ 图片 OCR + 签章识别

---

## 快速使用

```python
from File_handle import FileProcessor

# 解析 PDF
result = FileProcessor().process_pdf_full(pdf_path="your_file.pdf")

# 获取合并后的文本
if result['success']:
    content = result['final_content']
```

---

## 参数说明

```python
result = processor.process_pdf_full(
    pdf_path="file.pdf",               # 必填：PDF 文件路径
    output_dir="output_complete",       # 输出目录
    save_table_images=True,             # 保存表格图片
    save_single_table_results=True,     # 保存单张表格结果
    remove_header_footer=True,          # 移除页眉页脚
    enable_stamp_detection=True         # 启用签章识别
)
```

---

## 返回值

| 字段 | 说明 |
|------|------|
| `success` | 是否成功 |
| `final_content` | **合并后的完整文本** |
| `final_output` | 输出文件路径 |
| `statistics` | 统计信息（页数、表格数等） |
| `error` | 错误信息 |

---

## 功能开关

修改 `config/config.py` 启用/禁用解析功能：

```python
class Config:
    # 功能开关
    ENABLE_TABLE_PARSING = True      # 表格解析
    ENABLE_IMAGE_PARSING = True      # 图片解析（提取+OCR）
    ENABLE_STAMP_DETECTION = True    # 签章识别
    ENABLE_STAMP_PARSING = True      # 签章解析（OCR读取签章内容）
```

| 场景 | 配置 |
|------|------|
| 只解析文本 | 全部设为 `False` |
| 文本+表格 | `ENABLE_TABLE_PARSING=True`，其他 `False` |
| 文本+图片（无签章） | `ENABLE_IMAGE_PARSING=True`，`ENABLE_STAMP_DETECTION=False` |
| 识别签章但不解析 | `ENABLE_STAMP_DETECTION=True`，`ENABLE_STAMP_PARSING=False` |

---

## 保存开关

```python
class Config:
    # 保存总开关
    ENABLE_ALL_SAVES = False         # False=不保存任何文件
    
    # 单项保存开关
    SAVE_FINAL_RESULT = True         # 最终解析结果 (.txt)
    SAVE_TABLE_IMAGES = True         # 表格图片 (.png)
    SAVE_SINGLE_TABLE_RESULTS = True # 单张表格结果 (.txt)
    SAVE_EXTRACTED_IMAGES = True     # 提取的图片
    SAVE_STAMP_IMAGES = True         # 签章图片
```

---

## 安装依赖

```bash
pip install -r requirements.txt
```

---
