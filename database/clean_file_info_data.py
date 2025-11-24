#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理file_info和file_range表数据的脚本

使用方法：
1. 删除指定项目ID的数据：
   python database/clean_file_info_data.py --project_id 1999999999999981140

2. 删除所有数据：
   python database/clean_file_info_data.py --all

3. 删除重复数据（保留最早的一条）：
   python database/clean_file_info_data.py --remove-duplicates

4. 删除指定项目ID的重复数据：
   python database/clean_file_info_data.py --project_id 1999999999999981140 --remove-duplicates
"""

import sys
import os
import argparse
import logging
from typing import Optional

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.database import db_manager
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def delete_by_project_id(project_id: int) -> int:
    """
    删除指定项目ID的所有file_info和file_range数据
    
    Args:
        project_id: 项目ID
        
    Returns:
        int: 删除的记录数
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
                logger.info(f"项目 {project_id} 没有找到file_info记录")
                return 0
            
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
            
            return deleted_infos + deleted_ranges
            
    except Exception as e:
        logger.error(f"删除项目 {project_id} 的数据失败: {e}")
        raise


def delete_all() -> int:
    """
    删除所有file_info和file_range数据
    
    Returns:
        int: 删除的记录数
    """
    try:
        with db_manager.get_db_session() as session:
            # 先查询总数
            count_info_sql = text("SELECT COUNT(*) FROM file_info")
            count_range_sql = text("SELECT COUNT(*) FROM file_range")
            
            total_infos = session.execute(count_info_sql).scalar()
            total_ranges = session.execute(count_range_sql).scalar()
            
            # 删除file_range数据
            delete_range_sql = text("DELETE FROM file_range")
            session.execute(delete_range_sql)
            
            # 删除file_info数据
            delete_info_sql = text("DELETE FROM file_info")
            session.execute(delete_info_sql)
            
            session.commit()
            
            logger.info(f"成功删除所有数据：")
            logger.info(f"  - file_info: {total_infos} 条")
            logger.info(f"  - file_range: {total_ranges} 条")
            
            return total_infos + total_ranges
            
    except Exception as e:
        logger.error(f"删除所有数据失败: {e}")
        raise


def remove_duplicates(project_id: Optional[int] = None) -> int:
    """
    删除重复数据，保留最早的一条记录
    
    Args:
        project_id: 可选，指定项目ID。如果为None，则处理所有项目
        
    Returns:
        int: 删除的记录数
    """
    try:
        with db_manager.get_db_session() as session:
            # 构建查询条件
            where_clause = ""
            params = {}
            if project_id:
                where_clause = "WHERE project_id = :project_id"
                params["project_id"] = project_id
            
            # 查找重复的记录（相同project_id, bid_url, eval_item的组合）
            # 保留id最小的那条，删除其他的
            find_duplicates_sql = text(f"""
                SELECT 
                    fi1.id,
                    fi1.project_id,
                    fi1.bid_url,
                    fi1.eval_item
                FROM file_info fi1
                INNER JOIN (
                    SELECT project_id, bid_url, eval_item, MIN(id) as min_id
                    FROM file_info
                    {where_clause}
                    GROUP BY project_id, bid_url, eval_item
                    HAVING COUNT(*) > 1
                ) fi2 ON fi1.project_id = fi2.project_id
                    AND fi1.bid_url = fi2.bid_url
                    AND fi1.eval_item = fi2.eval_item
                    AND fi1.id > fi2.min_id
            """)
            
            duplicates = session.execute(find_duplicates_sql, params).fetchall()
            
            if not duplicates:
                logger.info("没有找到重复数据")
                return 0
            
            logger.info(f"找到 {len(duplicates)} 条重复记录")
            
            # 收集要删除的file_info_id
            duplicate_ids = [row[0] for row in duplicates]
            
            # 删除file_range数据
            deleted_ranges = 0
            for file_info_id in duplicate_ids:
                delete_range_sql = text("""
                    DELETE FROM file_range
                    WHERE file_info_id = :file_info_id
                """)
                result = session.execute(delete_range_sql, {"file_info_id": file_info_id})
                deleted_ranges += result.rowcount
            
            # 删除file_info数据
            deleted_infos = 0
            for file_info_id in duplicate_ids:
                delete_info_sql = text("""
                    DELETE FROM file_info
                    WHERE id = :file_info_id
                """)
                result = session.execute(delete_info_sql, {"file_info_id": file_info_id})
                deleted_infos += result.rowcount
            
            session.commit()
            
            logger.info(f"成功删除重复数据：")
            logger.info(f"  - file_info: {deleted_infos} 条")
            logger.info(f"  - file_range: {deleted_ranges} 条")
            
            return deleted_infos + deleted_ranges
            
    except Exception as e:
        logger.error(f"删除重复数据失败: {e}")
        raise


def list_data(project_id: Optional[int] = None) -> None:
    """
    列出file_info和file_range数据
    
    Args:
        project_id: 可选，指定项目ID。如果为None，则列出所有数据
    """
    try:
        with db_manager.get_db_session() as session:
            # 构建查询条件
            where_clause = ""
            params = {}
            if project_id:
                where_clause = "WHERE fi.project_id = :project_id"
                params["project_id"] = project_id
            
            query_sql = text(f"""
                SELECT 
                    fi.id,
                    fi.project_id,
                    fi.bid_url,
                    fi.bidder_name,
                    fi.eval_item,
                    fr.start,
                    fr.end,
                    fr.retry
                FROM file_info fi
                LEFT JOIN file_range fr ON fi.id = fr.file_info_id
                {where_clause}
                ORDER BY fi.project_id, fi.bid_url, fi.eval_item
            """)
            
            results = session.execute(query_sql, params).fetchall()
            
            if not results:
                logger.info("没有找到数据")
                return
            
            logger.info(f"找到 {len(results)} 条记录：")
            logger.info("-" * 120)
            logger.info(f"{'ID':<6} {'项目ID':<20} {'投标人':<25} {'条款':<30} {'start':<8} {'end':<8}")
            logger.info("-" * 120)
            
            for row in results:
                file_info_id = row[0]
                proj_id = row[1]
                bid_url = row[2][:20] + "..." if row[2] and len(row[2]) > 20 else (row[2] or "")
                bidder_name = row[3][:23] + "..." if row[3] and len(row[3]) > 23 else (row[3] or "")
                eval_item = row[4][:28] + "..." if row[4] and len(row[4]) > 28 else (row[4] or "")
                start = row[5] if row[5] is not None else "NULL"
                end = row[6] if row[6] is not None else "NULL"
                
                logger.info(f"{file_info_id:<6} {str(proj_id):<20} {bidder_name:<25} {eval_item:<30} {str(start):<8} {str(end):<8}")
            
            logger.info("-" * 120)
            
    except Exception as e:
        logger.error(f"列出数据失败: {e}")
        raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='清理file_info和file_range表数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 列出所有数据
  python database/clean_file_info_data.py --list
  
  # 列出指定项目ID的数据
  python database/clean_file_info_data.py --list --project_id 1999999999999981140
  
  # 删除指定项目ID的数据
  python database/clean_file_info_data.py --project_id 1999999999999981140
  
  # 删除所有数据（需要确认）
  python database/clean_file_info_data.py --all
  
  # 删除重复数据（保留最早的一条）
  python database/clean_file_info_data.py --remove-duplicates
  
  # 删除指定项目ID的重复数据
  python database/clean_file_info_data.py --project_id 1999999999999981140 --remove-duplicates
        """
    )
    
    parser.add_argument(
        '--project_id',
        type=int,
        help='项目ID（可选）'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='删除所有数据（危险操作，需要确认）'
    )
    
    parser.add_argument(
        '--remove-duplicates',
        action='store_true',
        help='删除重复数据，保留最早的一条'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='列出数据，不删除'
    )
    
    parser.add_argument(
        '--yes',
        action='store_true',
        help='跳过确认提示（危险操作时使用）'
    )
    
    args = parser.parse_args()
    
    try:
        # 列出数据
        if args.list:
            list_data(args.project_id)
            return
        
        # 删除所有数据
        if args.all:
            if not args.yes:
                confirm = input("警告：这将删除所有file_info和file_range数据！输入 'YES' 确认: ")
                if confirm != 'YES':
                    logger.info("操作已取消")
                    return
            
            deleted_count = delete_all()
            logger.info(f"删除完成，共删除 {deleted_count} 条记录")
            return
        
        # 删除重复数据
        if args.remove_duplicates:
            if not args.yes:
                scope = f"项目 {args.project_id}" if args.project_id else "所有项目"
                confirm = input(f"警告：这将删除 {scope} 的重复数据（保留最早的一条）！输入 'YES' 确认: ")
                if confirm != 'YES':
                    logger.info("操作已取消")
                    return
            
            deleted_count = remove_duplicates(args.project_id)
            logger.info(f"✅ 删除完成，共删除 {deleted_count} 条重复记录")
            return
        
        # 删除指定项目ID的数据
        if args.project_id:
            if not args.yes:
                confirm = input(f"警告：这将删除项目 {args.project_id} 的所有file_info和file_range数据！输入 'YES' 确认: ")
                if confirm != 'YES':
                    logger.info("操作已取消")
                    return
            
            deleted_count = delete_by_project_id(args.project_id)
            logger.info(f"删除完成，共删除 {deleted_count} 条记录")
            return
        
        # 如果没有指定任何操作，显示帮助信息
        parser.print_help()
        
    except Exception as e:
        logger.error(f"操作失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

