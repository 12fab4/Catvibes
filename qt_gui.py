from PyQt6.QtWidgets import (
    QApplication,
    QPushButton,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QLabel,
    QTabWidget
)

from PyQt6.QtGui import (
    QPixmap,
    QImage
)

from PyQt6.QtCore import (
    QTimer,
    Qt,
    QSize
)

from pathlib import Path
import shutil
import sys
import requests
import os
from functools import partial

import catvibes_lib as lib


workdir = Path(__file__).parent
default_config_location = workdir.joinpath("config")
config_location = Path.home().joinpath(".config/Catvibes/config")
if not Path.is_file(config_location):
    shutil.copy2(default_config_location, config_location)

lib.data = lib.datamanager()

config:lib.Pointer = lib.config
lib.data.load(config_location,config)

lib.main_dir = Path.home().joinpath(config.val["maindirectory"])
lib.song_dir = lib.main_dir.joinpath("songs")
lib.data_dir = lib.main_dir.joinpath("data")
lib.playlist_dir = lib.main_dir.joinpath("playlists")

playlists:lib.Pointer = lib.playlists
song_data:lib.Pointer = lib.song_data


# loads the song db
lib.data.load(lib.data_dir.joinpath("data"), song_data,{})

with os.scandir(lib.playlist_dir) as files:
    for f in files:
        with open(f,"r") as loaded_file:
            name = Path(f).stem
            temp = lib.Pointer([])
            lib.data.load(f,temp)
            playlists.val[name] = temp

lib.music_player = lib.music_player_class()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Catvibes")
        layout = QGridLayout()

        playlistsWidget = QTabWidget()
        for name,playlist in playlists.val.items():
            playlistsWidget.addTab(playlistWidget(playlist), name)

        layout.addWidget(playlistsWidget,0,0)


        self.timer = QTimer()
        self.timer.start(100)
        self.timer.timeout.connect(partial(self.check_player,self.timer.interval() / 1000))


        centralWidget = QWidget()
        centralWidget.setLayout(layout)
        self.setCentralWidget(centralWidget)
    
    def check_player(self,seconds):
        lib.music_player.query(seconds)


class songWidget(QWidget):
    def __init__(self, songId:str):
        super().__init__()
        self.id = songId
        layout = QHBoxLayout()
        songinfo = song_data.val[songId]
        url = songinfo["thumbnails"][0]["url"]

        self.Icon = QLabel()
        image = QImage()
        image.loadFromData(requests.get(url).content)
        self.Icon.setPixmap(QPixmap(image))
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
        if lib.music_player.playlist == []:
            lib.music_player.add_list(
                [lib.song_file(song) for song in self.playlist.val]
                )
        lib.music_player.shuffle()
    
    def playsong(self,num):
        lib.music_player.clear_list()
        lib.music_player.add_list(
            [lib.song_file(song) for song in self.playlist.val[num:]]
            )

class playerWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QGridLayout()
        icon = QImage()



app = QApplication(sys.argv)
app.setStyle('kvantum')

window = MainWindow()
window.show()


if __name__ =="__main__":
    try:
        app.exec()
    finally:
        lib.music_player.proc.kill()
        lib.data.save_all()