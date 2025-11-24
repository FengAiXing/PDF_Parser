#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import sys
import os
import logging
import json
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.business.service.bid_report_service import BidReportService

async def test_bid_report_steps():
    service = BidReportService()
    
    project_id = "1999999999999981134"
    template_id = "3"
    
    files_config = {
        #   服务3
        # "tender_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/89a14909e5944efdabc8f16a843c9b4d/中央机厂运输入围服务招标文件.pdf",
        # "opening_record_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/9cfec91f4e384abea1b0b76185b068d2/JNA140-ZB-250613520_001开标.xls",
        # "review_experts_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/b61a17468277454e8e8a834ef3b659fd/评审监督表.pdf",
        # "evaluation_summary_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/96b47bef4a4d4e1a899985c116b9dbd1/JNA140-ZB-250613520-001评标.pdf",
        # "candidate_bid_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/94ead216e4f64522ab998f3a22a01f39/第四大同市平城区骏腾吊装运输部-投标文件.pdf",
        # "other_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/8e0b731880db4450becaaf8ba86edbc1/项目公告审批记录.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/dc5c9f63a36743cb98fdc21127c4b4b5/评标复核卡9.25.pdf"
      
        #   服务3
        # "tender_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/72494435ebc541259b97e177588e68b2/阳泉燕龛块炭加工招标文件.pdf",
        # "opening_record_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/a721ac5c9ba44747816fbd01f7895f3e/JNC152-ZB-250613354_001开标.xls",
        # "review_experts_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/a343804daf714391b210829143e939da/块炭加工分拣及储装运监督报告.pdf",
        # "evaluation_summary_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/4c58b7f5a57b46279f3c18033aa38cfe/JNC152-ZB-250613354-001评标.pdf",
        # "candidate_bid_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/9f3d56c99e4240edbf37fd7a39747c99/一--阳泉煤矿签章版投标文件4.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/87833941d14a4be2b05f847bf41ffb50/天佑成投标文件.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/2604cca6defc4106ba7cdf649bb4c38e/昔阳县赛诺洁净煤有限公司投标文件.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/0c7dbe0b7e1b451eb9b8e0ebdea87cfb/阳泉兴正贸易有限公司投标文件.pdf",
        # "other_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/0cc0d091e1944dd3aeb772fc4af5f355/块炭加工分拣及储装运_下载记录_202506260.xlsx,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/a55e585d26204ea88f21e514fe7fe1c0/项目公告审批记录.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/dc5c9f63a36743cb98fdc21127c4b4b5/评标复核卡9.25.pdf"
      
            
        #   服务3  小的投标文件
        # "tender_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/72494435ebc541259b97e177588e68b2/阳泉燕龛块炭加工招标文件.pdf",
        # "opening_record_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/a721ac5c9ba44747816fbd01f7895f3e/JNC152-ZB-250613354_001开标.xls",
        # "review_experts_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/a343804daf714391b210829143e939da/块炭加工分拣及储装运监督报告.pdf",
        # "evaluation_summary_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/4c58b7f5a57b46279f3c18033aa38cfe/JNC152-ZB-250613354-001评标.pdf",
        # "candidate_bid_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/0c7dbe0b7e1b451eb9b8e0ebdea87cfb/阳泉兴正贸易有限公司投标文件.pdf",
        # "other_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/0cc0d091e1944dd3aeb772fc4af5f355/块炭加工分拣及储装运_下载记录_202506260.xlsx,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/a55e585d26204ea88f21e514fe7fe1c0/项目公告审批记录.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/dc5c9f63a36743cb98fdc21127c4b4b5/评标复核卡9.25.pdf"
      
      
        #   工程1
        "tender_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/6f71eac0ec6645b79ce9a8454be7c0fc/定山西晋丰煤化工有限责任公司造气节能环保提升及配套.pdf",
        "opening_record_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/ef610ef802a64c1d8f59f8af783a4807/JNA134-ZB-240811324_001开标.xls",
        "review_experts_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/c810d1a754a747dbb7a6b60322a4d10d/山西晋丰煤化工有限责任公司造气节能环保提升及配套改.pdf",
        "evaluation_summary_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/05b5ba3bb52f4d2284b7c75af1bd668a/JNA134-ZB-240811324-001评标.pdf",
        # "candidate_bid_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/5c9189bce8604f29a50416d1a8b6d5ee/二--山西晋丰煤化工有限责任公司造气节能环保提升及.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/9406507896b44d4da7cceaeff13bd76b/一--（改版）投标文件2024.12.10.pdf",
        "candidate_bid_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/5c9189bce8604f29a50416d1a8b6d5ee/二--山西晋丰煤化工有限责任公司造气节能环保提升及.pdf",
        "other_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/208dea84c9514286ac52a896afa93d4d/项目公告审批记录.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/ce8273847cf04ec2add0ab880e3e3e70/山西晋丰煤化工有限责任公司造气节能环保提升及配套改.xlsx,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/dc5c9f63a36743cb98fdc21127c4b4b5/评标复核卡9.25.pdf"
     
        # 工程1  无投标文件
        # "tender_file": r"C:\Users\gf133\Desktop\变量提取文件\测试文件\中央机厂运输入围服务招标文件.pdf",
        # "opening_record_file": r"C:\Users\gf133\Desktop\变量提取文件\测试文件\JNA140-ZB-250613520_001开标记录表.xls",
        # "review_experts_file": r"C:\Users\gf133\Desktop\变量提取文件\测试文件\评审监督表.pdf",
        # "evaluation_summary_file": r"C:\Users\gf133\Desktop\变量提取文件\测试文件\JNA140-ZB-250613520-001评标表格.pdf",
        # "candidate_bid_files": r"C:\Users\gf133\Desktop\变量提取文件\测试文件\项目公告审批记录.pdf",
        # "other_files": r"C:\Users\gf133\Desktop\变量提取文件\测试文件\项目公告审批记录.pdf"
        
        # 本地文件测试用例 - 服务文件  有复核卡
        # "tender_file": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\阳泉燕龛块炭加工招标文件.pdf",
        # "opening_record_file": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\JNC152-ZB-250613354_001开标记录表.xls",
        # "review_experts_file": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\块炭加工分拣及储装运监督报告.pdf",
        # "evaluation_summary_file": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\JNC152-ZB-250613354-001评标表格.pdf",
        # "candidate_bid_files": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\阳泉兴正贸易有限公司投标文件.pdf",
        # "other_files": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\块炭加工分拣及储装运_下载记录_202506260914.xlsx,C:\Users\gf133\Desktop\变量提取文件\服务文件\项目公告审批记录.pdf,C:\Users\gf133\Desktop\变量提取文件\模板文件\评标复核卡9.25.pdf"
        
        # 无复核卡
        #  "tender_file": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\阳泉燕龛块炭加工招标文件.pdf",
        # "opening_record_file": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\JNC152-ZB-250613354_001开标记录表.xls",
        # "review_experts_file": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\块炭加工分拣及储装运监督报告.pdf",
        # "evaluation_summary_file": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\JNC152-ZB-250613354-001评标表格.pdf",
        # "candidate_bid_files": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\一--阳泉煤矿签章版投标文件4.pdf",
        # "other_files": r"C:\Users\gf133\Desktop\变量提取文件\服务文件\块炭加工分拣及储装运_下载记录_202506260914.xlsx,C:\Users\gf133\Desktop\变量提取文件\服务文件\项目公告审批记录.pdf"
        
      
      
        #   货物2
        # "tender_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/2a6afbb6030743408d11315e30b08865/阳泉市南庄煤炭集团有限责任公司西上庄煤矿高压柴油发.pdf",
        # "opening_record_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/086be0888c524a5396929eed56a97e56/JNB148-ZB-241111862_001开标.xls",
        # "review_experts_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/32720cfe93ee4a35ac7663245cc8f505/阳泉市南庄煤炭集团有限责任公司西上庄煤矿高压柴油发.pdf",
        # "evaluation_summary_file": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/955160da1fd64233833e492313c0eeae/JNB148-ZB-241111862-001评标.pdf",
        # "candidate_bid_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/28c82ef06fd843c1afdfd28097d6b5c4/第一山西斯坦福机电设备有限公司西上庄-投标文件.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/1423d3d5f2844d0f82e048c64f4c5ffa/第二潍坊博发动力设备有限公司投标文件阳泉gai.pdf",
        # "other_files": "http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/116be763d2e742758f418d76248bfe86/项目公告审批记录.pdf,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/5bff2855255c48d79d55ebbb0ab11372/阳泉市南庄煤炭集团有限责任公司西上庄煤矿高压柴油发.xlsx,http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/dc5c9f63a36743cb98fdc21127c4b4b5/评标复核卡9.25.pdf",
        
        # "candidate_bid_files": r"C:\Users\gf133\Desktop\变量提取文件\测试文件\项目公告审批记录.pdf",
        # "candidate_bid_files": r"C:\Users\gf133\Desktop\变量提取文件\货物文件\第三安徽和源中电科技股份有限公司投标文件.pdf",
      
      
    }
    
    print("开始测试...")
    print(f"文件配置: {files_config}")
    
    try:
        result = await service.generate_bid_report(
            project_id=project_id,
            template_id=template_id,
            files_config=files_config
        )
        
        print("测试完成")
        #保存为txt文件
        with open("result.txt", "w", encoding="utf-8") as f:
            if isinstance(result, dict):
                # 如果result是字典，提取report字段
                if 'report' in result:
                    f.write(result['report'])
                else:
                    # 如果没有report字段，将整个字典转换为JSON字符串
                    import json
                    f.write(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                # 如果result是字符串，直接写入
                f.write(str(result))
        # print(result)
        
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bid_report_steps())
