#!/usr/bin/env python
"""生成示例 PDF 脚本"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.export_service import _generate_pdf


def generate_sample():
    """生成示例 PDF"""

    print("🎨 正在生成示例 PDF...")

    # 示例数据
    title = "小学三年级数学练习卷"

    original_text = """1. 小明有 8 个苹果，小红有 5 个苹果，他们一共有多少个苹果？

解题提示：这是一道加法应用题。"""

    variants = [
        "小明有 10 个橘子，小红有 7 个橘子，他们一共有多少个橘子？",

        """小李有 12 个梨，小王有 9 个梨，他们一共有多少个梨？

（要求：写出完整的计算过程）""",

        "小张有 15 个桃子，小赵有 11 个桃子，他们一共有多少个桃子？",
    ]

    # 生成 PDF
    pdf_bytes = _generate_pdf(
        title=title,
        original_text=original_text,
        variants=variants,
        include_images=False
    )

    # 保存文件
    output_dir = PROJECT_ROOT / "storage" / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "sample_practice_sheet.pdf"
    with open(output_file, 'wb') as f:
        f.write(pdf_bytes)

    print(f"✅ PDF 生成成功！")
    print(f"📄 文件大小：{len(pdf_bytes)} bytes")
    print(f"📁 保存位置：{output_file.resolve()}")
    print(f"\n💡 提示：可以直接打开查看排版效果")

    return str(output_file)


if __name__ == "__main__":
    try:
        output_file = generate_sample()
        print(f"\n🎉 完成！请查看文件：{output_file}")
    except Exception as e:
        print(f"❌ 生成失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
