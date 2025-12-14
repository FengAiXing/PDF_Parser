import os
from typing import Any, List, Optional

from PIL import Image

from .merge_table_images import merge_table_images


def merge_multiple_table_images(
    merger: Any, image_paths: List[str], output_dir: str, filename: str
) -> Optional[str]:
    """
    合并多个表格图片（垂直拼接，支持2张以上）

    Args:
        merger: CrossPageTableMerger 实例
        image_paths: 表格图片路径列表
        output_dir: 输出目录
        filename: 输出文件名

    Returns:
        合并后的图片路径
    """
    try:
        if len(image_paths) == 0:
            raise ValueError("图片列表为空")

        if len(image_paths) == 1:
            # 只有一张图片，直接返回
            return image_paths[0]

        if len(image_paths) == 2:
            # 两张图片，使用原有方法
            return merge_table_images(merger, image_paths[0], image_paths[1], output_dir, filename)

        # 多于两张图片，逐一拼接
        images = [Image.open(path) for path in image_paths]

        # 找到最大宽度
        max_width = max(img.width for img in images)

        # 调整所有图片宽度一致
        resized_images = []
        for img in images:
            if img.width != max_width:
                resized_img = img.resize((max_width, img.height), Image.Resampling.LANCZOS)
                resized_images.append(resized_img)
            else:
                resized_images.append(img)

        # 计算总高度
        total_height = sum(img.height for img in resized_images)

        # 创建新图片
        merged_img = Image.new("RGB", (max_width, total_height), "white")

        # 逐一粘贴图片
        current_y = 0
        for img in resized_images:
            merged_img.paste(img, (0, current_y))
            current_y += img.height

        # 保存合并后的图片
        merged_path = os.path.join(output_dir, f"{filename}.png")
        merged_img.save(merged_path)
        return merged_path

    except Exception as e:
        merger.logger.error(f"合并多张表格图片失败: {e}")
        # 失败时返回第一张图片
        return image_paths[0] if image_paths else None

