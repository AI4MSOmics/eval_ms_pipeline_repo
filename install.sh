#!/bin/bash
# eval_ms_pipeline 一键安装 / One-command installer
# 用法 / Usage: bash install.sh [源码目录 / source directory]
#   不给参数时自动从同级 skill_eval_ms_pipeline/ 目录复制
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
echo "安装目录 / Install directory: $HERE"

# 源码目录 / Source directory
SRC="${1:-$(dirname "$HERE")/skill_eval_ms_pipeline}"
if [ ! -f "$SRC/eval_ms_pipeline.py" ]; then
    # 尝试 analysis_scripts
    SRC="$(dirname "$HERE")/analysis_scripts"
fi
if [ ! -f "$SRC/eval_ms_pipeline.py" ]; then
    echo "错误 / Error: eval_ms_pipeline.py not found."
    echo "用法 / Usage: bash install.sh /path/to/analysis_scripts"
    exit 1
fi
echo "源码目录 / Source: $SRC"

# 1. 检查 Python / Check Python
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    echo "错误 / Error: Python not found. Install Python 3.8+ first."
    exit 1
fi
echo "Python: $($PYTHON --version)"

# 2. 安装依赖 / Install dependencies
echo ""
echo "安装 Python 依赖 / Installing Python dependencies..."
$PYTHON -m pip install numpy pandas matplotlib python-docx --quiet
echo "  ✓ numpy pandas matplotlib python-docx"

# 3. 复制源码 / Copy source code
echo ""
echo "复制源码 / Copying source code..."
for f in eval_ms_pipeline.py xic_raw.py; do
    if [ -f "$SRC/$f" ]; then
        cp "$SRC/$f" "$HERE/"
        echo "  ✓ $f"
    else
        echo "  ✗ $f not found in $SRC"
    fi
done

# 4. 复制示例 / Copy examples
if [ -d "$SRC/examples" ]; then
    mkdir -p "$HERE/examples"
    for f in "$SRC/examples/"*.py; do
        [ -f "$f" ] && cp "$f" "$HERE/examples/" && echo "  ✓ examples/$(basename $f)"
    done
fi

# 5. 检查工具 / Check tools
echo ""
echo "检查工具 / Checking tools..."
for tool in rawdump.exe rawmethod.exe; do
    if [ -f "$HERE/tools/$tool" ]; then
        echo "  ✓ tools/$tool"
    elif [ -f "$SRC/rawdump_bin/Debug/netcoreapp3.1/$tool" ] || [ -f "$SRC/rawmethod_tool/bin/Debug/netcoreapp3.1/$tool" ]; then
        # 从 skill 目录复制
        FOUND=$(find "$SRC" -name "$tool" -path "*/Debug/*" | head -1)
        [ -n "$FOUND" ] && cp "$FOUND" "$HERE/tools/" && echo "  ✓ tools/$tool (copied)"
    else
        echo "  ⚠ tools/$tool not found"
        echo "    Rebuild: cd src/rawdump && dotnet build rawdump.csproj -c Debug"
    fi
done

# 6. 验证导入 / Verify import
echo ""
echo "验证 / Verifying..."
cd "$HERE"
$PYTHON -c "
import sys; sys.path.insert(0, '.')
import eval_ms_pipeline
print('  ✓ eval_ms_pipeline imported')
print('  ✓ Engines:', len(eval_ms_pipeline.ENGINE_FINGERPRINTS))
print('  ✓ Languages:', list(eval_ms_pipeline.LANG.keys()))
print('  ✓ Cleavage QC:', hasattr(eval_ms_pipeline, 'compute_cleavage_from_db'))
" || { echo "验证失败 / Verification failed"; exit 1; }

# 7. 使用指引 / Usage guide
echo ""
echo "=============================================="
echo "安装完成 / Installation complete!"
echo "=============================================="
echo ""
echo "三种使用方式 / Three ways to use:"
echo ""
echo "  1. 直接运行 / Direct:"
echo "     python eval_ms_pipeline.py <dataset_name>"
echo ""
echo "  2. ZCode Skill:"
echo "     cp -r zcode/ ~/.zcode/skills/eval_ms_pipeline/"
echo ""
echo "  3. DeepSeek Agent:"
echo "     See agent/deepseek_guide.md"
echo ""
echo "文档 / Docs:"
echo "  - 中文: docs/guide_zh.md"
echo "  - English: docs/guide_en.md"
echo "  - Config: docs/configuration.md"
echo ""
