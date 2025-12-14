# -*- coding: utf-8 -*-
"""
签章识别器 - StampDetector

从提取的图片中识别签章：
- 按尺寸筛选可能是签章的图片（签章通常为正方形或接近正方形）
- 检测红色比例（印章通常是红色，手写签名通常是黑色/蓝色）
- 使用点积方式计算图片相似度
- 相似度高于阈值的认为是相同签章，只保留一张用于视觉模型处理
"""

import os
import logging
import shutil
import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

try:
    from PIL import Image
except ImportError:
    Image = None


class StampDetector:
    """签章识别器 - 识别并去重签章图片"""
    
    def __init__(self,
                 min_size: int = 30,
                 max_size: int = 1000,
                 aspect_ratio_range: Tuple[float, float] = (0.7, 1.5),
                 similarity_threshold: float = 0.95,
                 resize_for_compare: Tuple[int, int] = (64, 64),
                 red_ratio_threshold: float = 0.80):
        """
        初始化签章识别器
        
        Args:
            min_size: 签章图片最小边长（像素）
            max_size: 签章图片最大边长（像素）
            aspect_ratio_range: 签章图片宽高比范围 (min_ratio, max_ratio)
            similarity_threshold: 相似度阈值（0-1），高于此值认为是相同签章
            resize_for_compare: 用于相似度比较时调整的图片尺寸
            red_ratio_threshold: 红色像素比例阈值，高于此值才认为是印章（用于区分手写签名）
        """
        self.logger = logging.getLogger(__name__)
        self.min_size = min_size
        self.max_size = max_size
        self.aspect_ratio_range = aspect_ratio_range
        self.similarity_threshold = similarity_threshold
        self.resize_for_compare = resize_for_compare
        self.red_ratio_threshold = red_ratio_threshold
        
        if Image is None:
            self.logger.warning("PIL未安装，签章识别功能将受限")
        
        # 初始化日志已移除（调试时可取消注释）
        # self.logger.debug(f"签章识别器初始化: size=[{min_size}, {max_size}], threshold={similarity_threshold}")
    
    def filter_stamp_candidates(self, 
                               images_info: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        按尺寸和颜色筛选可能是签章的图片
        
        筛选条件：
        1. 尺寸在指定范围内
        2. 宽高比在指定范围内
        3. 包含足够比例的红色像素（印章通常是红色的）
        
        Args:
            images_info: 图片信息列表，每个元素包含：
                - path: 图片路径
                - page: 页码
                - width: 宽度
                - height: 高度
                
        Returns:
            (签章候选列表, 非签章图片列表)
        """
        stamp_candidates = []
        non_stamp_images = []
        size_filtered_count = 0
        color_filtered_count = 0
        size_filtered_details = []  # 记录被尺寸过滤的图片尺寸
        
        for img_info in images_info:
            width = img_info.get('width', 0)
            height = img_info.get('height', 0)
            
            if width == 0 or height == 0:
                # 尝试从文件读取尺寸
                try:
                    width, height = self._get_image_size(img_info['path'])
                    img_info['width'] = width
                    img_info['height'] = height
                except Exception as e:
                    self.logger.warning(f"无法获取图片尺寸: {img_info['path']}, 错误: {e}")
                    non_stamp_images.append(img_info)
                    continue
            
            # 检查尺寸范围
            min_dim = min(width, height)
            max_dim = max(width, height)
            
            if min_dim < self.min_size or max_dim > self.max_size:
                non_stamp_images.append(img_info)
                size_filtered_count += 1
                # 记录被尺寸过滤的图片详情
                size_filtered_details.append({
                    'name': os.path.basename(img_info['path']),
                    'width': width,
                    'height': height,
                    'reason': 'too_small' if min_dim < self.min_size else 'too_large'
                })
                continue
            
            # 检查宽高比
            aspect_ratio = width / height if height > 0 else 0
            min_ratio, max_ratio = self.aspect_ratio_range
            
            if aspect_ratio < min_ratio or aspect_ratio > max_ratio:
                non_stamp_images.append(img_info)
                size_filtered_count += 1
                self.logger.debug(f"宽高比过滤: {os.path.basename(img_info['path'])}, "
                                 f"宽高比: {aspect_ratio:.2f}, "
                                 f"范围要求: [{min_ratio}, {max_ratio}]")
                continue
            
            # 检查红色比例（区分印章和手写签名）
            red_ratio = self._detect_red_ratio(img_info['path'])
            img_info['red_ratio'] = red_ratio
            
            if red_ratio < self.red_ratio_threshold:
                # 红色比例过低，可能是手写签名而非印章
                non_stamp_images.append(img_info)
                color_filtered_count += 1
                self.logger.debug(f"因红色比例过低被过滤: {os.path.basename(img_info['path'])}, "
                                 f"红色比例: {red_ratio:.4f} < 阈值: {self.red_ratio_threshold}")
                continue
            
            # 符合签章特征（尺寸+颜色）
            stamp_candidates.append(img_info)
            self.logger.debug(f"识别为签章: {os.path.basename(img_info['path'])}, "
                             f"尺寸: {width}x{height}, 红色比例: {red_ratio:.4f}")
        
        # 尺寸过滤详情日志已移除（调试时可取消注释）
        # if size_filtered_details:
        #     too_small = [d for d in size_filtered_details if d['reason'] == 'too_small']
        #     too_large = [d for d in size_filtered_details if d['reason'] == 'too_large']
        #     self.logger.debug(f"尺寸过滤详情: 过小({len(too_small)}张), 过大({len(too_large)}张)")
        
        # 签章筛选日志已移除
        
        return stamp_candidates, non_stamp_images
    
    def _get_image_size(self, image_path: str) -> Tuple[int, int]:
        """
        获取图片尺寸
        
        Args:
            image_path: 图片路径
            
        Returns:
            (width, height)
        """
        if Image is None:
            raise ImportError("PIL未安装")
        
        with Image.open(image_path) as img:
            return img.size
    
    def _detect_red_ratio(self, image_path: str) -> float:
        """
        检测图片中红色像素的比例（用于区分印章和手写签名）
        
        印章通常是红色的，手写签名通常是黑色或蓝色
        
        Args:
            image_path: 图片路径
            
        Returns:
            红色像素占有效像素（非白色、非黑色）的比例（0-1）
        """
        if Image is None:
            return 0.0
        
        try:
            with Image.open(image_path) as img:
                # 强制转换为 RGB 模式（处理各种图片格式：P模式、CMYK等）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                img_array = np.array(img)
                total_pixels = img_array.shape[0] * img_array.shape[1]
                
                # 获取 RGB 通道
                r = img_array[:, :, 0].astype(np.int32)
                g = img_array[:, :, 1].astype(np.int32)
                b = img_array[:, :, 2].astype(np.int32)
                
                # 排除白色背景（R, G, B 都大于 240）
                non_white = ~((r > 240) & (g > 240) & (b > 240))
                
                # 排除黑色/深灰色（R, G, B 都小于 60）
                non_black = ~((r < 60) & (g < 60) & (b < 60))
                
                # 有效像素：非白色且非黑色
                valid_mask = non_white & non_black
                valid_count = np.sum(valid_mask)
                
                if valid_count == 0:
                    return 0.0
                
                # 红色像素判断条件（非常宽松）：
                # 只要 R 通道明显高于 G 和 B 就认为是红色调
                # 条件1: R > G 且 R > B 且 R >= 100（基本红色）
                red_basic = (r > g) & (r > b) & (r >= 100)
                
                # 条件2: R 比 G 和 B 都大至少 20（更明显的红色）
                red_dominant = (r > g + 20) & (r > b + 20) & (r >= 80)
                
                # 条件3: 典型印章红（R高，G和B相对低）
                red_stamp = (r >= 150) & (g < 200) & (b < 200) & (r > g) & (r > b)
                
                # 条件4: 浅红/粉红（R高，但G和B也不太低）
                red_pink = (r >= 180) & (r > g) & (r > b) & ((r - g) > 10) & ((r - b) > 10)
                
                # 合并所有红色条件
                red_mask = (red_basic | red_dominant | red_stamp | red_pink) & valid_mask
                red_count = np.sum(red_mask)
                
                # 红色占有效像素的比例
                red_ratio = red_count / valid_count
                
                # 红色检测调试日志已移除
                
                return float(red_ratio)
                
        except Exception as e:
            self.logger.warning(f"红色检测失败: {image_path}, 错误: {e}")
            return 0.0
    
    def _image_to_vector(self, image_path: str) -> Optional[np.ndarray]:
        """
        将图片转换为向量（用于相似度计算）
        
        Args:
            image_path: 图片路径
            
        Returns:
            归一化的图片向量，如果失败返回None
        """
        if Image is None:
            return None
        
        try:
            with Image.open(image_path) as img:
                # 转换为灰度图
                img_gray = img.convert('L')
                
                # 调整到统一尺寸
                img_resized = img_gray.resize(self.resize_for_compare, Image.Resampling.LANCZOS)
                
                # 转换为numpy数组并展平
                img_array = np.array(img_resized, dtype=np.float32).flatten()
                
                # 归一化（用于点积计算余弦相似度）
                norm = np.linalg.norm(img_array)
                if norm > 0:
                    img_array = img_array / norm
                
                return img_array
                
        except Exception as e:
            self.logger.warning(f"图片转向量失败: {image_path}, 错误: {e}")
            return None
    
    def calculate_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        使用点积计算两个向量的余弦相似度
        
        Args:
            vector1: 归一化的图片向量1
            vector2: 归一化的图片向量2
            
        Returns:
            相似度值（0-1）
        """
        # 点积计算余弦相似度（因为向量已归一化）
        similarity = np.dot(vector1, vector2)
        
        # 确保结果在[0, 1]范围内
        return max(0.0, min(1.0, float(similarity)))
    
    def group_similar_stamps(self, 
                            stamp_candidates: List[Dict]) -> List[List[Dict]]:
        """
        将相似的签章分组
        
        Args:
            stamp_candidates: 签章候选列表
            
        Returns:
            分组后的签章列表，每组包含相似的签章
        """
        if not stamp_candidates:
            return []
        
        # 计算所有签章的向量
        vectors = []
        valid_candidates = []
        
        for candidate in stamp_candidates:
            vector = self._image_to_vector(candidate['path'])
            if vector is not None:
                vectors.append(vector)
                valid_candidates.append(candidate)
        
        if not valid_candidates:
            self.logger.warning("无法提取任何签章向量")
            return [[c] for c in stamp_candidates]  # 每个签章单独一组
        
        # 使用并查集进行分组
        n = len(valid_candidates)
        parent = list(range(n))
        
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # 计算所有对之间的相似度
        for i in range(n):
            for j in range(i + 1, n):
                similarity = self.calculate_similarity(vectors[i], vectors[j])
                if similarity >= self.similarity_threshold:
                    union(i, j)
                    self.logger.debug(f"签章相似: {os.path.basename(valid_candidates[i]['path'])} "
                                     f"<-> {os.path.basename(valid_candidates[j]['path'])}, "
                                     f"相似度: {similarity:.4f}")
        
        # 根据并查集结果分组
        groups = defaultdict(list)
        for i in range(n):
            groups[find(i)].append(valid_candidates[i])
        
        result = list(groups.values())
        
        self.logger.info(f"签章分组完成: {len(valid_candidates)}张候选签章 -> {len(result)}组")
        
        return result
    
    def deduplicate_stamps(self, 
                          stamp_candidates: List[Dict]) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
        """
        对签章进行去重，返回每组签章的代表图片
        
        Args:
            stamp_candidates: 签章候选列表
            
        Returns:
            (去重后的签章列表（每组一张代表），相似签章映射（代表图片路径 -> 同组其他签章列表）)
        """
        if not stamp_candidates:
            return [], {}
        
        # 分组相似签章
        groups = self.group_similar_stamps(stamp_candidates)
        
        unique_stamps = []
        similar_stamps_map = {}
        
        for group in groups:
            if not group:
                continue
            
            # 选择第一张作为代表
            representative = group[0]
            unique_stamps.append(representative)
            
            # 记录同组的其他签章
            if len(group) > 1:
                similar_stamps_map[representative['path']] = group[1:]
        
        self.logger.info(f"签章去重完成: {len(stamp_candidates)}张 -> {len(unique_stamps)}张唯一签章")
        
        return unique_stamps, similar_stamps_map
    
    def detect_and_deduplicate(self, 
                              images_info: List[Dict]) -> Dict:
        """
        完整的签章检测和去重流程
        
        Args:
            images_info: 图片信息列表
            
        Returns:
            结果字典：
            - stamp_candidates: 所有签章候选
            - unique_stamps: 去重后的唯一签章
            - non_stamp_images: 非签章图片
            - similar_stamps_map: 相似签章映射
            - statistics: 统计信息
        """
        result = {
            'stamp_candidates': [],
            'unique_stamps': [],
            'non_stamp_images': [],
            'similar_stamps_map': {},
            'statistics': {}
        }
        
        if not images_info:
            return result
        
        # 1. 筛选签章候选
        stamp_candidates, non_stamp_images = self.filter_stamp_candidates(images_info)
        result['stamp_candidates'] = stamp_candidates
        result['non_stamp_images'] = non_stamp_images
        
        # 2. 去重签章
        if stamp_candidates:
            unique_stamps, similar_stamps_map = self.deduplicate_stamps(stamp_candidates)
            result['unique_stamps'] = unique_stamps
            result['similar_stamps_map'] = similar_stamps_map
        
        # 3. 统计信息
        result['statistics'] = {
            'total_images': len(images_info),
            'stamp_candidates_count': len(stamp_candidates),
            'unique_stamps_count': len(result['unique_stamps']),
            'duplicated_stamps_count': len(stamp_candidates) - len(result['unique_stamps']),
            'non_stamp_count': len(non_stamp_images)
        }
        
        # 签章检测完成日志已移除
        
        return result
    
    def save_stamps_to_directory(self,
                                stamp_detection_result: Dict,
                                output_dir: str,
                                save_all_candidates: bool = False) -> str:
        """
        保存签章图片到指定目录
        
        Args:
            stamp_detection_result: detect_and_deduplicate 返回的结果
            output_dir: 输出目录
            save_all_candidates: 是否保存所有候选签章（True）还是只保存去重后的唯一签章（False）
            
        Returns:
            签章保存目录路径
        """
        os.makedirs(output_dir, exist_ok=True)
        
        stamps_to_save = (stamp_detection_result['stamp_candidates'] 
                         if save_all_candidates 
                         else stamp_detection_result['unique_stamps'])
        
        saved_count = 0
        for idx, stamp_info in enumerate(stamps_to_save, 1):
            src_path = stamp_info['path']
            page_num = stamp_info['page']
            ext = os.path.splitext(src_path)[1]
            
            if save_all_candidates:
                dst_filename = f"stamp_candidate_{idx}_page_{page_num}{ext}"
            else:
                dst_filename = f"stamp_{idx}_page_{page_num}{ext}"
            
            dst_path = os.path.join(output_dir, dst_filename)
            
            try:
                shutil.copy2(src_path, dst_path)
                saved_count += 1
            except Exception as e:
                self.logger.warning(f"保存签章图片失败: {src_path} -> {dst_path}, 错误: {e}")
        
        self.logger.info(f"保存{saved_count}张签章图片到: {output_dir}")
        
        return output_dir
    
    def get_stamps_for_vision_processing(self, 
                                        images_info: List[Dict]) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]], Dict]:
        """
        获取需要发送给视觉模型处理的图片列表
        
        对于签章：相似度高的只发送一张代表
        对于非签章：全部发送
        
        Args:
            images_info: 图片信息列表，每个元素包含 path 和 page
            
        Returns:
            (签章代表列表[(path, page), ...], 非签章列表[(path, page), ...], 检测结果详情)
        """
        detection_result = self.detect_and_deduplicate(images_info)
        
        # 转换为 (path, page) 格式
        stamp_images = [(img['path'], img['page']) for img in detection_result['unique_stamps']]
        non_stamp_images = [(img['path'], img['page']) for img in detection_result['non_stamp_images']]
        
        return stamp_images, non_stamp_images, detection_result

