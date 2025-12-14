# -*- coding: utf-8 -*-
"""
文件处理器 - FileProcessor

提供完整的PDF解析功能（文本 + 表格 + 图片）：
- 粗解析提取文本内容（移除页眉页脚）
- 识别并解析表格（包括跨页表格）
- 提取并识别图片（OCR）
- 组装完整文档（按页组织）
"""

import os
import shutil
import logging
import fitz
import asyncio
from datetime import datetime
from typing import Dict, Optional

from .config import Config
from .parsers import CoarseParser, VisionParser, TableParser
from .image import ImageExtractor, StampDetector
from .utils import DocumentAssembler, HeaderFooterCleaner


class FileProcessor:
    """文件处理器 - 完整PDF解析功能"""
    
    def __init__(self, 
                 vision_model: str = "doubao-seed-1-6-vision-250815",
                 max_workers: int = 100):
        """
        初始化文件处理器
        
        Args:
            vision_model: 视觉模型名称
            max_workers: 并发处理数
        """
        self.logger = logging.getLogger(__name__)
        self.vision_model = vision_model
        self.max_workers = max_workers
        
        self.logger.info(f"文件处理器初始化完成: vision_model={vision_model}, max_workers={max_workers}")
    
    def process_pdf_full(self,
                        pdf_path: str,
                        output_dir: str = "output_complete",
                        save_table_images: bool = True,
                        save_single_table_results: bool = True,
                        remove_header_footer: bool = True,
                        use_smart_removal: bool = True,
                        enable_stamp_detection: bool = True,
                        stamp_similarity_threshold: float = 0.95) -> Dict:
        """
        完整解析PDF文件（文本 + 表格 + 图片）
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            save_table_images: 是否保存表格图片
            save_single_table_results: 是否保存单张表格识别结果
            remove_header_footer: 是否移除页眉页脚
            use_smart_removal: 是否使用智能移除方法（基于位置）
            enable_stamp_detection: 是否启用签章识别（自动去重相似签章）
            stamp_similarity_threshold: 签章相似度阈值（0-1），高于此值认为是相同签章
            
        Returns:
            解析结果字典：
            - success: 是否成功
            - final_output: 最终输出文件路径
            - tables_dir: 表格图片目录
            - images_dir: 图片目录
            - single_table_results_dir: 单张表格识别结果目录
            - image_ocr_results_dir: 单张图片OCR结果目录
            - stamps_dir: 签章图片目录（如果启用签章识别）
            - statistics: 统计信息
            - stamp_detection: 签章识别结果（如果启用）
            - error: 错误信息（如果有）
        """
        # 始终使用异步实现（文本/表格/图片/签章互不阻塞，仅最终合并）
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                msg = "检测到事件循环正在运行，请直接调用并 await process_pdf_full_async"
                self.logger.error(msg)
                raise RuntimeError(msg)
        except RuntimeError:
            pass

        # 使用异步实现
        return asyncio.run(self.process_pdf_full_async(
            pdf_path=pdf_path,
            output_dir=output_dir,
            save_table_images=save_table_images,
            save_single_table_results=save_single_table_results,
            remove_header_footer=remove_header_footer,
            use_smart_removal=use_smart_removal,
            enable_stamp_detection=enable_stamp_detection,
            stamp_similarity_threshold=stamp_similarity_threshold
        ))

    async def process_pdf_full_async(self,
                                    pdf_path: str,
                                    output_dir: str = "output_complete",
                                    save_table_images: bool = True,
                                    save_single_table_results: bool = True,
                                    remove_header_footer: bool = True,
                                    use_smart_removal: bool = True,
                                    enable_stamp_detection: bool = True,
                                    stamp_similarity_threshold: float = 0.95) -> Dict:
        """
        异步完整解析PDF文件（文本 + 表格 + 图片）
        将耗时的同步步骤放入线程池，图片OCR/签章使用异步接口。
        """
        result = {
            'success': False,
            'final_output': None,
            'tables_dir': None,
            'images_dir': None,
            'stamps_dir': None,
            'single_table_results_dir': None,
            'image_ocr_results_dir': None,
            'statistics': {},
            'stamp_detection': None,
            'error': None
        }

        loop = asyncio.get_running_loop()

        try:
            if not os.path.exists(pdf_path):
                error_msg = f"找不到文件: {pdf_path}"
                self.logger.error(error_msg)
                result['error'] = error_msg
                return result
            
            # 只有需要保存文件时才创建输出目录
            if Config.ENABLE_ALL_SAVES:
                os.makedirs(output_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]

            tables_dir = os.path.join(output_dir, f"tables_{timestamp}")
            images_dir = os.path.join(output_dir, f"images_{timestamp}")
            stamps_dir = os.path.join(output_dir, f"stamps_{timestamp}")
            final_output = os.path.join(output_dir, f"{base_name}_完整解析含表格_{timestamp}.txt")

            self.logger.info(f"[async] 开始处理PDF: {pdf_path}")

            # Step 1: 文本粗解析（线程池）
            start_time_text = datetime.now()
            common_headers, common_footers = set(), set()
            
            # 预先检测页眉页脚（只检测一次）
            if remove_header_footer and use_smart_removal:
                try:
                    cleaner = HeaderFooterCleaner()
                    doc_for_common = fitz.open(pdf_path)
                    common_headers, common_footers = cleaner.detect_common_texts(doc_for_common, repeat_threshold=2)
                    doc_for_common.close()
                except Exception as e:
                    self.logger.warning(f"[async] 检测通用页眉页脚失败: {e}")
            
            # 传入预检测的页眉页脚，避免重复检测
            coarse_parser = CoarseParser(
                remove_header_footer=remove_header_footer,
                use_smart_removal=use_smart_removal,
                common_headers=common_headers,
                common_footers=common_footers
            )

            text_content = await coarse_parser.parse_file_async(pdf_path)

            assembler = DocumentAssembler(
                pdf_path=pdf_path,
                common_headers=common_headers,
                common_footers=common_footers
            )
            page_texts = assembler.parse_text_by_page(text_content) if text_content else {}
            duration_text = (datetime.now() - start_time_text).total_seconds()
            self.logger.info(f"[async] 文本提取完成: {len(page_texts)}页, 耗时{duration_text:.2f}秒")

            # Step 2 & 3: 表格解析 与 (图片提取+OCR) 并行执行
            # 并行执行表格识别和图片OCR
            start_time_parallel = datetime.now()
            
            # ========== 定义表格处理任务 ==========
            async def process_tables_task():
                start_time = datetime.now()
                
                # 根据 Config 决定是否启用表格解析
                if not Config.should_parse_tables():
                    self.logger.info("[async] 表格解析已禁用 (ENABLE_TABLE_PARSING=False)")
                    return {'tables': [], 'total_count': 0, 'cross_page_count': 0, 'duration': 0}
                
                table_parser = TableParser(max_workers=self.max_workers)
                # 根据 Config 决定是否保存表格图片
                should_save_table_images = save_table_images and Config.should_save_table_images()
                result = await table_parser.parse_pdf_tables_async(
                    pdf_path=pdf_path,
                    output_dir=tables_dir,
                    save_images=should_save_table_images
                )
                result['duration'] = (datetime.now() - start_time).total_seconds()
                return result
            
            # ========== 定义图片处理任务（提取+签章识别+OCR） ==========
            async def process_images_task():
                start_time = datetime.now()
                image_result = {
                    'images_metadata': [],
                    'page_images': {},
                    'stamp_detection_result': None,
                    'total_extracted': 0,
                    'total_processed': 0,
                    'duration': 0
                }
                
                # 根据 Config 决定是否启用图片解析
                if not Config.should_parse_images():
                    self.logger.info("[async] 图片解析已禁用 (ENABLE_IMAGE_PARSING=False)")
                    image_result['duration'] = (datetime.now() - start_time).total_seconds()
                    return image_result
                
                # 1. 智能图片提取（自动处理扫描版PDF）
                # 对于没有文本和嵌入图片的页面，自动渲染为图片进行OCR
                image_extractor = ImageExtractor()
                should_save_images = Config.should_save_extracted_images()
                images_metadata = await loop.run_in_executor(
                    None, lambda: image_extractor.extract_images_smart(
                        pdf_path, images_dir, save_to_disk=should_save_images,
                        render_empty_pages=True, render_dpi=150
                    )
                )
                image_result['images_metadata'] = images_metadata
                image_result['total_extracted'] = len(images_metadata)
                
                if not images_metadata:
                    image_result['duration'] = (datetime.now() - start_time).total_seconds()
                    return image_result
                
                # 2. 签章识别（根据 Config 决定是否启用）
                stamp_images_to_process = []
                non_stamp_images_to_process = []
                
                # 检查是否启用签章识别
                should_detect_stamps = enable_stamp_detection and Config.should_detect_stamps()
                
                if should_detect_stamps:
                    stamp_detector = StampDetector(similarity_threshold=stamp_similarity_threshold)
                    stamp_detection_result = await loop.run_in_executor(
                        None, stamp_detector.detect_and_deduplicate, images_metadata
                    )
                    image_result['stamp_detection_result'] = stamp_detection_result
                    
                    # 根据 Config 决定是否解析签章内容
                    if Config.should_parse_stamps():
                        stamp_images_to_process = [
                            (img['path'], img['page'], img.get('y0', 0)) for img in stamp_detection_result['unique_stamps']
                        ]
                    
                    non_stamp_images_to_process = [
                        (img['path'], img['page'], img.get('y0', 0)) for img in stamp_detection_result['non_stamp_images']
                    ]
                    
                    # 保存签章图片（根据 Config 配置）
                    if Config.should_save_stamp_images() and stamp_detection_result['unique_stamps']:
                        os.makedirs(stamps_dir, exist_ok=True)
                        for idx, stamp_info in enumerate(stamp_detection_result['unique_stamps'], 1):
                            src_path = stamp_info['path']
                            page_num = stamp_info['page']
                            ext = os.path.splitext(src_path)[1]
                            dst_filename = f"stamp_{idx}_page_{page_num}{ext}"
                            dst_path = os.path.join(stamps_dir, dst_filename)
                            try:
                                shutil.copy2(src_path, dst_path)
                            except Exception as e:
                                self.logger.warning(f"[async] 保存签章图片失败: {e}")
                else:
                    non_stamp_images_to_process = [(img['path'], img['page'], img.get('y0', 0)) for img in images_metadata]
                
                # 3. 图片OCR
                vision_parser = VisionParser()
                page_images = {}
                
                # 根据配置选择普通图片的提示词
                # - 签章识别开启：非签章图片用含圆章判断的提示词
                # - 签章识别关闭但签章解析开启：所有图片用含圆章判断的提示词
                # - 两者都关闭：所有图片用不含圆章判断的提示词
                if should_detect_stamps:
                    # 签章识别开启，非签章图片用默认提示词（含圆章判断）
                    non_stamp_prompt = vision_parser.DEFAULT_TEXT_PROMPT
                elif Config.should_parse_stamps():
                    # 签章识别关闭但签章解析开启，用含圆章判断的提示词
                    non_stamp_prompt = vision_parser.DEFAULT_TEXT_PROMPT
                else:
                    # 两者都关闭，用不含圆章判断的提示词
                    non_stamp_prompt = vision_parser.DEFAULT_TEXT_PROMPT_NO_STAMP
                
                # 打印待处理图片统计
                total_to_process = len(non_stamp_images_to_process) + len(stamp_images_to_process)
                if total_to_process > 0:
                    self.logger.info(f"[async] 开始视觉模型解析: 签章图片 {len(stamp_images_to_process)} 张, "
                                    f"非签章图片 {len(non_stamp_images_to_process)} 张, "
                                    f"总共处理 {total_to_process} 张图片")
                
                if non_stamp_images_to_process:
                    ocr_results_by_page = await vision_parser.parse_images_with_pages_async(
                        non_stamp_images_to_process,
                        max_workers=self.max_workers,
                        prompt=non_stamp_prompt
                    )
                    page_images = assembler.organize_images_by_page(ocr_results_by_page)
                
                if stamp_images_to_process:
                    stamp_ocr_results = await vision_parser.parse_images_with_pages_async(
                        stamp_images_to_process,
                        max_workers=self.max_workers,
                        prompt=vision_parser.DEFAULT_STAMP_PROMPT
                    )
                    stamp_page_images = assembler.organize_images_by_page(stamp_ocr_results)
                    for page_num, images in stamp_page_images.items():
                        if page_num not in page_images:
                            page_images[page_num] = []
                        page_images[page_num].extend(images)
                
                image_result['page_images'] = page_images
                image_result['total_processed'] = len(non_stamp_images_to_process) + len(stamp_images_to_process)
                
                # 如果不保存图片，OCR 完成后清理临时文件
                if not should_save_images and images_metadata:
                    for img_info in images_metadata:
                        try:
                            img_path = img_info.get('path')
                            if img_path and os.path.exists(img_path):
                                os.remove(img_path)
                        except Exception as e:
                            self.logger.debug(f"清理临时图片失败: {e}")
                    # 清理临时目录
                    try:
                        temp_dir = os.path.dirname(images_metadata[0].get('path', ''))
                        if temp_dir and os.path.exists(temp_dir) and 'temp' in temp_dir.lower():
                            shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception as e:
                        self.logger.debug(f"清理临时目录失败: {e}")
                
                image_result['duration'] = (datetime.now() - start_time).total_seconds()
                return image_result
            
            # ========== 并行执行两个任务 ==========
            table_result, image_result = await asyncio.gather(
                process_tables_task(),
                process_images_task()
            )
            
            duration_parallel = (datetime.now() - start_time_parallel).total_seconds()
            duration_table = table_result.get('duration', 0)
            duration_image = image_result.get('duration', 0)
            
            # 处理表格结果
            page_tables = assembler.organize_tables_by_page(table_result['tables'])
            
            # 处理图片结果
            images_metadata = image_result['images_metadata']
            page_images = image_result['page_images']
            stamp_detection_result = image_result['stamp_detection_result']
            total_images_extracted = image_result['total_extracted']
            total_images_processed = image_result['total_processed']
            
            # 保存签章检测结果
            if stamp_detection_result:
                result['stamp_detection'] = stamp_detection_result
                if stamp_detection_result['unique_stamps']:
                    result['stamps_dir'] = stamps_dir

            # 保存单张表格识别结果（根据 Config 配置）
            single_table_results_dir = None
            if save_single_table_results and Config.should_save_single_table_results() and table_result['tables']:
                single_table_results_dir = os.path.join(output_dir, f"single_table_results_{timestamp}")
                os.makedirs(single_table_results_dir, exist_ok=True)
                for i, table in enumerate(table_result['tables'], 1):
                    if table.get('is_cross_page'):
                        original_results = table.get('original_results', {})
                        original_image_paths = table.get('original_image_paths', [])
                        original_tables = table.get('original_tables', [])
                        if original_results and original_image_paths:
                            for idx, img_path in enumerate(original_image_paths):
                                if img_path in original_results and original_results[img_path]:
                                    orig_table = original_tables[idx] if idx < len(original_tables) else None
                                    page_num = orig_table['page'] if orig_table else '?'
                                    result_filename = f"table_{table['id']}_part{idx+1}_page_{page_num}.txt"
                                    result_filepath = os.path.join(single_table_results_dir, result_filename)
                                    with open(result_filepath, 'w', encoding='utf-8') as f:
                                        f.write(f"跨页表格ID: {table['id']} (第{idx+1}/{len(original_image_paths)}部分)\n")
                                        f.write(f"页码: 第{page_num}页\n")
                                        f.write(f"原始图片: {os.path.basename(img_path)}\n")
                                        f.write("=" * 80 + "\n\n")
                                        f.write(original_results[img_path])
                    else:
                        if table.get('recognized_content'):
                            result_filename = f"table_{table['id']}_page_{table['page']}.txt"
                            result_filepath = os.path.join(single_table_results_dir, result_filename)
                            col_count = table.get('col_count', 0)
                            row_count = table.get('row_count', 0)
                            with open(result_filepath, 'w', encoding='utf-8') as f:
                                f.write(f"表格ID: {table['id']}\n")
                                f.write(f"页码: 第{table['page']}页\n")
                                f.write(f"类型: 单页表格\n")
                                f.write(f"列数: {col_count}\n")
                                f.write(f"行数: {row_count}\n")
                                f.write("=" * 80 + "\n\n")
                                f.write(table['recognized_content'])

            # 保存单张图片OCR结果（根据 Config 配置）
            image_ocr_results_dir = None
            if Config.should_save_image_ocr_results() and page_images:
                image_ocr_results_dir = os.path.join(output_dir, f"image_ocr_results_{timestamp}")
                os.makedirs(image_ocr_results_dir, exist_ok=True)
                img_counter = 0
                for page_num in sorted(page_images.keys()):
                    for img_info in page_images[page_num]:
                        img_filename = img_info.get('image', '')
                        ocr_text = img_info.get('text', '')
                        if ocr_text and ocr_text.strip():
                            img_counter += 1
                            img_name_without_ext = os.path.splitext(img_filename)[0] if img_filename else f"image_{img_counter}"
                            result_filename = f"image_{img_counter}_page_{page_num}_{img_name_without_ext}.txt"
                            result_filepath = os.path.join(image_ocr_results_dir, result_filename)
                            with open(result_filepath, 'w', encoding='utf-8') as f:
                                f.write(f"图片序号: {img_counter}\n")
                                f.write(f"页码: 第{page_num}页\n")
                                f.write(f"原始图片: {img_filename}\n")
                                f.write("=" * 80 + "\n\n")
                                f.write(ocr_text)

            # 组装 & 落盘
            self.logger.info("[async] 【组织内容】按页合并文本、表格、图片")
            final_content = assembler.assemble_document(
                page_texts=page_texts,
                page_tables=page_tables,
                page_images=page_images,
                pdf_filename=base_name,
                single_table_results_dir=single_table_results_dir
            )
            
            # 保存最终结果（根据 Config 配置）
            if Config.should_save_final_result():
                with open(final_output, 'w', encoding='utf-8') as f:
                    f.write(final_content)

            total_duration = duration_text + duration_parallel
            
            statistics = {
                'total_duration': total_duration,
                'text_duration': duration_text,
                'table_duration': duration_table,
                'image_duration': duration_image,
                'parallel_duration': duration_parallel,
                'text_pages': len(page_texts),
                'total_tables': table_result['total_count'],
                'cross_page_tables': table_result['cross_page_count'],
                'single_page_tables': table_result['total_count'] - table_result['cross_page_count'],
                'total_images': total_images_extracted,
                'images_processed': total_images_processed
            }
            if stamp_detection_result:
                stamp_stats = stamp_detection_result['statistics']
                statistics['stamp_detection'] = {
                    'enabled': True,
                    'stamp_candidates': stamp_stats['stamp_candidates_count'],
                    'unique_stamps': stamp_stats['unique_stamps_count'],
                    'duplicated_stamps': stamp_stats['duplicated_stamps_count'],
                    'non_stamp_images': stamp_stats['non_stamp_count'],
                    'similarity_threshold': stamp_similarity_threshold
                }
            else:
                statistics['stamp_detection'] = {'enabled': False}

            result.update({
                'success': True,
                'final_content': final_content,  # 合并后的完整文本内容
                'final_output': final_output,
                'tables_dir': tables_dir,
                'images_dir': images_dir,
                'single_table_results_dir': single_table_results_dir,
                'image_ocr_results_dir': image_ocr_results_dir,
                'statistics': statistics
            })

            # 显示解析完成总结
            print("\n" + "="*100)
            print("【解析完成】")
            print("="*100)
            
            print(f"\n⏱️  总耗时: {total_duration:.2f} 秒 ({total_duration/60:.1f} 分钟)")
            print(f"   - 文本提取: {duration_text:.2f} 秒")
            print(f"   - 表格解析: {duration_table:.2f} 秒")
            print(f"   - 图片解析: {duration_image:.2f} 秒")
            
            print(f"\n📊 内容统计:")
            print(f"   - 文本页数: {len(page_texts)} 页")
            print(f"   - 表格数: {table_result['total_count']} 个")
            print(f"   - 跨页表格: {table_result['cross_page_count']} 个")
            print(f"   - 单页表格: {table_result['total_count'] - table_result['cross_page_count']} 个")
            print(f"   - 图片数: {total_images_extracted} 张 (处理: {total_images_processed} 张)")
            
            # 显示签章识别统计
            if stamp_detection_result:
                ss = stamp_detection_result['statistics']
                print(f"\n🔏 签章识别:")
                print(f"   - 签章候选: {ss['stamp_candidates_count']} 张")
                print(f"   - 唯一签章: {ss['unique_stamps_count']} 张")
                print(f"   - 去重签章: {ss['duplicated_stamps_count']} 张")
                print(f"   - 相似度阈值: {stamp_similarity_threshold:.0%}")
            
            print(f"\n💾 输出文件:")
            if Config.should_save_final_result():
                print(f"   📄 完整解析结果: {final_output}")
            if table_result['total_count'] > 0 and Config.should_save_table_images():
                print(f"   📁 表格图片: {tables_dir}")
            if single_table_results_dir and Config.should_save_single_table_results():
                print(f"   📁 单张表格识别结果: {single_table_results_dir}")
            if total_images_extracted > 0 and Config.should_save_extracted_images():
                print(f"   📁 提取的图片: {images_dir}")
            if result.get('stamps_dir') and Config.should_save_stamp_images():
                print(f"   🔏 签章图片: {result['stamps_dir']}")
            if image_ocr_results_dir and Config.should_save_image_ocr_results():
                print(f"   📁 单张图片OCR结果: {image_ocr_results_dir}")
            
            print(f"\n✅ 解析成功完成！")
            
            return result

        except Exception as e:
            error_msg = f"[async] 处理PDF失败: {pdf_path}, 错误: {e}"
            self.logger.error(error_msg, exc_info=True)
            result['error'] = str(e)
            return result
