# -- coding: utf-8 --
import os, sys, io, random
import vlc
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QSlider, QTextBrowser, QFileDialog,
    QStyle, QSizePolicy, QMenu
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap, QIcon
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from PIL import Image

class MusicPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("播放器 V6.3 · 浅色模式")
        self.setGeometry(200, 100, 960, 640)
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        self.playlist = []
        self.current_index = -1
        self.duration = 0
        self.user_seeking = False
        self.lyrics = []
        self.intro_info = ""
        self.current_lyric_index = 0
        self.lyric_auto_scroll = True

        self.init_ui()
        self.setStyleSheet("""
            QWidget { background-color: #f2f2f2; font-family: 微软雅黑; }
            QPushButton { border: none; padding: 6px 10px; border-radius: 8px; background: #e0e0e0; }
            QPushButton:hover { background: #d6d6d6; }
            QListWidget { background: #f9f9f9; border-radius: 6px; }
            QTextBrowser { background: white; border-radius: 10px; padding: 10px; }
        """)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(1000)

        # 默认目录
        default_dir = "C:/PlayMc"
        if os.path.exists(default_dir):
            self.load_music_files(default_dir)

    def init_ui(self):
        main = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.song_selected)
        left.addWidget(QLabel("🎵 播放列表"))
        left.addWidget(self.list_widget)

        self.btn_toggle_list = QPushButton("📁 播放列表")
        self.btn_toggle_list.clicked.connect(self.toggle_playlist)
        left.addWidget(self.btn_toggle_list)

        self.cover = QLabel("🎵")
        self.cover.setFixedSize(200, 200)
        self.cover.setStyleSheet("border: 1px solid #ccc;")
        self.cover.setAlignment(Qt.AlignCenter)
        left.addWidget(self.cover)

        self.title = QLabel("未播放")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("微软雅黑", 14))
        left.addWidget(self.title)

        self.lyric_browser = QTextBrowser()
        self.lyric_browser.setFont(QFont("微软雅黑", 11))
        self.lyric_browser.setOpenExternalLinks(False)
        self.lyric_browser.anchorClicked.connect(self.on_lyric_clicked)
        self.lyric_browser.verticalScrollBar().sliderPressed.connect(self.pause_auto_scroll)
        right.addWidget(QLabel("🎵 歌词"))
        right.addWidget(self.lyric_browser)

        self.btn_back_to_lyric = QPushButton("🎯 跳回当前歌词")
        self.btn_back_to_lyric.clicked.connect(self.scroll_to_current_lyric)
        right.addWidget(self.btn_back_to_lyric)

        control = QHBoxLayout()
        self.btn_prev = QPushButton("⏮")
        self.btn_play = QPushButton("▶")
        self.btn_next = QPushButton("⏭")
        self.btn_mode = QPushButton("🔁")
        self.btn_folder = QPushButton("📂")
        self.btn_setting = QPushButton("⚙️")
        self.btn_setting.setMenu(self.create_setting_menu())
        control.addWidget(self.btn_folder)
        control.addWidget(self.btn_prev)
        control.addWidget(self.btn_play)
        control.addWidget(self.btn_next)
        control.addWidget(self.btn_mode)
        control.addWidget(self.btn_setting)
        right.addLayout(control)

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.sliderPressed.connect(self.start_seek)
        self.progress_slider.sliderReleased.connect(self.seek)
        right.addWidget(self.progress_slider)

        self.time_label = QLabel("00:00 / 00:00")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self.set_volume)
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("🔊"))
        volume_layout.addWidget(self.volume_slider)
        right.addWidget(self.time_label)
        right.addLayout(volume_layout)

        main.addLayout(left, 3)
        main.addLayout(right, 6)
        self.setLayout(main)

        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(self.play_next)
        self.btn_prev.clicked.connect(self.play_prev)
        self.btn_mode.clicked.connect(self.switch_mode)
        self.btn_folder.clicked.connect(self.choose_folder)

    def create_setting_menu(self):
        menu = QMenu()
        mode_action = menu.addAction("切换深/浅色模式")
        mode_action.triggered.connect(self.toggle_theme)
        return menu

    def toggle_theme(self):
        if "浅色" in self.windowTitle():
            self.setWindowTitle("播放器 V6.3 · 深色模式")
            self.setStyleSheet("""
                QWidget { background-color: #202020; color: white; font-family: 微软雅黑; }
                QPushButton { background: #444; color: white; border-radius: 8px; }
                QPushButton:hover { background: #555; }
                QListWidget, QTextBrowser { background: #2a2a2a; color: white; border-radius: 10px; }
            """)
        else:
            self.setWindowTitle("播放器 V6.3 · 浅色模式")
            self.setStyleSheet("""
                QWidget { background-color: #f2f2f2; font-family: 微软雅黑; }
                QPushButton { border: none; padding: 6px 10px; border-radius: 8px; background: #e0e0e0; }
                QPushButton:hover { background: #d6d6d6; }
                QListWidget { background: #f9f9f9; border-radius: 6px; }
                QTextBrowser { background: white; border-radius: 10px; padding: 10px; }
            """)

    def toggle_playlist(self):
        visible = self.list_widget.isVisible()
        self.list_widget.setVisible(not visible)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐目录")
        if folder:
            self.load_music_files(folder)

    def load_music_files(self, folder):
        self.playlist.clear()
        self.list_widget.clear()
        for f in os.listdir(folder):
            if f.lower().endswith((".mp3", ".wav", ".flac")):
                path = os.path.join(folder, f)
                self.playlist.append(path)
                self.list_widget.addItem(os.path.basename(path))
        if self.playlist:
            self.current_index = 0
            self.list_widget.setCurrentRow(0)
            self.play_file(self.playlist[0])

    def song_selected(self, item):
        self.current_index = self.list_widget.row(item)
        self.play_file(self.playlist[self.current_index])

    def play_file(self, path):
        self.player.set_media(self.instance.media_new(path))
        self.player.play()
        self.player.audio_set_volume(self.volume_slider.value())
        self.title.setText(os.path.basename(path))
        self.load_cover(path)
        self.load_lyrics(path)
        self.btn_play.setText("⏸")
        if path.endswith(".mp3"):
            self.duration = MP3(path).info.length
        else:
            self.duration = 0

    def toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
            self.btn_play.setText("▶")
        else:
            self.player.play()
            self.btn_play.setText("⏸")

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

    def start_seek(self): self.user_seeking = True
    def seek(self):
        self.player.set_position(self.progress_slider.value() / 1000)
        self.user_seeking = False

    def update_ui(self):
        if self.player.is_playing() and not self.user_seeking:
            pos = self.player.get_position()
            cur = pos * self.duration
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(pos * 1000))
            self.progress_slider.blockSignals(False)
            self.time_label.setText(f"{int(cur//60):02}:{int(cur%60):02} / {int(self.duration//60):02}:{int(self.duration%60):02}")
            self.update_lyrics(cur)

    def set_volume(self, v):
        self.player.audio_set_volume(v)

    def switch_mode(self):
        # 暂不实现
        pass

    def load_cover(self, path):
        try:
            tags = ID3(path)
            for tag in tags.values():
                if tag.FrameID == 'APIC':
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
        self.intro_info = ""
        folder = os.path.dirname(path)
        base = os.path.splitext(os.path.basename(path))[0]
        for f in os.listdir(folder):
            if f.endswith(".lrc") and base in f:
                lrc_path = os.path.join(folder, f)
                break
        else:
            self.lyric_browser.setText("未找到歌词")
            return
        with open(lrc_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("[ti:") or line.startswith("[ar:") or line.startswith("[by:"):
                    self.intro_info += line.strip("[]\n") + "  "
                elif line.startswith("[") and "]" in line:
                    time_tag = line[1:line.find("]")]
                    content = line[line.find("]") + 1:].strip()
                    try:
                        mins, secs = time_tag.split(":")
                        time_sec = int(mins) * 60 + float(secs)
                        self.lyrics.append((time_sec, content))
                    except:
                        continue
        self.lyrics.sort()

    def update_lyrics(self, current_time):
        if not self.lyrics: return
        for i, (t, _) in enumerate(self.lyrics):
            if current_time < t:
                self.current_lyric_index = max(0, i - 1)
                break
        html_lines = []
        for i, (t, line) in enumerate(self.lyrics):
            if i == self.current_lyric_index:
                html_lines.append(f'<p style="text-align:center; color:red; font-weight:bold;">{line}</p>')
            else:
                html_lines.append(f'<a href="{t}"><p style="text-align:center; color:#333;">{line}</p></a>')
        if self.lyric_auto_scroll:
            self.lyric_browser.setHtml("".join(html_lines))
            cursor = self.lyric_browser.textCursor()
            cursor.movePosition(cursor.Start)
            for _ in range(self.current_lyric_index):
                cursor.movePosition(cursor.Down)
            self.lyric_browser.setTextCursor(cursor)

    def pause_auto_scroll(self):
        self.lyric_auto_scroll = False

    def scroll_to_current_lyric(self):
        self.lyric_auto_scroll = True

    def on_lyric_clicked(self, url):
        try:
            seconds = float(url.toString())
            self.player.set_time(int(seconds * 1000))
            self.lyric_auto_scroll = True
        except:
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = MusicPlayer()
    player.show()
    sys.exit(app.exec_())
