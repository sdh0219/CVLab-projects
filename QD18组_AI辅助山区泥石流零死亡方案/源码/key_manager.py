"""
授权管理模块：验证 .license 文件、还原 AES 密钥、单次消费
被 main.py 导入使用
"""
import hashlib
import hmac
import json
import os
import platform
import uuid


# ===== 共享秘密（与 keygen.py 一致） =====
HMAC_SECRET = b'NLP-Project18-HMAC-Secret-2026'


def get_device_fingerprint():
    """获取当前设备指纹"""
    mac = uuid.getnode()
    hostname = platform.node()
    raw = f"{mac}-{hostname}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def xor_decrypt(key_bytes, data):
    """XOR 解密（与加密对称）"""
    key_len = len(key_bytes)
    return bytes(b ^ key_bytes[i % key_len] for i, b in enumerate(data))


def verify_signature(license_dict):
    """验证 .license 的 HMAC-SHA256 签名"""
    sig = license_dict.pop("signature", None)
    if sig is None:
        return False
    content = json.dumps(license_dict, sort_keys=True, ensure_ascii=False)
    expected = hmac.new(HMAC_SECRET, content.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def load_license(license_path):
    """加载并验证 .license 文件，返回 AES 密钥或 None"""
    # 1. 检查文件存在
    if not os.path.exists(license_path):
        print("[License] Error: .license 文件不存在。")
        print("[License] 请先运行 keygen.exe 生成授权文件。")
        return None

    # 2. 读取 JSON
    try:
        with open(license_path, 'r', encoding='utf-8') as f:
            license_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[License] Error: .license 文件损坏 ({e})。")
        return None

    # 3. 检查有效标志
    if not license_data.get("valid", False):
        print("[License] Error: 授权已失效。")
        print("[License] 请重新运行 keygen.exe 生成新授权。")
        return None

    # 4. 检查使用次数
    if license_data.get("use_count", 0) >= license_data.get("max_uses", 1):
        print("[License] Error: 授权已用完。")
        print("[License] 请重新运行 keygen.exe 生成新授权。")
        return None

    # 5. 验证签名
    license_for_verify = dict(license_data)  # 浅拷贝，不修改原数据
    if not verify_signature(license_for_verify):
        print("[License] Error: 授权签名无效，文件可能被篡改。")
        return None

    # 6. 验证设备指纹
    current_fp = get_device_fingerprint()
    if not current_fp.startswith(license_data["device_hash"]):
        print("[License] Error: 授权与当前设备不匹配。")
        print(f"[License] 当前设备: {current_fp[:16]}...")
        print(f"[License] 授权设备: {license_data['device_hash']}...")
        return None

    # 7. 用设备指纹解密 AES 密钥
    fp_key = current_fp[:32].encode('utf-8')[:16]
    enc_key = bytes.fromhex(license_data["enc_key"])
    aes_key = xor_decrypt(fp_key, enc_key)

    return aes_key, license_data


def consume_license(license_path, license_data):
    """标记授权为已消费（仅在程序正常运行后调用）"""
    license_data["use_count"] += 1
    if license_data["use_count"] >= license_data.get("max_uses", 1):
        license_data["valid"] = False

    with open(license_path, 'w', encoding='utf-8') as f:
        json.dump(license_data, f, indent=2, ensure_ascii=False)


def initialize():
    """主入口：验证授权 → 返回 AES 密钥，失败则 sys.exit"""
    import sys

    script_dir = os.path.dirname(os.path.abspath(__file__))
    license_path = os.path.join(script_dir, ".license")

    print("[License] 验证授权 ...")
    result = load_license(license_path)
    if result is None:
        sys.exit(1)

    aes_key, license_data = result
    print(f"[License] 设备验证通过。")
    print(f"[License] 授权有效 (uses: {license_data['use_count']+1}/{license_data['max_uses']})")

    # 消费授权
    consume_license(license_path, license_data)
    if not license_data.get("valid", True):
        print("[License] 授权已消费，下次使用请重新运行 keygen.exe。")

    return aes_key
