import _curses
import curses
import sys
import json
import os
import random
import re
import shutil
import time
import logging
from pathlib import Path
from typing import Any, Callable, Iterable, Literal

import yt_dlp
import ytmusicapi
import vlc

# placeholders for directories
main_dir: Path
song_dir: Path
data_dir: Path
playlist_dir: Path

# a function to circumvent pythons refusal to hash lists (very janky but it works by adding hashvalues of items)


def hash_container(container: Iterable) -> int:
    """hashes a typically unhashable Object (like list or dict by adding all hashes of items)"""
    hashval = 0
    for i in container:
        try:
            hashval += hash(i)
        except TypeError:
            hashval += hash_container(i)
    return hashval


class Pointer:
    """a VERY bad implementation of pointers. use .val to retrieve or set value"""

    def __init__(self, val):
        self.val = val

    def __hash__(self) -> int:
        try:
            return hash(self.val)
        except:
            return hash_container(self.val)


playlists = Pointer({})
song_data = Pointer({})
config = Pointer({})


def init():
    """loads files and config"""
    # global was never intended to be used this way... oh pythongod forgive my sins
    global playlists, song_data, data, main_dir, config, song_dir, data_dir, playlist_dir, music_player, config_location, yt
    # the location where the os stores config (the $HOME/.config most likely)
    config_base = os.environ.get('APPDATA') or \
        os.environ.get('XDG_CONFIG_HOME') or \
        os.path.join(os.environ['HOME'], '.config')
    # the location of the config file
    config_location = Path(config_base).joinpath("Catvibes/config")
    # if the onfig file is nonexistent
    if not Path.is_file(config_location):
        # ensure that there are the required folders
        os.makedirs(config_location.parent, exist_ok=True)
        # the workdir to determine the location of the default config file
        workdir = Path(__file__).parent
        default_config_location = workdir.joinpath("config")
        # and copy the default file to the location of the permanent config
        shutil.copy2(default_config_location, config_location.parent)

    # create a datamanager to store all sorts of files and variables without a hassle
    data = Datamanager()
    # and load the config from the config file (json was not supposed to be used as a user editable config :()
    data.load(config_location, config)
    # retrieve the maindir ($HOME/Musik/Catvibes by default)
    main_dir = Path.home().joinpath(config.val["maindirectory"])
    # songs (the mp3 files) are stored in an /songs subdir
    song_dir = main_dir.joinpath("songs")
    os.makedirs(song_dir, exist_ok=True)
    # the songmetadata db (again in json) is stored in an /data subdir
    data_dir = main_dir.joinpath("data")
    os.makedirs(data_dir, exist_ok=True)
    # the playlists (json lists of strings) are stored in an /songs subdir
    playlist_dir = main_dir.joinpath("playlists")
    os.makedirs(playlist_dir, exist_ok=True)
    # also there is a logfile
    logfile = main_dir.joinpath("catvibes.log")
    # and a previous log for archival purposes
    if Path.is_file(logfile):
        shutil.copy2(logfile, main_dir.joinpath("prev_log.log"))

    # inits the logger
    data.create_if_not_exsisting(logfile, "")
    logging.basicConfig(filename=str(logfile), filemode="w", encoding="utf-8", format="%(asctime)s: %(message)s", datefmt="%m/%d/%y %H:%M:%S", level=logging.INFO)
    # loads the song db
    data.load(data_dir.joinpath("data"), song_data, {})

    # fix for pyinstaller & python-vlc
    if sys.platform.startswith("linux"):
        os.environ["VLC_PLUGIN_PATH"] = "/usr/lib64/vlc/plugins"
    if sys.platform.startswith("win"):
        ffmpeg_path = Path(__file__).parent
        os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)
        os.environ["VLC_PLUGIN_PATH"] = "C:\\Program Files\\VideoLAN\\VLC\\plugins"

    # loads all playlists
    with os.scandir(playlist_dir) as files:
        for f in files:
            name = Path(f).stem
            logging.info(f"loaded playlist {name}")
            temp = Pointer([])
            data.load(Path(f), temp)
            playlists.val[name] = temp
    # creates a musicplayer
    music_player = MusicPlayer()
    # and a YouTube interface
    yt = YTInterface()


class YTInterface:
    """a basic wrapper class around YTMusicapi mainly to prevent errors if no internet connection is available"""

    def __init__(self):
        self.yt = ytmusicapi.YTMusic()
        self.connect()

    def search(self, *args, **kwargs) -> list[dict]:
        """returns dictionaries containing info about songs matching the first argument
            second argument: filter, str "videos" searches YT or "songs" searches YTMusic
        """
        if self.online:
            return self.yt.search(*args, **kwargs)
        else:
            raise self.offline_error

    def get_search_suggestions(self, *args, **kwargs) -> list[str]:
        """returns possible search completions"""
        if self.online:
            return self.yt.get_search_suggestions(*args, **kwargs)
        else:
            raise self.offline_error

    def get_song(self, song_id: str) -> dict:
        """returns metadata about a specific song"""
        if self.online:
            return self.yt.get_song(song_id)
        else:
            raise self.offline_error

    def connect(self):
        """checks connectivity"""
        self.online = True
        try:
            self.yt.search("test")
        except:
            self.online = False

    @property
    def offline_error(self) -> Exception:
        self.connect()
        return Exception("you are offline")


class DisplayTab:
    """# base_class for other tabs of the terminal UI"""

    def __init__(self, window, title: str, linestart: int = 0):
        self.screen = window  # a curses.screen object, where to paint the tab
        self.title: str = title  # the title of the tab
        self.keyhandler: dict[str, Callable] = {}  # a map of key -> function
        self.line: int = linestart  # the preselected line
        self.maxy, self.maxx = self.screen.getmaxyx()  # the dimensions of the screen
        self.on_key("KEY_UP", self.up)
        self.on_key("KEY_DOWN", self.down)

    def on_key(self, key: str, f):
        """registers functions with key strings like KEY_LEFT"""
        self.keyhandler[key] = f

    @property
    def maxlines(self) -> int:
        """the number of lines drawn to interact with"""
        ...

    def up(self):
        """goes one line up"""
        if self.maxlines > 0:
            self.line = (self.line - 1) % self.maxlines

    def down(self):
        """goes one line down"""
        if self.maxlines > 0:
            self.line = (self.line + 1) % self.maxlines

    def handle_key(self, key: str):
        """tries to do actions a defined with on_key()"""
        if key in self.keyhandler:
            self.keyhandler[key]()

    def disp(self):
        """draws the tab"""
        ...


class PlaylistTab(DisplayTab):
    """a tab for simply interacting with playlists"""

    def __init__(self, window, title: str, playlist: Pointer, linestart: int = 0):
        super().__init__(window, title, linestart=linestart)
        self.playlist = playlist  # a pointer of an list[str]
        self.on_key("f", self.add_song)
        self.on_key("p", self.play_playlist)
        self.on_key("a", self.add_song_to_queue)
        self.on_key("d", self.remove_song)
        self.on_key(" ", self.play_or_pause)
        self.on_key("r", self.shuffle)
        self.on_key("n", self.next)
        self.on_key("b", self.prev)

    @property
    def maxlines(self):
        return len(self.playlist.val)

    def disp(self):
        """displays the playlist on the screen"""
        # which song to display at the top
        start = 0
        # which song to display at the bottom
        end = 0

        playlist_view = []
        # adjusts the dimensions to account for possible resizes
        self.maxy, self.maxx = self.screen.getmaxyx()
        # clears the screen
        self.screen.clear()
        if self.maxy > len(self.playlist.val):  # is the window big enough for all songs
            start = 0
            end = len(self.playlist.val)  # the just display all songs
        else:  # if not, then
            half = int(self.maxy / 2)  # the half of the screen
            odd_max: Literal[0, 1] = 0 if half == self.maxy / 2 else 1  # if there are odd numbers of lines on the screen
            if self.line < half:  # if the current line is under half
                start = 0  # just display the playlist from top
                end = self.maxy
            elif self.line > len(self.playlist.val) - half - 1:  # if the current line is in the last half-of-display lines
                end = len(self.playlist.val)  # just display the last lines
                start = end - self.maxy
            else:  # if the current line is somewhere inbetween
                start = self.line - half  # calculate so the current line is displayed in the middle
                end = self.line + half + odd_max

        # the resulting slice of the playlist
        playlist_view = self.playlist.val[start:end]
        # display the slice
        for i, song in enumerate(playlist_view):
            try:
                if i == self.line - start:  # the current line is displayed with a reverse filter
                    addstr(self.screen, i, 0, song_string(song_data.val[song]), curses.A_REVERSE)
                else:  # all other lines not
                    addstr(self.screen, i, 0, song_string(song_data.val[song]))
            except KeyError:  # display a warning if a song is not found
                info(self.screen, f"a song with id {song} was not found. ")
                self.playlist.val.remove(song)
        # actually draws on the screen
        self.screen.refresh()

    def add_song(self):
        """ searches for a song and adds it to the playlist"""
        # gets a song_data dict for a userinput or None if aborted
        result: dict[str, Any] | None = search(self.screen)
        if result is not None:
            # if the song finished downloading add the song to the playlist and display the tab again
            def finished():
                self.playlist.val.append(result["videoId"])
                self.line = len(self.playlist.val) - 1
                self.disp()
            # download the song
            download_song(result, wait=True, on_finished=finished)

    def remove_song(self):
        """removes the selected song from the playlist"""
        del self.playlist.val[self.line]
        if self.maxlines > 0:
            self.line = self.line % self.maxlines

    def play_playlist(self):
        """plays this playlist from the current line  till the end"""
        music_player.clear_list()
        music_player.add_list(
            [song_file(self.playlist.val[i]) for i in range(self.line, self.maxlines)]
        )

    def add_song_to_queue(self):
        """appends the selected song to the queue"""
        music_player.add(song_file(self.playlist.val[self.line]))

    def shuffle(self):
        """plays the playlist from current line in shuffeled order"""
        self.play_playlist()
        music_player.shuffle()

    @staticmethod
    def play_or_pause():
        """ plays / pauses depending on current state"""
        music_player.toggle()

    @staticmethod
    def next():
        """skip to the next song"""
        music_player.next()

    @staticmethod
    def prev():
        """skips to the previous song"""
        music_player.prev()

    def new_playlist(self):
        """creates a new playlist. currently requires restart to list playlist"""
        # gets the name as input or None if aborted
        name: str | None = inputstr(self.screen, "Name of the playlist: ")
        if name is not None:
            # creates a new playlist
            temp = Pointer([])
            data.load(playlist_dir.joinpath(name), temp, default=[])
            playlists.val[name] = temp.val


class SongsTab(PlaylistTab):
    """a tab for all songs"""

    def __init__(self, screen):
        super().__init__(screen, "Songs", Pointer([]))
        self.playlist.val = list(song_data.val.keys())  # the songsoverview works by using all known songs in a list
        self.on_key("d", self.del_song_from_db)  # but removing a song deletes the song completely
        del self.keyhandler["f"]  # finding a song is not supported here

    def del_song_from_db(self):
        """deletes a song from everything"""
        song_id = self.playlist.val[self.line]
        # first the metadata about the song is removed alongside
        try:
            del song_data.val[song_id]
        except IndexError:
            info(self.screen, f"Cannot delete that Song {song_id}. ")
            return
        # then the song is removed from all playlists
        for playlist in playlists.val.values():
            while song_id in playlist:
                playlist.remove(song_id)
        self.disp()

    def disp(self):
        self.playlist.val = list(song_data.val.keys())
        super().disp()


class Datamanager:
    """a class for saving and loading variables to files"""

    def __init__(self):
        # files[i] and vars[i] belong together
        self.files: list[Path] = []
        self.vars: list[Pointer] = []

    def load(self, file: Path, to: Pointer, default: Any = {}):
        """loads and links a file to a variable. if the file is nonexistent load default and create file"""
        self.create_if_not_exsisting(file, default)
        # saves the content of the file in the Pointer
        with open(file, "r") as loaded_file:
            to.val = json.load(loaded_file)
        # remembers the Pointer-file association for later saving purposes
        self.vars.append(to)
        self.files.append(file)

    @staticmethod
    def save(var: Pointer, file=Path):
        """saves a variable to a file"""
        if var.val is not None:
            with open(file, "w") as f:
                f.write(json.dumps(var.val, indent=4))

    def save_all(self):
        """saves all var:file associations"""
        for i in range(len(self.files)):
            var_pointer: Pointer = self.vars[i]
            file: Path = self.files[i]
            self.save(var_pointer, file)
        logging.info("saved all files")

    @staticmethod
    def create_if_not_exsisting(file:Path, content):
        """if the given file doesn't exist, create it with content"""
        if not file.is_file() and not file.is_dir(): # only run if the current file does not exist
            filepath = file.parent
            os.makedirs(filepath, exist_ok=True) # ensure that all relevant folders are in place
            with open(file, "x") as f:      # create file with content
                f.write(json.dumps(content))


class MusicPlayer:
    """a class for playing files"""

    def __init__(self) -> None:
        self.playlist: list[Path] = [] # the list of files to play
        self.counter: int = -1 # current position in the songqueue
        self.proc: vlc.MediaPlayer = vlc.MediaPlayer() # the actual Musicplayer
        self.playing: bool = False # playing or paused

    @property
    def timer(self):
        """returns the progress of the current song"""
        return int(self.proc.get_time() / 1000)

    def play(self, file: Path):
        """play a file"""
        self.proc.set_media(vlc.Media(file))
        self.proc.play()
        self.playing = True

    def pause(self):
        """pauses playback"""
        self.playing = False
        self.proc.pause()

    def continu(self):
        """continues playback (continue is a python keyword so continu)"""
        if self.playlist != []: # ofc this only works if there is a song to continue
            self.playing = True
            self.proc.play()

    def toggle(self):
        """toggles between playing and pausing"""
        if self.playing:
            self.pause()
        else:
            self.continu()

    def add(self, file: Path):
        """adds a song(file) to the queue"""
        self.playlist.append(file)
        if self.counter == -1: # conter == -1 represents there is no song to play
            self.counter = 0
            self.play(self.playlist[0])

    def add_list(self, songs: list[Path]):
        """adds a list of song(files) to the queue"""
        for file in songs:
            self.add(file)

    def clear_list(self):
        """resets the queue"""
        self.playlist = []
        self.counter = -1

    def query(self):
        """updates the Musicplayer -> starts next song if current is finished"""
        if self.proc.get_state() == 6: # get_state() == 6 means the current song is finished
            if self.counter < len(self.playlist) - 1: # if there is a next song to play
                self.counter += 1 # then play the next song
                self.play(self.playlist[self.counter])
            else:
                self.playing = False # else stop playing

    def shuffle(self):
        """randomly shuffles the songqueue"""
        random.shuffle(self.playlist)
        self.counter = 0 # and starts to play the now first song
        self.play(self.playlist[self.counter])

    def next(self):
        """skips the current song if possible (wraps around)"""
        if len(self.playlist) > 0:
            self.counter = (self.counter + 1) % len(self.playlist)
            self.play(self.playlist[self.counter])

    def prev(self):
        """plays the previous song if possible (wraps around)"""
        if len(self.playlist) > 0:
            self.counter = (self.counter - 1) % len(self.playlist)
            self.play(self.playlist[self.counter])

    @property
    def song(self):
        """returns the title of the current playing song or None"""
        if self.playlist != []:
            return self.playlist[self.counter].stem
        return None


class MusicPlayerWithScreen(MusicPlayer):
    """a music player with a curses screen for the terminal UI"""
    def __init__(self, screen):
        super().__init__()
        self.screen = screen # a 1 Line curses.screen object

    def disp(self):
        """displays information about the current song on the screen"""
        self.screen.clear()
        if self.playing: # if there is something to report
            file = self.playlist[self.counter]
            song_id = file.stem
            addstr(self.screen, 0, 0, info_string(song_data.val[song_id], self.timer)) # then print so pretty info about the current song and progress
            self.screen.refresh()

    def query(self):
        """updates the player (plays next song if finished) and disps the lates information"""
        super().query()
        self.disp()

    def play(self, file: Path):
        super().play(file)
        self.disp()


music_player: MusicPlayer  # placeholder for musicplayer
data: Datamanager  # placeholder for Datamanager


def delline(screen, y: int, refresh=False):
    """clears the line y of the provided screen and optionally updates the screen"""
    screen.move(y, 0)
    screen.clrtoeol()
    if refresh:
        screen.refresh()


def inputchoice(screen, choices: list) -> int:
    """displays a number of choices to the user and returns the chosen number. -1 if exited"""
    maxy, _ = getmax(screen)
    # displays all choices with numbers to select
    for i, choice in enumerate(choices):
        delline(screen, maxy - len(choices) + i + 1)
        addstr(screen, maxy - len(choices) + i + 1, 0, f"{i + 1}. {choice}")
    screen.refresh()
    key = -1
    # waits for the user to type in a valid number or press esc to exit
    while key < 1 or key > len(choices):
        key = screen.getkey()
        try:
            key = int(key)
        except ValueError:
            if key == "\x1b": # \x1b is the escape sequence for the Esc key
                key = 0
                break
            key = -1
    # clears all displayed choices
    for i in range(maxy - len(choices), maxy):
        delline(screen, i + 1)
    screen.refresh()
    return key - 1


def search(screen) -> dict[str, Any] | None:
    """asks and searches for a song on YouTube and returns a corresponding song_info dict or None if aborted"""
    # asks the user for a searchquery
    search_str = inputstr(screen, "Search Song: ")
    if search_str is None:
        return
    # searches for the query and informs the user about possible errors
    try:
        results = yt.search(search_str, filter="songs", limit=config.val["results"])
    except Exception as e:
        e = str(e).replace('\n', '')
        info(screen, f"Something went wrong searching Youtube: {e}")
        return

    # presents the user with some pretty choices based on the results of the query
    choice: list[str] = list(map(song_string, results))
    chosen = inputchoice(screen, choices)
    if chosen == -1:
        return
    # returns the metadata dict about the selected song
    chosen = results[chosen]
    return chosen


def inputstr(screen, question: str) -> str | None:
    """asks for a simple textinput"""
    # prints the question at the bottom of the screen
    maxy, _ = getmax(screen)
    delline(screen, maxy)
    addstr(screen, maxy, 0, question)
    screen.refresh()
    # waits for the user to input a string and press enter (also displays the current input)
    text = ""
    key = screen.getkey()
    while key != "\n": # as long as the current key is not enter
        if key == "\x7f":  # backspace
            text = text[:-1]
        elif key == "\x1b":  # escape
            return
        else:
            text += key # add the current pressed key to the input
        # display the current input
        addstr(screen, maxy, len(question), text + "   ")
        screen.refresh()
        # and wait for the next key
        key = screen.getkey()
    # removes everythng about the input
    delline(screen, maxy, True)
    return text


def info(screen, text: str, important=True) -> None:
    """prints a message at the bottom of the screen"""
    maxy, _ = getmax(screen)
    addstr(screen, maxy, 0, text + " press any key to continue")
    screen.refresh()
    if important:
        screen.getkey()
        delline(screen, maxy, True)


def download_song(song_info: dict, on_finished: Callable=lambda: None) -> None:
    """downloads a song from a song_info dict returned by yt.search() and executes some arbitrary code after the download is finished"""
    song_id = song_info["videoId"]

    def save_data(): # if the download is finished
        song_data.val[song_id] = song_info # add the metadata to the songdb
        data.save_all()
        on_finished() # and run additional code

    if Path.is_file(song_dir.joinpath(f"{song_id}.mp3")): # if the file already exists
        save_data() # skip the download
        return


    # generated by cli_to_api.py https://github.com/yt-dlp/yt-dlp/blob/master/devscripts/cli_to_api.py
    yt_dlp_opts = {'extract_flat': 'discard_in_playlist',
                    'final_ext': 'mp3',
                    'format': 'bestaudio/best',
                    'fragment_retries': 10,
                    'ignoreerrors': 'only_download',
                    'outtmpl': {'default': f"{song_dir}/{song_id}.mp3", 'pl_thumbnail': ''},
                    'postprocessors': [{'key': 'FFmpegExtractAudio',
                                        'nopostoverwrites': False,
                                        'preferredcodec': 'mp3',
                                        'preferredquality': '0'},
                                        {'add_chapters': True,
                                        'add_infojson': 'if_exists',
                                        'add_metadata': True,
                                        'key': 'FFmpegMetadata'},
                                        {'already_have_thumbnail': False, 'key': 'EmbedThumbnail'},
                                        {'key': 'FFmpegConcat',
                                        'only_multi_video': True,
                                        'when': 'playlist'}],
                    'retries': 10,
                    'writethumbnail': True}

    # downloads the song with the thumbnail embedded as an mp3 file to the song dir
    with yt_dlp.YoutubeDL(yt_dlp_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={song_id}"])

    save_data()
    logging.info("finished")



def song_file(song_id: str) -> Path:
    """returns the Path to a song by id"""
    return Path(f"{song_dir}/{song_id}.mp3")


def song_string(song_info: dict) -> str:
    """returns a string representation for a song_info dict according to config"""
    string = config.val["songstring"]
    # returns the string specified in the config with ARTIST replaced by the actual artist usw..
    return string_replace(string, song_info)


def info_string(song_info: dict, play_time: float) -> str:
    """returns a string representing the currently playing track"""
    string = config.val["infostring"]

    # eg. CURRENT_TIME -> 3:24
    formatted_time = format_time(int(play_time))
    string = string.replace("CURRENT_TIME", formatted_time)

    # eg. BAR -> ==‣──────
    progress = int(int(play_time) / song_info["duration_seconds"] * config.val["barlenght"])
    bar = "═" * progress + "‣" + "─" * (config.val["barlenght"] - progress - 1)
    string = string.replace("BAR", bar)

    # replaces some more stuff
    return string_replace(string, song_info)


def format_time(seconds: int) -> str:
    """returns a prefix free representation of seconds eg. 3:24 or 1:05:23"""
    # gets a string representation of the seconds
    formatted_time = time.strftime("%H:%M:%S", time.gmtime(seconds))
    # removes the prefix eg 00:03:24 -> 3:24
    prefix = str(re.findall("^[0:]{1,4}", formatted_time)[0])
    formatted_time = formatted_time.replace(prefix, "")
    return formatted_time


def string_replace(string: str, song_info) -> str:
    """replaces varoius KEYs in a string like TITLE with the info in the song_info dict"""
    try:
        string = string.replace("TITLE", song_info["title"])
    except:
        string = string.replace("TITLE", "")

    try:
        string = string.replace("ARTIST", song_info["artists"][0]["name"])
    except:
        string = string.replace("ARTIST", "")

    try:
        string = string.replace("LENGHT", song_info["duration"])
    except:
        string = string.replace("LENGHT", "")
    return string


def getmax(screen) -> tuple[int, int]:
    """returns the bottom most corner of the screen"""
    maxy, maxx = screen.getmaxyx()
    return maxy - 1, maxx - 1


def addstr(screen, y: int, x: int, string: str, params=None) -> None:
    """adds a string to the specified screen at the x,y coordinates"""
    try:
        if params is not None:
            screen.addstr(y, x, string, params)
        else:
            screen.addstr(y, x, string)
    except _curses.error:
        pass  # bad practise but required for smaller windows
