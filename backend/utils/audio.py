import os
import uuid
from backend.config import OUTPUT_DIR


def hex_to_file(hex_data: str, ext: str = "mp3") -> str:
    """将 hex 编码的音频数据保存为文件，返回相对路径。"""
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(bytes.fromhex(hex_data))
    return f"/files/{filename}"
