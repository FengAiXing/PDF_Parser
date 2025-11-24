import os
import PyPDF2


def remove_annotations(input_pdf, output_pdf=None):
    """
    去除PDF文件中的注释和印章
    
    Args:
        input_pdf (str): 输入PDF文件路径
        output_pdf (str): 输出PDF文件路径，如果为None则覆盖原文件
    """
    try:
        reader = PyPDF2.PdfReader(input_pdf)
        writer = PyPDF2.PdfWriter()
        cnt = 0
        for page_number, page in enumerate(reader.pages):
            # 删除注释的关键步骤：清空 Annots 字段
            if "/Annots" in page:
                cnt += len(page['/Annots'])
                page.__delitem__("/Annots")
            writer.add_page(page)

        # 如果指定了输出路径，则保存到新文件，否则覆盖原文件
        output_path = output_pdf if output_pdf else input_pdf
        
        with open(output_path, "wb") as f:
            writer.write(f)
        print(f"Annots字段处理完成,共处理了{cnt}个！")
        print(f"All annotations removed. Cleaned PDF saved to: {output_path}")
        return True
        
    except PermissionError:
        print(f"权限错误：无法写入文件 {input_pdf}")
        print("请检查：1. 文件是否被其他程序打开 2. 是否有写入权限")
        return False
    except FileNotFoundError:
        print(f"文件未找到：{input_pdf}")
        return False
    except Exception as e:
        print(f"处理PDF时发生错误：{str(e)}")
        return False


if __name__ == '__main__':
    input_pdf_path = r'C:\Users\gf133\Desktop\变量提取文件\服务文件\一--阳泉煤矿签章版投标文件4.pdf'
    
    # 创建test文件夹（如果不存在）
    test_dir = 'test'
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    # 生成输出文件路径（保存到test文件夹，避免权限问题）
    output_filename = 'processed_' + os.path.basename(input_pdf_path)
    output_path = os.path.join(test_dir, output_filename)
    
    # 处理PDF并保存到test文件夹
    success = remove_annotations(input_pdf_path, output_path)
    
    if success:
        print(f"处理后的PDF已保存到: {output_path}")
    else:
        print("PDF处理失败，请检查错误信息")
