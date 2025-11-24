import requests
import os
import logging

logging.basicConfig(level=logging.INFO)

def call_dotsocr_api(pdf_file_path):
    """
    调用DotsOCR API处理PDF文件
    
    Args:
        pdf_file_path: PDF文件路径
        
    Returns:
        str: 解析后的文本内容，失败时返回None
    """
    logging.info(f"=======使用dotsocr API处理PDF文件========")
    url = 'http://192.168.1.94:8089/parse-pdf-to-md'
    headers = {
        'accept': 'text/plain',
    }

    if not os.path.exists(pdf_file_path):
        print(f"Error: PDF file not found at {pdf_file_path}")
        return None

    try:
        with open(pdf_file_path, 'rb') as f:
            files = {
                'pdf_file': (os.path.basename(pdf_file_path), f, 'application/pdf')
            }
            response = requests.post(url, headers=headers, files=files, timeout=600)
            response.raise_for_status() 
            return response.text
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"API Response Status Code: {response.status_code}")
            print(f"API Response Text: {response.text}")
        return None


def merge_pages_by_dotsocr(parsed_data, filename):
    """
    按页码整理dotsocr返回的内容
    
    Args:
        parsed_data: DotsOCR返回的解析数据
        filename: 文件名
        
    Returns:
        str: 按页码整理后的内容字符串
    """
    page_contents = {}
    current_page = 0
    current_content = []

    lines = parsed_data.splitlines()
    for line in lines:
        if line.startswith("==第") and line.endswith("页=="):
            if current_page != 0:
                page_contents[current_page] = "\n".join(current_content).strip()
                current_content = []
            try:
                current_page = int(line.replace("==第", "").replace("页==", "").strip())
            except ValueError:
                current_page = 0 
        elif current_page != 0:
            current_content.append(line.strip())
    
    if current_page != 0 and current_content:
        page_contents[current_page] = "\n".join(current_content).strip()

    merged = []
    for page in sorted(page_contents.keys()):
        merged.append(f"\n===== 文件: {os.path.basename(filename)} - 第{page}页 =====")
        merged.append(page_contents[page])
    
    return "\n".join(merged)


if __name__ == "__main__":
    test_pdf_path = os.path.abspath('./catalog/黃土采购项目招标资料要求.pdf') 
    
    if not os.path.exists(test_pdf_path):
        print(f"Warning: Test PDF file not found at {test_pdf_path}. Please update test_pdf_path to a valid file.")
    else:
        print(f"Calling dotsocr API with PDF: {test_pdf_path}")
        result = call_dotsocr_api(test_pdf_path)

        if result:
            # 保存到文件
            with open('dotsocr_result.txt', 'w') as f:
                f.write(result)
            print(f"API Response saved to dotsocr_result.txt")
        else:
            print("API call failed or returned no data.")
