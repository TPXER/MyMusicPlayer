# -*- coding: utf-8 -*-

import os, sys, io, random, json
import vlc
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QSlider, QTextBrowser, QFileDialog, QMenu,
    QSizePolicy, QListWidgetItem, QSystemTrayIcon, QAction, QFrame,
    QDialog, QVBoxLayout, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QSize, QEasingCurve
from PyQt5.QtGui import QFont, QPixmap, QTextCursor, QIcon
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from PIL import Image

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

def resource_path(relative_path):
    """根据是否打包，返回资源的绝对路径"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ========== 悬浮歌词窗口类 ==========
class LyricOverlay(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 无边框 + 置顶 + 不抢焦点
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.ToolTip)
        # 允许背景透明
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 关闭时删除对象
        self.setAttribute(Qt.WA_DeleteOnClose)
        # 默认大小
        self.resize(600, 100)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self.frame.setMouseTracking(True)

        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        self.shadow_effect = QGraphicsDropShadowEffect(self)
        self.shadow_effect.setBlurRadius(15)
        self.shadow_effect.setOffset(0, 0)
        self.frame.setGraphicsEffect(self.shadow_effect)
        self.shadow_effect.setEnabled(False)

        # 主布局
        layout = QVBoxLayout(self)
        # 在整个 QDialog 上放置一个 QFrame，用来接收鼠标事件
        self.frame = QFrame()
        self.frame.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 160);
                border-radius: 10px;
            }
        """)
        layout.addWidget(self.frame)

        # 在 frame 中再加一个垂直布局，用于放 QTextBrowser
        frame_layout = QVBoxLayout(self.frame)
        self.browser = QTextBrowser()
        self.browser.setStyleSheet("""
            QTextBrowser {
                background: transparent; /* 透明，透出 frame 背景 */
                color: white;
                font-size: 24px;
                font-weight: bold;
                border: none;
                padding: 10px;
            }
        """)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setText("")
        frame_layout.addWidget(self.browser)

        # 用于计算拖动偏移
        self.drag_pos = None

    def enterEvent(self, event):
        self.shadow_effect.setEnabled(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.shadow_effect.setEnabled(False)
        super().leaveEvent(event)

    def update_lyric(self, text):
        self.browser.setText(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 记录下鼠标与窗口左上角的距离
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            # 拖拽移动窗口
            self.move(event.globalPos() - self.drag_pos)
            event.accept()


# ========== 可拖拽播放列表控件 ==========
class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QListWidget.InternalMove)
        # 这里读取 material_style.qss，如果没有可以注释
        qss_path = resource_path("material_style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                stylesheet = f.read()
            self.setStyleSheet(stylesheet)

# ========== 主播放器类 ==========
class MusicPlayer(QWidget):
    def __init__(self):
        super().__init__()
        # 基础UI
        self.setWindowTitle("🎧 播放器 V6.9")
        self.setGeometry(200, 100, 960, 640)
        self.setWindowIcon(QIcon(resource_path("player_icon.ico")))

        # 初始化 VLC
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.playlist = []
        self.current_index = -1
        self.duration = 0
        self.user_seeking = False
        self.lyrics = []
        self.play_mode = "loop_all"  # 循环全部
        self.playlist_visible = True
        self.is_dark = False
        self.lyric_locked = False

        # 初始化系统音量控制
        global PYCAW_AVAILABLE
        if PYCAW_AVAILABLE:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume_ctrl = interface.QueryInterface(IAudioEndpointVolume)
            except:
                PYCAW_AVAILABLE = False

        # 创建悬浮歌词窗口
        self.lyric_overlay = LyricOverlay()
        self.lyric_overlay.show()

        # 初始化UI
        self.init_ui()

        # 绑定按钮动画
        self.btn_play.clicked.connect(lambda: self.animate_button_click(self.btn_play))
        self.btn_next.clicked.connect(lambda: self.animate_button_click(self.btn_next))
        self.btn_prev.clicked.connect(lambda: self.animate_button_click(self.btn_prev))
        self.btn_mode.clicked.connect(lambda: self.animate_button_click(self.btn_mode))
        self.btn_folder.clicked.connect(lambda: self.animate_button_click(self.btn_folder))
        self.btn_settings.clicked.connect(lambda: self.animate_button_click(self.btn_settings))
        self.btn_settings.clicked.connect(self.toggle_settings_menu)
        self.btn_theme.clicked.connect(lambda: self.animate_button_click(self.btn_theme))
        self.btn_playlist.clicked.connect(lambda: self.animate_button_click(self.btn_playlist))

        # 定时器更新UI
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(1000)

        # 主题按钮
        self.btn_theme.clicked.connect(self.theme_button_clicked)

        # 加载、恢复播放列表
        self.load_saved_playlist()
        self.restoring = False

        # 如果没有播放列表，就默认加载文件夹
        default_dir = "C:/PlayMc"
        if not self.playlist and os.path.exists(default_dir):
            self.load_music_files(default_dir)

        # 系统托盘
        self.init_tray_icon()

    # ========== 播放列表保存/恢复 ==========
    def save_playlist(self):
        try:
            data = {
                "playlist": self.playlist,
                "current_index": self.current_index,
                "position": self.player.get_time() / 1000 if self.player else 0
            }
            with open("playlist.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("保存播放列表失败：", e)

    def load_saved_playlist(self):
        try:
            if os.path.exists("playlist.json"):
                with open("playlist.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.playlist = data.get("playlist", [])
                    self.current_index = data.get("current_index", 0)
                    position = data.get("position", 0)

                    self.list_widget.clear()
                    for path in self.playlist:
                        self.list_widget.addItem(os.path.basename(path))

                    if self.playlist:
                        self.restoring = True
                        self.list_widget.setCurrentRow(self.current_index)
                        self.play_file(self.playlist[self.current_index])

                        def restore_position():
                            if self.player.get_state() == vlc.State.Playing:
                                self.player.set_time(int(position * 1000))
                                self.restoring = False
                            else:
                                QTimer.singleShot(200, restore_position)
                        restore_position()
        except Exception as e:
            print("加载播放列表失败：", e)

    # ========== UI 初始化 ==========
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        self.left_layout = QVBoxLayout()
        self.right_layout = QVBoxLayout()

        # Top bar
        top_bar = QHBoxLayout()
        self.btn_playlist = QPushButton("🎵 播放列表")
        self.btn_theme = QPushButton("🌗")
        self.btn_settings = QPushButton("⚙")
        top_bar.addWidget(self.btn_playlist)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_theme)
        top_bar.addWidget(self.btn_settings)
        self.right_layout.addLayout(top_bar)

        # 设置菜单
        self.settings_menu = QWidget()
        settings_layout = QVBoxLayout(self.settings_menu)
        self.vlc_vol_label = QLabel("🎚️ VLC 音量")
        self.vlc_vol_slider = QSlider(Qt.Horizontal)
        self.vlc_vol_slider.setRange(0, 100)
        self.vlc_vol_slider.setValue(80)
        self.vlc_vol_slider.valueChanged.connect(self.set_vlc_volume)
        settings_layout.addWidget(self.vlc_vol_label)
        settings_layout.addWidget(self.vlc_vol_slider)
        self.btn_toggle_lyric = QPushButton("🪟 显示/隐藏悬浮歌词")
        self.btn_toggle_lyric.clicked.connect(self.toggle_lyric_overlay)
        settings_layout.addWidget(self.btn_toggle_lyric)
        self.settings_menu.setVisible(False)
        self.right_layout.addWidget(self.settings_menu)

        # 播放列表
        playlist_card = QFrame()
        playlist_card.setObjectName("card")
        playlist_layout = QVBoxLayout(playlist_card)
        self.list_widget = DraggableListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_playlist_context_menu)
        self.list_widget.itemClicked.connect(self.song_selected)
        playlist_layout.addWidget(self.list_widget)
        self.left_layout.addWidget(playlist_card)

        # 封面 + 标题
        cover_card = QFrame()
        cover_card.setObjectName("card")
        cover_layout = QVBoxLayout(cover_card)
        self.cover = QLabel("🎵")
        self.cover.setFixedSize(220, 220)
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.title = QLabel("未播放")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("微软雅黑", 14))
        cover_layout.addWidget(self.cover)
        cover_layout.addWidget(self.title)
        self.left_layout.addWidget(cover_card)

        # 歌词区域
        lyric_card = QFrame()
        lyric_card.setObjectName("card")
        lyric_layout = QVBoxLayout(lyric_card)
        self.lyric_browser = QTextBrowser()
        self.lyric_browser.setFont(QFont("微软雅黑", 12))
        self.lyric_browser.verticalScrollBar().valueChanged.connect(self.on_lyric_scroll)
        lyric_layout.addWidget(self.lyric_browser)
        self.btn_jump_to_current = QPushButton("📍 回到当前歌词")
        self.btn_jump_to_current.clicked.connect(self.unlock_lyrics)
        lyric_layout.addWidget(self.btn_jump_to_current)
        self.right_layout.addWidget(lyric_card)

        # 控制区
        controls_card_inner = QWidget()
        controls_layout = QVBoxLayout(controls_card_inner)
        controls = QHBoxLayout()
        self.btn_prev = QPushButton("⏮️")
        self.btn_play = QPushButton("▶️")
        self.btn_next = QPushButton("⏭️")
        self.btn_mode = QPushButton("🔁")
        self.btn_folder = QPushButton("📂")
        for btn in [self.btn_folder, self.btn_prev, self.btn_play, self.btn_next, self.btn_mode]:
            controls.addWidget(btn)
        controls_layout.addLayout(controls)

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.sliderPressed.connect(self.start_seek)
        self.progress_slider.sliderReleased.connect(self.seek)
        controls_layout.addWidget(self.progress_slider)

        self.time_label = QLabel("00:00 / 00:00")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.valueChanged.connect(self.set_system_volume)
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("🔊"))
        vol_layout.addWidget(self.volume_slider)
        controls_layout.addWidget(self.time_label)
        controls_layout.addLayout(vol_layout)

        controls_card = QFrame()
        controls_card.setObjectName("card")
        controls_card_layout = QVBoxLayout(controls_card)
        controls_card_layout.addWidget(controls_card_inner)
        self.right_layout.addWidget(controls_card)

        main_layout.addLayout(self.left_layout, 3)
        main_layout.addLayout(self.right_layout, 6)
        self.setLayout(main_layout)

        # 绑定事件
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(self.play_next)
        self.btn_prev.clicked.connect(self.play_prev)
        self.btn_mode.clicked.connect(self.switch_mode)
        self.btn_folder.clicked.connect(self.choose_folder)
        self.btn_playlist.clicked.connect(self.toggle_playlist)

        # 如果有系统音量控制，则同步一下
        if PYCAW_AVAILABLE and hasattr(self, 'volume_ctrl'):
            try:
                vol = int(self.volume_ctrl.GetMasterVolumeLevelScalar() * 100)
                self.volume_slider.blockSignals(True)
                self.volume_slider.setValue(vol)
                self.volume_slider.blockSignals(False)
            except:
                pass

    # ========== 托盘图标 ==========
    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(resource_path("player_icon.ico")))
        self.tray_icon.setToolTip("🎧 播放器 V6.7")

        tray_menu = QMenu(self)
        action_show = QAction("显示窗口", self)
        action_show.triggered.connect(self.showNormal)
        action_quit = QAction("退出", self)
        action_quit.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(action_show)
        tray_menu.addAction(action_quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()

    # ========== 功能逻辑 ==========
    def play_file(self, path):
        self.player.set_media(self.instance.media_new(path))
        self.player.play()
        self.title.setText(os.path.basename(path))
        self.btn_play.setText("⏸️")
        self.load_cover(path)
        self.load_lyrics(path)
        try:
            self.duration = MP3(path).info.length
        except:
            self.duration = 0

        if not getattr(self, 'restoring', False):
            self.save_playlist()

    def load_cover(self, path):
        try:
            tags = ID3(path)
            for tag in tags.values():
                if tag.FrameID == "APIC":
                    image = Image.open(io.BytesIO(tag.data)).resize((200, 200))
                    buf = io.BytesIO()
                    image.save(buf, format='PNG')
                    pixmap = QPixmap()
                    pixmap.loadFromData(buf.getvalue())
                    self.cover.setPixmap(pixmap)
                    return
        except:
            pass
        self.cover.setText("🎵")

    def load_lyrics(self, path):
        self.lyrics.clear()
        folder = os.path.dirname(path)
        base = os.path.splitext(os.path.basename(path))[0]
        for f in os.listdir(folder):
            if f.endswith(".lrc") and base in f:
                with open(os.path.join(folder, f), encoding="utf-8", errors="ignore") as lrc:
                    for line in lrc:
                        if "[" in line and "]" in line:
                            try:
                                time_tag = line[line.find("[") + 1 : line.find("]")]
                                text = line[line.find("]") + 1:].strip()
                                mins, secs = time_tag.split(":")
                                sec = int(mins) * 60 + float(secs)
                                self.lyrics.append((sec, text))
                            except:
                                continue
                break
        self.lyrics.sort()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if folder:
            self.load_music_files(folder)

    def load_music_files(self, folder):
        self.playlist.clear()
        self.list_widget.clear()
        for f in os.listdir(folder):
            if f.lower().endswith((".mp3", ".wav", ".flac")):
                path = os.path.join(folder, f)
                self.playlist.append(path)
                self.list_widget.addItem(os.path.basename(f))
        if self.playlist:
            self.current_index = 0
            self.list_widget.setCurrentRow(0)
            self.play_file(self.playlist[0])

    def song_selected(self, item):
        self.current_index = self.list_widget.row(item)
        self.play_file(self.playlist[self.current_index])

    def toggle_settings_menu(self):
        self.settings_menu.setVisible(not self.settings_menu.isVisible())

    def toggle_lyric_overlay(self):
        if self.lyric_overlay.isVisible():
            self.lyric_overlay.hide()
        else:
            self.lyric_overlay.show()

    # ========== 播放控制 ==========
    def toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
            self.btn_play.setText("▶️")
        else:
            self.player.play()
            self.btn_play.setText("⏸️")

    def play_next(self):
        if not self.playlist: return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.list_widget.setCurrentRow(self.current_index)
        self.play_file(self.playlist[self.current_index])

    def play_prev(self):
        if not self.playlist: return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.list_widget.setCurrentRow(self.current_index)
        self.play_file(self.playlist[self.current_index])

    def toggle_playlist(self):
        self.playlist_visible = not self.playlist_visible
        self.list_widget.setVisible(self.playlist_visible)
        self.cover.setFixedSize(220 if self.playlist_visible else 300,
                                220 if self.playlist_visible else 300)

    def switch_mode(self):
        modes = {"loop_all": "loop_one", "loop_one": "shuffle", "shuffle": "loop_all"}
        icons = {"loop_all": "🔁", "loop_one": "🔂", "shuffle": "🔀"}
        self.play_mode = modes[self.play_mode]
        self.btn_mode.setText(icons[self.play_mode])
        self.btn_mode.repaint()

    # ========== 进度条/音量/歌词更新 ==========
    def start_seek(self):
        self.user_seeking = True

    def seek(self):
        self.player.set_position(self.progress_slider.value() / 1000)
        self.user_seeking = False

    def set_system_volume(self, val):
        if PYCAW_AVAILABLE and hasattr(self, 'volume_ctrl'):
            try:
                self.volume_ctrl.SetMasterVolumeLevelScalar(val / 100, None)
            except:
                pass

    def set_vlc_volume(self, val):
        if self.player:
            self.player.audio_set_volume(val)

    def on_lyric_scroll(self):
        self.lyric_locked = True

    def unlock_lyrics(self):
        self.lyric_locked = False

    def update_ui(self):
        if self.player.is_playing() and not self.user_seeking:
            pos = self.player.get_position()
            cur_time = pos * self.duration
            self.progress_slider.setValue(int(pos * 1000))
            self.time_label.setText(
                f"{int(cur_time//60):02}:{int(cur_time%60):02} / {int(self.duration//60):02}:{int(self.duration%60):02}"
            )
            self.update_lyrics(cur_time)

        # 播放结束处理
        if self.player.get_state() == vlc.State.Ended:
            if self.play_mode == "loop_one":
                self.play_file(self.playlist[self.current_index])
            elif self.play_mode == "shuffle":
                self.current_index = random.randint(0, len(self.playlist)-1)
                self.play_file(self.playlist[self.current_index])
            else:
                self.play_next()

    def update_lyrics(self, current_time):
        if not self.lyrics:
            return
        current_index = 0
        for i, (t, _) in enumerate(self.lyrics):
            if current_time < t:
                current_index = max(0, i - 1)
                break

        # 构建 HTML
        html_lines = []
        for i, (t, line) in enumerate(self.lyrics):
            if i == current_index:
                html_lines.append(f'<p style="color:red; font-weight:bold; text-align:center; text-decoration:none;">{line}</p>')
            else:
                html_lines.append(f'<p style="color:gray; text-align:center; text-decoration:none;">{line}</p>')

        # 滚动锁定
        if self.lyric_locked:
            scrollbar = self.lyric_browser.verticalScrollBar()
            cur_scroll = scrollbar.value()
            self.lyric_browser.setHtml("".join(html_lines))
            scrollbar.setValue(cur_scroll)
        else:
            self.lyric_browser.setHtml("".join(html_lines))
            cursor = self.lyric_browser.textCursor()
            cursor.movePosition(QTextCursor.Start)
            for _ in range(current_index):
                cursor.movePosition(QTextCursor.Down)
            self.lyric_browser.setTextCursor(cursor)

        # 同步悬浮歌词
        self.lyric_overlay.update_lyric(self.lyrics[current_index][1])

    # ========== 右键菜单删除歌曲 ==========
    def show_playlist_context_menu(self, pos):
        menu = QMenu()
        remove_action = menu.addAction("🗑 删除当前歌曲")
        action = menu.exec_(self.list_widget.mapToGlobal(pos))
        if action == remove_action:
            row = self.list_widget.currentRow()
            if row >= 0:
                del self.playlist[row]
                self.list_widget.takeItem(row)

    # ========== 明暗主题切换 ==========
    def theme_button_clicked(self):
        self.animate_button_click(self.btn_theme)
        self.toggle_theme()

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        if self.is_dark:
            dark_stylesheet = (
                "QWidget { background-color: #1e1e1e; color: white; }"
                "QFrame#card { background-color: #2a2a2a; }"
                "QPushButton { background-color: #444; color: white; border-radius: 5px; }"
                "QListWidget, QTextBrowser { background-color: #2a2a2a; color: white; }"
            )
            self.setStyleSheet(dark_stylesheet)
        else:
            # 恢复默认样式
            try:
                with open(resource_path("material_style.qss"), "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
            except:
                pass

    # ========== 按钮点击动画 ==========
    def animate_button_click(self, button):
        anim = QPropertyAnimation(button, b"size")
        anim.setDuration(120)
        anim.setStartValue(QSize(button.width(), button.height()))
        anim.setEndValue(QSize(button.width() - 6, button.height() - 6))
        anim.setEasingCurve(QEasingCurve.OutQuad)

        anim_back = QPropertyAnimation(button, b"size")
        anim_back.setDuration(120)
        anim_back.setStartValue(QSize(button.width() - 6, button.height() - 6))
        anim_back.setEndValue(QSize(button.width(), button.height()))
        anim_back.setEasingCurve(QEasingCurve.InOutQuad)

        anim.finished.connect(anim_back.start)
        anim.start()

    # ========== 关闭事件 ==========
    def closeEvent(self, event):
        self.tray_icon.hide()
        self.lyric_overlay.close()
        event.accept()

# ========== 程序入口 ==========
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("player_icon.ico")))

    # 如果有 material_style.qss
    try:
        with open(resource_path("material_style.qss"), "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except:
        pass

    player = MusicPlayer()
    player.show()
    sys.exit(app.exec_())
