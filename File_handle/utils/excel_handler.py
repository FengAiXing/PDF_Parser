# -*- coding: utf-8 -*-
"""
Excel处理器 - ExcelHandler

提供Excel文件的处理功能：
- 提取所有工作表内容
- 获取工作表信息
- 按工作表解析
- 支持.xlsx和.xls格式
"""

import os
import logging
import warnings
import pandas as pd
from typing import Dict, List, Optional

# 抑制 openpyxl 的样式警告
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')


class ExcelHandler:
    """Excel文件处理器"""
    
    def __init__(self):
        """初始化Excel处理器"""
        self.logger = logging.getLogger(__name__)
    
    def parse_excel(self, excel_path: str) -> Optional[str]:
        """
        解析Excel文件（所有工作表）
        
        Args:
            excel_path: Excel文件路径
            
        Returns:
            所有工作表的文本内容
        """
        try:
            # 根据文件扩展名确定引擎
            engine = self._get_engine(excel_path)
            
            with pd.ExcelFile(excel_path, engine=engine) as excel_file:
                content_parts = []
                
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    
                    # 添加工作表标题
                    content_parts.append(f"=== 工作表: {sheet_name} ===")
                    
                    # 将DataFrame转换为文本
                    if not df.empty:
                        text_content = df.to_string(index=True, header=True, na_rep='')
                        content_parts.append(text_content)
                    else:
                        content_parts.append("(空工作表)")
                    
                    content_parts.append("")  # 添加空行分隔
                
                result = "\n".join(content_parts)
                self.logger.info(f"Excel解析完成: {excel_path}, 共{len(excel_file.sheet_names)}个工作表")
                return result
                
        except Exception as e:
            self.logger.error(f"Excel解析失败: {excel_path}, 错误: {e}")
            return None
    
    def parse_sheet(self, excel_path: str, sheet_name: str) -> Optional[str]:
        """
        解析指定工作表
        
        Args:
            excel_path: Excel文件路径
            sheet_name: 工作表名称
            
        Returns:
            工作表文本内容
        """
        try:
            engine = self._get_engine(excel_path)
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine=engine)
            
            if not df.empty:
                result = df.to_string(index=True, header=True, na_rep='')
                self.logger.info(f"工作表解析完成: {excel_path} - {sheet_name}")
                return result
            else:
                self.logger.warning(f"工作表为空: {excel_path} - {sheet_name}")
                return "(空工作表)"
                
        except Exception as e:
            self.logger.error(f"工作表解析失败: {excel_path} - {sheet_name}, 错误: {e}")
            return None
    
    def get_sheet_names(self, excel_path: str) -> List[str]:
        """
        获取所有工作表名称
        
        Args:
            excel_path: Excel文件路径
            
        Returns:
            工作表名称列表
        """
        try:
            engine = self._get_engine(excel_path)
            
            with pd.ExcelFile(excel_path, engine=engine) as excel_file:
                sheet_names = excel_file.sheet_names
                self.logger.info(f"获取工作表名称: {excel_path}, 共{len(sheet_names)}个工作表")
                return sheet_names
                
        except Exception as e:
            self.logger.error(f"获取工作表名称失败: {excel_path}, 错误: {e}")
            return []
    
    def get_sheet_info(self, excel_path: str) -> List[Dict[str, any]]:
        """
        获取所有工作表的详细信息
        
        Args:
            excel_path: Excel文件路径
            
        Returns:
            工作表信息列表，每个元素包含：
            - name: 工作表名称
            - rows: 行数
            - columns: 列数
            - column_names: 列名列表
            - is_empty: 是否为空
        """
        try:
            engine = self._get_engine(excel_path)
            
            with pd.ExcelFile(excel_path, engine=engine) as excel_file:
                sheets_info = []
                
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    
                    sheet_info = {
                        'name': sheet_name,
                        'rows': len(df),
                        'columns': len(df.columns),
                        'column_names': df.columns.tolist(),
                        'is_empty': df.empty
                    }
                    
                    sheets_info.append(sheet_info)
                
                self.logger.info(f"获取工作表信息完成: {excel_path}, 共{len(sheets_info)}个工作表")
                return sheets_info
                
        except Exception as e:
            self.logger.error(f"获取工作表信息失败: {excel_path}, 错误: {e}")
            return []
    
    def parse_excel_with_details(self, excel_path: str) -> Dict[str, any]:
        """
        解析Excel并返回详细信息
        
        Args:
            excel_path: Excel文件路径
            
        Returns:
            包含解析结果和元数据的字典：
            - content: 文本内容
            - sheet_count: 工作表数量
            - sheets: 每个工作表的详细信息
            - file_size: 文件大小
        """
        try:
            engine = self._get_engine(excel_path)
            
            with pd.ExcelFile(excel_path, engine=engine) as excel_file:
                sheets = []
                all_content = []
                
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    
                    sheet_info = {
                        'name': sheet_name,
                        'rows': len(df),
                        'columns': len(df.columns),
                        'column_names': df.columns.tolist(),
                        'is_empty': df.empty
                    }
                    
                    sheets.append(sheet_info)
                    
                    # 添加到总内容
                    all_content.append(f"=== 工作表: {sheet_name} ===")
                    if not df.empty:
                        all_content.append(df.to_string(index=True, header=True, na_rep=''))
                    else:
                        all_content.append("(空工作表)")
                    all_content.append("")
                
                result = {
                    'content': "\n".join(all_content),
                    'sheet_count': len(excel_file.sheet_names),
                    'sheets': sheets,
                    'file_size': os.path.getsize(excel_path)
                }
                
                self.logger.info(f"Excel详细解析完成: {excel_path}")
                return result
                
        except Exception as e:
            self.logger.error(f"Excel详细解析失败: {excel_path}, 错误: {e}")
            return {}
    
    def parse_sheets_by_names(self, excel_path: str, sheet_names: List[str]) -> Dict[str, Optional[str]]:
        """
        按名称解析指定的多个工作表
        
        Args:
            excel_path: Excel文件路径
            sheet_names: 工作表名称列表
            
        Returns:
            工作表名称到内容的映射
        """
        results = {}
        
        for sheet_name in sheet_names:
            try:
                content = self.parse_sheet(excel_path, sheet_name)
                results[sheet_name] = content
            except Exception as e:
                self.logger.error(f"解析工作表失败: {sheet_name}, 错误: {e}")
                results[sheet_name] = None
        
        self.logger.info(f"批量解析工作表完成: {excel_path}, 共{len(sheet_names)}个工作表")
        return results
    
    def export_sheet_to_csv(self, excel_path: str, sheet_name: str, output_csv_path: str) -> bool:
        """
        导出工作表为CSV
        
        Args:
            excel_path: Excel文件路径
            sheet_name: 工作表名称
            output_csv_path: 输出CSV文件路径
            
        Returns:
            是否导出成功
        """
        try:
            engine = self._get_engine(excel_path)
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine=engine)
            df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
            
            self.logger.info(f"工作表导出成功: {sheet_name} -> {output_csv_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"工作表导出失败: {sheet_name}, 错误: {e}")
            return False
    
    def get_dataframe(self, excel_path: str, sheet_name: str = None) -> Optional[pd.DataFrame]:
        """
        获取DataFrame对象
        
        Args:
            excel_path: Excel文件路径
            sheet_name: 工作表名称，为None时返回第一个工作表
            
        Returns:
            DataFrame对象
        """
        try:
            engine = self._get_engine(excel_path)
            
            if sheet_name is None:
                # 读取第一个工作表
                with pd.ExcelFile(excel_path, engine=engine) as excel_file:
                    sheet_name = excel_file.sheet_names[0]
            
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine=engine)
            self.logger.info(f"获取DataFrame成功: {excel_path} - {sheet_name}")
            return df
            
        except Exception as e:
            self.logger.error(f"获取DataFrame失败: {excel_path}, 错误: {e}")
            return None
    
    def is_valid_excel(self, excel_path: str) -> bool:
        """
        检查是否为有效的Excel文件
        
        Args:
            excel_path: Excel文件路径
            
        Returns:
            是否为有效Excel
        """
        try:
            if not os.path.exists(excel_path):
                return False
            
            engine = self._get_engine(excel_path)
            
            with pd.ExcelFile(excel_path, engine=engine) as excel_file:
                is_valid = len(excel_file.sheet_names) > 0
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Excel验证失败: {excel_path}, 错误: {e}")
            return False
    
    def _get_engine(self, excel_path: str) -> Optional[str]:
        """
        根据文件扩展名确定引擎
        
        Args:
            excel_path: Excel文件路径
            
        Returns:
            引擎名称
        """
        file_ext = os.path.splitext(excel_path)[1].lower()
        
        if file_ext == '.xlsx':
            return 'openpyxl'
        elif file_ext == '.xls':
            return 'xlrd'
        else:
            return None
    
    def batch_parse_excels(self, excel_paths: List[str]) -> Dict[str, Optional[str]]:
        """
        批量解析Excel文件
        
        Args:
            excel_paths: Excel文件路径列表
            
        Returns:
            文件路径到解析结果的映射
        """
        results = {}
        
        for excel_path in excel_paths:
            try:
                content = self.parse_excel(excel_path)
                results[excel_path] = content
            except Exception as e:
                self.logger.error(f"批量解析Excel失败: {excel_path}, 错误: {e}")
                results[excel_path] = None
        
        self.logger.info(f"批量解析Excel完成: 共{len(excel_paths)}个文件")
        return results

