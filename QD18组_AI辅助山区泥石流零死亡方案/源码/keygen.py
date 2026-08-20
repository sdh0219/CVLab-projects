"""
密钥生成器：生成设备绑定的单次授权 license 文件
编译方式：pyinstaller --onefile --console keygen.py
"""
import hashlib
import hmac
import json
import os
import platform
import sys
import time
import uuid

# ===== 共享秘密（keygen.exe 和 key_manager.py 共用） =====
# HMAC 签名密钥 — 仅存在于 keygen.exe 二进制和 key_manager.py 源码中
HMAC_SECRET = b'NLP-Project18-HMAC-Secret-2026'
# AES 数据密钥的原始材料 — 仅在此处存在明文
AES_KEY_MATERIAL = b'NLP-Course-Project18-DebrisFlow-2026'


def get_device_fingerprint():
    """获取设备指纹：SHA256(MAC地址 + 主机名)"""
    mac = uuid.getnode()
    hostname = platform.node()
    raw = f"{mac}-{hostname}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def xor_encrypt(key_bytes, data):
    """用 key_bytes 对 data 做 XOR 加密（对称）"""
    key_len = len(key_bytes)
    return bytes(b ^ key_bytes[i % key_len] for i, b in enumerate(data))


def sign_license(license_dict):
    """对 license 内容计算 HMAC-SHA256 签名"""
    # 排除 signature 字段本身
    content = json.dumps(license_dict, sort_keys=True, ensure_ascii=False)
    return hmac.new(HMAC_SECRET, content.encode('utf-8'), hashlib.sha256).hexdigest()


def generate_license():
    """生成设备绑定的 license 文件"""
    # 1. 设备指纹
    device_fp = get_device_fingerprint()

    # 2. AES 数据密钥
    aes_key = hashlib.sha256(AES_KEY_MATERIAL).digest()  # 32 bytes

    # 3. 用设备指纹前16字节 XOR 加密 AES 密钥
    fp_key = device_fp[:32].encode('utf-8')[:16]  # 取前16字节
    enc_key = xor_encrypt(fp_key, aes_key)

    # 4. 构造 license 数据
    license_data = {
        "device_hash": device_fp[:16],
        "enc_key": enc_key.hex(),
        "use_count": 0,
        "max_uses": 1,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "valid": True,
    }

    # 5. 签名
    license_data["signature"] = sign_license(license_data)

    return license_data, device_fp


def main():
    print("=" * 50)
    print("  泥石流防控系统 - 设备授权生成器")
    print("=" * 50)

    license_data, device_fp = generate_license()

    # 写入 .license 文件（与 keygen.exe 同目录）
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    license_path = os.path.join(script_dir, ".license")

    with open(license_path, 'w', encoding='utf-8') as f:
        json.dump(license_data, f, indent=2, ensure_ascii=False)

    print(f"\n  设备指纹: {device_fp[:16]}...")
    print(f"  授权文件: {license_path}")
    print(f"  有效期:   单次使用 (max_uses=1)")
    print(f"  生成时间: {license_data['created_at']}")
    print(f"\n  授权文件已生成，请运行 main.py 使用系统。")
    print("=" * 50)


if __name__ == "__main__":
    main()
