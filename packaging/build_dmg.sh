#!/bin/bash
# 满族音乐 · 生成可分发的 macOS 安装盘(DMG)
# 用法: bash packaging/build_dmg.sh
#
# 产物: packaging/满族音乐.dmg  (拖拽式安装: 把 满族音乐.app 拖进 Applications 即可)
#
# 注意: 不用 `hdiutil create -srcfolder`, 因为它在受限环境下要写 /Volumes 会被拒绝。
#       改为"自建可读写镜像 -> 挂到自建挂载点 -> 填内容 -> 卸掉 -> 转成压缩只读镜像"。
set -euo pipefail

ROOT="/Users/liguiyao/WorkBuddy/民族音乐/Zeqqqnl"
PKG="$ROOT/packaging"
SRC_APP="${1:-/Applications/满族音乐.app}"
DMG="$PKG/满族音乐.dmg"
VOLNAME="满族音乐"
WORK="$PKG/.dmgwork"
SPARSE="$WORK/sparse.dmg"
MNT="$WORK/mnt"

[ -d "$SRC_APP" ] || { echo "源应用不存在: $SRC_APP"; exit 1; }

echo "==> 准备工作目录"
if [ -e "$WORK" ]; then mv "$WORK" "$PKG/.dmgwork.old.$(date +%s)"; fi
mkdir -p "$WORK" "$MNT"

echo "==> 创建可读写镜像"
# 注意: -type SPARSE 会在 -o 指定的名字后再追加 .sparseimage 后缀
hdiutil create -size 600m -fs HFS+J -volname "$VOLNAME" -type SPARSE -o "$SPARSE" >/dev/null
SPARSE_FILE="$SPARSE.sparseimage"
[ -f "$SPARSE_FILE" ] || SPARSE_FILE="$SPARSE"
echo "  镜像: $SPARSE_FILE"

echo "==> 挂载到自建挂载点(避开 /Volumes)"
hdiutil attach "$SPARSE_FILE" -mountpoint "$MNT" -nobrowse -noverify >/dev/null

echo "==> 填入内容"
rsync -a --exclude='.DS_Store' "$SRC_APP/" "$MNT/满族音乐.app/"
ln -sfn /Applications "$MNT/Applications"

echo "==> 校验包体签名"
if codesign -v "$MNT/满族音乐.app" 2>/dev/null; then
  echo "  签名有效"
else
  echo "  签名无效, 重新 ad-hoc 签名"
  xattr -dr com.apple.quarantine "$MNT/满族音乐.app" 2>/dev/null || true
  codesign --force --deep --sign - "$MNT/满族音乐.app" >/dev/null 2>&1
fi

echo "==> 卸载"
hdiutil detach "$MNT" >/dev/null

echo "==> 转换为压缩只读镜像(UDZO)"
[ -f "$DMG" ] && mv "$DMG" "$PKG/.满族音乐.dmg.old.$(date +%s)"
hdiutil convert "$SPARSE_FILE" -format UDZO -imagekey zlib-level=6 -o "$DMG" >/dev/null

echo "==> 清理工作目录"
mv "$WORK" "$PKG/.dmgwork.done.$(date +%s)"

echo "==> 完成"
du -sh "$DMG"
echo "路径: $DMG"
