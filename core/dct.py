import cv2
import numpy as np
from PIL import Image

class DCTError(Exception):
    pass

def str_to_bin(message):
    """將文字轉為二進位 (UTF-8)"""
    return ''.join(format(b, '08b') for b in message.encode('utf-8'))

def bin_to_str(binary_data):
    """將二進位轉回文字"""
    chars = []
    for i in range(0, len(binary_data), 8):
        byte = binary_data[i:i+8]
        if len(byte) < 8: break
        chars.append(chr(int(byte, 2)))
    return ''.join(chars)

def embed_dct(img_pil: Image.Image, message: str) -> Image.Image:
    """
    使用 DCT 變換將訊息寫入圖片 (抗壓縮浮水印)
    原理：修改 Y 通道 (亮度) 的 8x8 區塊中頻係數
    """
    # 1. 前置處理：轉為 numpy 格式並轉成 YCrCb 顏色空間
    # OpenCV 使用 BGR，Pillow 使用 RGB，需轉換
    img_np = np.array(img_pil)
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2YCrCb)
    
    h, w, _ = img_cv.shape
    
    # 2. 容量檢查
    # 每個 8x8 區塊只能藏 1 bit
    max_bits = (h // 8) * (w // 8)
    full_message = message + "#####" # 結束符號
    binary_data = str_to_bin(full_message)
    
    if len(binary_data) > max_bits:
        raise DCTError(f"訊息太長！DCT 模式容量較小。圖片可藏 {max_bits} bits，但你需要 {len(binary_data)} bits。")

    # 取出 Y 通道 (亮度)，因為人眼對亮度變化較不敏感，適合藏浮水印
    y_channel = img_cv[:, :, 0].astype(np.float32)

    data_index = 0
    msg_len = len(binary_data)

    # 3. 遍歷所有 8x8 區塊
    for row in range(0, h - 7, 8):
        for col in range(0, w - 7, 8):
            if data_index >= msg_len:
                break
            
            # 取得 8x8 區塊
            block = y_channel[row:row+8, col:col+8]
            
            # 進行 DCT 變換 (轉成頻率域)
            dct_block = cv2.dct(block)
            
            # 選定兩個中頻位置 (P1, P2) 來比較
            # 這裡選 (4, 1) 和 (3, 2) 是經驗法則，抗壓縮能力不錯
            p1 = dct_block[4, 1]
            p2 = dct_block[3, 2]
            
            bit = int(binary_data[data_index])
            
            # 修改係數關係來編碼 (差距 K=50，越大越抗壓縮但畫質越差)
            k = 50
            
            if bit == 0:
                # 若要藏 0，確保 P1 > P2 + k
                if p1 <= p2 + k:
                    p1 = p2 + k + 1
            else:
                # 若要藏 1，確保 P2 > P1 + k
                if p2 <= p1 + k:
                    p2 = p1 + k + 1
            
            dct_block[4, 1] = p1
            dct_block[3, 2] = p2
            
            # 進行 IDCT 反變換 (轉回圖片)
            y_channel[row:row+8, col:col+8] = cv2.idct(dct_block)
            
            data_index += 1

    # 4. 組合回去
    # 確保數值在 0-255 之間
    y_channel = np.clip(y_channel, 0, 255).astype(np.uint8)
    img_cv[:, :, 0] = y_channel
    
    # 轉回 RGB 並變回 Pillow 物件
    img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_YCrCb2RGB)
    return Image.fromarray(img_rgb)

def extract_dct(img_pil: Image.Image) -> str:
    """讀取 DCT 浮水印"""
    img_np = np.array(img_pil)
    
    # 轉 YCrCb
    if len(img_np.shape) == 2: # 如果是灰階
         img_cv = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR) # 先假轉
         img_cv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2YCrCb)
    else:
         img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2YCrCb)
         
    h, w, _ = img_cv.shape
    y_channel = img_cv[:, :, 0].astype(np.float32)
    
    extracted_bits = ""
    delimiter = "#####"
    
    # 遍歷區塊讀取
    for row in range(0, h - 7, 8):
        for col in range(0, w - 7, 8):
            block = y_channel[row:row+8, col:col+8]
            dct_block = cv2.dct(block)
            
            p1 = dct_block[4, 1]
            p2 = dct_block[3, 2]
            
            # 判斷 bit
            if p1 > p2:
                extracted_bits += "0"
            else:
                extracted_bits += "1"
    
    # 將 bit 轉回文字，並尋找結束符號
    # 這裡不做嚴格的 8 bit 切割，因為 DCT 經過壓縮可能會有一兩個 bit 讀錯
    # 我們嘗試還原出文字
    
    full_text = ""
    try:
        full_text = bin_to_str(extracted_bits)
    except:
        pass
        
    if delimiter in full_text:
        return full_text.split(delimiter)[0]
    
    return "解讀失敗或無浮水印 (DCT 模式雜訊較多，請確保圖片清晰)"