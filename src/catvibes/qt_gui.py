from typing import Any, Callable
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
    QTabWidget,
    QLineEdit,
    QCompleter,
    QMenu, QLayout,
    QStyleFactory,
    QStyle,
    QDialog,
    QComboBox
)

from PyQt6.QtGui import (
    QAction,
    QColor,
    QPalette,
    QPixmap,
    QImage,
    QStandardItemModel,
    QStandardItem,
    QCursor,
    QIcon
)

from PyQt6.QtCore import (
    QTimer,
    Qt,
    QSize,
    QThread,
    pyqtSignal
)


import sys
from pathlib import Path
from functools import partial
import eyed3
import requests
import logging

# these imports are written so they work if run as a python module
try:
    from catvibes import catvibes_lib as lib
except ModuleNotFoundError:
    import catvibes_lib as lib  # or as standart script calls

playlists = lib.playlists
song_data = lib.song_data


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()  # required for Qt Widgets
        self.setWindowTitle("Catvibes")

        # the basewindow has a Gridlayout
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # the Musicplayer is exposed as a global var to access the underlying MusicPlayer
        global player
        player = PlayerWidget()
        lib.music_player = player
        layout.addWidget(player, 0, 1)  # and the Windget itself is placed in the 2nd column

        playlists_widget = QTabWidget()  # the overview about the Playlists is a tabWidget

        new_playlist = QWidget()  # this is a placeholder for the add playlist button

        def on_tab_change():  # called if the user switches tabs
            if playlists_widget.currentWidget() != new_playlist:  # on "normal" tabs
                playlists_widget.currentWidget().refresh()  # just update the widget associated with the tab
            else:  # if the + button (to add a playlist) is pressed
                # Display a Dialog with a simple textinput
                dialog = NewPlaylistDialog()
                r = dialog.exec()
                if r == 100:  # returncode of 100 means everythong is fine
                    name = dialog.text.text()  # retreive the inputtext
                    temp = lib.Pointer([])  # create a new playlist with the given name
                    lib.data.load(lib.playlist_dir.joinpath(name), temp, default=[])
                    playlists.val[name] = temp
                    playlists_widget.insertTab(len(playlists.val.keys()), PlaylistWidget(temp), name)  # and add a tab with a Widget for the playlist
                # regardless of success select the last normal tab (as the + tab just contains an empty widget)
                playlists_widget.setCurrentIndex(len(playlists.val.keys()))

        # actually links the previous function with the event
        playlists_widget.currentChanged.connect(on_tab_change)

        # the first tab is an overview about all songs
        playlists_widget.addTab(SongsWidget(), "Songs")
        # then one tab for each playlist is created
        for name, playlist in playlists.val.items():
            widget = PlaylistWidget(playlist)
            playlists_widget.addTab(widget, name)
        # and the last tab is for adding a new playlist
        playlists_widget.addTab(new_playlist, "+")

        # the Playlistoverview is placed in the 1st row, but twice as big as the second (the musicplayer)
        layout.addWidget(playlists_widget, 0, 0)
        layout.setColumnStretch(0, 2)

        # every 100 ms the Musicplayer refreshs and potentially plays the next song
        self.timer = QTimer()
        self.timer.start(100)
        self.timer.timeout.connect(player.query)

        # this places everything in the mainwindow
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)


class SongWidget(QWidget):
    """a Widget to Display a Simple Button with an Cover and Info about a song along with controlls on how to play the song"""
    # IMPORTANT: all button actions should be connected from the owning widget. on its own it does nothing (the widget itself know nothing about its position in a playlist so how could it possibly start playing a playlist from a specific point)

    def __init__(self, song_id: str):
        super().__init__()
        self.id = song_id  # the main identifier of the Song is its ID (eg. sdjgf234bn)
        layout = QHBoxLayout()  # the components are placed on a horizontal line
        # tries to get the metadata about the song
        if song_id not in song_data.val:
            raise IndexError("Song not found")
        songinfo = song_data.val[song_id]

        # the Mainbutton for playing the Song
        self.Button = QPushButton()
        buttonlayout = QHBoxLayout()
        self.Button.setLayout(buttonlayout)
        self.Button.setFixedHeight(80)

        # the songcover is actually a QLabel with an icon
        self.Icon = QLabel()
        self.Icon.setPixmap(song_cover_info(song_id)[0])
        self.Icon.setFixedSize(60, 60)  # of fixed dimensions
        buttonlayout.addWidget(self.Icon)  # and part of the Mainbutton

        # the some Songmetadata (like the Title) are also displayed on the mainbutton
        self.Info = QLabel(lib.string_replace(lib.config.val["songstring_qt"], songinfo))
        self.Info.setMinimumWidth(200)
        self.Info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttonlayout.addWidget(self.Info)

        # there is also a secondary Button for additional purposes
        self.MenuButton = QPushButton()
        self.MenuButton.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_CommandLink))  # with just an Icon
        self.MenuButton.setFixedSize(30, 80)

        # adds the two Buttons to the actual Widget
        layout.addWidget(self.Button)
        layout.addWidget(self.MenuButton)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.setMinimumWidth(300)


class thread(QThread):
    """a wrapper around QThread intended mainly for running a function in a nonblocking way and also execution some othe function on the Main thread if the function finishes"""
    ended = pyqtSignal(object)  # this is the notifier to teel when the function has finished

    def __init__(self, parent: QWidget, func: Callable):
        super().__init__()
        if parent is not None:
            self.setParent(parent)  # this is required to keep the thread in the QT-Mainloop
        self.func = func  # the function to run

    def run(self):
        """runs the provided function and emits the ended signal when the function finishes"""
        return_val = self.func()
        self.ended.emit(return_val)  # signals should return something so we pass the returnvalue of the function


class PlaylistWidget(QWidget):
    """a Widget to Display an Overview of Songs in a Playlist with some basic controlls"""
    minimumwidth = 350

    def __init__(self, playlist: lib.Pointer) -> None:
        super().__init__()
        self.playlist = playlist  # the main information is all about the playlist
        self.playlisthash = 0  # there to detect changes of the playlist

        layout = QGridLayout()

        # a button intended for playing the whole playlist in a random order
        shuffle = QPushButton("Shuffle")
        shuffle.clicked.connect(self.shuffle)
        layout.addWidget(shuffle, 0, 0)

        # a button intended for playing the whole playlist in order
        play = QPushButton("Play")
        play.clicked.connect(partial(self.play_from_song, 0))  # on press it plays the playlist from position 0 (the first song)
        layout.addWidget(play, 0, 1)

        # a textinput for searching for songs
        self.search = QLineEdit()
        self.search.textChanged.connect(self.search_suggest)  # whenever the user changes something offer autocompletions
        self.search.returnPressed.connect(self.find_song)  # when the user presses enter, search for the query
        # set up autocompletion for the searchbox
        self.searchresults = QStandardItemModel()
        completion = QCompleter(self.searchresults, self)
        completion.setModelSorting(QCompleter.ModelSorting.CaseInsensitivelySortedModel)
        completion.setCompletionMode(QCompleter.CompletionMode.InlineCompletion)
        self.search.setCompleter(completion)
        layout.addWidget(self.search, 0, 2)  # add the searchbox next to the two buttons

        # a dropdown menu for selection where to search for the query (YT or YTMusic)
        self.searchtype = QComboBox()
        self.searchtype.addItem("songs")  # YTMusic
        self.searchtype.addItem("videos")  # YT
        self.searchtype.setEditable(False)  # so the user cant type something but only select the provided actions
        layout.addWidget(self.searchtype, 0, 3)

        # the actual Widget for displaying the Playlist
        self.playlistarea = QScrollArea()  # it is scrollable
        self.playlistarea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # but only vertical
        self.playlistarea.setWidgetResizable(True)
        self.playlistbox = QWidget()  # the widget that is scrolled just acts as a container
        self.playlistarea.setWidget(self.playlistbox)
        self.playlistlayout = QVBoxLayout()  # for a vertical stack of songwidgets
        self.playlistbox.setLayout(self.playlistlayout)

        # the playlistview is added in the 2nd row
        layout.addWidget(self.playlistarea, 1, 0, 2, 0)

        # displays everything and ensures some minimus space
        self.setLayout(layout)
        self.setMinimumWidth(self.minimumwidth)
        self.setMinimumHeight(400)

    def search_suggest(self, text: str):
        """updates the searchsuggestions for the searchbox based on its contents"""
        if len(text) > 3:  # only offer completions after 4 input chars
            self.searchresults.clear()  # delete previous suggestions
            if lib.yt.online:
                completions = lib.yt.get_search_suggestions(text)  # and request new ones from YTMusicapi
                self.searchresults.appendRow([QStandardItem(val) for val in completions])

    def find_song(self):
        """initiates the download of a new song (called when enter is pressed in the search box)"""
        if lib.yt.online:
            def on_finished():  # called when the download finished
                self.playlist.val.append(song_info["videoId"])  # add song to the playlist
                self.playlistlayout.addWidget(self.nth_songwidget(len(self.playlist.val) - 1))  # and a corresponding widget
                self.playlisthash = lib.hash_container(self.playlist.val)  # set the playlisthash to avoid a rebuild of the entire playlist

            # get potential matches
            song_infos: list[dict[str, Any]] = lib.yt.search(self.search.text(), self.searchtype.currentText(), limit=lib.config.val["results"])
            # show a dialog window with the potential matches
            dialog = ChooseSongDialog(song_infos)
            r = dialog.exec()  # the returncode is < 100 for serveral errors
            if r >= 100:           # but returncode >= 100 means the r-100th song was chosen
                song_info = song_infos[r - 100]  # get metadata of specific song
                th = thread(self, lambda: lib.download_song(song_info))  # download via a QThread (this is important because one cant modify a QWidet from a different thread)
                th.ended.connect(on_finished)  # and run the finished function on the Mainthread when the download has finished
                th.start()

    def shuffle(self):
        """plays the entire playlist in a random order"""
        files: list[Path] = [lib.song_file(song) for song in self.playlist.val]  # a list of all files the playlist contains
        if set(player.playlist) != set(files):  # checks if an other playlist is currently played (in any order)
            player.clear_list()  # if yes then play this playlist
            player.add_list(files)
        player.shuffle()  # and ofc shuffle randomly

    def play_from_song(self, num: int):
        """plays the playlist from the n-th song till the end"""
        player.clear_list()
        player.add_list(
            [lib.song_file(song) for song in self.playlist.val[num:]]
        )

    def refresh(self) -> None:
        """populates the playlist with songwidgets to represent the current state of the playlist"""
        if self.playlisthash != lib.hash_container(self.playlist.val):  # as it takes some time only run it if there are changes
            self.playlisthash = lib.hash_container(self.playlist.val)  # save the last state when the widget was refreshed
            clear_layout(self.playlistlayout)  # clear the current layout
            for i, val in enumerate(self.playlist.val):
                try:
                    self.playlistlayout.addWidget(self.nth_songwidget(i))  # and add a songwidget for each song (with buttonactions connected)
                except (IndexError):
                    pass

    def nth_songwidget(self, n: int) -> SongWidget:
        """generates a songwidget for the n-th song in the playlist and connects actions to all buttons"""
        wid = SongWidget(self.playlist.val[n])  # generates the Songwidget (without actions)
        wid.Button.clicked.connect(partial(self.play_from_song, n))  # clicking on the main Button starts playing the playlist from that point
        menu = QMenu()  # we create a popup menu
        append: QAction = menu.addAction("append")  # with these actions
        remove: QAction = menu.addAction("remove")
        insert: QAction = menu.addAction("play next")
        append.triggered.connect(partial(player.add, lib.song_file(self.playlist.val[n])))  # append adds a song to the queue
        remove.triggered.connect(partial(self.remove_song, n))  # remove deletes the song from the playlist

        def insert_song(n):
            """inserts a song to be played after the current"""
            song: Path = lib.song_file(self.playlist.val[n])  # gets the required songfile
            if player.playlist != []:  # if there is a current playing track
                player.playlist.insert(player.counter + 1, song)  # insert the song at the position after the current playing song
            else:
                player.play(song)  # else just play the song
        insert.triggered.connect(partial(insert_song, n))  # inset plays the song next

        def contextmenu() -> None:
            """shows the defined popup menu under the Cursor"""
            menu.popup(QCursor.pos())

        # the secondary Button opens the popup Menu
        wid.MenuButton.clicked.connect(contextmenu)
        return wid

    def remove_song(self, n):
        """removes a song from the playlist"""
        del self.playlist.val[n]
        self.refresh()


class ChooseSongDialog(QDialog):
    """a Dialog Window to offer several songs in a pretty way and return the index of the chosen one"""

    def __init__(self, songs: list[dict[str, Any]]):
        super().__init__()
        self.setWindowTitle("Choose Song")
        layout = QVBoxLayout()
        for i, song in enumerate(songs):  # for each songmetadata
            wid = QPushButton(song["title"] + " - " + song["artists"][0]["name"])  # create a Button with TITLE - ARTIST label
            # each button returns the index of the song it represents
            wid.clicked.connect(partial(self.done, i + 100))   # + 100 to tell apart from codes like 0 which is also emitted on window closing

            # and give each Button a covericon
            url: str = song["thumbnails"][0]["url"]  # get the location of a thumbnail from the metadata
            image = QImage()
            image.loadFromData(requests.get(url).content)
            pixmap = QPixmap(image)
            wid.setIcon(QIcon(pixmap))

            # ensure the dialog has enough space
            wid.setFixedHeight(80)
            wid.setMinimumWidth(500)
            wid.setIconSize(QSize(60, 60))
            wid.setStyleSheet("font-size: 20px")  # this is how one modifies the textsize of QLabels
            layout.addWidget(wid)  # add each Button to the Dialog
        self.setLayout(layout)
        self.setMinimumSize(550, len(songs)*80+60)


class NewPlaylistDialog(QDialog):
    """ a simple dialog that asks for the name of a new playlist"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enter Name")
        layout = QVBoxLayout() # has a very simple layout
        self.text = QLineEdit() # containing only an textinput
        self.text.returnPressed.connect(partial(self.done, 100)) # if pressing enter the dialog closes and returns the sucess code 100
        layout.addWidget(self.text)
        self.setLayout(layout)
        self.setFixedSize(300, 60)


class SongsWidget(PlaylistWidget):
    """a widget to show all songs"""
    def __init__(self) -> None:
        playlist = lib.Pointer(list(song_data.val.keys())) # the playlist for this widget is just all songs in the db
        super().__init__(playlist)

        # one cannot add a song only to the db -> remove junk only made for the playlist
        self.layout().removeWidget(self.search) 
        self.layout().removeWidget(self.searchtype)
        self.search.setParent(None)
        self.searchtype.setParent(None)

    def remove_song(self, n):
        """deletes a song from the db"""
        del song_data.val[self.playlist.val[n]]
        super().remove_song(n)

    def refresh(self):
        # adjusted to accout for the playlist being generated as all songs in the db
        if self.playlisthash != hash(song_data): # check if playlist is up to date
            self.playlist = lib.Pointer(list(song_data.val.keys())) # if not gets the new playlist
            self.playlisthash = 0 # ensures that the refresh regenerates the layout
            super().refresh()
            self.playlisthash = hash(song_data) # remember the state of the playlist


class PlayerWidget(QWidget, lib.MusicPlayer):
    """a Widget not only providing graphicla information but also acting as an interface for controlling playback"""
    def __init__(self):
        QWidget.__init__(self) # ensures working as a widget
        lib.MusicPlayer.__init__(self) # ensures working as an Interface

        layout = QGridLayout()
        layout.setRowStretch(0, 3) # the first rom is three times higher than others

        # creates an Icon meant to display the cover of the current playing song 
        self.Icon = QLabel()
        layout.addWidget(self.Icon, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        #  a Button with a skip icon that skips the current song
        self.Button_f = QPushButton("")
        self.Button_f.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.Button_f.clicked.connect(self.next)
        self.Button_f.setFixedWidth(80)

        # a button with a previous icon that plays the previous song
        self.Button_b = QPushButton("")
        self.Button_b.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.Button_b.clicked.connect(self.prev)
        self.Button_b.setFixedWidth(80)

        # a Button with an adjusting icon that reflects and toggles the play/pause state 
        self.Button_play = QPushButton("")
        self.Button_play.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.Button_play.clicked.connect(self.toggle)

        # a progress bar displaying the song progress
        self.prog_bar = QProgressBar()

        # a title label to show the songtitle
        self.title = QLabel()
        self.title.setFixedHeight(30)

        layout.addWidget(self.title, 1, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.prog_bar, 2, 0, 1, 3)
        layout.addWidget(self.Button_b, 3, 0)
        layout.addWidget(self.Button_play, 3, 1)
        layout.addWidget(self.Button_f, 3, 2)

        # required for the Background to be filled with the basecolor of the Songcover
        self.setAutoFillBackground(True)
        self.setLayout(layout)

    def toggle(self):
        # adjusted to also toggle the Icon of the play/pause button
        super().toggle()
        if self.playing:
            self.Button_play.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.Button_play.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def get_icon_scale(self) -> int:
        """returns an optimal scale for the songcover"""
        size = self.parent().size()
        h, w = size.height(), size.width()
        return min(h - 150, w - PlaylistWidget.minimumwidth) # either the Windowheight - space for title & buttons or Windowwidth - space for the Playlistwidgets

    def query(self):
        # adjusted to also update the progressbar
        if self.playlist != []:
            super().query()
            song: str | None = self.song
            if song:
                # self.Icon.setPixmap(song_cover_info(song, self.get_icon_scale())[0]) # sets the songcover
                try: # tries to update the progressbar
                    self.prog_bar.setValue(int(self.timer))
                    self.prog_bar.setFormat(f"{lib.format_time(int(self.timer))} - {song_data.val[song]['duration']}")
                except KeyError: # if playing a song not in the db anymore
                    del self.playlist[self.counter] # stop playing the current song
                    self.counter = self.counter % len(self.playlist)
                    self.proc.stop()

    def play(self, file: Path):
        # adjusted to set songcover, background color and title
        super().play(file) # actually play the song

        song = file.stem # gets the songs ID
        self.title.setText(song_data.val[song]['title']) # displays the Title of the song in the corresponding Widget
        self.prog_bar.setRange(0, song_data.val[song]["duration_seconds"]) # and sets the progressbar to the range of the song

        cover, color = song_cover_info(song, self.get_icon_scale()) # retreives info about the current cover
        self.Icon.setPixmap(cover) # displays the cover

        # and fills the background with the basecolor of the cover
        colors = self.palette()
        colors.setColor(QPalette.ColorRole.Window, color)
        self.setPalette(colors)


def song_cover_info(song_id: str, scale=60) -> tuple[QPixmap, QColor]:
    """returns a Icon and the basecolor of the icon of the cover of a specific song"""
    # this works as YTdlp embeds thumbnails into mp3s and YTMusic thumbnails (which are rectangular) contain a quadratic cover infront of a basecolor matching the cover
    file = lib.song_file(song_id) # gets the file for the song
    metadata: eyed3.AudioFile = eyed3.load(file) # reads metadata about the song with eyeD3
    image = QImage.fromData(metadata.tag.images[0].image_data) # reads the thumbnail of the mp3
    color = image.pixelColor(1, 1) # reads the color of the topmost pixel
    width, height = image.width(), image.height()

    image = image.copy(int((width - height) / 2), 0, height, height) # the actual cover is a centere square

    pixmap = QPixmap.fromImage(image) # generate a Pixmap to be used in labels as Icons
    return pixmap.scaledToHeight(scale), color


def clear_layout(layout: QLayout):
    """deletes all Widgets from a layout"""
    for i in reversed(range(layout.count())):
        layout.itemAt(i).widget().setParent(None)


def main(on_start: Callable=lambda: None):
    """initialises the GUI. on_start is a callable and executed right before the mainloop"""
    # creates the QApplication
    app = QApplication(sys.argv)

    # tries to apply the theme specified in the config
    theme = lib.config.val["theme"]
    logging.getLogger().info(f"theme:{theme}, available={QStyleFactory.keys()}")
    if theme in QStyleFactory.keys():
        app.setStyle(theme)
    
    # creates the mainwindow
    window = MainWindow()
    # and runs on_star (used to start playing immediately)
    on_start()

    window.show()
    try: # runs the Qt Mainloop
        app.exec()
    finally: # and stops playing music & saves everything if the window is closed
        player.proc.stop()
        lib.data.save_all()


if __name__ == "__main__":
    main()
