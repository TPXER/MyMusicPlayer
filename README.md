 功能特色
一个基于 Python + PyQt5 + VLC 的本地音乐播放器，支持双行悬浮歌词、Material Design 风格、深浅色切换、播放列表保存、自动记忆播放位置、自定义设置等多项功能。

🌟 功能特色
🎵 播放本地音频（支持 .mp3 .wav .flac）

🎙️ 悬浮歌词窗口（可自由拖动 / 单双行切换 / 点击跳转播放）

💡 Material Design 风格 + 深色 / 浅色主题切换

📂 记忆上次播放位置和播放列表

⚙️ 设置菜单：VLC 独立音量、启动动画开关、歌词控制等

🎛️ 支持播放模式切换（循环 / 单曲 / 随机）

🔊 音量条支持系统音量同步（使用 Pycaw）

🖱️ 播放列表支持拖拽排序、右键删除

📦 PyInstaller 可打包为单文件可执行程序

所需依赖
pip install PyQt5 python-vlc mutagen pillow
# 如需系统音量同步（可选）：
pip install pycaw comtypes

 启动方式
python player_v7.py

 打包指令示例（使用 PyInstaller）
pyinstaller -F -w --icon=player_icon.ico ^
--add-data "material_style.qss;." ^
--add-data "dark_theme.qss;." ^
--add-data "splash_resized.png;." ^
--add-data "player_icon.ico;." ^
player_v7.py

项目结构建议
📁 本地音乐播放器/
├── player_v7.py
├── material_style.qss
├── dark_theme.qss
├── player_icon.ico
├── splash_resized.png
├── playlist.json（程序运行后自动生成）

 关于系统托盘与关闭行为
默认点击右上角关闭按钮将直接退出程序（非最小化到托盘）
托盘菜单可右键选择“退出”或双击图标恢复窗口

📝 开发者备注
本项目由 AI 辅助完成，核心逻辑包括：
VLC 播放控制
歌词解析与双重渲染
可保存播放状态
UI 动画与样式切换等

