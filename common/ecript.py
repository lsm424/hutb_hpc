import base64
import urllib.parse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import struct

def parse_key_iv(key_str):
    """
    模拟JavaScript中的parse函数
    ae.exports.parse => Pe.parse => new $e.init
    将字符串转换为CryptoJS的WordArray格式
    """
    # 1. 先进行encodeURIComponent和unescape处理（等同于UTF-8编码）
    # JavaScript中的unescape(encodeURIComponent(str))等同于Python中的UTF-8编码
    utf8_bytes = key_str.encode('utf-8')
    
    # 2. 模拟Pe.parse函数，将字节数组转换为32位整数数组
    # 每4个字节转换为一个32位整数（大端序）
    words = []
    length = len(utf8_bytes)
    
    # 确保字节长度是4的倍数，不足补0
    padded_bytes = utf8_bytes + b'\x00' * (4 - len(utf8_bytes) % 4 if len(utf8_bytes) % 4 != 0 else 0)
    
    for i in range(0, len(padded_bytes), 4):
        if i + 3 < len(padded_bytes):
            # 将4个字节组合成一个32位整数（大端序）
            word = (padded_bytes[i] << 24) | (padded_bytes[i+1] << 16) | (padded_bytes[i+2] << 8) | padded_bytes[i+3]
            words.append(word)
    
    # 返回字节数组（实际加密时使用的是原始字节）
    return utf8_bytes[:16]  # AES-128需要16字节密钥

def encrypt_username(username):
    """
    使用AES-128-CBC加密用户名
    参数:
        username: 要加密的用户名字符串
    """
    # 准备密钥和IV
    key_str = "akamario@funsine"
    iv_str = "funsine@akamario"
    
    # 解析密钥和IV
    key = parse_key_iv(key_str)
    iv = parse_key_iv(iv_str)
    
    # 确保密钥和IV都是16字节（AES-128）
    if len(key) < 16:
        key = key.ljust(16, b'\x00')
    else:
        key = key[:16]
    
    if len(iv) < 16:
        iv = iv.ljust(16, b'\x00')
    else:
        iv = iv[:16]
    
    # 准备要加密的数据（用户名）
    data = username.encode('utf-8')
    
    # 使用PKCS7填充
    data_padded = pad(data, AES.block_size, style='pkcs7')
    
    # 创建AES-CBC加密器
    cipher = AES.new(key, AES.MODE_CBC, iv)
    
    # 加密数据
    encrypted_data = cipher.encrypt(data_padded)
    
    # 转换为Base64字符串（模拟JavaScript中的toString()）
    # JavaScript中默认使用Base64编码
    encrypted_base64 = base64.b64encode(encrypted_data).decode('utf-8')
    
    return encrypted_base64

# 简化版本，直接使用UTF-8编码的字节作为密钥和IV
def encrypt_username_simple(username):
    """
    简化版本：直接使用UTF-8编码的字符串作为密钥和IV
    """
    # 密钥和IV
    key = "akamario@funsine".encode('utf-8')[:16].ljust(16, b'\x00')
    iv = "funsine@akamario".encode('utf-8')[:16].ljust(16, b'\x00')
    
    # 要加密的数据
    data = username.encode('utf-8')
    
    # PKCS7填充
    data_padded = pad(data, AES.block_size, style='pkcs7')
    
    # AES-128-CBC加密
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_data = cipher.encrypt(data_padded)
    
    # Base64编码
    return base64.b64encode(encrypted_data).decode('utf-8')

# 如果需要完全模拟JavaScript的parse函数（包括words数组的生成）
def parse_to_words(key_str):
    """
    完全模拟JavaScript的parse函数，生成words数组
    """
    utf8_bytes = key_str.encode('utf-8')
    length = len(utf8_bytes)
    words = []
    
    for i in range(0, length, 4):
        word = 0
        for j in range(4):
            if i + j < length:
                word |= (utf8_bytes[i + j] & 0xFF) << (24 - j * 8)
            else:
                word |= 0 << (24 - j * 8)
        words.append(word)
    
    # 确保有4个words（16字节）
    while len(words) < 4:
        words.append(0)
    
    return words, length

def words_to_bytes(words, sigBytes):
    """
    将words数组转换回字节数组
    """
    byte_array = bytearray()
    for word in words:
        for i in range(4):
            if len(byte_array) < sigBytes:
                byte_array.append((word >> (24 - i * 8)) & 0xFF)
    return bytes(byte_array)

def encrypt_username_exact(username):
    """
    精确模拟JavaScript的加密过程
    """
    # 解析密钥和IV
    key_words, key_len = parse_to_words("akamario@funsine")
    iv_words, iv_len = parse_to_words("funsine@akamario")
    
    # 转换为字节
    key = words_to_bytes(key_words, key_len)
    iv = words_to_bytes(iv_words, iv_len)
    
    # 确保是16字节
    key = key[:16].ljust(16, b'\x00')
    iv = iv[:16].ljust(16, b'\x00')
    
    # 加密
    data = username.encode('utf-8')
    data_padded = pad(data, AES.block_size, style='pkcs7')
    
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_data = cipher.encrypt(data_padded)
    
    return base64.b64encode(encrypted_data).decode('utf-8')

# 使用示例
if __name__ == "__main__":
    username = "lisiming518"
    
    # 方法1：简化版本
    encrypted1 = encrypt_username_simple(username)
    print(f"简化版本加密结果: {encrypted1}")
    
    # 方法2：精确版本
    encrypted2 = encrypt_username_exact(username)
    print(f"精确版本加密结果: {encrypted2}")
    
    # 方法3：第一种实现
    encrypted3 = encrypt_username(username)
    print(f"完整版本加密结果: {encrypted3}")