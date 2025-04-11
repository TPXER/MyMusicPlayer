
# -- coding: utf-8 --
import os
os.add_dll_directory(r"C:\Program Files\VideoLAN\VLC")

import sys
import vlc
import io
import random
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QSlider,
    QFileDialog, QLabel, QHBoxLayout, QTextBrowser, QListWidget
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QFont
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from PIL import Image


class MusicPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎧 播放器 V4.1")
        self.setGeometry(300, 100, 900, 600)

        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        self.volume_ctrl = interface.QueryInterface(IAudioEndpointVolume)

        self.playlist = []
        self.current_index = -1
        self.duration = 0
        self.user_seeking = False
        self.lyrics = []
        self.play_mode = "loop_all"
        self.intro_info = ""

        self.init_ui()

        vol = int(self.volume_ctrl.GetMasterVolumeLevelScalar() * 100)
        self.volume_slider.setValue(vol)
        self.volume_label.setText(f"🔊 音量：{vol}%")

        self.volume_timer = QTimer()
        self.volume_timer.timeout.connect(self.sync_volume)
        self.volume_timer.start(1000)

        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.start(1000)

        # 默认路径
        self.load_music_files("C:/PlayMc")

    def init_ui(self):
        layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.list_item_clicked)
        left_layout.addWidget(QLabel("🎵 播放列表"))
        left_layout.addWidget(self.list_widget)

        self.cover_label = QLabel("无封面")
        self.cover_label.setFixedSize(200, 200)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("border: 1px solid gray;")

        self.song_label = QLabel("未播放")
        self.song_label.setAlignment(Qt.AlignCenter)
        self.song_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.lyric_browser = QTextBrowser()
        self.lyric_browser.setFixedHeight(220)
        self.lyric_browser.setFont(QFont("微软雅黑", 12))

        self.folder_btn = QPushButton("📂 打开文件夹")
        self.play_btn = QPushButton("▶ 播放")
        self.pause_btn = QPushButton("⏸ 暂停")
        self.stop_btn = QPushButton("⏹ 停止")
        self.prev_btn = QPushButton("⏮ 上一首")
        self.next_btn = QPushButton("⏭ 下一首")
        self.mode_btn = QPushButton("🔁 列表循环")
        self.mode_btn.clicked.connect(self.switch_mode)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_label = QLabel()

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_label = QLabel("进度：00:00 / 00:00")

        self.folder_btn.clicked.connect(self.choose_folder)
        self.play_btn.clicked.connect(self.play_music)
        self.pause_btn.clicked.connect(self.pause_music)
        self.stop_btn.clicked.connect(self.stop_music)
        self.prev_btn.clicked.connect(self.play_prev)
        self.next_btn.clicked.connect(self.play_next)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.progress_slider.sliderPressed.connect(self.start_seek)
        self.progress_slider.sliderReleased.connect(self.seek_position)

        for w in [
            self.cover_label, self.song_label, self.lyric_browser, self.folder_btn,
            self.play_btn, self.pause_btn, self.stop_btn,
            self.prev_btn, self.next_btn, self.mode_btn,
            self.progress_label, self.progress_slider, self.volume_label, self.volume_slider
        ]:
            right_layout.addWidget(w)

        layout.addLayout(left_layout, 2)
        layout.addLayout(right_layout, 4)
        self.setLayout(layout)

    def switch_mode(self):
        if self.play_mode == "loop_all":
            self.play_mode = "loop_one"
            self.mode_btn.setText("🔂 单曲循环")
        elif self.play_mode == "loop_one":
            self.play_mode = "shuffle"
            self.mode_btn.setText("🔀 随机播放")
        else:
            self.play_mode = "loop_all"
            self.mode_btn.setText("🔁 列表循环")

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if folder:
            self.load_music_files(folder)

    def load_music_files(self, folder):
        self.playlist = []
        self.list_widget.clear()
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path) and f.lower().endswith((".mp3", ".wav", ".flac")):
                self.playlist.append(path)
                self.list_widget.addItem(os.path.basename(path))
        if self.playlist:
            self.current_index = 0
            self.list_widget.setCurrentRow(0)
            self.play_file(self.playlist[0])

    def list_item_clicked(self, item):
        index = self.list_widget.row(item)
        if index != -1:
            self.current_index = index
            self.play_file(self.playlist[index])

    def play_file(self, path):
        self.player.set_media(self.instance.media_new(path))
        self.player.play()
        self.song_label.setText(os.path.basename(path))
        self.set_volume(self.volume_slider.value())
        self.load_cover(path)
        self.load_lyrics_auto(path)
        self.duration = MP3(path).info.length

    def play_music(self): self.player.play()
    def pause_music(self): self.player.pause()
    def stop_music(self): self.player.stop()

    def play_next(self):
        if not self.playlist: return
        if self.play_mode == "shuffle":
            self.current_index = random.randint(0, len(self.playlist) - 1)
        else:
            self.current_index = (self.current_index + 1) % len(self.playlist)
        self.list_widget.setCurrentRow(self.current_index)
        self.play_file(self.playlist[self.current_index])

    def play_prev(self):
        if not self.playlist: return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.list_widget.setCurrentRow(self.current_index)
        self.play_file(self.playlist[self.current_index])

    def set_volume(self, value):
        self.volume_label.setText(f"🔊 音量：{value}%")
        self.volume_ctrl.SetMasterVolumeLevelScalar(value / 100, None)
        self.player.audio_set_volume(100)

    def sync_volume(self):
        sys_vol = int(self.volume_ctrl.GetMasterVolumeLevelScalar() * 100)
        if self.volume_slider.value() != sys_vol:
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(sys_vol)
            self.volume_label.setText(f"🔊 音量：{sys_vol}%")
            self.volume_slider.blockSignals(False)

    def update_progress(self):
        if self.player.is_playing() and not self.user_seeking:
            pos = self.player.get_position()
            cur = pos * self.duration
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(pos * 1000))
            self.progress_slider.blockSignals(False)
            self.progress_label.setText(f"进度：{self.format_time(cur)} / {self.format_time(self.duration)}")
            self.update_lyrics(cur)
        elif not self.player.is_playing() and self.duration > 0:
            state = self.player.get_state()
            if state == vlc.State.Ended:
                if self.play_mode == "loop_one":
                    self.play_file(self.playlist[self.current_index])
                else:
                    self.play_next()

    def start_seek(self): self.user_seeking = True
    def seek_position(self):
        val = self.progress_slider.value() / 1000
        self.player.set_position(val)
        self.user_seeking = False

    def format_time(self, sec):
        mins = int(sec // 60)
        secs = int(sec % 60)
        return f"{mins:02}:{secs:02}"

    def load_cover(self, filepath):
        try:
            tags = ID3(filepath)
            for tag in tags.values():
                if tag.FrameID == 'APIC':
                    image = Image.open(io.BytesIO(tag.data)).resize((200, 200))
                    byte_arr = io.BytesIO()
                    image.save(byte_arr, format='PNG')
                    pixmap = QPixmap()
                    pixmap.loadFromData(byte_arr.getvalue())
                    self.cover_label.setPixmap(pixmap)
                    return
        except:
            pass
        self.cover_label.setText("无封面")

    def load_lyrics_auto(self, music_path):
        self.lyrics = []
        folder = os.path.dirname(music_path)
        base_name = os.path.splitext(os.path.basename(music_path))[0]
        candidates = [f for f in os.listdir(folder) if f.lower().endswith(".lrc")]

        match = None
        for f in candidates:
            if base_name in f:
                match = os.path.join(folder, f)
                break

        if not match:
            self.lyric_browser.setText("无歌词")
            return

        try:
            with open(match, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith("[ti:") or line.startswith("[ar:") or line.startswith("[by:"):
                        self.intro_info += line.strip("[]\n") + "  "
                    elif line.startswith("[") and "]" in line:
                        time_tag = line[line.find("[") + 1: line.find("]")]
                        text = line[line.find("]") + 1:].strip()
                        try:
                            parts = time_tag.split(":")
                            minutes = int(parts[0])
                            secs = float(parts[1])
                            seconds = minutes * 60 + secs
                            self.lyrics.append((seconds, text))
                        except:
                            continue
            self.lyric_browser.setText("歌词加载成功")
        except:
            self.lyric_browser.setText("歌词读取失败")

    def update_lyrics(self, current_time):
        if self.lyrics and current_time < self.lyrics[0][0]:
            html = f'<p style="text-align:center; color:blue; font-weight:bold;">{self.intro_info or self.lyrics[0][1]}</p>'
            self.lyric_browser.setHtml("<p>&nbsp;</p>" * 5 + html + "<p>&nbsp;</p>" * 5)
            return

        current_index = 0
        for i, (t, line) in enumerate(self.lyrics):
            if current_time < t:
                current_index = max(0, i - 1)
                break
            current_index = i

        html_lines = []
        for i, (t, line) in enumerate(self.lyrics):
            if i == current_index:
                html_lines.append(f'<p style="text-align:center; color:red; font-weight:bold;">{line}</p>')
            else:
                diff = abs(i - current_index)
                opacity = max(60, 200 - diff * 40)
                html_lines.append(f'<p style="text-align:center; color:rgb({opacity},{opacity},{opacity});">{line}</p>')

        center_line = 7
        top_padding = max(0, center_line - current_index)
        bottom_padding = max(0, 15 - (top_padding + len(html_lines)))
        full_html = "".join(["<p>&nbsp;</p>"] * top_padding + html_lines + ["<p>&nbsp;</p>"] * bottom_padding)
        self.lyric_browser.setHtml(full_html)

        cursor = self.lyric_browser.textCursor()
        cursor.movePosition(cursor.Start)
        for _ in range(current_index + top_padding):
            cursor.movePosition(cursor.Down)
        self.lyric_browser.setTextCursor(cursor)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MusicPlayer()
    window.show()
    sys.exit(app.exec_())
