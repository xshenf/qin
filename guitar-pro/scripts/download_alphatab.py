"""
下载 AlphaTab 资源到本地 vendor 目录

用法: python scripts/download_alphatab.py

下载内容:
  - alphaTab.min.js  — 核心渲染引擎
  - font/             — Bravura 乐谱字体
  - soundfont/        — SoniVox MIDI 音色库
"""

import urllib.request
import os
import sys

# AlphaTab 版本（锁定版本避免 breaking change）
VERSION = "1.3.1"
BASE_URL = f"https://cdn.jsdelivr.net/npm/@coderline/alphatab@{VERSION}/dist"

# 目标目录
VENDOR_DIR = os.path.join(
    os.path.dirname(__file__), "..", "src", "ui", "vendor", "alphatab"
)

# 需要下载的文件列表
FILES = [
    # 核心 JS
    ("alphaTab.min.js", f"{BASE_URL}/alphaTab.min.js"),
    # 字体文件
    ("font/Bravura.eot", f"{BASE_URL}/font/Bravura.eot"),
    ("font/Bravura.otf", f"{BASE_URL}/font/Bravura.otf"),
    ("font/Bravura.svg", f"{BASE_URL}/font/Bravura.svg"),
    ("font/Bravura.woff", f"{BASE_URL}/font/Bravura.woff"),
    ("font/Bravura.woff2", f"{BASE_URL}/font/Bravura.woff2"),
    # SoundFont
    ("soundfont/sonivox.sf2", f"{BASE_URL}/soundfont/sonivox.sf2"),
]


def download_file(url: str, dest: str):
    """下载单个文件"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if os.path.exists(dest):
        print(f"  [跳过] {dest} 已存在")
        return

    print(f"  [下载] {url}")
    print(f"     -> {dest}")
    try:
        urllib.request.urlretrieve(url, dest)
        size = os.path.getsize(dest)
        print(f"     OK ({size:,} bytes)")
    except Exception as e:
        print(f"     失败: {e}")
        # 删除不完整文件
        if os.path.exists(dest):
            os.remove(dest)
        raise


def main():
    vendor_dir = os.path.abspath(VENDOR_DIR)
    print(f"AlphaTab v{VERSION} 资源下载")
    print(f"目标目录: {vendor_dir}")
    print(f"共 {len(FILES)} 个文件\n")

    success = 0
    failed = 0

    for rel_path, url in FILES:
        dest = os.path.join(vendor_dir, rel_path)
        try:
            download_file(url, dest)
            success += 1
        except Exception:
            failed += 1

    print(f"\n完成: {success} 成功, {failed} 失败")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
