#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投标文件排名识别提示词模块
用于根据投标文件前2000字符和评审结果识别每个文件对应的排名
"""

import logging
import json
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BidFileRankingIdentifier:
    """投标文件排名识别器"""
    
    def __init__(self):
        """初始化"""
        pass
    
    def generate_ranking_identification_prompt(
        self, 
        file_previews: Dict[str, str], 
        evaluation_result: str
    ) -> str:
        """
        生成排名识别提示词
        
        Args:
            file_previews: 文件预览字典，格式为 {"文件1": "前2000字符内容", "文件2": "..."}
            evaluation_result: 评审结果内容（包含投标人名称和排名信息）
            
        Returns:
            str: 生成的提示词
        """
        # 构建文件预览部分
        file_preview_text = ""
        for file_key, preview_content in file_previews.items():
            file_preview_text += f"\n\n【{file_key}】:\n{preview_content}\n"
            file_preview_text += "=" * 80
        
        prompt = f"""
你是一个专业的投标文件分析助手。你需要根据投标文件的前2000字符内容，结合评审结果中的投标人信息，判断每个文件对应的是第几名的投标人。

## 任务说明

### 输入信息
1. **评审结果**：包含所有投标人的名称和排名信息
2. **投标文件预览**：每个投标文件的前2000字符，这部分内容通常包含：
   - 投标人名称
   - 公司盖章信息（会有"盖单位公章"、"投标人公章"等字样）
   - 投标函或投标承诺书等关键信息

### 识别方法
1. 在每个文件的前2000字符中查找投标人名称
2. 通常在"投标人："、"盖单位公章"、"投标单位"等位置附近可以找到公司全称
3. 将找到的投标人名称与评审结果中的投标人进行匹配
4. 确定该文件属于第几名的投标人

### 评审结果
```
{evaluation_result}
```

### 投标文件预览（前2000字符）
{file_preview_text}

## 输出要求

请以JSON格式返回每个文件的排名识别结果，格式如下：

```json
{{
  "文件1": "第一名",
  "文件2": "第三名",
  "文件3": "第二名"
}}
```

**注意事项**：
1. 排名格式必须为中文，如："第一名"、"第二名"、"第三名"等
2. 如果某个文件无法识别出对应的投标人，请返回"未识别"
3. 确保每个文件都有对应的返回值
4. 只返回JSON格式，不要添加任何其他文字说明
5. 仔细查找投标人名称，可能出现在多个位置：
   - 投标函中的"投标人："后面
   - 盖章处的公司名称
   - 法定代表人授权书中的公司名称
   - 投标承诺书中的公司名称

请开始识别：
"""
        return prompt
    
    async def identify_bid_file_rankings(
        self, 
        file_previews: Dict[str, str], 
        evaluation_result: str
    ) -> Optional[Dict[str, str]]:
        """
        调用LLM识别投标文件的排名
        
        Args:
            file_previews: 文件预览字典，格式为 {"文件1": "前2000字符内容", "文件2": "..."}
            evaluation_result: 评审结果内容
            
        Returns:
            Optional[Dict[str, str]]: 文件排名映射，格式为 {"文件1": "第一名", "文件2": "第二名", ...}
                                      如果识别失败返回None
        """
        try:
            from common.llm_client import LLMClient
            llm_client = LLMClient()
            
            # 生成提示词
            prompt = self.generate_ranking_identification_prompt(file_previews, evaluation_result)
            
            logger.info(f"开始识别投标文件排名，共 {len(file_previews)} 个文件")
            logger.info(f"提示词长度: {len(prompt)} 字符")
            
            # 使用重试机制调用LLM
            ranking_map = await self._identify_ranking_with_retry(llm_client, prompt)
            
            if ranking_map:
                logger.info(f"成功识别投标文件排名: {ranking_map}")
                return ranking_map
            else:
                logger.error("无法解析排名识别结果")
                return None
                
        except Exception as e:
            logger.error(f"识别投标文件排名失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def _identify_ranking_with_retry(self, llm_client, prompt: str) -> Optional[Dict[str, str]]:
        """
        带重试机制的排名识别方法
        
        Args:
            llm_client: LLM客户端
            prompt: 提示词
            
        Returns:
            Optional[Dict[str, str]]: 解析后的排名映射字典
        """
        max_retries = 1
        
        for attempt in range(max_retries + 1):
            try:
                # 调用LLM
                result = await llm_client.call_llm(
                    prompt=prompt,
                    file_content=""
                )
                
                # 检查结果是否为空
                if not result or result.strip() == "":
                    if attempt < max_retries:
                        logger.warning(f"第{attempt + 1}次调用返回空结果，准备重试")
                        continue
                    else:
                        logger.error("重试后仍然返回空结果")
                        return None
                
                logger.info(f"第{attempt + 1}次调用LLM返回结果长度: {len(result)} 字符")
                logger.debug(f"LLM原始返回:\n{result}")
                
                # 解析JSON结果
                ranking_map = self._parse_ranking_result(result)
                
                # 检查解析结果
                if ranking_map:
                    logger.info(f"第{attempt + 1}次调用成功识别投标文件排名")
                    return ranking_map
                else:
                    if attempt < max_retries:
                        logger.warning(f"第{attempt + 1}次调用无法解析排名识别结果，准备重试")
                        continue
                    else:
                        logger.error("重试后仍然无法解析排名识别结果")
                        return None
                        
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"第{attempt + 1}次调用发生异常: {e}，准备重试")
                    continue
                else:
                    logger.error(f"重试后仍然发生异常: {e}")
                    return None
        
        return None
    
    def _parse_ranking_result(self, llm_result: str) -> Optional[Dict[str, str]]:
        """
        解析LLM返回的排名识别结果
        
        Args:
            llm_result: LLM返回的原始结果
            
        Returns:
            Optional[Dict[str, str]]: 解析后的排名映射字典
        """
        try:
            # 清理结果
            clean_result = llm_result.strip()
            
            # 移除可能的markdown代码块标记
            if clean_result.startswith("```json"):
                clean_result = clean_result[7:]
            if clean_result.startswith("```"):
                clean_result = clean_result[3:]
            if clean_result.endswith("```"):
                clean_result = clean_result[:-3]
            clean_result = clean_result.strip()
            
            # 尝试提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', clean_result)
            if json_match:
                clean_result = json_match.group(0)
            
            # 解析JSON
            ranking_map = json.loads(clean_result)
            
            # 验证格式
            if not isinstance(ranking_map, dict):
                logger.error("排名识别结果不是字典格式")
                return None
            
            # 验证每个值都是有效的排名
            valid_rankings = set()
            for file_key, ranking in ranking_map.items():
                if not isinstance(ranking, str):
                    logger.warning(f"文件 {file_key} 的排名不是字符串: {ranking}")
                    continue
                
                # 检查是否为有效的排名格式（第X名或未识别）
                if ranking == "未识别" or re.match(r'^第[一二三四五六七八九十\d]+名$', ranking):
                    valid_rankings.add(file_key)
                else:
                    logger.warning(f"文件 {file_key} 的排名格式无效: {ranking}")
            
            if not valid_rankings:
                logger.error("没有有效的排名识别结果")
                return None
            
            return ranking_map
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"原始内容: {llm_result[:500]}")
            return None
        except Exception as e:
            logger.error(f"解析排名结果失败: {e}")
            return None


def rename_files_by_ranking(
    candidate_files: Dict[str, Dict[str, Any]], 
    ranking_map: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
    """
    根据排名映射重命名投标文件
    
    Args:
        candidate_files: 原始文件字典，键为"文件1"、"文件2"等
        ranking_map: 排名映射字典，格式为 {"文件1": "第一名", "文件2": "第二名", ...}
        
    Returns:
        Dict[str, Dict[str, Any]]: 重命名后的文件字典，键为"第一名"、"第二名"等
    """
    renamed_files = {}
    
    for file_key, file_info in candidate_files.items():
        # 获取该文件对应的排名
        ranking = ranking_map.get(file_key, "未识别")
        
        if ranking == "未识别":
            logger.warning(f"{file_key} 未能识别排名，保持原名称")
            renamed_files[file_key] = file_info
        else:
            # 使用排名作为新的键名
            renamed_files[ranking] = file_info
            logger.info(f"文件重命名: {file_key} -> {ranking}")
    
    return renamed_files

