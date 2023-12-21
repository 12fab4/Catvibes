from PyQt6.QtWidgets import (
    QApplication,
    QProgressBar,
    QPushButton,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget, QLineEdit, QCompleter, QMenu, QLayout, QStyleFactory, QStyle
)

from PyQt6.QtGui import (
    QColor,
    QPalette,
    QPixmap,
    QImage,
    QStandardItemModel, QStandardItem, QCursor
)

from PyQt6.QtCore import (
    QTimer,
    Qt, QProcess
)

import sys
from pathlib import Path
from functools import partial
import eyed3

from catvibes import catvibes_lib as lib

lib.init()
playlists = lib.playlists
song_data = lib.song_data


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Catvibes")
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        global player
        player = PlayerWidget()
        layout.addWidget(player, 0, 1)

        playlists_widget = QTabWidget()

        def refresh_tab():
            playlists_widget.currentWidget().refresh()
            # print("tab refreshed ")

        playlists_widget.currentChanged.connect(refresh_tab)

        playlists_widget.addTab(SongsWidget(), "Songs")
        for name, playlist in playlists.val.items():
            playlists_widget.addTab(PlaylistWidget(playlist), name)

        layout.addWidget(playlists_widget, 0, 0)
        layout.setColumnStretch(0, 2)

        self.timer = QTimer()
        self.timer.start(100)
        self.timer.timeout.connect(partial(player.refresh, self.timer.interval() / 1000))

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)


class SongWidget(QWidget):
    def __init__(self, song_id: str):
        super().__init__()
        self.id = song_id
        layout = QHBoxLayout()
        if song_id not in song_data.val:
            raise IndexError("Song not found")
        songinfo = song_data.val[song_id]

        self.Icon = QLabel()
        self.Icon.setPixmap(song_cover_info(song_id)[0])
        self.Icon.setFixedWidth(60)
        self.Info = QLabel(lib.song_string(songinfo))
        self.Info.setMinimumWidth(200)
        self.Info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.Button = QPushButton("Play")
        self.Button.setFixedWidth(100)
        layout.addWidget(self.Icon)
        layout.addWidget(self.Info, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.Button)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.setMinimumWidth(480)


class PlaylistWidget(QWidget):
    def __init__(self, playlist: lib.Pointer) -> None:
        super().__init__()
        self.playlist = playlist
        layout = QGridLayout()
        shuffle = QPushButton("Shuffle")
        shuffle.clicked.connect(self.shuffle)
        layout.addWidget(shuffle)
        play = QPushButton("Play")
        play.clicked.connect(partial(self.playsong, 0))
        layout.addWidget(play, 0, 1)
        self.search = QLineEdit()
        self.search.textChanged.connect(self.search_suggest)
        self.search.returnPressed.connect(self.find_song)
        self.searchresults = QStandardItemModel()
        completion = QCompleter(self.searchresults, self)
        completion.setModelSorting(QCompleter.ModelSorting.CaseInsensitivelySortedModel)
        completion.setCompletionMode(QCompleter.CompletionMode.InlineCompletion)
        self.search.setCompleter(completion)
        layout.addWidget(self.search, 0, 2)
        self.playlistarea = QScrollArea()
        self.playlistarea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlistbox = QWidget()
        self.playlistlayout = QVBoxLayout()
        self.refresh()
        self.playlistbox.setLayout(self.playlistlayout)
        self.playlistarea.setWidget(self.playlistbox)
        self.playlistarea.setWidgetResizable(True)
        layout.addWidget(self.playlistarea, 1, 0, 2, 0)
        self.setLayout(layout)
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)

    def search_suggest(self, text: str):
        if len(text) > 2:
            completions = lib.yt.get_search_suggestions(text)
            self.searchresults.clear()
            self.searchresults.appendRow([QStandardItem(val) for val in completions])

    def find_song(self):
        def finish():
            # print("proc finished")
            nonlocal p
            if p.exitCode() == 0:
                # print("sucessfully downloaded", song_info["title"])
                song_data.val[song_info["videoId"]] = song_info
                self.playlist.val.append(song_id)
                self.refresh()
            p = None

        song_info = lib.yt.search(self.search.text(), "songs", limit=1)[0]
        song_id = song_info["videoId"]
        p = QProcess()
        p.finished.connect(finish)
        p.start("yt-dlp",
                ["--extract-audio",
                 "--audio-format", "mp3",
                 "--audio-quality", "0",
                 "--embed-thumbnail", "--embed-metadata",
                 "-o", f"{lib.song_dir}/{song_id}.mp3", f"https://www.youtube.com/watch?v={song_id}"])

    def shuffle(self):
        if player.playlist == []:
            player.add_list(
                [lib.song_file(song) for song in self.playlist.val]
            )
        player.shuffle()

    def playsong(self, num: int):
        player.clear_list()
        player.add_list(
            [lib.song_file(song) for song in self.playlist.val[num:]]
        )

    def refresh(self):
        clear_layout(self.playlistlayout)
        for i, val in enumerate(self.playlist.val):
            try:
                self.playlistlayout.addWidget(self.nth_songwidget(i))
            except (IndexError):
                pass

    def nth_songwidget(self, n: int):
        wid = SongWidget(self.playlist.val[n])
        wid.Button.clicked.connect(partial(self.playsong, n))
        menu = QMenu()
        append = menu.addAction("append")
        remove = menu.addAction("remove")
        append.triggered.connect(partial(player.add, lib.song_file(self.playlist.val[n])))
        remove.triggered.connect(partial(self.remove_song, n))

        def contextmenu(*args):
            menu.popup(QCursor.pos())

        wid.Button.contextMenuEvent = contextmenu
        return wid

    def remove_song(self, n):
        del self.playlist.val[n]
        self.refresh()


class SongsWidget(PlaylistWidget):
    def __init__(self) -> None:
        playlist = lib.Pointer(list(song_data.val.keys()))
        super().__init__(playlist)
        self.layout().removeWidget(self.search)
        del self.search

    def remove_song(self, n):
        del song_data.val[self.playlist.val[n]]
        super().remove_song(n)

    def refresh(self):
        self.playlist = lib.Pointer(list(song_data.val.keys()))
        super().refresh()


class PlayerWidget(QWidget, lib.MusicPlayerClass):
    def __init__(self):
        QWidget.__init__(self)
        lib.MusicPlayerClass.__init__(self)

        layout = QGridLayout()
        layout.setRowStretch(0, 3)
        self.Icon = QLabel()
        layout.addWidget(self.Icon, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        self.Button_f = QPushButton("")
        self.Button_f.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.Button_f.clicked.connect(self.next)
        self.Button_f.setFixedWidth(80)
        self.Button_b = QPushButton("")
        self.Button_b.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.Button_b.clicked.connect(self.prev)
        self.Button_b.setFixedWidth(80)
        self.Button_play = QPushButton("")
        self.Button_play.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.Button_play.clicked.connect(self.toggle)
        self.prog_bar = QProgressBar()

        self.title = QLabel()
        self.title.setFixedHeight(30)

        layout.addWidget(self.title, 1, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.prog_bar, 2, 0, 1, 3)
        layout.addWidget(self.Button_b, 3, 0)
        layout.addWidget(self.Button_play, 3, 1)
        layout.addWidget(self.Button_f, 3, 2)

        self.setAutoFillBackground(True)
        self.setLayout(layout)

    def toggle(self):
        super().toggle()
        if self.playing:
            self.Button_play.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.Button_play.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def refresh(self, seconds: float):
        if self.playlist != []:
            self.query(seconds)
            song = self.playlist[self.counter].stem
            try:
                self.prog_bar.setRange(0, song_data.val[song]["duration_seconds"])
                self.prog_bar.setValue(int(self.timer))
                self.prog_bar.setFormat(f"{lib.format_time(int(self.timer))} - {song_data.val[song]['duration']}")
                self.title.setText(song_data.val[song]['title'])
            except KeyError:
                del self.playlist[self.counter]
                self.counter = self.counter % len(self.playlist)
                self.proc.kill()

    def play(self, file: Path):
        super().play(file)
        song = file.stem
        cover, color = song_cover_info(song, 300, 300)
        self.Icon.setPixmap(cover)
        colors = self.palette()
        colors.setColor(QPalette.ColorRole.Window, color)
        self.setPalette(colors)


def song_cover_info(song_id: str, scalex=60, scaley=60) -> tuple[QPixmap, QColor]:
    file = lib.song_file(song_id)
    metadata: eyed3.AudioFile = eyed3.load(file)
    image = QImage.fromData(metadata.tag.images[0].image_data)
    color = image.pixelColor(1, 1)
    width, height = image.width(), image.height()

    image = image.copy(int((width - height) / 2), 0, height, height)

    pixmap = QPixmap.fromImage(image)
    return pixmap.scaled(scalex, scaley), color


def clear_layout(layout: QLayout):
    for i in reversed(range(layout.count())):
        layout.itemAt(i).widget().setParent(None)


def main():
    app = QApplication(sys.argv)
    theme = lib.config.val["theme"]
    print(theme, QStyleFactory.keys())
    if theme in QStyleFactory.keys():
        app.setStyle(theme)
    window = MainWindow()
    window.show()
    try:
        app.exec()
    finally:
        player.proc.kill()
        lib.data.save_all()


if __name__ == "__main__":
    main()
