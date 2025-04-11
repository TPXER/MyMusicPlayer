# -- coding: utf-8 --
import os, sys, vlc, io, random
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QSlider, QTextBrowser, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from PIL import Image


class NeumorphicPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎧 播放器 V5.0")
        self.setGeometry(300, 100, 920, 600)

        with open("neumorphism_style.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.playlist = []
        self.current_index = -1
        self.duration = 0
        self.user_seeking = False
        self.lyrics = []

        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(1000)

        self.load_music_files("C:/PlayMc")

    def init_ui(self):
        layout = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.song_selected)
        left.addWidget(QLabel("🎵 播放列表"))
        left.addWidget(self.list_widget)

        self.cover = QLabel("🎵")
        self.cover.setFixedSize(200, 200)
        self.cover.setAlignment(Qt.AlignCenter)
        right.addWidget(self.cover)

        self.song_label = QLabel("未播放")
        self.song_label.setAlignment(Qt.AlignCenter)
        self.song_label.setFont(QFont("微软雅黑", 16))
        right.addWidget(self.song_label)

        self.lyric_browser = QTextBrowser()
        self.lyric_browser.setFont(QFont("微软雅黑", 12))
        self.lyric_browser.setFixedHeight(200)
        right.addWidget(self.lyric_browser)

        ctrl = QHBoxLayout()
        self.play_btn = QPushButton("▶ 播放")
        self.next_btn = QPushButton("⏭ 下一首")
        self.open_btn = QPushButton("📂 打开文件夹")
        ctrl.addWidget(self.open_btn)
        ctrl.addWidget(self.play_btn)
        ctrl.addWidget(self.next_btn)
        right.addLayout(ctrl)

        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderPressed.connect(self.start_seek)
        self.progress.sliderReleased.connect(self.seek_to)
        right.addWidget(self.progress)

        layout.addLayout(left, 2)
        layout.addLayout(right, 4)
        self.setLayout(layout)

        self.play_btn.clicked.connect(self.toggle_play)
        self.next_btn.clicked.connect(self.play_next)
        self.open_btn.clicked.connect(self.choose_folder)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if folder:
            self.load_music_files(folder)

    def load_music_files(self, folder):
        self.playlist = []
        self.list_widget.clear()
        for f in os.listdir(folder):
            if f.lower().endswith((".mp3", ".wav")):
                path = os.path.join(folder, f)
                self.playlist.append(path)
                self.list_widget.addItem(os.path.basename(f))
        if self.playlist:
            self.current_index = 0
            self.list_widget.setCurrentRow(0)
            self.play_file(self.playlist[0])

    def song_selected(self, item):
        index = self.list_widget.row(item)
        if index != -1:
            self.current_index = index
            self.play_file(self.playlist[index])

    def play_file(self, path):
        self.player.set_media(self.instance.media_new(path))
        self.player.play()
        self.song_label.setText(os.path.basename(path))
        self.load_lyrics(path)
        self.load_cover(path)
        self.duration = MP3(path).info.length

    def toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
            self.play_btn.setText("▶ 播放")
        else:
            self.player.play()
            self.play_btn.setText("⏸ 暂停")

    def play_next(self):
        if not self.playlist: return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.list_widget.setCurrentRow(self.current_index)
        self.play_file(self.playlist[self.current_index])

    def update_progress(self):
        if self.player.is_playing() and not self.user_seeking:
            pos = self.player.get_position()
            self.progress.blockSignals(True)
            self.progress.setValue(int(pos * 1000))
            self.progress.blockSignals(False)

    def start_seek(self): self.user_seeking = True
    def seek_to(self):
        self.player.set_position(self.progress.value() / 1000)
        self.user_seeking = False

    def load_cover(self, filepath):
        try:
            tags = ID3(filepath)
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

    def load_lyrics(self, music_path):
        self.lyrics = []
        folder = os.path.dirname(music_path)
        base = os.path.splitext(os.path.basename(music_path))[0]
        lrc_file = None
        for f in os.listdir(folder):
            if f.lower().endswith(".lrc") and base in f:
                lrc_file = os.path.join(folder, f)
                break
        if not lrc_file:
            self.lyric_browser.setText("无歌词")
            return

        try:
            with open(lrc_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("[") and "]" in line:
                        time_tag = line[line.find("[")+1:line.find("]")]
                        text = line[line.find("]")+1:].strip()
                        parts = time_tag.split(":")
                        try:
                            sec = int(parts[0]) * 60 + float(parts[1])
                            self.lyrics.append((sec, text))
                        except:
                            continue
            self.lyric_browser.setText("\n".join([line for _, line in self.lyrics]))
        except:
            self.lyric_browser.setText("歌词读取失败")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = NeumorphicPlayer()
    win.show()
    sys.exit(app.exec_())