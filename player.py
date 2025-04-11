# -*- coding: utf-8 -*-
import os, sys, io, random
import vlc
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QSlider, QTextBrowser, QFileDialog, QMenu,
    QSizePolicy, QListWidgetItem, QSystemTrayIcon, QAction, QFrame
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QSize, QEasingCurve
from PyQt5.QtGui import QFont, QPixmap, QTextCursor, QIcon
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from PIL import Image

PYCAW_AVAILABLE = False
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL

    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False


class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        with open("material_style.qss", "r", encoding="utf-8") as f:
            self.default_stylesheet = f.read()
        self.setStyleSheet(self.default_stylesheet)


class MusicPlayer(QWidget):
    def __init__(self):
        global PYCAW_AVAILABLE  # 加上此声明
        super().__init__()
        with open("material_style.qss", "r", encoding="utf-8") as f:
            self.default_stylesheet = f.read()
        QApplication.instance().setStyleSheet(self.default_stylesheet)

        self.setWindowTitle("🎧 播放器 V6.7")
        self.setWindowIcon(QIcon("player_icon.ico"))
        self.setGeometry(200, 100, 960, 640)

        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.playlist = []
        self.current_index = -1
        self.duration = 0
        self.user_seeking = False
        self.lyrics = []
        self.play_mode = "loop_all"
        self.playlist_visible = True
        self.is_dark = False
        self.lyric_locked = False

        if PYCAW_AVAILABLE:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume_ctrl = interface.QueryInterface(IAudioEndpointVolume)
            except:
                PYCAW_AVAILABLE = False

        self.init_ui()

        # 主题按钮先执行动画后切换主题
        self.btn_theme.clicked.connect(self.theme_button_clicked)

        # 其它按钮的点击连接动画
        self.btn_play.clicked.connect(lambda: self.animate_button_click(self.btn_play))
        self.btn_next.clicked.connect(lambda: self.animate_button_click(self.btn_next))
        self.btn_prev.clicked.connect(lambda: self.animate_button_click(self.btn_prev))
        self.btn_mode.clicked.connect(lambda: self.animate_button_click(self.btn_mode))
        self.btn_folder.clicked.connect(lambda: self.animate_button_click(self.btn_folder))
        self.btn_settings.clicked.connect(lambda: self.animate_button_click(self.btn_settings))
        self.btn_playlist.clicked.connect(lambda: self.animate_button_click(self.btn_playlist))

        self.init_tray_icon()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(1000)

        default_dir = "C:/PlayMc"
        if os.path.exists(default_dir):
            self.load_music_files(default_dir)

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
            QApplication.instance().setStyleSheet(dark_stylesheet)
        else:
            QApplication.instance().setStyleSheet(self.default_stylesheet)

    def set_vlc_volume(self, val):
        if self.player:
            self.player.audio_set_volume(val)

    def unlock_lyrics(self):
        self.lyric_locked = False

    def on_lyric_scroll(self):
        self.lyric_locked = True

    def show_playlist_context_menu(self, pos):
        menu = QMenu()
        remove_action = menu.addAction("🗑 删除当前歌曲")
        action = menu.exec_(self.list_widget.mapToGlobal(pos))
        if action == remove_action:
            row = self.list_widget.currentRow()
            if row >= 0:
                del self.playlist[row]
                self.list_widget.takeItem(row)

    def animate_button_click(self, button):
        animation = QPropertyAnimation(button, b"size")
        animation.setDuration(120)
        animation.setStartValue(QSize(button.width(), button.height()))
        animation.setEndValue(QSize(button.width() - 6, button.height() - 6))
        animation.setEasingCurve(QEasingCurve.OutQuad)

        animation_back = QPropertyAnimation(button, b"size")
        animation_back.setDuration(120)
        animation_back.setStartValue(QSize(button.width() - 6, button.height() - 6))
        animation_back.setEndValue(QSize(button.width(), button.height()))
        animation_back.setEasingCurve(QEasingCurve.InOutQuad)

        animation.finished.connect(animation_back.start)
        animation.start()

    def toggle_settings_menu(self):
        self.settings_menu.setVisible(not self.settings_menu.isVisible())

    def song_selected(self, item):
        self.current_index = self.list_widget.row(item)
        self.play_file(self.playlist[self.current_index])

    def set_system_volume(self, val):
        try:
            self.volume_ctrl.SetMasterVolumeLevelScalar(val / 100, None)
        except:
            pass

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("player_icon.ico"))
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

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if folder:
            self.load_music_files(folder)

    def init_ui(self):
        main_layout = QHBoxLayout()
        self.left_layout = QVBoxLayout()
        self.right_layout = QVBoxLayout()

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
        settings_layout = QVBoxLayout()
        self.vlc_vol_label = QLabel("🎚️ VLC 音量")
        self.vlc_vol_slider = QSlider(Qt.Horizontal)
        self.vlc_vol_slider.setRange(0, 100)
        self.vlc_vol_slider.setValue(80)
        self.vlc_vol_slider.valueChanged.connect(self.set_vlc_volume)
        settings_layout.addWidget(self.vlc_vol_label)
        settings_layout.addWidget(self.vlc_vol_slider)
        self.settings_menu.setLayout(settings_layout)
        self.settings_menu.setVisible(False)
        self.right_layout.addWidget(self.settings_menu)

        playlist_card = QFrame()
        playlist_card.setObjectName("card")
        playlist_layout = QVBoxLayout(playlist_card)
        self.list_widget = DraggableListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_playlist_context_menu)
        self.list_widget.itemClicked.connect(self.song_selected)
        playlist_layout.addWidget(self.list_widget)
        self.left_layout.addWidget(playlist_card)

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
        self.lyric_browser.anchorClicked.connect(self.seek_to_lyric_time)
        self.lyric_browser.verticalScrollBar().valueChanged.connect(self.on_lyric_scroll)
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

        try:
            vol = int(self.volume_ctrl.GetMasterVolumeLevelScalar() * 100)
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(vol)
            self.volume_slider.blockSignals(False)
        except:
            pass

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

    def toggle_playlist(self):
        self.playlist_visible = not self.playlist_visible
        self.list_widget.setVisible(self.playlist_visible)
        self.cover.setFixedSize(220 if self.playlist_visible else 300,
                                220 if self.playlist_visible else 300)

    def play_prev(self):
        if not self.playlist: return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.list_widget.setCurrentRow(self.current_index)
        self.play_file(self.playlist[self.current_index])

    def switch_mode(self):
        modes = {"loop_all": "loop_one", "loop_one": "shuffle", "shuffle": "loop_all"}
        icons = {"loop_all": "🔁", "loop_one": "🔂", "shuffle": "🔀"}
        self.play_mode = modes[self.play_mode]
        self.btn_mode.setText(icons[self.play_mode])
        self.btn_mode.repaint()

    def start_seek(self):
        self.user_seeking = True

    def seek(self):
        self.player.set_position(self.progress_slider.value() / 1000)
        self.user_seeking = False

    def update_ui(self):
        if self.player.is_playing() and not self.user_seeking:
            pos = self.player.get_position()
            cur_time = pos * self.duration
            self.progress_slider.setValue(int(pos * 1000))
            self.time_label.setText(
                f"{int(cur_time // 60):02}:{int(cur_time % 60):02} / {int(self.duration // 60):02}:{int(self.duration % 60):02}")
            self.update_lyrics(cur_time)

        if self.player.get_state() == vlc.State.Ended:
            if self.play_mode == "loop_one":
                self.play_file(self.playlist[self.current_index])
            elif self.play_mode == "shuffle":
                self.current_index = random.randint(0, len(self.playlist) - 1)
                self.play_file(self.playlist[self.current_index])
            else:
                self.play_next()

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
                                time_tag = line[line.find("[") + 1:line.find("]")]
                                text = line[line.find("]") + 1:].strip()
                                mins, secs = time_tag.split(":")
                                sec = int(mins) * 60 + float(secs)
                                self.lyrics.append((sec, text))
                            except:
                                continue
                break
        self.lyrics.sort()

    def seek_to_lyric_time(self, url):
        try:
            time_sec = float(url.toString())
            self.player.set_time(int(time_sec * 1000))
        except Exception as e:
            print("跳转歌词失败:", e)

    def update_lyrics(self, current_time):
        if not self.lyrics:
            return
        current_index = 0
        for i, (t, _) in enumerate(self.lyrics):
            if current_time < t:
                current_index = max(0, i - 1)
                break
        html_lines = []
        for i, (t, line) in enumerate(self.lyrics):
            if i == current_index:
                html_lines.append(
                    f'<a href="{t}"><p style="color:red; font-weight:bold; text-align:center; text-decoration:none;">{line}</p></a>')
            else:
                html_lines.append(
                    f'<a href="{t}"><p style="color:gray; text-align:center; text-decoration:none;">{line}</p></a>')

        if self.lyric_locked:
            scrollbar = self.lyric_browser.verticalScrollBar()
            current_scroll = scrollbar.value()
            self.lyric_browser.setHtml("".join(html_lines))
            scrollbar.setValue(current_scroll)
        else:
            self.lyric_browser.setHtml("".join(html_lines))
            cursor = self.lyric_browser.textCursor()
            cursor.movePosition(QTextCursor.Start)
            for _ in range(current_index):
                cursor.movePosition(QTextCursor.Down)
            self.lyric_browser.setTextCursor(cursor)

    def closeEvent(self, event):
        self.tray_icon.hide()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("player_icon.ico"))
    player = MusicPlayer()
    player.show()
    sys.exit(app.exec_())
