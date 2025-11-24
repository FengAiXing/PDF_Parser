# -*- coding: utf-8 -*-
"""
异步PDF处理器
将同步的PDF去签章和筛选操作异步化，避免阻塞事件循环
"""

import asyncio
import logging
import os
import shutil
from typing import Optional
from .file_range_filter.pdf_remove_signature import remove_annotations
from .file_range_filter.pdf_content_filter import PDFContentFilter


class AsyncPDFProcessor:
    """异步PDF处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pdf_filter = PDFContentFilter()
    
    async def remove_signature_async(self, file_path: str, temp_dir: str) -> Optional[str]:
        """
        异步去除PDF签章
        
        Args:
            file_path: PDF文件路径
            temp_dir: 临时目录
            
        Returns:
            Optional[str]: 去除签章后的文件路径，失败时返回None
        """
        try:
            # 检查文件是否为PDF格式
            if not file_path.lower().endswith('.pdf'):
                self.logger.info(f"文件不是PDF格式，跳过签章去除: {file_path}")
                return None
            
            # 在线程池中执行同步操作
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._remove_signature_sync, 
                file_path, 
                temp_dir
            )
            return result
        except Exception as e:
            self.logger.error(f"异步去除PDF签章失败: {file_path}, 错误: {e}")
            return None
    
    def _remove_signature_sync(self, file_path: str, temp_dir: str) -> Optional[str]:
        """
        同步去除PDF签章的内部方法
        
        Args:
            file_path: PDF文件路径
            temp_dir: 临时目录
            
        Returns:
            Optional[str]: 去除签章后的文件路径
        """
        try:
            # 生成去除签章后的文件路径
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            signature_removed_path = os.path.join(temp_dir, f"{base_name}_signature_removed.pdf")
            
            # 复制原文件到临时位置进行处理
            shutil.copy2(file_path, signature_removed_path)
            
            # 调用去除签章函数
            self.logger.info(f"开始去除PDF签章: {file_path}")
            success = remove_annotations(signature_removed_path)
            
            if success and os.path.exists(signature_removed_path):
                self.logger.info(f"✓ 成功去除PDF签章: {file_path}")
                return signature_removed_path
            else:
                self.logger.warning(f"去除PDF签章失败，使用原始文件: {file_path}")
                # 清理临时文件
                if os.path.exists(signature_removed_path):
                    try:
                        os.remove(signature_removed_path)
                    except:
                        pass
                return None
                
        except Exception as e:
            self.logger.error(f"去除PDF签章过程中发生错误: {file_path}, 错误: {e}")
            # 清理临时文件
            if 'signature_removed_path' in locals() and os.path.exists(signature_removed_path):
                try:
                    os.remove(signature_removed_path)
                except:
                    pass
            return None
    
    async def filter_content_async(self, file_path: str, temp_dir: str) -> Optional[str]:
        """
        异步PDF内容筛选
        
        Args:
            file_path: PDF文件路径
            temp_dir: 临时目录
            
        Returns:
            Optional[str]: 筛选后的文件路径，失败时返回None
        """
        try:
            # 检查文件是否为PDF格式
            if not file_path.lower().endswith('.pdf'):
                self.logger.info(f"文件不是PDF格式，跳过内容筛选: {file_path}")
                return None
            
            # 在线程池中执行同步操作
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._filter_content_sync,
                file_path,
                temp_dir
            )
            return result
        except Exception as e:
            self.logger.error(f"异步PDF内容筛选失败: {file_path}, 错误: {e}")
            return None
    
    def _filter_content_sync(self, file_path: str, temp_dir: str) -> Optional[str]:
        """
        同步PDF内容筛选的内部方法
        
        Args:
            file_path: PDF文件路径
            temp_dir: 临时目录
            
        Returns:
            Optional[str]: 筛选后的文件路径
        """
        try:
            # 生成临时筛选文件路径
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            temp_filtered_path = os.path.join(temp_dir, f"{base_name}_temp_filtered.pdf")
            
            # 应用PDF过滤器
            self.logger.info(f"开始应用PDF过滤器: {file_path}")
            success = self.pdf_filter.filter_pdf_content(file_path, temp_filtered_path)
            
            if success and os.path.exists(temp_filtered_path):
                self.logger.info(f"PDF过滤完成: {file_path}")
                
                # 用过滤后的文件替换原文件
                try:
                    shutil.copy2(temp_filtered_path, file_path)
                    self.logger.info(f"✓ 成功用过滤后的PDF替换原文件: {file_path}")
                    
                    # 删除临时文件
                    os.remove(temp_filtered_path)
                    
                    return file_path  # 返回原文件路径，因为已经替换了
                except Exception as replace_error:
                    self.logger.error(f"替换原文件时发生错误: {replace_error}")
                    # 删除临时文件
                    try:
                        os.remove(temp_filtered_path)
                    except:
                        pass
                    return None
            else:
                self.logger.warning(f"PDF过滤失败，使用原始文件: {file_path}")
                # 清理临时过滤文件
                if os.path.exists(temp_filtered_path):
                    try:
                        os.remove(temp_filtered_path)
                    except:
                        pass
                return None
                
        except Exception as e:
            self.logger.error(f"PDF过滤过程中发生错误: {file_path}, 错误: {e}")
            # 清理临时过滤文件
            if 'temp_filtered_path' in locals() and os.path.exists(temp_filtered_path):
                try:
                    os.remove(temp_filtered_path)
                except:
                    pass
            return None
    
    async def process_pdf_async(self, file_path: str, temp_dir: str) -> Optional[str]:
        """
        异步处理PDF文件：先去签章，再筛选内容
        
        Args:
            file_path: PDF文件路径
            temp_dir: 临时目录
            
        Returns:
            Optional[str]: 处理后的文件路径
        """
        try:
            # 第一步：去除签章
            signature_removed_path = await self.remove_signature_async(file_path, temp_dir)
            
            # 如果去除签章成功，使用去除签章后的文件；否则使用原文件
            current_file_path = signature_removed_path if signature_removed_path else file_path
            self.logger.info(f"使用文件进行后续处理: {current_file_path}")
            
            # 第二步：内容筛选
            filtered_path = await self.filter_content_async(current_file_path, temp_dir)
            
            # 返回最终处理结果
            final_path = filtered_path if filtered_path else current_file_path
            
            # 如果使用了去除签章的文件，需要清理它
            if current_file_path != file_path and current_file_path != final_path:
                try:
                    os.remove(current_file_path)
                    self.logger.info(f"清理去除签章的临时文件: {current_file_path}")
                except Exception as cleanup_error:
                    self.logger.warning(f"清理去除签章的临时文件失败: {cleanup_error}")
            
            return final_path
            
        except Exception as e:
            self.logger.error(f"异步PDF处理失败: {file_path}, 错误: {e}")
            return None
