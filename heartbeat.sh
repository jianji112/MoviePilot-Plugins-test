#!/bin/bash
# MP 插件迭代优化心跳脚本
# 用法：./heartbeat.sh [step]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$SCRIPT_DIR/plugins/autosubv3"
SHARED_DIR="/home/chen/共享/2_代码/4_autosubv3"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "========================================"
echo "MP 插件迭代优化心跳"
echo "时间: $(date)"
echo "========================================"

# Step 1: 检查插件目录
if [ ! -d "$PLUGIN_DIR" ]; then
    echo "❌ 插件目录不存在: $PLUGIN_DIR"
    exit 1
fi
echo "✓ 插件目录: $PLUGIN_DIR"

# Step 2: 备份当前版本
BACKUP_DIR="$PLUGIN_DIR/backup"
mkdir -p "$BACKUP_DIR"
echo "✓ 备份目录: $BACKUP_DIR"

# Step 3: 打包插件
echo ""
echo "📦 打包插件..."
cd "$SCRIPT_DIR"
ZIP_FILE="autosubv3_$TIMESTAMP.zip"
zip -rq "$ZIP_FILE" plugins/autosubv3/
echo "✓ 打包完成: $ZIP_FILE"
echo "  文件大小: $(du -h "$ZIP_FILE" | cut -f1)"

# Step 4: 复制到共享目录
mkdir -p "$SHARED_DIR"
cp "$ZIP_FILE" "$SHARED_DIR/"
echo "✓ 已复制到共享目录: $SHARED_DIR/$ZIP_FILE"

# Step 5: 清理旧版本（保留最近 5 个）
echo ""
echo "🧹 清理旧版本..."
cd "$SHARED_DIR"
ls -t autosubv3_*.zip 2>/dev/null | tail -n +6 | xargs -r rm -f
REMAINING=$(ls -1 autosubv3_*.zip 2>/dev/null | wc -l)
echo "✓ 保留 $REMAINING 个版本"

# Step 6: 显示最新版本路径
echo ""
echo "========================================"
echo "✅ 插件已打包，可以安装测试"
echo "========================================"
echo "共享路径: $SHARED_DIR/$ZIP_FILE"
echo ""
echo "下一步："
echo "1. 在 MP 中安装此插件包"
echo "2. 运行翻译测试: python3 $PLUGIN_DIR/test_translate.py"
echo "3. 检查日志，确认优化效果"
echo ""
