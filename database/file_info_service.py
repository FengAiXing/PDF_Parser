# -*- coding: utf-8 -*-
"""
file_info和file_range表的数据操作服务
"""

import sys
import os
import logging
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.database import db_manager
from sqlalchemy import text

logger = logging.getLogger(__name__)


def save_file_info_and_range(
    project_id: int,
    bid_url: str,
    bider_name: str,
    eval_item: str
) -> Optional[int]:
    """
    保存file_info和file_range数据（每个评审项对应单个条款）
    如果已存在相同的(project_id, bid_url, eval_item)组合，则返回现有记录ID，不重复插入
    
    Args:
        project_id: 项目ID
        bid_url: 投标文件URL
        bider_name: 投标人名称（参数名保持兼容，实际数据库字段是bidder_name）
        eval_item: 单个评审条款（不再是列表）
        
    Returns:
        Optional[int]: file_info的主键ID，失败返回None
    """
    try:
        with db_manager.get_db_session() as session:
            # 先检查是否已存在相同的记录
            check_sql = text("""
                SELECT id FROM file_info
                WHERE project_id = :project_id
                AND bid_url = :bid_url
                AND eval_item = :eval_item
                LIMIT 1
            """)
            
            existing = session.execute(check_sql, {
                "project_id": project_id,
                "bid_url": bid_url,
                "eval_item": eval_item
            }).fetchone()
            
            if existing:
                # 记录已存在，返回现有ID
                file_info_id = existing[0]
                logger.info(f"记录已存在，使用现有file_info_id: {file_info_id}, 评审条款: {eval_item}")
                
                # 检查是否已有file_range记录
                check_range_sql = text("""
                    SELECT id FROM file_range
                    WHERE file_info_id = :file_info_id
                    LIMIT 1
                """)
                existing_range = session.execute(check_range_sql, {
                    "file_info_id": file_info_id
                }).fetchone()
                
                if not existing_range:
                    # 如果没有file_range记录，创建一个
                    insert_file_range_sql = text("""
                        INSERT INTO file_range (file_info_id, start, end, retry)
                        VALUES (:file_info_id, :start, :end, :retry)
                    """)
                    
                    session.execute(insert_file_range_sql, {
                        "file_info_id": file_info_id,
                        "start": None,
                        "end": None,
                        "retry": 0
                    })
                    session.commit()
                    logger.info(f"为现有file_info创建file_range记录，file_info_id: {file_info_id}")
                
                return file_info_id
            
            # 记录不存在，插入新记录
            insert_file_info_sql = text("""
                INSERT INTO file_info (bid_url, project_id, bidder_name, eval_item)
                VALUES (:bid_url, :project_id, :bidder_name, :eval_item)
            """)
            
            result = session.execute(insert_file_info_sql, {
                "bid_url": bid_url,
                "project_id": project_id,
                "bidder_name": bider_name,  # 参数名是bider_name，但数据库字段是bidder_name
                "eval_item": eval_item
            })
            
            # 获取插入的file_info的ID
            file_info_id = result.lastrowid
            
            # 插入file_range数据（不再包含 eval_item，因为已移到 file_info 中）
            insert_file_range_sql = text("""
                INSERT INTO file_range (file_info_id, start, end, retry)
                VALUES (:file_info_id, :start, :end, :retry)
            """)
            
            session.execute(insert_file_range_sql, {
                "file_info_id": file_info_id,
                "start": None,  # 开始页留空
                "end": None,    # 结束页留空
                "retry": 0      # 初始重试次数为0
            })
            
            session.commit()
            logger.info(f"成功保存file_info和file_range数据，file_info_id: {file_info_id}, 评审条款: {eval_item}")
            return file_info_id
            
    except Exception as e:
        logger.error(f"保存file_info和file_range数据失败: {e}")
        return None


def batch_save_file_info_and_range(
    project_id: int,
    file_data_list: List[Dict[str, Any]]
) -> bool:
    """
    批量保存file_info和file_range数据（每个条款创建一条记录）
    
    Args:
        project_id: 项目ID
        file_data_list: 文件数据列表，每个元素包含：
            - bid_url: 投标文件URL
            - bider_name: 投标人名称
            - eval_items: 评审条款列表（会为每个条款创建一条file_info记录）
            
    Returns:
        bool: 是否全部保存成功
    """
    try:
        success_count = 0
        total_count = 0
        
        for file_data in file_data_list:
            bid_url = file_data.get("bid_url")
            bider_name = file_data.get("bider_name")
            eval_items = file_data.get("eval_items", [])
            
            if not bid_url or not bider_name:
                logger.warning(f"文件数据缺少必要字段: {file_data}")
                continue
            
            # 为每个条款创建一条 file_info 记录
            if not eval_items:
                logger.warning(f"文件数据没有评审条款: {file_data}")
                continue
            
            for eval_item in eval_items:
                total_count += 1
                file_info_id = save_file_info_and_range(
                    project_id=project_id,
                    bid_url=bid_url,
                    bider_name=bider_name,
                    eval_item=eval_item
                )
                
                if file_info_id:
                    success_count += 1
        
        logger.info(f"批量保存完成，成功: {success_count}/{total_count}")
        return success_count == total_count
        
    except Exception as e:
        logger.error(f"批量保存file_info和file_range数据失败: {e}")
        return False


def get_file_info_and_range_by_project_id(project_id: int) -> List[Dict[str, Any]]:
    """
    根据项目ID获取file_info和file_range数据
    
    Args:
        project_id: 项目ID
        
    Returns:
        List[Dict[str, Any]]: file_info和file_range数据列表，每个元素包含：
            - file_info_id: file_info的主键ID
            - bid_url: 投标文件URL
            - bidder_name: 投标人名称
            - eval_item: 评审条款
            - start: 开始页码
            - end: 结束页码
            - retry: 重试次数
    """
    try:
        with db_manager.get_db_session() as session:
            query = text("""
                SELECT 
                    fi.id as file_info_id,
                    fi.bid_url,
                    fi.bidder_name,
                    fi.eval_item,
                    fr.start,
                    fr.end,
                    fr.retry
                FROM file_info fi
                LEFT JOIN file_range fr ON fi.id = fr.file_info_id
                WHERE fi.project_id = :project_id
                ORDER BY fi.bid_url, fi.eval_item
            """)
            
            result = session.execute(query, {"project_id": project_id}).fetchall()
            
            data_list = []
            for row in result:
                data_list.append({
                    "file_info_id": row[0],
                    "bid_url": row[1],
                    "bidder_name": row[2],
                    "eval_item": row[3],
                    "start": row[4],
                    "end": row[5],
                    "retry": row[6] if row[6] is not None else 0
                })
            
            logger.info(f"成功获取项目 {project_id} 的 {len(data_list)} 条file_info和file_range数据")
            return data_list
            
    except Exception as e:
        logger.error(f"获取file_info和file_range数据失败: {e}")
        return []


def update_reference_sources(project_id: int, reference_sources: List[Dict[str, Any]]) -> bool:
    """
    更新eval_report表的reference_sources字段
    
    Args:
        project_id: 项目ID
        reference_sources: 引用来源列表
        
    Returns:
        bool: 是否更新成功
    """
    try:
        import json
        
        with db_manager.get_db_session() as session:
            # 将reference_sources转换为JSON字符串（格式化，与save_task_results_to_database保持一致）
            reference_sources_json = json.dumps(reference_sources, ensure_ascii=False, indent=2)
            
            # 更新reference_sources字段
            update_sql = text("""
                UPDATE eval_report 
                SET reference_sources = :reference_sources
                WHERE id = :project_id
            """)
            
            result = session.execute(update_sql, {
                "reference_sources": reference_sources_json,
                "project_id": project_id
            })
            
            if result.rowcount > 0:
                session.commit()
                logger.info(f"成功更新reference_sources，项目ID: {project_id}")
                return True
            else:
                logger.warning(f"未找到项目ID为 {project_id} 的记录")
                return False
                
    except Exception as e:
        logger.error(f"更新reference_sources失败: {e}")
        return False

def update_file_range_page_range(file_info_id: int, start: Optional[int], end: Optional[int]) -> bool:
    """
    更新file_range表的start和end字段
    
    Args:
        file_info_id: file_info的主键ID
        start: 开始页码（从1开始，可以为None）
        end: 结束页码（从1开始，可以为None）
        
    Returns:
        bool: 是否更新成功
    """
    try:
        with db_manager.get_db_session() as session:
            update_sql = text("""
                UPDATE file_range 
                SET start = :start, end = :end
                WHERE file_info_id = :file_info_id
            """)
            
            result = session.execute(update_sql, {
                "file_info_id": file_info_id,
                "start": start,
                "end": end
            })
            
            if result.rowcount > 0:
                session.commit()
                logger.info(f"成功更新file_range页码范围，file_info_id: {file_info_id}, start: {start}, end: {end}")
                return True
            else:
                logger.warning(f"未找到file_info_id为 {file_info_id} 的file_range记录")
                return False
                
    except Exception as e:
        logger.error(f"更新file_range页码范围失败: {e}")
        return False


def delete_file_info_and_range_by_project_id(project_id: int) -> bool:
    """
    删除指定项目ID的所有file_info和file_range数据
    
    Args:
        project_id: 项目ID
        
    Returns:
        bool: 是否删除成功
    """
    try:
        with db_manager.get_db_session() as session:
            # 先查询要删除的file_info_id列表
            query_sql = text("""
                SELECT id FROM file_info
                WHERE project_id = :project_id
            """)
            file_info_ids = session.execute(query_sql, {"project_id": project_id}).fetchall()
            file_info_id_list = [row[0] for row in file_info_ids]
            
            if not file_info_id_list:
                logger.info(f"项目 {project_id} 没有找到file_info记录，无需删除")
                return True
            
            # 删除file_range数据（先删除外键关联的表）
            deleted_ranges = 0
            for file_info_id in file_info_id_list:
                delete_range_sql = text("""
                    DELETE FROM file_range
                    WHERE file_info_id = :file_info_id
                """)
                result = session.execute(delete_range_sql, {"file_info_id": file_info_id})
                deleted_ranges += result.rowcount
            
            # 删除file_info数据
            delete_info_sql = text("""
                DELETE FROM file_info
                WHERE project_id = :project_id
            """)
            result = session.execute(delete_info_sql, {"project_id": project_id})
            deleted_infos = result.rowcount
            
            session.commit()
            
            logger.info(f"成功删除项目 {project_id} 的数据：")
            logger.info(f"  - file_info: {deleted_infos} 条")
            logger.info(f"  - file_range: {deleted_ranges} 条")
            
            return True
            
    except Exception as e:
        logger.error(f"删除项目 {project_id} 的数据失败: {e}")
        return False


