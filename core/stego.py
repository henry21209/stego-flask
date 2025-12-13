from PIL import Image
import json

class StegoError(Exception):
    """自定義隱寫術錯誤"""
    pass

def str_to_bin(message: str) -> str:
    """將文字轉為二進位 (UTF-8)"""
    return ''.join(format(b, '08b') for b in message.encode('utf-8'))

def limit_image_size(img: Image.Image, max_dim=1000) -> Image.Image:
    """
    🛡️ 防爆機制：強制縮小圖片
    將圖片長寬限制在 max_dim (預設1000px) 以內。
    這樣可以將記憶體消耗控制在安全範圍 (約 50-100MB)。
    """
    if img.width > max_dim or img.height > max_dim:
        # thumbnail 會進行等比例縮小，直接修改物件本身
        img.thumbnail((max_dim, max_dim))
    return img

def encode_image(img: Image.Image, message: str, bit_map: list) -> Image.Image:
    """依照 bit_map 將訊息寫入圖片"""
    
    # === 🔥 關鍵修改 1：加密前先強制縮圖 ===
    # 這樣不管使用者傳 4K 還是 8K 的圖，都會被縮小到 1000px 左右
    img = limit_image_size(img)
    # ===================================

    # 確保是 RGB 模式
    if img.mode != 'RGB':
        img = img.convert("RGB")

    full_message = message + "#####"
    binary_data = str_to_bin(full_message)
    
    pixels = list(img.getdata())
    capacity = len(pixels) * len(bit_map)
    
    if len(binary_data) > capacity:
        raise StegoError(f"容量不足！圖片縮小後容量為 {capacity} bits，但訊息需要 {len(binary_data)} bits。請減少訊息長度。")

    new_pixels = []
    data_index = 0
    msg_len = len(binary_data)
    
    pixel_iter = iter(pixels)

    for p in pixel_iter:
        pixel = list(p)
        
        for target in bit_map:
            if data_index < msg_len:
                channel = target['c']
                bit_pos = target['b']
                bit_val = int(binary_data[data_index])
                
                mask = 1 << bit_pos
                pixel[channel] = (pixel[channel] & ~mask) | (bit_val << bit_pos)
                data_index += 1
            else:
                break
        new_pixels.append(tuple(pixel))

    new_img = Image.new(img.mode, img.size)
    new_img.putdata(new_pixels)
    return new_img

def decode_image(img: Image.Image, bit_map: list) -> str:
    """依照 bit_map 解讀圖片訊息"""
    
    # === 🔥 關鍵修改 2：解密前的安全檢查 ===
    # 我們不能幫使用者縮圖 (因為會破壞隱藏的訊息)，但我們可以「拒絕」太大的圖
    # 限制 200萬畫素 (約 1920x1080)，避免伺服器解密時崩潰
    if img.width * img.height > 2100000:
        raise StegoError("圖片過大，無法在免費伺服器上解密。請確保圖片是由此工具產生 (長寬小於 1000px)。")
    # ===================================
    
    if img.mode != 'RGB':
        img = img.convert("RGB")

    pixels = list(img.getdata())
    limit = 800000 
    count = 0
    
    extracted_bytes = bytearray()
    current_byte = 0
    bit_in_byte_count = 0
    delimiter_seq = b'#####'
    
    for p in pixels:
        for target in bit_map:
            channel = target['c']
            bit_pos = target['b']
            
            bit_val = (p[channel] >> bit_pos) & 1
            current_byte = (current_byte << 1) | bit_val
            bit_in_byte_count += 1
            
            if bit_in_byte_count == 8:
                extracted_bytes.append(current_byte)
                current_byte = 0
                bit_in_byte_count = 0
                
                if extracted_bytes.endswith(delimiter_seq):
                    try:
                        return extracted_bytes[:-5].decode('utf-8')
                    except UnicodeDecodeError:
                        return extracted_bytes[:-5].decode('utf-8', errors='ignore')
            
            count += 1
            if count > limit: return None
            
    return None