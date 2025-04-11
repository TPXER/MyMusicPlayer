#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, io, random, json
import vlc
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QSlider, QTextBrowser, QFileDialog, QMenu,
    QSizePolicy, QListWidgetItem, QSystemTrayIcon, QAction, QFrame,
    QDialog, QLineEdit, QGraphicsDropShadowEffect, QSplashScreen, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QSize, QEasingCurve, QSettings
from PyQt5.QtGui import QTextCursor, QIcon, QFont, QPixmap
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
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ---------------------------
# 内嵌 QSS 样式，包含自定义滚动条、滑块等效果
styleSheet = """
/* 主界面背景 */
QWidget {
    background-color: #F0F0F0;
    color: black;
}

/* 卡片样式 */
QFrame#card {
    background-color: white;
    border: 1px solid #C0C0C0;
    border-radius: 8px;
}

/* 按钮样式 */
QPushButton {
    background-color: #E0E0E0;
    color: black;
    border-radius: 5px;
    padding: 5px;
}

/* 列表/文本浏览器 */
QListWidget, QTextBrowser {
    background-color: white;
    color: black;
}

/* 输入框 */
QLineEdit {
    background-color: white;
    color: black;
    border: 1px solid #C0C0C0;
    border-radius: 4px;
    padding: 4px;
}

/* ========================= */
/* 自定义滚动条样式 */

/* 垂直滚动条 */
QScrollBar:vertical {
    background: #ECECEC;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #A8DBA8, stop:1 #79BD9A);
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #98CC98, stop:1 #69AD8A);
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    background: transparent;
    height: 0px;
}

/* 水平滚动条 */
QScrollBar:horizontal {
    background: #ECECEC;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #A8DBA8, stop:1 #79BD9A);
    min-width: 20px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #98CC98, stop:1 #69AD8A);
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    background: transparent;
    width: 0px;
}

/* ========================= */
/* 自定义水平滑块（进度条/音量条）样式 */
QSlider::groove:horizontal {
    height: 6px;
    background: #DDD;
    border-radius: 3px;
    margin: 0px;
}
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -4px 0;
    background: #4CAF50;
    border-radius: 7px;
    border: none;
}
QSlider::sub-page:horizontal {
    background: #4CAF50;
    border-radius: 3px;
}
QSlider::add-page:horizontal {
    background: #BBB;
    border-radius: 3px;
}
QSlider::groove:horizontal:hover {
    background: #CCC;
}
QSlider::handle:horizontal:hover {
    background: #66BB6A;
}
"""

# ---------------------------
# 可拖拽播放列表控件
class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QListWidget.InternalMove)
        self.add_file_callback = None
        self.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                background: #ECECEC;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #A8DBA8, stop:1 #79BD9A);
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #98CC98, stop:1 #69AD8A);
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                background: transparent;
                height: 0px;
            }
        """)
        qss_path = resource_path("material_style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith((".mp3", ".wav", ".flac")):
                    if self.add_file_callback:
                        self.add_file_callback(file_path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

# ---------------------------
# 可拖拽文本浏览器
class DraggableTextBrowser(QTextBrowser):
    def mousePressEvent(self, event):
        if self.anchorAt(event.pos()):
            super().mousePressEvent(event)
        else:
            self.window().mousePressEvent(event)
    def mouseMoveEvent(self, event):
        if self.anchorAt(event.pos()):
            super().mouseMoveEvent(event)
        else:
            self.window().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event):
        if self.anchorAt(event.pos()):
            super().mouseReleaseEvent(event)
        else:
            self.window().mouseReleaseEvent(event)

# ---------------------------
# 空提示控件
class EmptyPromptWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10,10,10,10)
        self.message_label = QLabel("播放列表为空，请拖拽文件或添加歌曲")
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)
        btn_layout = QHBoxLayout()
        self.btn_close_prompt = QPushButton("关闭提示")
        btn_layout.addWidget(self.btn_close_prompt)
        layout.addLayout(btn_layout)

# ---------------------------
# 悬浮歌词窗口，不带阴影，且不出现在任务栏及Alt+Tab中
class LyricOverlay(QDialog):
    def __init__(self, parent=None):
        # 独立窗口，不作为主窗口的子窗口
        super().__init__(None)
        # 设置无边框、置顶，并使用 Qt.Tool 使之不出现在任务栏或 Alt+Tab 中
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # 允许背景透明
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(600, 100)

        # 默认状态：完全透明背景；鼠标悬停时显示半透明黑框
        self.bg_style_normal = "background: transparent; border: none;"
        self.bg_style_hover = "background: rgba(0, 0, 0, 160); border: none;"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.frame = QFrame(self)
        self.frame.setStyleSheet(self.bg_style_normal)
        # 启用鼠标跟踪
        self.frame.setMouseTracking(True)
        layout.addWidget(self.frame)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        # 歌词显示区域，使用金黄色文本（可根据需要修改颜色）
        self.browser = QTextBrowser(self.frame)
        self.browser.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                color: #FFD700;
                font-size: 24px;
                font-weight: bold;
                border: none;
                padding: 10px;
            }
        """)
        # 隐藏滚动条
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setText("")
        self.installEventFilter(self)
        frame_layout.addWidget(self.browser)

        # 关闭按钮，默认隐藏；鼠标悬停时显示，可点击关闭（这里采用 hide()，你也可用 close()）
        self.btn_close = QPushButton("×", self.frame)
        self.btn_close.setStyleSheet("""
            QPushButton {
                color: white;
                background: transparent;
                border: none;
                font-size: 20px;
            }
            QPushButton:hover {
                color: red;
            }
        """)
        self.btn_close.setFixedSize(24, 24)
        # 初步将关闭按钮定位在右上角
        self.btn_close.move(self.frame.width() - 30, 5)
        self.btn_close.clicked.connect(self.hide)
        self.btn_close.hide()

        # 使整个窗口能够拖拽
        self.setMouseTracking(True)
        self.drag_pos = None

    def update_lyric(self, text):
        self.browser.setText(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drag_pos is not None:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()

    def enterEvent(self, event):
        # 鼠标进入时显示半透明背景和关闭按钮
        self.frame.setStyleSheet(self.bg_style_hover)
        self.btn_close.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        # 鼠标移出后恢复透明背景并隐藏关闭按钮
        self.frame.setStyleSheet(self.bg_style_normal)
        self.btn_close.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        # 每次窗口大小变化时更新关闭按钮位置
        self.btn_close.move(self.frame.width() - 30, 5)
        super().resizeEvent(event)
    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            return True
        elif event.type() == QEvent.MouseMove and event.buttons() & Qt.LeftButton:
            if self.drag_pos is not None:
                self.move(event.globalPos() - self.drag_pos)
                return True
        return super().eventFilter(obj, event)


# ---------------------------
# 主播放器类
class MusicPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎧 播放器 V6.9")
        self.setGeometry(200, 100, 960, 640)
        self.setWindowIcon(QIcon(resource_path("player_icon.ico")))
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.playlist = []
        self.filtered_playlist = []
        self.current_index = -1
        self.duration = 0
        self.user_seeking = False
        self.lyrics = []
        self.play_mode = "loop_all"  # "loop_all", "loop_one", "shuffle"
        self.playlist_visible = True
        self.is_dark = False
        self.lyric_locked = False
        self.double_line_mode = False
        self.search_mode = True
        self.emptyPromptDismissed = False
        self.lyrics_offset = 0
        self.is_muted = False
        self.prev_volume = None

        global PYCAW_AVAILABLE
        if PYCAW_AVAILABLE:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume_ctrl = interface.QueryInterface(IAudioEndpointVolume)
            except:
                PYCAW_AVAILABLE = False

        # 创建悬浮歌词窗口（独立窗口，不传parent）
        self.lyric_overlay = LyricOverlay()
        self.lyric_overlay.show()

        self.init_ui()
        self.list_widget.itemClicked.connect(self.song_selected)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(250)
        self.load_saved_playlist()
        self.restoring = False

        default_dir = "C:/PlayMc"
        if not self.playlist and os.path.exists(default_dir):
            self.load_music_files(default_dir)
        self.init_tray_icon()

    def add_file_to_playlist(self, file_path):
        if file_path not in self.playlist:
            self.playlist.append(file_path)
            self.update_playlist_view()

    def seek_to_lyric_time(self, url):
        try:
            time_sec = float(url.toString())
            self.player.set_time(int(time_sec * 1000))
        except Exception as e:
            print("点击歌词跳转失败:", e)

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
            print("保存播放列表失败:", e)

    def load_saved_playlist(self):
        try:
            if os.path.exists("playlist.json"):
                with open("playlist.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.playlist = data.get("playlist", [])
                    self.current_index = data.get("current_index", 0)
                    position = data.get("position", 0)
                    self.update_playlist_view()
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
            print("加载播放列表失败:", e)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        self.left_layout = QVBoxLayout()
        self.right_layout = QVBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索歌曲...")
        self.search_box.textChanged.connect(self.search_playlist)
        self.search_box.setVisible(True)
        self.left_layout.addWidget(self.search_box)

        self.playlist_stack = QStackedWidget()
        self.list_widget = DraggableListWidget()
        self.list_widget.add_file_callback = self.add_file_to_playlist
        self.empty_prompt = EmptyPromptWidget()
        self.empty_prompt.btn_close_prompt.clicked.connect(lambda: self.playlist_stack.setCurrentWidget(self.list_widget))
        self.playlist_stack.addWidget(self.list_widget)
        self.playlist_stack.addWidget(self.empty_prompt)
        self.update_playlist_view()
        self.left_layout.addWidget(self.playlist_stack)

        top_bar = QHBoxLayout()
        self.btn_playlist = QPushButton("🎵 播放列表")
        self.btn_theme = QPushButton("🌗")
        self.btn_settings = QPushButton("⚙")
        top_bar.addWidget(self.btn_playlist)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_theme)
        top_bar.addWidget(self.btn_settings)
        self.right_layout.addLayout(top_bar)

        self.settings_menu = QWidget()
        settings_layout = QVBoxLayout(self.settings_menu)
        self.vlc_vol_label = QLabel("🎚️ VLC 音量")
        self.vlc_vol_slider = QSlider(Qt.Horizontal)
        self.vlc_vol_slider.setRange(0, 100)
        self.vlc_vol_slider.setValue(80)
        self.vlc_vol_slider.valueChanged.connect(self.set_vlc_volume)
        settings_layout.addWidget(self.vlc_vol_label)
        settings_layout.addWidget(self.vlc_vol_slider)
        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setFixedWidth(40)
        self.btn_mute.clicked.connect(self.toggle_mute)
        settings_layout.addWidget(self.btn_mute)
        self.btn_toggle_lyric = QPushButton("🪟 显示/隐藏悬浮歌词")
        self.btn_toggle_lyric.clicked.connect(self.toggle_lyric_overlay)
        settings_layout.addWidget(self.btn_toggle_lyric)
        self.btn_toggle_lyric_mode = QPushButton("切换为双行歌词")
        self.btn_toggle_lyric_mode.clicked.connect(self.toggle_lyric_mode)
        settings_layout.addWidget(self.btn_toggle_lyric_mode)
        self.settings_menu.setVisible(False)
        self.right_layout.addWidget(self.settings_menu)

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

        lyric_card = QFrame()
        lyric_card.setObjectName("card")
        lyric_layout = QVBoxLayout(lyric_card)
        self.lyric_browser = QTextBrowser()
        self.lyric_browser.setFont(QFont("微软雅黑", 12))
        self.lyric_browser.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                background: #ECECEC;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #A8DBA8, stop:1 #79BD9A);
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #98CC98, stop:1 #69AD8A);
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                background: transparent;
                height: 0px;
            }
        """)
        self.lyric_browser.verticalScrollBar().setSingleStep(10)
        self.lyric_browser.setOpenExternalLinks(False)
        self.lyric_browser.anchorClicked.connect(self.seek_to_lyric_time)
        lyric_layout.addWidget(self.lyric_browser)
        self.btn_jump_to_current = QPushButton("📍 回到当前歌词")
        self.btn_jump_to_current.clicked.connect(self.unlock_lyrics)
        lyric_layout.addWidget(self.btn_jump_to_current)
        self.right_layout.addWidget(lyric_card)

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

        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(self.play_next)
        self.btn_prev.clicked.connect(self.play_prev)
        self.btn_mode.clicked.connect(self.switch_mode)
        self.btn_folder.clicked.connect(self.choose_folder)
        self.btn_playlist.clicked.connect(self.toggle_playlist)
        self.btn_settings.clicked.connect(self.toggle_settings_menu)
        self.btn_theme.clicked.connect(self.theme_button_clicked)

        if PYCAW_AVAILABLE and hasattr(self, 'volume_ctrl'):
            try:
                vol = int(self.volume_ctrl.GetMasterVolumeLevelScalar() * 100)
                self.volume_slider.blockSignals(True)
                self.volume_slider.setValue(vol)
                self.volume_slider.blockSignals(False)
            except:
                pass

    def update_playlist_view(self):
        query = self.search_box.text().strip().lower()
        if query:
            filtered = [f for f in self.playlist if query in os.path.basename(f).lower()]
            self.filtered_playlist = filtered
            self.list_widget.clear()
            if filtered:
                for f in filtered:
                    self.list_widget.addItem(os.path.basename(f))
                self.playlist_stack.setCurrentWidget(self.list_widget)
            else:
                self.list_widget.clear()
                self.list_widget.addItem("没有找到匹配项")
                self.playlist_stack.setCurrentWidget(self.list_widget)
        else:
            self.filtered_playlist = self.playlist[:]
            if not self.playlist and not self.emptyPromptDismissed:
                self.playlist_stack.setCurrentWidget(self.empty_prompt)
            else:
                self.list_widget.clear()
                for f in self.playlist:
                    self.list_widget.addItem(os.path.basename(f))
                self.playlist_stack.setCurrentWidget(self.list_widget)

    def search_playlist(self, text):
        self.update_playlist_view()

    def toggle_lyric_mode(self):
        self.double_line_mode = not self.double_line_mode
        if self.double_line_mode:
            self.btn_toggle_lyric_mode.setText("切换为单行歌词")
        else:
            self.btn_toggle_lyric_mode.setText("切换为双行歌词")
        print("切换歌词模式：", self.double_line_mode)

    def toggle_lyric_overlay(self):
        if self.lyric_overlay.isVisible():
            self.lyric_overlay.hide()
        else:
            self.lyric_overlay.show()
            self.lyric_overlay.raise_()
            self.lyric_overlay.activateWindow()

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
                    image.save(buf, format="PNG")
                    pixmap = QPixmap()
                    pixmap.loadFromData(buf.getvalue())
                    self.cover.setPixmap(pixmap)
                    return
        except:
            pass
        self.cover.setText("没有封面？音乐本身最美！")

    def load_lyrics(self, path):
        self.lyrics.clear()
        folder = os.path.dirname(path)
        base = os.path.splitext(os.path.basename(path))[0]
        found = False
        for f in os.listdir(folder):
            if f.endswith(".lrc") and base in f:
                with open(os.path.join(folder, f), encoding="utf-8", errors="ignore") as lrc:
                    for line in lrc:
                        if "[" in line and "]" in line:
                            try:
                                time_tag = line[line.find("[")+1:line.find("]")]
                                text = line[line.find("]")+1:].strip()
                                mins, secs = time_tag.split(":")
                                sec = int(mins)*60 + float(secs)
                                self.lyrics.append((sec, text))
                            except:
                                continue
                found = True
                break
        self.lyrics.sort()
        if not found or not self.lyrics:
            self.lyrics = [(0, "这首歌没有歌词，请用心聆听！")]

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if folder:
            self.load_music_files(folder)

    def load_music_files(self, folder):
        self.playlist.clear()
        self.emptyPromptDismissed = False
        for f in os.listdir(folder):
            if f.lower().endswith((".mp3", ".wav", ".flac")):
                path = os.path.join(folder, f)
                self.playlist.append(path)
        self.update_playlist_view()
        if self.playlist:
            self.current_index = 0
            self.list_widget.setCurrentRow(0)
            self.play_file(self.playlist[0])

    def song_selected(self, item):
        if self.search_box.text().strip():
            if item.text() == "没有找到匹配项":
                return
            index = self.list_widget.row(item)
            file_path = self.filtered_playlist[index]
            self.current_index = self.playlist.index(file_path)
            self.play_file(file_path)
        else:
            index = self.list_widget.row(item)
            self.current_index = index
            self.play_file(self.playlist[self.current_index])
        print("切换歌曲至：", self.playlist[self.current_index])

    def toggle_settings_menu(self):
        new_state = not self.settings_menu.isVisible()
        self.settings_menu.setVisible(new_state)
        print("设置菜单状态：", new_state)

    def toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
            self.btn_play.setText("▶️")
        else:
            self.player.play()
            self.btn_play.setText("⏸️")

    def play_next(self):
        if not self.playlist:
            return
        if self.play_mode == "shuffle":
            self.current_index = random.randint(0, len(self.playlist)-1)
        else:
            self.current_index = (self.current_index + 1) % len(self.playlist)
        self.list_widget.setCurrentRow(self.current_index)
        self.play_file(self.playlist[self.current_index])
        print("播放下一首：", self.playlist[self.current_index])

    def play_prev(self):
        if not self.playlist:
            return
        if self.play_mode == "shuffle":
            self.current_index = random.randint(0, len(self.playlist)-1)
        else:
            self.current_index = (self.current_index - 1) % len(self.playlist)
        self.list_widget.setCurrentRow(self.current_index)
        self.play_file(self.playlist[self.current_index])
        print("播放上一首：", self.playlist[self.current_index])

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
        print("播放模式切换为：", self.play_mode)

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
            cur_time = pos * self.duration + self.lyrics_offset
            self.progress_slider.setValue(int(pos * 1000))
            self.time_label.setText(f"{int(cur_time//60):02}:{int(cur_time%60):02} / {int(self.duration//60):02}:{int(self.duration%60):02}")
            if self.lyric_locked:
                bar = self.lyric_browser.verticalScrollBar()
                current_scroll = bar.value()
                self.lyric_browser.setUpdatesEnabled(False)
                self.lyric_browser.setHtml("".join(self.compose_lyrics_html(cur_time)))
                self.lyric_browser.setUpdatesEnabled(True)
                QTimer.singleShot(0, lambda: bar.setValue(current_scroll))
            else:
                self.update_lyrics(cur_time)

        if self.player.is_playing() and not self.lyric_overlay.isVisible():
            self.lyric_overlay.show()
            self.lyric_overlay.raise_()
            self.lyric_overlay.activateWindow()

        if self.player.get_state() == vlc.State.Ended:
            if self.play_mode == "loop_one":
                self.play_file(self.playlist[self.current_index])
            elif self.play_mode == "shuffle":
                self.current_index = random.randint(0, len(self.playlist) - 1)
                self.play_file(self.playlist[self.current_index])
            else:
                self.play_next()

    def compose_lyrics_html(self, current_time):
        if not self.lyrics:
            return [""]
        current_index = 0
        for i, (t, _) in enumerate(self.lyrics):
            if current_time < t:
                current_index = max(0, i - 1)
                break
        html_lines = []
        for i, (t, line) in enumerate(self.lyrics):
            if i == current_index:
                html_lines.append(f'<a href="{t}"><p style="color:red; font-weight:bold; text-align:center; text-decoration:none;">{line}</p></a>')
            else:
                html_lines.append(f'<a href="{t}"><p style="color:gray; text-align:center; text-decoration:none;">{line}</p></a>')
        return html_lines

    def update_lyrics(self, current_time):
        html_lines = self.compose_lyrics_html(current_time)
        self.lyric_browser.setHtml("".join(html_lines))
        cursor = self.lyric_browser.textCursor()
        cursor.movePosition(QTextCursor.Start)
        current_index = 0
        for i, (t, _) in enumerate(self.lyrics):
            if current_time < t:
                current_index = max(0, i - 1)
                break
        for _ in range(current_index):
            cursor.movePosition(QTextCursor.Down)
        self.lyric_browser.setTextCursor(cursor)
        self.lyric_browser.ensureCursorVisible()
        if self.lyrics:
            _, line_text = self.lyrics[current_index]
            self.lyric_overlay.update_lyric(line_text)
        else:
            self.lyric_overlay.update_lyric("没有找到歌词")

    def show_playlist_context_menu(self, pos):
        menu = QMenu()
        remove_action = menu.addAction("🗑 删除当前歌曲")
        action = menu.exec_(self.list_widget.mapToGlobal(pos))
        if action == remove_action:
            row = self.list_widget.currentRow()
            if row >= 0:
                del self.playlist[row]
                self.list_widget.takeItem(row)
                self.update_playlist_view()

    def theme_button_clicked(self):
        print("按钮'🌗'被点击")
        self.animate_button_click(self.btn_theme)
        self.toggle_theme()

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        if self.is_dark:
            dark_file = resource_path("dark_theme.qss")
            if os.path.exists(dark_file):
                try:
                    with open(dark_file, "r", encoding="utf-8") as f:
                        dark_stylesheet = f.read()
                    self.setStyleSheet(dark_stylesheet)
                    print("已加载外部深色主题文件")
                except Exception as e:
                    print("加载 dark_theme.qss 失败:", e)
                    self.setStyleSheet(dark_theme)
            else:
                self.setStyleSheet(dark_theme)
        else:
            light_file = resource_path("material_style.qss")
            if os.path.exists(light_file):
                try:
                    with open(light_file, "r", encoding="utf-8") as f:
                        self.setStyleSheet(f.read())
                    print("已加载外部浅色主题文件")
                except Exception as e:
                    print("加载 material_style.qss 失败:", e)
                    self.setStyleSheet(light_theme)
            else:
                self.setStyleSheet(light_theme)

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

    def toggle_mute(self):
        if not self.is_muted:
            self.prev_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
            self.btn_mute.setText("🔇")
            self.is_muted = True
            print("静音")
        else:
            if self.prev_volume is not None:
                self.volume_slider.setValue(self.prev_volume)
            self.btn_mute.setText("🔊")
            self.is_muted = False
            print("恢复声音")

    def closeEvent(self, event):
        self.tray_icon.hide()
        self.lyric_overlay.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("player_icon.ico")))
    try:
        with open(resource_path("material_style.qss"), "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print("样式加载失败:", e)

    # ===== 启动动画开始 =====
    splash = QSplashScreen(QPixmap(resource_path("splash_resized.png")), Qt.WindowStaysOnTopHint)
    splash.show()

    fade_anim = QPropertyAnimation(splash, b"windowOpacity")
    fade_anim.setDuration(1500)
    fade_anim.setStartValue(1)
    fade_anim.setEndValue(0)
    fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
    QTimer.singleShot(1500, fade_anim.start)
    QTimer.singleShot(3000, splash.close)
    # ===== 启动动画结束 =====

    player = MusicPlayer()
    QTimer.singleShot(3000, player.show)

    sys.exit(app.exec_())
