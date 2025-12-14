import os
from typing import Any

from PIL import Image


def merge_table_images(
    merger: Any, image_path1: str, image_path2: str, output_dir: str, filename: str
) -> str:
    """
    合并两个表格图片（垂直拼接）

    Args:
        merger: CrossPageTableMerger 实例
        image_path1: 第一个表格图片路径
        image_path2: 第二个表格图片路径
        output_dir: 输出目录
        filename: 输出文件名

    Returns:
        合并后的图片路径
    """
    try:
        # 打开两张图片
        img1 = Image.open(image_path1)
        img2 = Image.open(image_path2)

        # 确保两张图片宽度一致
        max_width = max(img1.width, img2.width)

        # 调整图片宽度
        if img1.width != max_width:
            img1 = img1.resize((max_width, img1.height), Image.Resampling.LANCZOS)
        if img2.width != max_width:
            img2 = img2.resize((max_width, img2.height), Image.Resampling.LANCZOS)

        # 创建新图片（垂直拼接）
        total_height = img1.height + img2.height
        merged_img = Image.new("RGB", (max_width, total_height), "white")

        # 粘贴两张图片
        merged_img.paste(img1, (0, 0))
        merged_img.paste(img2, (0, img1.height))

        # 保存合并后的图片
        merged_path = os.path.join(output_dir, f"{filename}.png")
        merged_img.save(merged_path)
        return merged_path

    except Exception as e:
        merger.logger.error(f"合并表格图片失败: {e}")
        return image_path1  # 失败时返回第一张图片

