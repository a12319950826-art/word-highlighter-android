[app]

# 应用信息
title = WordHighlighter
package.name = wordhighlighter
package.domain = org.example

# 源码配置
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
source.main = word_highlighter_android.py

# 版本
version = 1.0.0

# Python 依赖（简化版，避免编译问题）
requirements = python3,kivy==2.1.0,requests,beautifulsoup4,html5lib

# Android 配置
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 31
android.minapi = 21
android.ndk = 25b
android.sdk = 31
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True

# 应用配置
orientation = portrait
fullscreen = 0

# 构建配置
p4a.bootstrap = sdl2
log_level = 2

[buildozer]

# 构建目录
build_dir = ./.buildozer
bin_dir = ./bin
log_level = 2
