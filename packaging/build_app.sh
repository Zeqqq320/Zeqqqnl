#!/bin/bash
# 满族音乐 · 组装 macOS 独立应用
# 用法: bash packaging/build_app.sh [输出目录]   默认输出到 packaging/dist
#
# 设计要点: 全程不做批量删除。
#   - 装配一律用 rsync 增量复制 + 排除规则(缓存/无关包就地跳过, 而不是先拷再删)
#   - 旧产物用 mv 挪进 packaging/.trash, 避免在构建过程中触发批量删除
set -euo pipefail

ROOT="/Users/liguiyao/WorkBuddy/民族音乐/Zeqqqnl"
PKG="$ROOT/packaging"
OUT_BASE="${1:-$PKG/dist}"
APP="$OUT_BASE/满族音乐.app"
RES="$APP/Contents/Resources"
PY_SRC="$PKG/runtime/python"
SP_SRC="$ROOT/venv/lib/python3.13/site-packages"

echo "==> 旧产物挪到回收区(不删除)"
mkdir -p "$OUT_BASE" "$PKG/.trash"
if [ -e "$APP" ]; then
  mv "$APP" "$PKG/.trash/满族音乐.app.$(date +%s)"
fi
mkdir -p "$APP/Contents/MacOS" "$RES/app" "$RES/bin"

echo "==> 打包便携 Python 运行时(排除图形栈/测试套件/字节码缓存)"
rsync -a \
  --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='/include' --exclude='/share' \
  --exclude='/lib/tcl*' --exclude='/lib/tk*' --exclude='/lib/itcl*' --exclude='/lib/thread*' \
  --exclude='/lib/python3.13/test' --exclude='/lib/python3.13/idlelib' --exclude='/lib/python3.13/turtledemo' \
  --exclude='/lib/python3.13/site-packages' \
  "$PY_SRC/" "$RES/runtime/python/"

echo "==> 同步第三方依赖(排除只服务 YouTube/TIDAL 的重量级包)"
# nodejs_wheel 200MB: 全项目无任何 Python 引用, 仅 youtubeutils 用 which("node") 从 PATH 找 node
# av            44MB: 仅 tidalutils 的 FLAC 重封装用, 走 optionalimport(), 缺失时自动降级
rsync -a \
  --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='/nodejs_wheel' --exclude='/nodejs_wheel-*' \
  --exclude='/av' --exclude='/av-*' \
  "$SP_SRC/" "$RES/runtime/python/lib/python3.13/site-packages/"

echo "==> 打包应用源码"
mkdir -p "$RES/app/webui/ethnos_cache"
cp "$ROOT/webui/mountainriverechoes.py" "$RES/app/webui/"
rsync -a --exclude='__pycache__' --exclude='*.pyc' "$ROOT/webui/templates/" "$RES/app/webui/templates/"
# 满族专属界面的样式与逻辑(css/js)。漏掉这行的话重建出来的是通用山河回响页面。
rsync -a --exclude='__pycache__' --exclude='*.pyc' "$ROOT/webui/static/" "$RES/app/webui/static/"
rsync -a --exclude='__pycache__' --exclude='*.pyc' "$ROOT/musicdl/" "$RES/app/musicdl/"
cp "$ROOT/webui/ethnos_cache/t03_满族音乐.json" "$RES/app/webui/ethnos_cache/"
mkdir -p "$RES/app/packaging/standalone"
cp "$PKG/standalone/launcher.py" "$PKG/standalone/run.sh" "$PKG/standalone/stop.sh" "$RES/app/packaging/standalone/"

echo "==> 放置 yt-dlp 启动器(指向内置运行时)"
cat > "$RES/runtime/python/bin/yt-dlp" <<'EOF'
#!/bin/sh
exec "$(cd "$(dirname "$0")" && pwd)/python3" -m yt_dlp "$@"
EOF
chmod +x "$RES/runtime/python/bin/yt-dlp"
cp "$RES/runtime/python/bin/yt-dlp" "$RES/bin/yt-dlp"

echo "==> 写入 app 可执行入口"
cp "$PKG/standalone/run.sh" "$APP/Contents/MacOS/launcher"
chmod +x "$APP/Contents/MacOS/launcher"
printf 'APPL????' > "$APP/Contents/PkgInfo"

echo "==> 写入 Info.plist"
cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDevelopmentRegion</key>
	<string>zh_CN</string>
	<key>CFBundleDisplayName</key>
	<string>满族音乐</string>
	<key>CFBundleExecutable</key>
	<string>launcher</string>
	<key>CFBundleIconFile</key>
	<string>AppIcon</string>
	<key>CFBundleIdentifier</key>
	<string>cn.edu.ynu.mountainriverechoes.manchu.standalone</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>满族音乐</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>2.0</string>
	<key>CFBundleVersion</key>
	<string>2</string>
	<key>LSApplicationCategoryType</key>
	<string>public.app-category.music</string>
	<key>LSMinimumSystemVersion</key>
	<string>12.0</string>
	<key>NSHighResolutionCapable</key>
	<true/>
	<key>NSHumanReadableCopyright</key>
	<string>山河回响 · 满族音乐专题(独立版)</string>
</dict>
</plist>
EOF
plutil -lint "$APP/Contents/Info.plist"

echo "==> 安装图标"
if [ -f "$PKG/AppIcon-manchu.icns" ]; then
  cp "$PKG/AppIcon-manchu.icns" "$RES/AppIcon.icns"
else
  echo "   (跳过: 未找到 $PKG/AppIcon-manchu.icns)"
fi

echo "==> 解除隔离属性并做 ad-hoc 签名"
# 关键: bundle 只要带 com.apple.quarantine, Gatekeeper 就会在启动时 SIGKILL(exit 137) 掉
# 内嵌的 python 二进制 —— 症状是双击后无任何输出、服务起不来。必须先剥离。
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
# ad-hoc 签名让 LaunchServices 认可包体完整性(失败不影响使用, 故不中断构建)
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 && echo "  已 ad-hoc 签名" || echo "  (跳过签名)"

echo "==> 完成"
du -sh "$APP"
echo "路径: $APP"
