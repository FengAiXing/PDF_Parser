# 内容提取服务
import asyncio
import json
import logging
import re
from typing import Dict, List, Any, Optional
from common.variable_templates import VariableTemplateManager
from prompts.prompt_templates import PromptTemplateManager
from common.llm_client import LLMClient
from src.utils.llm_utils import call_llm_with_retry


class ContentExtractionService:
    """内容提取服务类"""
    
    def __init__(self):
        """初始化服务"""
        self.variable_manager = VariableTemplateManager()
        self.prompt_manager = PromptTemplateManager()
        self.llm_client = LLMClient()
        # 延迟导入避免循环依赖
        from src.utils.file_process import FileProcessor
        from src.utils.dotsocr_process import DotsOCRProcessor
        self.file_processor = FileProcessor()
        self.dotsocr_processor = DotsOCRProcessor()
    
    async def _extract_regular_file_content_from_text(self, parsed_content: str, file_type: str, variables: List, original_url: str = None) -> str:
        """
        从已解析的文本内容中提取变量 - 避免重复下载和解析
        
        Args:
            parsed_content: 第三步已解析的文件内容（文本格式）
            file_type: 文件类型
            variables: 变量列表
            original_url: 原始URL
            
        Returns:
            str: 模型提取的JSON格式结果
        """
        try:
            logging.info(f"[已解析内容提取-常规] 使用已解析内容进行变量提取，内容长度: {len(parsed_content)} 字符")
            
            if not parsed_content or len(parsed_content.strip()) < 10:
                logging.error(f"[已解析内容提取-常规] 已解析内容为空或过短")
                raise Exception(f"已解析内容为空或过短")
            
            # 第一步：生成提示词
            logging.info(f"[已解析内容提取-常规] 生成提示词...")
            prompt = self.prompt_manager.generate_prompt(file_type, variables, original_url)
            logging.info(f"[已解析内容提取-常规] 提示词生成完成，长度: {len(prompt)} 字符")
            
            # 第二步：使用重试机制调用模型进行内容提取
            logging.info(f"[已解析内容提取-常规] 调用LLM进行内容提取...")
            normalized_result = await self._extract_with_retry(prompt, parsed_content, file_type, original_url)
            logging.info(f"[已解析内容提取-常规] 结果规范化完成，提取到 {len(normalized_result)} 个变量")
            
            # 第四步：返回JSON格式的结果
            result_json = json.dumps(normalized_result, ensure_ascii=False)
            logging.info(f"[已解析内容提取-常规] 处理完成，返回JSON长度: {len(result_json)} 字符")
            
            return result_json
            
        except Exception as e:
            logging.error(f"[已解析内容提取-常规] 处理失败，错误: {e}")
            raise Exception(f"已解析内容处理失败: {str(e)}")
    
    async def _extract_large_file_content_from_text(self, parsed_content: str, file_type: str, variables: List, original_url: str = None) -> str:
        """
        从已解析的文本内容中提取大文件变量 - 包含关键字截取优化
        
        Args:
            parsed_content: 第三步已解析的文件内容（完整文本）
            file_type: 文件类型
            variables: 变量列表
            original_url: 原始URL
            
        Returns:
            str: 模型提取的JSON格式结果
        """
        try:
            logging.info(f"[已解析内容提取-大文件] 使用已解析内容进行大文件处理，内容长度: {len(parsed_content)} 字符")
            
            if not parsed_content or len(parsed_content.strip()) < 10:
                logging.error(f"[已解析内容提取-大文件] 已解析内容为空或过短")
                raise Exception(f"已解析内容为空或过短")
            
            # 第一步：针对大文件进行关键字截取优化（在已解析的文本上操作）
            if file_type == "candidate_bid_files":
                logging.info(f"[已解析内容提取-大文件] 使用关键字截取优化处理...")
                variable_names = [var.english_name for var in variables]
                processed_content = self._extract_content_by_keywords(parsed_content, variable_names, file_type)
                logging.info(f"[已解析内容提取-大文件] 关键字截取完成，处理后内容长度: {len(processed_content)} 字符")
            else:
                logging.info(f"[已解析内容提取-大文件] 使用原始内容（无优化）...")
                processed_content = parsed_content
            
            # 第二步：检查处理后的内容是否为空
            if not processed_content or len(processed_content.strip()) == 0:
                logging.warning(f"[已解析内容提取-大文件] 关键字截取后内容为空，直接返回空结果")
                # 返回空结果，所有变量值为空
                empty_result = []
                for var in variables:
                    empty_result.append({
                        "variable_name": var.name,
                        "variable_value": "",
                        "reference_source": {
                            "source_url": original_url or "",
                            "evidence_text": "",
                            "pages": "",
                            "file_type": file_type
                        }
                    })
                return json.dumps(empty_result, ensure_ascii=False)
            
            # 第三步：生成提示词
            logging.info(f"[已解析内容提取-大文件] 生成提示词...")
            prompt = self.prompt_manager.generate_prompt(file_type, variables, original_url)
            logging.info(f"[已解析内容提取-大文件] 提示词生成完成，长度: {len(prompt)} 字符")
            
            # 第四步：使用重试机制调用模型进行内容提取
            logging.info(f"[已解析内容提取-大文件] 调用LLM进行内容提取...")
            normalized_result = await self._extract_with_retry(prompt, processed_content, file_type, original_url)
            logging.info(f"[已解析内容提取-大文件] 结果规范化完成，提取到 {len(normalized_result)} 个变量")
            
            # 第六步：返回JSON格式的结果
            result_json = json.dumps(normalized_result, ensure_ascii=False)
            logging.info(f"[已解析内容提取-大文件] 处理完成，返回JSON长度: {len(result_json)} 字符")
            
            return result_json
            
        except Exception as e:
            logging.error(f"[已解析内容提取-大文件] 处理失败，错误: {e}")
            raise Exception(f"已解析大文件内容处理失败: {str(e)}")
    
    async def _download_and_extract_content(self, file_url: str, file_type: str = None, variables: List = None, merged_contents: Dict[str, str] = None) -> str:
        """
        从已解析内容中提取变量 - 使用第三步已解析的文本内容
        
        Args:
            file_url: 文件URL（用于获取原始URL）
            file_type: 文件类型，用于优化处理策略
            variables: 变量列表
            merged_contents: 第三步已解析和合并的文件内容
            
        Returns:
            str: 提取的变量JSON结果
        """
        logging.info(f"[文件处理] 开始处理文件: {file_url}")
        
        # 保存原始URL用于LLM的source_url
        original_url = file_url
        
        # 检查是否有已解析的内容
        if not merged_contents or file_type not in merged_contents:
            error_msg = f"未找到已解析内容: {file_type}"
            logging.error(f"[文件处理] {error_msg}")
            raise Exception(error_msg)
        
        logging.info(f"[文件处理] 使用已解析的内容进行变量提取")
        file_type_data = merged_contents[file_type]
        
        # 处理新的数据结构（包含URL映射）
        if isinstance(file_type_data, dict) and 'content' in file_type_data:
            parsed_content = file_type_data['content']
            logging.info(f"[文件处理] 检测到多文件类型，包含 {file_type_data.get('file_count', 1)} 个文件")
        else:
            # 兼容旧的数据结构（直接是字符串）
            parsed_content = file_type_data
            logging.info(f"[文件处理] 使用单文件模式")
        
        # 根据文件类型选择处理策略
        if file_type == "candidate_bid_files":
            # 大文件使用已解析内容进行关键字截取优化
            logging.info(f"[文件处理] 大文件使用关键字截取优化...")
            return await self._extract_large_file_content_from_text(parsed_content, file_type, variables, original_url)
        else:
            # 常规文件直接使用已解析的内容
            logging.info(f"[文件处理] 常规文件直接提取变量...")
            return await self._extract_regular_file_content_from_text(parsed_content, file_type, variables, original_url)
    
    async def _extract_with_retry(self, prompt: str, file_content: str, file_type: str, original_url: str = None) -> List[Dict[str, Any]]:
        """
        带重试机制的内容提取方法
        
        Args:
            prompt: 提示词
            file_content: 文件内容
            file_type: 文件类型
            original_url: 原始URL
            
        Returns:
            List[Dict[str, Any]]: 标准格式的变量数组
        """
        max_retries = 1
        
        for attempt in range(max_retries + 1):
            try:
                # 调用LLM进行内容提取
                llm_result = await call_llm_with_retry(
                    llm_client=self.llm_client,
                    prompt=prompt,
                    file_content=file_content,
                    step_name="内容提取"
                )
                
                # 检查结果是否为空
                if not llm_result or llm_result.strip() == "":
                    if attempt < max_retries:
                        logging.warning(f"第{attempt + 1}次调用返回空结果，准备重试")
                        continue
                    else:
                        logging.error("重试后仍然返回空结果")
                        return []
                
                # 规范化处理结果
                normalized_result = self._normalize_result(llm_result, file_type, original_url)
                
                # 检查结果是否有效
                if normalized_result and len(normalized_result) > 0:
                    return normalized_result
                else:
                    if attempt < max_retries:
                        logging.warning(f"第{attempt + 1}次调用返回空结果，准备重试")
                        continue
                    else:
                        logging.error("重试后仍然返回空结果")
                        return []
                        
            except Exception as e:
                if attempt < max_retries:
                    logging.warning(f"第{attempt + 1}次调用发生异常: {e}，准备重试")
                    continue
                else:
                    logging.error(f"重试后仍然发生异常: {e}")
                    return []
        
        return []
    
    def _convert_reference_source_format(self, ref_source: Dict[str, Any], original_url: str = None, file_type: str = "") -> Dict[str, Any]:
        """
        将旧格式的reference_source转换为新格式
        
        旧格式: page_number, section, content_preview
        新格式: pages, evidence_text
        
        Args:
            ref_source: 原始reference_source字典
            original_url: 原始URL（如果ref_source中没有source_url）
            file_type: 文件类型
            
        Returns:
            Dict[str, Any]: 转换后的标准格式reference_source
        """
        if not isinstance(ref_source, dict):
            return {
                "source_url": original_url or "",
                "evidence_text": "",
                "pages": "",
                "file_type": file_type
            }
        
        # 检查是否是旧格式（包含page_number, section, content_preview）
        has_old_format = any(key in ref_source for key in ["page_number", "section", "content_preview"])
        
        if has_old_format:
            # 转换旧格式到新格式
            # 将page_number转换为pages
            pages = ref_source.get("page_number", "")
            # 如果pages包含"第"和"页"，提取数字部分
            if pages and "第" in pages and "页" in pages:
                # 提取所有页码数字，支持"第142-159页"或"710, 711, 712"等格式
                import re
                # 提取所有数字
                page_numbers = re.findall(r'\d+', pages)
                if page_numbers:
                    pages = ", ".join(page_numbers)
            
            # 合并section和content_preview为evidence_text
            section = ref_source.get("section", "")
            content_preview = ref_source.get("content_preview", "")
            evidence_text_parts = []
            if section:
                evidence_text_parts.append(section)
            if content_preview:
                evidence_text_parts.append(content_preview)
            evidence_text = " ".join(evidence_text_parts)
            
            # 获取source_url，优先使用ref_source中的，否则使用original_url
            source_url = ref_source.get("source_url", original_url or "")
            
            # 获取file_type，优先使用ref_source中的
            ref_file_type = ref_source.get("file_type", file_type)
            
            return {
                "source_url": source_url,
                "evidence_text": evidence_text,
                "pages": pages,
                "file_type": ref_file_type
            }
        else:
            # 已经是新格式，直接使用，但确保所有字段都存在
            result = {
                "source_url": ref_source.get("source_url", original_url or ""),
                "evidence_text": ref_source.get("evidence_text", ""),
                "pages": ref_source.get("pages", ""),
                "file_type": ref_source.get("file_type", file_type)
            }
            return result
    
    def _normalize_result(self, llm_result: str, file_type: str, original_url: str = None) -> List[Dict[str, Any]]:
        """
        规范化处理大模型返回的结果 - 返回标准格式的数组
        
        Args:
            llm_result: 大模型返回的原始结果
            file_type: 文件类型

        Returns:
            List[Dict[str, Any]]: 标准格式的变量数组
        """
        try:
            # 获取该文件类型的变量定义，用于映射变量名称
            variables = self.variable_manager.get_variables_for_file_type(file_type)
            variable_mapping = {var.english_name: var.name for var in variables}
            
            # 清理结果，移除可能的markdown代码块标记
            clean_result = llm_result.strip()
            if clean_result.startswith("```json"):
                clean_result = clean_result[7:]
            if clean_result.startswith("```"):
                clean_result = clean_result[3:]
            if clean_result.endswith("```"):
                clean_result = clean_result[:-3]
            clean_result = clean_result.strip()
            
            # 尝试解析JSON结果
            parsed_data = json.loads(clean_result)
            
            # 转换为标准格式数组
            result_array = []
            
            if isinstance(parsed_data, list):
                # 已经是数组格式，直接处理
                for i, item in enumerate(parsed_data):
                    if isinstance(item, dict) and "variable_value" in item:
                        # 优先使用模型返回的variable_name，如果没有则根据顺序从变量模板中获取
                        variable_name = item.get("variable_name", "")
                        if not variable_name and i < len(variables):
                            # 使用变量模板中的中文名称
                            variable_name = variables[i].name
                        
                        # 处理reference_source，确保source_url正确
                        reference_source = item.get("reference_source", {})
                        variable_value = item.get("variable_value", "")
                        
                        # 检查变量值是否真正为空（null或undefined）
                        is_variable_null = (variable_value is None or 
                                           variable_value == "null" or 
                                           variable_value == "undefined" or
                                           (isinstance(variable_value, str) and variable_value.strip() == ""))
                        
                        if not is_variable_null:
                            # 变量有值，处理reference_source
                            if isinstance(reference_source, dict) and reference_source:
                                # 转换格式（支持旧格式和新格式）
                                reference_source = self._convert_reference_source_format(
                                    reference_source, original_url, file_type
                                )
                            elif not reference_source:
                                # 如果LLM没有返回reference_source，创建默认的
                                reference_source = {
                                    "source_url": original_url or "",
                                    "evidence_text": "",
                                    "pages": "",
                                    "file_type": file_type
                                }
                        else:
                            # 变量值为空，reference_source应该包含字段但值为空字符串
                            reference_source = {
                                "source_url": "",
                                "evidence_text": "", 
                                "pages": "",
                                "file_type": ""
                            }
                        
                        result_array.append({
                            "variable_name": variable_name,
                            "variable_value": item.get("variable_value", ""),
                            "reference_source": reference_source
                        })
            elif isinstance(parsed_data, dict):
                # 对象格式，转换为数组格式
                for key, value in parsed_data.items():
                    # 尝试从变量映射中获取中文名称
                    chinese_name = variable_mapping.get(key, key)
                    # 检查变量值是否真正为空
                    is_variable_null = (value is None or 
                                       value == "null" or 
                                       value == "undefined" or
                                       (isinstance(value, str) and value.strip() == ""))
                    
                    if not is_variable_null:
                        reference_source = {
                            "source_url": original_url or "",
                            "evidence_text": "",
                            "pages": "",
                            "file_type": file_type
                        }
                    else:
                        reference_source = {
                            "source_url": "",
                            "evidence_text": "",
                            "pages": "",
                            "file_type": ""
                        }
                    
                    result_array.append({
                        "variable_name": chinese_name,
                        "variable_value": value,
                        "reference_source": reference_source
                    })
            
            return result_array

        except json.JSONDecodeError as e:
            # JSON解析失败，记录详细错误信息
            logging.error(f"JSON解析失败: {str(e)}")
            logging.error(f"错误位置: line {e.lineno}, column {e.colno}, position {e.pos}")
            
            # 输出错误附近的内容（前后100个字符）
            error_pos = e.pos
            start_pos = max(0, error_pos - 100)
            end_pos = min(len(clean_result), error_pos + 100)
            error_context = clean_result[start_pos:end_pos]
            logging.error(f"错误附近的内容: ...{error_context}...")
            
            # JSON解析失败，返回空数组
            logging.error(f"JSON解析失败，所有修复尝试均失败")
            logging.error(f"原始结果前500字符: {llm_result[:500]}...")
            return []
        except Exception as e:
            # 其他异常，抛出异常
            logging.error(f"结果处理异常: {str(e)}")
            raise Exception(f"结果处理失败: {str(e)}")
    
    def _fix_json_format(self, json_str: str) -> str:
        """
        修复常见的JSON格式问题
        
        Args:
            json_str: 原始JSON字符串
            
        Returns:
            str: 修复后的JSON字符串
        """
        try:
            import re
            
            # 1. 移除BOM标记
            if json_str.startswith('\ufeff'):
                json_str = json_str[1:]
            
            # 2. 移除末尾的逗号（JSON不允许末尾逗号）
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            # 3. 尝试修复截断的JSON
            # 如果最后一个字符不是 ] 或 }，可能是被截断了
            if json_str and json_str[-1] not in [']', '}', '"']:
                # 找到最后一个完整的对象/数组结束位置
                last_brace = json_str.rfind(']')
                last_curly = json_str.rfind('}')
                last_complete = max(last_brace, last_curly)
                
                if last_complete > 0:
                    logging.warning(f"检测到JSON可能被截断，尝试截取到最后完整位置: {last_complete}")
                    json_str = json_str[:last_complete + 1]
            
            # 4. 检查并尝试闭合未闭合的括号
            open_braces = json_str.count('[') - json_str.count(']')
            open_curlies = json_str.count('{') - json_str.count('}')
            
            if open_curlies > 0 or open_braces > 0:
                logging.warning(f"检测到未闭合的括号: {{ {open_curlies}, [ {open_braces}")
                # 先尝试添加缺失的引号（如果最后是未闭合的字符串）
                if json_str and json_str[-1] not in [']', '}', '"', ',']:
                    json_str += '"'
                # 然后闭合括号
                if open_curlies > 0:
                    json_str += '}' * open_curlies
                if open_braces > 0:
                    json_str += ']' * open_braces
            
            return json_str
            
        except Exception as e:
            logging.error(f"修复JSON格式失败: {e}")
            return json_str
    
    def _extract_content_by_keywords(self, file_content: str, variables: List[str], file_type: str) -> str:
        """
        根据关键字截取大文件内容 - 使用新的智能关键字截取器
        
        Args:
            file_content: 完整的文件内容
            variables: 需要提取的变量列表
            file_type: 文件类型
            
        Returns:
            str: 截取后的内容，用于LLM处理
        """
        try:
            logging.info(f"[关键字截取] 开始关键字截取优化...")
            
            if not file_content:
                logging.warning(f"[关键字截取] 文件内容为空，返回原始内容")
                return file_content
            
            # 使用新的智能关键字截取器
            from src.utils.file_range_filter.keyword_extractor import KeywordExtractor
            keyword_extractor = KeywordExtractor()
            
            # 执行智能关键字截取
            extracted_content = keyword_extractor.extract_content_by_keywords(file_content, file_type)
            
            logging.info(f"[关键字截取] 完成: 原始内容长度 {len(file_content)}, 截取后长度 {len(extracted_content)}")
            
            return extracted_content
            
        except Exception as e:
            logging.error(f"[关键字截取] 失败: {e}")
            # 失败时抛出异常，中断整个流程
            raise Exception(f"关键字截取失败: {str(e)}")