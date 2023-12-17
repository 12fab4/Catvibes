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
    QTabWidget
)

from PyQt6.QtGui import (
    QPixmap,
    QImage
)

from PyQt6.QtCore import (
    QTimer
)

import sys
from pathlib import Path
from functools import partial
import eyed3

import catvibes_lib as lib


lib.init()
playlists = lib.playlists
song_data = lib.song_data

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Catvibes")
        layout = QGridLayout()

        playlistsWidget = QTabWidget()
        for name,playlist in playlists.val.items():
            playlistsWidget.addTab(playlistWidget(playlist), name)

        layout.addWidget(playlistsWidget,0,0)

        global player
        player = playerWidget()

        layout.addWidget(player,0,1)
        layout.setColumnStretch(0,2)

        self.timer = QTimer()
        self.timer.start(100)
        self.timer.timeout.connect(partial(player.refresh,self.timer.interval() / 1000))


        centralWidget = QWidget()
        centralWidget.setLayout(layout)
        self.setCentralWidget(centralWidget)


class songWidget(QWidget):
    def __init__(self, songId:str):
        super().__init__()
        self.id = songId
        layout = QHBoxLayout()
        songinfo = song_data.val[songId]

        self.Icon = QLabel()
        self.Icon.setPixmap(song_cover(songId))
        self.Info = QLabel(lib.song_string(songinfo))
        self.Info.setMaximumWidth(9999)
        self.Button = QPushButton("Play")
        self.Button.setFixedWidth(100)
        layout.addWidget(self.Icon)
        layout.addWidget(self.Info)
        layout.addWidget(self.Button)
        self.setLayout(layout)

class playlistWidget(QWidget):
    def __init__(self, playlist: lib.Pointer) -> None:
        super().__init__()
        self.playlist = playlist
        layout = QGridLayout()
        shuffle = QPushButton("Shuffle")
        shuffle.clicked.connect(partial(self.shuffle))
        layout.addWidget(shuffle)
        playlistarea = QScrollArea()
        playlistbox = QWidget()
        playlistlayout = QVBoxLayout()
        for i,val in enumerate(playlist.val):
            wid = songWidget(val)
            wid.Button.clicked.connect(partial(self.playsong,i))
            playlistlayout.addWidget(wid)
        playlistbox.setLayout(playlistlayout)
        playlistarea.setWidget(playlistbox)
        playlistarea.setWidgetResizable(True)
        layout.addWidget(playlistarea)
        self.setLayout(layout)
    
    def shuffle(self):
        if player.playlist == []:
            player.add_list(
                [lib.song_file(song) for song in self.playlist.val]
                )
        player.shuffle()
    
    def playsong(self,num):
        player.clear_list()
        player.add_list(
            [lib.song_file(song) for song in self.playlist.val[num:]]
            )

class playerWidget(QWidget, lib.music_player_class):
    def __init__(self):
        QWidget.__init__(self)
        lib.music_player_class.__init__(self)

        layout = QGridLayout()
        self.Icon = QLabel()
        layout.addWidget(self.Icon,0,0,1,3)

        self.Button_f = QPushButton(">")
        self.Button_f.clicked.connect(self.next)
        self.Button_b = QPushButton("<")
        self.Button_b.clicked.connect(self.prev)
        self.prog_bar = QProgressBar()

        layout.addWidget(self.Button_b, 1,0)
        layout.addWidget(self.Button_f, 1,2)
        layout.addWidget(self.prog_bar, 1,1)


        self.setLayout(layout)

    def refresh(self,seconds: float):
        if self.playlist != []:
            self.query(seconds)
            song = self.playlist[self.counter].stem
            self.prog_bar.setRange(0,song_data.val[song]["duration_seconds"])
            self.prog_bar.setValue(int(self.timer))
            self.prog_bar.setFormat(f"{song_data.val[song]['title']} {lib.format_time(int(self.timer))} - {song_data.val[song]['duration']}")

    def play(self, file: Path):
        super().play(file)
        song = file.stem
        self.Icon.setPixmap(song_cover(song, 300, 300, resolution= -1))


def song_cover(songId:str,scalex = 60, scaley = 60, resolution = 0) -> QPixmap:
    file = lib.song_file(songId)
    metadata = eyed3.load(file)
    image = QImage.fromData(metadata.tag.images[0].image_data)
    width, height = image.width(), image.height()

    image = image.copy(int((width-height)/2),0,height,height)

    pixmap = QPixmap.fromImage(image)
    return pixmap.scaled(scalex, scaley)


app = QApplication(sys.argv)
app.setStyle('kvantum')

window = MainWindow()
window.show()


if __name__ =="__main__":
    try:
        app.exec()
    finally:
        player.proc.kill()
        lib.data.save_all()