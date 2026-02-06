#!/usr/bin/env python
"""MVP 功能测试脚本"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_imports():
    """测试所有模块导入"""
    print("🔍 Testing imports...")

    try:
        from app.main import app
        from app.db.session import engine, SessionLocal
        from app.db.models import Paper, Question, QuestionImage, Variant, Export
        from app.services.image_service import crop_image
        from app.services.storage_service import get_storage_service
        from app.services.export_service import create_export
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_database():
    """测试数据库连接"""
    print("\n🔍 Testing database...")

    try:
        from app.db.session import SessionLocal
        from app.db.models import Paper

        db = SessionLocal()
        # 测试查询
        count = db.query(Paper).count()
        db.close()

        print(f"✅ Database connected, papers count: {count}")
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False


def test_storage():
    """测试存储服务"""
    print("\n🔍 Testing storage service...")

    try:
        from app.services.storage_service import get_storage_service
        from pathlib import Path

        storage = get_storage_service()
        base_dir = Path(storage.base_dir)

        if base_dir.exists():
            subdirs = [d.name for d in base_dir.iterdir() if d.is_dir()]
            print(f"✅ Storage initialized: {base_dir}")
            print(f"   Subdirectories: {subdirs}")
            return True
        else:
            print(f"⚠️  Storage directory not created yet: {base_dir}")
            return True
    except Exception as e:
        print(f"❌ Storage test failed: {e}")
        return False


def test_image_service():
    """测试图像裁剪服务"""
    print("\n🔍 Testing image service...")

    try:
        from app.services.image_service import crop_image
        from PIL import Image
        from io import BytesIO

        # 创建一个测试图片
        test_img = Image.new('RGB', (1000, 1000), color='white')
        buffer = BytesIO()
        test_img.save(buffer, format='PNG')
        buffer.seek(0)
        image_bytes = buffer.read()

        # 测试裁剪
        cropped_bytes, width, height = crop_image(
            image_bytes,
            ymin=100, xmin=100,
            ymax=300, xmax=300
        )

        print(f"✅ Image cropping works: {width}x{height}")
        return True
    except Exception as e:
        print(f"❌ Image service test failed: {e}")
        return False


def test_export_service():
    """测试导出服务"""
    print("\n🔍 Testing export service...")

    try:
        from app.services.export_service import _generate_pdf

        pdf_bytes = _generate_pdf(
            title="测试练习卷",
            original_text="1. 小明有8个苹果，小红有5个苹果，他们一共有多少个苹果？",
            variants=[
                "1. 小明有10个橘子，小红有7个橘子，他们一共有多少个橘子？",
                "2. 小李有12个梨，小王有9个梨，他们一共有多少个梨？",
                "3. 小张有15个桃子，小赵有11个桃子，他们一共有多少个桃子？"
            ]
        )

        print(f"✅ PDF generation works: {len(pdf_bytes)} bytes")
        return True
    except Exception as e:
        print(f"❌ Export service test failed: {e}")
        return False


def test_app_routes():
    """测试应用路由"""
    print("\n🔍 Testing app routes...")

    try:
        from app.main import app

        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        expected_routes = [
            '/api/health',
            '/api/ocr/extract',
            '/api/variants/generate',
            '/api/export'
        ]

        for route in expected_routes:
            if route in routes:
                print(f"   ✅ {route}")
            else:
                print(f"   ❌ {route} - MISSING")
                return False

        print(f"✅ All {len(expected_routes)} routes registered")
        return True
    except Exception as e:
        print(f"❌ Routes test failed: {e}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Smart Paper MVP 功能测试")
    print("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("Database", test_database),
        ("Storage", test_storage),
        ("Image Service", test_image_service),
        ("Export Service", test_export_service),
        ("App Routes", test_app_routes),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test {name} crashed: {e}")
            results.append((name, False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！MVP 初版已就绪。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
