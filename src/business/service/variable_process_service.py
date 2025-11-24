#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
变量处理服务
负责变量预处理、合并和格式化
"""

import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class VariableProcessService:
    """变量处理服务类"""
    
    def __init__(self):
        """初始化服务"""
        pass
    
    async def process_and_merge_variables(
        self, 
        extracted_variables: List[Dict[str, Any]],
        merged_contents: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        处理和合并变量
        
        流程：
        1. 对变量进行预处理（传入完整的变量列表以保留reference_source）
        2. 将预处理后的变量与原变量合并（相同变量名使用最新值）
        3. 确保JSON格式正确并返回
        
        Args:
            extracted_variables: 模型提取的变量列表
            merged_contents: 合并的文件内容字典，用于第四次模型调用（可选）
            
        Returns:
            List[Dict[str, Any]]: 处理和合并后的变量列表
        """
        try:
            logger.info("=" * 80)
            logger.info("开始处理和合并变量（四次模型调用结果合并）...")
            logger.info(f"第一次模型调用结果：{len(extracted_variables)} 个固定变量")
            
            # 第一步：调用预处理逻辑（执行第2、3、4次模型调用）
            # - 第二次：判断推荐中标候选人数量
            # - 第三次：提取各候选人公司名称
            # - 第四次：从candidate_bid_files提取候选人资质、业绩等详细信息
            from src.utils.pre_variables import preprocess_variables
            processed_variables_list = await preprocess_variables(
                extracted_variables,
                merged_contents
            )
            logger.info(f"预处理完成（包含2、3、4次调用结果），处理后包含 {len(processed_variables_list)} 个变量")
            
            # 第二步：合并所有四次模型调用的变量
            # - 原变量列表（第一次）
            # - 预处理后的变量列表（第二、三、四次）
            merged_variables_list = self._merge_variable_lists(
                extracted_variables, 
                processed_variables_list
            )
            logger.info(f"四次模型调用结果合并完成！最终包含 {len(merged_variables_list)} 个变量")
            logger.info("=" * 80)
            
            # 第三步：确保结果是正确的JSON格式
            self._validate_json_format(merged_variables_list)
            logger.info("JSON格式验证通过")
            
            return merged_variables_list
            
        except Exception as e:
            logger.error(f"处理和合并变量失败: {e}")
            raise Exception(f"变量处理失败: {str(e)}")
    
    def _convert_list_to_dict(
        self, 
        variables_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        将变量列表转换为字典格式
        
        Args:
            variables_list: 变量列表，每项包含variable_name和variable_value
            
        Returns:
            Dict[str, Any]: 变量名到变量值的字典
        """
        variables_dict = {}
        
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                var_value = var.get("variable_value", "")
                
                # 处理空值
                if var_value is None or var_value == "null":
                    var_value = ""
                
                variables_dict[var_name] = var_value
        
        return variables_dict
    
    def _merge_variable_lists(
        self, 
        original_list: List[Dict[str, Any]], 
        processed_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        合并原始变量列表和预处理后的变量列表
        
        规则：
        - 如果变量名相同，使用预处理后的值和reference_source（最新值优先）
        - 如果预处理后的值为None，保留原值
        - 保留所有变量
        
        Args:
            original_list: 原始变量列表
            processed_list: 预处理后的变量列表
            
        Returns:
            List[Dict[str, Any]]: 合并后的变量列表
        """
        # 构建变量名到变量的映射
        original_map = {}
        for var in original_list:
            if isinstance(var, dict) and "variable_name" in var:
                original_map[var["variable_name"]] = var
        
        processed_map = {}
        for var in processed_list:
            if isinstance(var, dict) and "variable_name" in var:
                processed_map[var["variable_name"]] = var
        
        # 合并变量
        merged_map = original_map.copy()
        
        for var_name, var_data in processed_map.items():
            var_value = var_data.get("variable_value", "")
            
            # 如果预处理后的值不为None且不为空，使用新值覆盖
            if var_value is not None and var_value != "":
                merged_map[var_name] = var_data
                logger.debug(f"更新变量 '{var_name}': {var_value}")
            # 如果预处理后的值为None或空，且原变量不存在，添加新变量
            elif var_name not in merged_map:
                merged_map[var_name] = var_data
        
        # 转换回列表
        merged_list = list(merged_map.values())
        
        return merged_list
    
    def _convert_dict_to_list(
        self, 
        variables_dict: Dict[str, Any], 
        original_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        将变量字典转换回列表格式，保留reference_source信息
        
        Args:
            variables_dict: 变量字典
            original_list: 原始变量列表（用于获取reference_source）
            
        Returns:
            List[Dict[str, Any]]: 变量列表
        """
        # 构建原始变量的reference_source映射
        reference_map = {}
        for var in original_list:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                reference_map[var_name] = var.get("reference_source", {
                    "source_url": "",
                    "evidence_text": "",
                    "pages": "",
                    "file_type": ""
                })
        
        # 转换字典为列表
        variables_list = []
        for var_name, var_value in variables_dict.items():
            # 获取reference_source
            reference_source = reference_map.get(var_name, {
                "source_url": "",
                "evidence_text": "",
                "pages": "",
                "file_type": ""
            })
            
            # 检查变量值是否为空
            is_value_empty = (
                var_value is None or 
                var_value == "null" or 
                var_value == "" or
                (isinstance(var_value, str) and var_value.strip() == "")
            )
            
            # 如果值为空，清空reference_source
            if is_value_empty:
                var_value = ""
                reference_source = {
                    "source_url": "",
                    "evidence_text": "",
                    "pages": "",
                    "file_type": ""
                }
            
            variables_list.append({
                "variable_name": var_name,
                "variable_value": var_value,
                "reference_source": reference_source
            })
        
        return variables_list
    
    def _validate_json_format(self, variables_list: List[Dict[str, Any]]) -> None:
        """
        验证变量列表是否可以正确转换为JSON格式
        
        Args:
            variables_list: 变量列表
            
        Raises:
            Exception: 如果JSON格式验证失败
        """
        try:
            # 尝试序列化为JSON
            json_str = json.dumps(variables_list, ensure_ascii=False)
            
            # 尝试反序列化验证
            json.loads(json_str)
            
            logger.info(f"JSON格式验证成功，序列化后长度: {len(json_str)} 字符")
            
        except Exception as e:
            logger.error(f"JSON格式验证失败: {e}")
            raise Exception(f"变量列表JSON格式验证失败: {str(e)}")

