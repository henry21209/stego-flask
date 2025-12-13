from PIL import Image
import json

class StegoError(Exception):
    """自定義隱寫術錯誤"""
    pass

def str_to_bin(message: str) -> str:
    """將文字轉為二進位 (UTF-8)"""
    return ''.join(format(b, '08b') for b in message.encode('utf-8'))

def encode_image(img: Image.Image, message: str, bit_map: list) -> Image.Image:
    """依照 bit_map 將訊息寫入圖片"""
    full_message = message + "#####"
    binary_data = str_to_bin(full_message)
    
    pixels = list(img.getdata())
    capacity = len(pixels) * len(bit_map)
    
    if len(binary_data) > capacity:
        raise StegoError(f"容量不足！需 {len(binary_data)} bits，但只有 {capacity} bits。")

    new_pixels = []
    data_index = 0
    msg_len = len(binary_data)
    
    # 建立 Iterator 以提升一點效能
    pixel_iter = iter(pixels)

    for p in pixel_iter:
        pixel = list(p)
        
        for target in bit_map:
            if data_index < msg_len:
                channel = target['c']
                bit_pos = target['b']
                bit_val = int(binary_data[data_index])
                
                # 位元運算
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