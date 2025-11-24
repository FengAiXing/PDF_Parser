# 关键字截取器
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from common.variable_templates import VariableTemplateManager


class KeywordExtractor:
    """关键字截取器 - 支持多关键字连续截取"""
    
    def __init__(self):
        """初始化关键字截取器"""
        self.variable_manager = VariableTemplateManager()
        self.extraction_length = 2000  # 每个关键字后截取2000字符
        self.context_before = 20  # 每个关键字前截取20字符
    
    def extract_content_by_keywords(self, file_content: str, file_type: str, file_url: str = None) -> str:
        """
        关键字截取 - 支持多关键字连续截取
        
        Args:
            file_content: 完整的文件内容
            file_type: 文件类型
            file_url: 文件URL（用于标识）
            
        Returns:
            str: 截取后的内容，按顺序合并
        """
        try:
            logging.info(f"[关键字截取] 开始处理文件类型: {file_type}")
            
            if not file_content or len(file_content.strip()) < 10:
                logging.warning(f"[关键字截取] 文件内容为空或过短")
                return ""
            
            # 只对candidate_bid_files类型使用关键字截取
            if file_type != "candidate_bid_files":
                logging.info(f"[关键字截取] 文件类型 {file_type} 不需要关键字截取，返回原始内容")
                return file_content
            
            # 使用新的特定匹配逻辑
            extracted_content = self._extract_qualification_section(file_content, file_url)
            
            if extracted_content:
                logging.info(f"[关键字截取] 完成: 原始长度 {len(file_content)}, 截取后长度 {len(extracted_content)}")
                return extracted_content
            else:
                # 如果没有找到特定匹配，使用原来的通用截取逻辑
                logging.info(f"[关键字截取] 未找到特定匹配，使用通用截取逻辑")
                return self._fallback_extraction(file_content, file_type, file_url)
            
        except Exception as e:
            logging.error(f"[关键字截取] 失败: {e}")
            raise Exception(f"关键字截取失败: {str(e)}")
    
    def _get_keywords_for_file_type(self, file_type: str) -> List[str]:
        """
        获取文件类型对应的关键字列表
        
        Args:
            file_type: 文件类型
            
        Returns:
            List[str]: 关键字列表
        """
        try:
            # 针对candidate_bid_files使用专门的关键字
            if file_type == "candidate_bid_files":
                return [
                    "商务文件", "法定代表人", "投标保证金", "财务状况", 
                    "资格审查资料", "类似项目业绩", "业绩","合同","证书","发票",
                    "投标人基本情况表", "补充的其他资格审查资料", "近年完成的类似项目情况表",
                    "近年完成的类似项目业绩", "项目管理机构人员配备", "项目经理近年完成的类似项目业绩",
                    "投标函附录", "项目经理简历表", "简历表", "汇总表", "具体业绩", "其他商务材料",
                    "近年财务状况", "审计报告", "安全生产许可证", "补充资质材料",
                    "编号", "投标保证金"
                ]
            
            # 其他文件类型从变量模板中获取关键字
            variables = self.variable_manager.get_variables_for_file_type(file_type)
            keywords = []
            for var in variables:
                if var.keywords:
                    keywords.extend(var.keywords)
            
            # 去重并保持顺序
            return list(dict.fromkeys(keywords))
            
        except Exception as e:
            logging.error(f"获取关键字失败: {e}")
            return []
    
    def _extract_qualification_section(self, content: str, file_url: str = None) -> str:
        """
        提取资格审查资料部分 - 使用与PDF过滤器完全相同的逻辑
        
        Args:
            content: 文件内容
            file_url: 文件URL
            
        Returns:
            str: 截取的内容
        """
        try:
            logging.info(f"[特定匹配] 开始提取资格审查资料部分")
            
            # 1. 查找所有"资格审查资料"位置（与PDF过滤器相同）
            qualification_positions = self._find_all_qualification_sections(content)
            if not qualification_positions:
                logging.info(f"[特定匹配] 未找到资格审查资料")
                return ""
            
            # 2. 验证每个位置后50字符内是否有"投标人基本情况表"（与PDF过滤器相同）
            valid_qualification_pos = None
            for pos_start, pos_end in qualification_positions:
                basic_info_pos = self._find_basic_info_table_near_position(content, pos_start, 50)
                if basic_info_pos is not None:
                    valid_qualification_pos = pos_start
                    logging.info(f"[特定匹配] 找到匹配的资格审查资料: 位置 {pos_start}")
                    break
            
            if valid_qualification_pos is None:
                logging.info(f"[特定匹配] 未找到包含基本情况表的资格审查资料")
                return ""
            
            # 3. 查找"第三部分"位置，并验证前后50字符内是否有"技术文件/技术部分"（与PDF过滤器相同）
            tech_positions = self._find_all_tech_file_sections(content)
            if not tech_positions:
                logging.info(f"[特定匹配] 未找到第三部分")
                return ""
            
            # 4. 找到资格审查资料之后的第三部分（与PDF过滤器相同）
            valid_tech_pos = None
            for tech_pos_start, tech_pos_end in tech_positions:
                if tech_pos_start > valid_qualification_pos:  # 第三部分必须在资格审查资料之后
                    valid_tech_pos = tech_pos_start
                    logging.info(f"[特定匹配] 找到第三部分: 位置 {tech_pos_start}")
                    break
            
            if valid_tech_pos is None:
                logging.info(f"[特定匹配] 未找到资格审查资料之后的第三部分")
                return ""
            
            # 5. 截取内容：从资格审查资料到第三部分
            start_pos = valid_qualification_pos
            end_pos = valid_tech_pos
            extracted_content = content[start_pos:end_pos]
            
            if not extracted_content.strip():
                logging.warning(f"[特定匹配] 截取内容为空")
                return ""
            
            # 6. 构建完整片段
            full_segment = f"[文件来源] {file_url or '未知'}\n[截取说明] 资格审查资料部分（从资格审查资料到第三部分技术文件/技术部分）\n[截取位置] {start_pos} - {end_pos}\n[截取内容] {extracted_content.strip()}"
            
            logging.info(f"[特定匹配] 成功截取: 位置 {start_pos}-{end_pos}, 长度 {len(extracted_content)}")
            
            return full_segment
            
        except Exception as e:
            logging.error(f"[特定匹配] 失败: {e}")
            return ""
    
    def _find_all_qualification_sections(self, content: str) -> List[Tuple[int, int]]:
        """
        查找所有"资格审查资料"的位置 - 与PDF过滤器完全相同的逻辑
        
        Args:
            content: 文件内容
            
        Returns:
            List[Tuple[int, int]]: 找到的位置列表，每个元素为(开始位置, 结束位置)
        """
        positions = []
        pattern = r'资格审查资料'
        
        for match in re.finditer(pattern, content):
            start = match.start()
            end = match.end()
            positions.append((start, end))
            logging.info(f"[特定匹配] 找到资格审查资料位置: {start}-{end}")
        
        return positions
    
    def _find_basic_info_table_near_position(self, content: str, position: int, search_range: int = 50) -> Optional[int]:
        """
        在指定位置后搜索"基本情况表" - 与PDF过滤器完全相同的逻辑
        
        Args:
            content: 文件内容
            position: 资格审查资料位置
            search_range: 搜索范围（字符数）
            
        Returns:
            Optional[int]: 位置，未找到返回None
        """
        # 从资格审查资料位置后开始搜索
        search_start = position + len("资格审查资料")
        search_end = min(len(content), search_start + search_range)
        
        # 确保搜索窗口不会跨越到其他"资格审查资料"位置
        # 查找搜索范围内是否有其他"资格审查资料"
        search_content = content[search_start:search_end]
        other_qualification_pos = search_content.find("资格审查资料")
        if other_qualification_pos != -1:
            # 如果找到其他"资格审查资料"，截断搜索范围
            search_end = search_start + other_qualification_pos
            search_window = content[search_start:search_end]
        else:
            search_window = search_content
        
        logging.info(f"[特定匹配] 搜索窗口: '{search_window}'")
        
        # 清理搜索窗口
        cleaned_window = re.sub(r'[^\u4e00-\u9fff0-9]', '', search_window)
        logging.info(f"[特定匹配] 清理后搜索窗口: '{cleaned_window}'")
        
        # 清理目标字符串
        target_patterns = [
            '基本情况表'
        ]
        
        for target in target_patterns:
            # 清理目标字符串
            cleaned_target = re.sub(r'[^\u4e00-\u9fff0-9]', '', target)
            logging.info(f"[特定匹配] 清理后目标: '{cleaned_target}'")
            
            # 在清理后的窗口中查找目标
            if cleaned_target in cleaned_window:
                # 找到匹配，需要计算原始位置
                match_pos = cleaned_window.find(cleaned_target)
                # 将清理后的位置映射回原始位置
                original_pos = self._map_cleaned_position_to_original(search_window, match_pos)
                if original_pos != -1:
                    actual_pos = search_start + original_pos
                    logging.info(f"[特定匹配] 找到投标人基本情况表: 位置: {actual_pos}")
                    return actual_pos
        
        return None
    
    def _find_all_tech_file_sections(self, content: str) -> List[Tuple[int, int]]:
        """
        查找所有"第三部分"的位置，并验证前后50字符内是否有"技术文件/技术部分" - 与PDF过滤器完全相同的逻辑
        
        Args:
            content: 文件内容
            
        Returns:
            List[Tuple[int, int]]: 找到的位置列表，每个元素为(开始位置, 结束位置)
        """
        positions = []
        pattern = r'第三部分'
        
        for match in re.finditer(pattern, content):
            start = match.start()
            end = match.end()
            
            # 在前后50字符内搜索"技术文件/技术部分"
            if self._find_tech_file_near_position(content, start, 50):
                positions.append((start, end))
                logging.info(f"[特定匹配] 找到第三部分位置: {start}-{end}")
            else:
                logging.info(f"[特定匹配] 第三部分位置 {start}-{end} 附近未找到技术文件/技术部分，跳过")
        
        return positions
    
    def _find_basic_info_table(self, content: str, start_pos: int) -> int:
        """
        在资格审查资料后50字符内查找"投标人基本情况表"
        
        Args:
            content: 文件内容
            start_pos: 资格审查资料位置
            
        Returns:
            int: 位置，未找到返回-1
        """
        # 从资格审查资料位置后开始搜索
        search_start = start_pos + len("资格审查资料")
        search_end = min(len(content), search_start + 50)
        search_window = content[search_start:search_end]
        
        logging.info(f"[特定匹配] 搜索窗口: '{search_window}'")
        
        # 去除搜索窗口中的所有符号、空格、换行等，只保留中文字符和数字
        cleaned_window = re.sub(r'[^\u4e00-\u9fff0-9]', '', search_window)
        logging.info(f"[特定匹配] 清理后搜索窗口: '{cleaned_window}'")
        
        # 清理目标字符串
        target_patterns = [
            '基本情况表'
        ]
        
        for target in target_patterns:
            # 清理目标字符串
            cleaned_target = re.sub(r'[^\u4e00-\u9fff0-9]', '', target)
            logging.info(f"[特定匹配] 清理后目标: '{cleaned_target}'")
            
            # 在清理后的窗口中查找目标
            if cleaned_target in cleaned_window:
                # 找到匹配，需要计算原始位置
                match_pos = cleaned_window.find(cleaned_target)
                # 将清理后的位置映射回原始位置
                original_pos = self._map_cleaned_position_to_original(search_window, match_pos)
                if original_pos != -1:
                    logging.info(f"[特定匹配] 找到投标人基本情况表: 位置: {search_start + original_pos}")
                    return search_start + original_pos
        
        return -1
    
    def _map_cleaned_position_to_original(self, original_text: str, cleaned_pos: int) -> int:
        """
        将清理后的位置映射回原始文本位置 - 使用与PDF过滤器相同的逻辑
        
        Args:
            original_text: 原始文本
            cleaned_pos: 清理后的位置
            
        Returns:
            int: 原始位置，失败返回-1
        """
        if cleaned_pos < 0:
            return -1
        
        # 计算清理后的文本
        cleaned_text = re.sub(r'[^\u4e00-\u9fff0-9]', '', original_text)
        
        if cleaned_pos >= len(cleaned_text):
            return -1
        
        # 找到清理后文本中指定位置的字符
        target_char = cleaned_text[cleaned_pos]
        
        # 在原始文本中找到对应的位置
        original_pos = 0
        cleaned_index = 0
        
        for i, char in enumerate(original_text):
            if re.match(r'[\u4e00-\u9fff0-9]', char):
                if cleaned_index == cleaned_pos:
                    return i
                cleaned_index += 1
        
        return -1
    
    def _find_tech_file_section(self, content: str, start_pos: int) -> int:
        """
        查找"第三部分"位置，并验证前后50字符内是否有"技术文件/技术部分" - 使用与PDF过滤器相同的逻辑
        
        Args:
            content: 文件内容
            start_pos: 开始搜索位置
            
        Returns:
            int: 位置，未找到返回-1
        """
        # 从指定位置开始搜索
        search_content = content[start_pos:]
        
        # 使用与PDF过滤器相同的逻辑：查找"第三部分"
        pattern = r'第三部分'
        matches = list(re.finditer(pattern, search_content))
        
        if not matches:
            return -1
        
        # 按位置排序，使用最后一个匹配
        matches.sort(key=lambda x: x.start())
        last_match = matches[-1]
        
        # 验证这个位置前后50字符内是否有"技术文件/技术部分"
        match_start = start_pos + last_match.start()
        if self._find_tech_file_near_position(content, match_start, 50):
            logging.info(f"[特定匹配] 找到第三部分位置: {match_start}")
            return match_start
        else:
            logging.info(f"[特定匹配] 第三部分位置 {match_start} 附近未找到技术文件/技术部分，跳过")
            # 如果验证失败，尝试其他匹配
            for match in reversed(matches[:-1]):
                match_start = start_pos + match.start()
                if self._find_tech_file_near_position(content, match_start, 50):
                    logging.info(f"[特定匹配] 找到验证通过的第三部分位置: {match_start}")
                    return match_start
        
        return -1
    
    def _find_tech_file_near_position(self, text: str, position: int, search_range: int = 50) -> bool:
        """
        在指定位置前后搜索"技术文件/技术部分" - 使用与PDF过滤器相同的逻辑
        
        Args:
            text: 文本内容
            position: 搜索中心位置
            search_range: 搜索范围（字符数，默认50）
            
        Returns:
            bool: 是否找到
        """
        # 计算搜索范围
        start_pos = max(0, position - search_range)
        end_pos = min(len(text), position + search_range)
        search_window = text[start_pos:end_pos]
        
        # 清理搜索窗口
        cleaned_window = re.sub(r'[^\u4e00-\u9fff0-9]', '', search_window)
        
        # 清理目标字符串
        target_patterns = [
            '技术文件',
            '第三部分技术文件',
            '技术部分',
            '第三部分技术部分',
            '技术'
        ]
        
        for target in target_patterns:
            cleaned_target = re.sub(r'[^\u4e00-\u9fff0-9]', '', target)
            if cleaned_target in cleaned_window:
                logging.info(f"[特定匹配] 在位置 {position} 附近找到技术文件/技术部分")
                return True
        
        return False
    
    def _fallback_extraction(self, content: str, file_type: str, file_url: str = None) -> str:
        """
        备用截取逻辑 - 使用原来的通用截取方法
        
        Args:
            content: 文件内容
            file_type: 文件类型
            file_url: 文件URL
            
        Returns:
            str: 截取的内容
        """
        try:
            # 获取关键字列表
            keywords = self._get_keywords_for_file_type(file_type)
            if not keywords:
                logging.warning(f"[备用截取] 未找到关键字定义")
                return content
            
            # 执行连续截取
            extracted_segments = self._smart_continuous_extraction(content, keywords, file_url)
            
            if not extracted_segments:
                logging.warning(f"[备用截取] 未找到任何关键字匹配")
                return content
            
            # 合并所有截取的内容
            merged_content = self._merge_extracted_segments(extracted_segments, file_url)
            
            return merged_content
            
        except Exception as e:
            logging.error(f"[备用截取] 失败: {e}")
            return content
    
    def _smart_continuous_extraction(self, content: str, keywords: List[str], file_url: str = None) -> List[Dict[str, Any]]:
        """
        连续截取 - 实现多关键字连续截取逻辑
        
        Args:
            content: 文件内容
            keywords: 关键字列表
            file_url: 文件URL
            
        Returns:
            List[Dict]: 截取的内容片段列表
        """
        try:
            logging.info(f"[连续截取] 开始连续截取，关键字数量: {len(keywords)}")
            
            # 执行连续截取
            extracted_segments = []
            processed_ranges = []  # 记录已处理的范围，避免重复
            
            # 1. 首先截取文件前2000字符（前三页内容，用于识别投标人名称）
            initial_segment = self._extract_initial_segment(content, file_url)
            if initial_segment:
                extracted_segments.append(initial_segment)
                processed_ranges.append((0, 2000))
                logging.info(f"[连续截取] 已添加文件前2000字符")
            
            # 2. 查找所有关键字的位置
            keyword_positions = self._find_all_keyword_positions(content, keywords)
            logging.info(f"[连续截取] 找到 {len(keyword_positions)} 个关键字位置")
            
            if not keyword_positions:
                # 如果没有找到关键字，至少返回前2000字符
                return extracted_segments if extracted_segments else []
            
            # 按位置排序
            keyword_positions.sort(key=lambda x: x['position'])
            
            # 3. 执行关键字截取
            
            for i, keyword_info in enumerate(keyword_positions):
                keyword = keyword_info['keyword']
                position = keyword_info['position']
                
                # 检查是否与已处理的范围重叠
                if self._is_position_processed(position, processed_ranges):
                    continue
                
                # 执行连续截取
                segment = self._extract_continuous_segment(content, keyword_positions, i, file_url)
                
                if segment and len(segment['content'].strip()) > 50:
                    extracted_segments.append(segment)
                    
                    # 记录处理范围
                    start_pos = segment['start_position']
                    end_pos = segment['end_position']
                    processed_ranges.append((start_pos, end_pos))
                    
                    logging.info(f"[连续截取] 成功截取: {keyword} (位置: {position}, 长度: {len(segment['content'])})")
            
            return extracted_segments
            
        except Exception as e:
            logging.error(f"[连续截取] 失败: {e}")
            raise Exception(f"连续截取失败: {str(e)}")
    
    def _extract_initial_segment(self, content: str, file_url: str = None) -> Optional[Dict[str, Any]]:
        """
        截取文件前2000字符（用于识别投标人名称等基本信息）
        
        Args:
            content: 文件内容
            file_url: 文件URL
            
        Returns:
            Dict: 截取的内容片段
        """
        try:
            # 截取前2000字符
            initial_content = content[:2000]
            
            if not initial_content.strip():
                return None
            
            # 构建完整片段
            full_segment = f"[文件来源] {file_url or '未知'}\n[截取说明] 文件前2000字符（用于识别投标人名称）\n[截取内容] {initial_content.strip()}"
            
            return {
                'keyword_sequence': ['文件开头'],
                'start_position': 0,
                'end_position': min(2000, len(content)),
                'content': full_segment,
                'file_url': file_url
            }
            
        except Exception as e:
            logging.error(f"[截取文件开头] 失败: {e}")
            return None
    
    def _find_all_keyword_positions(self, content: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        查找所有关键字在内容中的位置（不限制数量）
        
        Args:
            content: 文件内容
            keywords: 关键字列表
            
        Returns:
            List[Dict]: 关键字位置信息列表
        """
        positions = []
        content_lower = content.lower()
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            start = 0
            
            while True:
                pos = content_lower.find(keyword_lower, start)
                if pos == -1:
                    break
                
                positions.append({
                    'keyword': keyword,
                    'position': pos,
                    'length': len(keyword)
                })
                
                start = pos + 1
                # 移除了限制，查找所有关键字出现的位置
        
        return positions
    
    def _is_position_processed(self, position: int, processed_ranges: List[Tuple[int, int]]) -> bool:
        """
        检查位置是否已被处理
        
        Args:
            position: 位置
            processed_ranges: 已处理的范围列表
            
        Returns:
            bool: 是否已被处理
        """
        for start, end in processed_ranges:
            if start <= position <= end:
                return True
        return False
    
    def _extract_continuous_segment(self, content: str, keyword_positions: List[Dict], current_index: int, file_url: str = None) -> Optional[Dict[str, Any]]:
        """
        执行连续截取 - 从关键字前20字符开始，截取到关键字后2000字符
        如果在这2000字符内遇到其他关键字，则继续截取
        
        Args:
            content: 文件内容
            keyword_positions: 所有关键字位置
            current_index: 当前关键字索引
            file_url: 文件URL
            
        Returns:
            Dict: 截取的内容片段
        """
        try:
            current_keyword = keyword_positions[current_index]
            keyword_position = current_keyword['position']
            
            # 从关键字前20字符开始截取
            start_position = max(0, keyword_position - self.context_before)
            current_pos = keyword_position
            
            # 记录截取的关键字序列
            keyword_sequence = [current_keyword['keyword']]
            
            # 连续截取逻辑：从当前关键字开始，截取后2000字符
            # 如果在这2000字符内遇到其他关键字，则从那个关键字继续截取2000字符
            max_iterations = 100  # 防止无限循环
            iteration = 0
            
            while current_pos < len(content) and iteration < max_iterations:
                iteration += 1
                
                # 计算当前截取段的结束位置（从当前关键字位置开始往后2000字符）
                segment_end = min(current_pos + self.extraction_length, len(content))
                
                # 在当前2000字符范围内查找是否有其他关键字
                next_keyword = self._find_next_keyword_in_range(content, keyword_positions, current_pos, self.extraction_length)
                
                if next_keyword:
                    # 找到下一个关键字，从该关键字位置继续截取
                    next_pos = next_keyword['position']
                    keyword_sequence.append(next_keyword['keyword'])
                    current_pos = next_pos  # 从下一个关键字开始继续截取
                    logging.debug(f"[连续截取] 发现下一个关键字: {next_keyword['keyword']} (位置: {next_pos})")
                else:
                    # 没有找到下一个关键字，截取到2000字符结束
                    current_pos = segment_end
                    break
            
            # 截取内容：从 start_position 到 current_pos
            end_position = current_pos
            extracted_content = content[start_position:end_position]
            
            # 添加上下文信息（关键字前20字符）
            context_before = content[max(0, keyword_position - 50):keyword_position]
            
            # 构建完整片段
            full_segment = f"[文件来源] {file_url or '未知'}\n[关键字序列] {' -> '.join(keyword_sequence)}\n[上下文] {context_before.strip()}\n[截取内容] {extracted_content.strip()}"
            
            return {
                'keyword_sequence': keyword_sequence,
                'start_position': start_position,
                'end_position': end_position,
                'content': full_segment,
                'file_url': file_url
            }
            
        except Exception as e:
            logging.error(f"[连续截取] 失败: {e}")
            return None
    
    def _find_next_keyword_in_range(self, content: str, keyword_positions: List[Dict], current_pos: int, max_range: int) -> Optional[Dict[str, Any]]:
        """
        在指定范围内查找下一个关键字
        
        Args:
            content: 文件内容
            keyword_positions: 关键字位置列表
            current_pos: 当前位置
            max_range: 最大搜索范围
            
        Returns:
            Dict: 下一个关键字信息，如果没有则返回None
        """
        search_end = min(current_pos + max_range, len(content))
        
        # 在范围内查找关键字，找到最近的一个
        closest_keyword = None
        closest_distance = float('inf')
        
        for keyword_info in keyword_positions:
            pos = keyword_info['position']
            if current_pos < pos < search_end:
                distance = pos - current_pos
                if distance < closest_distance:
                    closest_distance = distance
                    closest_keyword = keyword_info
        
        return closest_keyword
    
    def _merge_extracted_segments(self, segments: List[Dict[str, Any]], file_url: str = None) -> str:
        """
        合并所有截取的内容片段
        
        Args:
            segments: 截取的内容片段列表
            file_url: 文件URL
            
        Returns:
            str: 合并后的内容
        """
        try:
            if not segments:
                return ""
            
            # 按起始位置排序
            segments.sort(key=lambda x: x['start_position'])
            
            # 构建合并后的内容
            merged_parts = []
            merged_parts.append("=== 关键字截取内容 ===")
            merged_parts.append(f"文件来源: {file_url or '未知'}")
            merged_parts.append(f"截取片段数: {len(segments)}")
            merged_parts.append(f"总截取长度: {sum(len(seg['content']) for seg in segments)} 字符")
            merged_parts.append("")
            
            # 按顺序添加所有片段
            for i, segment in enumerate(segments, 1):
                merged_parts.append(f"=== 片段 {i} ===")
                merged_parts.append(f"关键字序列: {' -> '.join(segment['keyword_sequence'])}")
                merged_parts.append(f"位置范围: {segment['start_position']} - {segment['end_position']}")
                merged_parts.append(f"内容长度: {len(segment['content'])} 字符")
                merged_parts.append("--- 内容开始 ---")
                merged_parts.append(segment['content'])
                merged_parts.append("--- 内容结束 ---")
                merged_parts.append("")
            
            return "\n".join(merged_parts)
            
        except Exception as e:
            logging.error(f"[内容合并] 失败: {e}")
            return ""
    
    def extract_keywords_for_multiple_files(self, file_contents: Dict[str, str], file_type: str) -> Dict[str, str]:
        """
        为多个文件执行关键字截取
        
        Args:
            file_contents: 文件内容字典 {file_url: content}
            file_type: 文件类型
            
        Returns:
            Dict[str, str]: 截取后的内容字典 {file_url: extracted_content}
        """
        try:
            logging.info(f"[多文件关键字截取] 开始处理 {len(file_contents)} 个文件")
            
            extracted_contents = {}
            
            for file_url, content in file_contents.items():
                try:
                    extracted_content = self.extract_content_by_keywords(content, file_type, file_url)
                    extracted_contents[file_url] = extracted_content
                    logging.info(f"[多文件关键字截取] 完成文件: {file_url}")
                except Exception as e:
                    logging.error(f"[多文件关键字截取] 文件处理失败: {file_url} - {e}")
                    # 单个文件失败不影响其他文件
                    extracted_contents[file_url] = ""
            
            logging.info(f"[多文件关键字截取] 完成，成功处理 {len(extracted_contents)} 个文件")
            return extracted_contents
            
        except Exception as e:
            logging.error(f"[多文件关键字截取] 失败: {e}")
            raise Exception(f"多文件关键字截取失败: {str(e)}")
