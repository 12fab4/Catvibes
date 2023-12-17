import curses
from pathlib import Path
import json
import os
import subprocess as sp
import signal
import random
import time
import re

import ytmusicapi


yt = ytmusicapi.YTMusic()



# placeholders for directories
main_dir: Path
song_dir: Path
data_dir: Path
playlist_dir: Path

class Pointer:
    """a bad implementation of pointers. use .val to retreive or set value"""
    def __init__(self,val):
        self.val = val



playlists = Pointer({})
song_data = Pointer({})
config = Pointer({})

class DisplayTab:
    """# base_class for other tabs"""

    def __init__(self,window,title:str, linestart:int = 0):
        self.screen = window
        self.title = title
        self.keyhandler = {}
        self.line = linestart
        self.maxlines = 0
        self.maxy, self.maxx = self.screen.getmaxyx()
        self.on_key("KEY_UP",self.up)
        self.on_key("KEY_DOWN",self.down)

    def on_key(self,key:str,f):
        """registers functions with key strings like KEY_LEFT"""
        self.keyhandler[key] = f

    def up(self):
        """goes one line up"""
        if self.maxlines > 0:
            self.line = (self.line - 1) % self.maxlines


    def down(self):
        """goes one line down"""
        if self.maxlines > 0:
            self.line = (self.line + 1) % self.maxlines

    def handle_key(self, key:str):
        """tries to do actions a defined with on_key()"""
        if key in self.keyhandler:
            self.keyhandler[key]()

class PlaylistTab(DisplayTab):
    """a tab for simply interacting with playlists"""

    def __init__(self, window, title:str, playlist:Pointer, linestart:int = 0):
        super().__init__(window, title, linestart=linestart)
        self.playlist = playlist
        self.maxlines = len(playlist.val)
        self.on_key("f", self.add_song)
        self.on_key("p", self.play_playlist)
        self.on_key("a", self.add_song_to_queue)
        self.on_key("d", self.remove_song)
        self.on_key(" ", self.play_or_pause)
        self.on_key("r", self.shuffle)
        self.on_key("n", self.next)
        self.on_key("b", self.prev)

    def disp(self):
        """displays the playlist on the screen"""
        start = 0
        end = 0
        playlist_view = []
        self.maxy, self.maxx = self.screen.getmaxyx()
        self.screen.clear()
        if self.maxy > len(self.playlist.val):  # is the window big enough for all songs
            start = 0
            end = len(self.playlist.val)
            playlist_view = self.playlist.val
        else:                                      # if not, then
            half = int(self.maxy / 2)
            odd_max = 0 if half == self.maxy / 2 else 1
            if self.line < half:
                start = 0
                end = self.maxy
            elif self.line > len(self.playlist.val) - half - 1:
                end = len(self.playlist.val)
                start = end - self.maxy
            else:
                start = self.line - half
                end = self.line + half + odd_max

            playlist_view = self.playlist.val[start:end]

        for i,song in enumerate(playlist_view):
            try:
                if i == self.line - start:
                    self.screen.addstr(i,0, song_string(song_data.val[song]),curses.A_REVERSE)
                else:
                    self.screen.addstr(i,0, song_string(song_data.val[song]))
            except KeyError:
                info(self.screen, f"a song with id {song} was not found. ")
                self.playlist.val.remove(song)
        self.screen.refresh()

    def add_song(self):
        """ searches for a song and adds it to the playlist"""
        result = search(self.screen)
        if result is not None:
            self.playlist.val.append(result["videoId"])
            self.line = len(self.playlist.val) - 1
        self.maxlines = len(self.playlist.val)
        self.disp()

    def remove_song(self):
        """removes the selected song from the playlist"""
        del self.playlist.val[self.line]
        self.maxlines = len(self.playlist.val)
        if self.maxlines > 0:
            self.line = self.line % self.maxlines

    def play_playlist(self):
        """plays this playlist from the start"""
        music_player.clear_list()
        music_player.add_list(
            [song_file(self.playlist.val[i]) for i in range(self.line, self.maxlines)]
            )

    def add_song_to_queue(self):
        """appends the selected song to the queue"""
        music_player.add(song_file(self.playlist.val[self.line]))

    def shuffle(self):
        """plays the whole playlist in shuffeled order"""
        self.play_playlist()
        music_player.shuffle()

    def play_or_pause(self):
        """ plays / pauses depending on current state"""
        music_player.toggle()

    def next(self):
        """skip to the next song"""
        music_player.next()

    def prev(self):
        """skips to the previous song"""
        music_player.prev()

    def new_playlist(self):
        """creates a new playlist. currently requires restart to list playlist"""
        name = inputstr(self.screen, "Name of the playlist: ")
        temp = Pointer([])
        data.load(playlist_dir.joinpath(name),temp, default=[])
        playlists.val[name] = temp.val

class SongsTab(PlaylistTab):
    """a tab for all songs"""
    def __init__(self,screen):
        super().__init__(screen,"Songs", Pointer([]))
        self.playlist.val = list(song_data.val.keys())
        self.maxlines = len(self.playlist.val)
        self.on_key("d", self.del_song_from_db)
        del self.keyhandler["f"]

    def del_song_from_db(self):
        """deletes a song from everything"""
        song_id = self.playlist.val[self.line]
        try:
            del song_data.val[song_id]
            del self.playlist.val[self.line]
        except IndexError:
            info(self.screen,f"Cannot delete that Song {song_id}. ")
            return
        for playlist in playlists.val.items():
            while song_id in playlist:
                playlist.remove(song_id)

    def disp(self):
        self.playlist.val = list(song_data.val.keys())
        super().disp()


class datamanager:
    """a class for saving and loading variables to files"""
    def __init__(self):
        # files[i] and vars[i] belong together
        self.files = []
        self.vars = []   # contains pointers
    
    def load(self, file: Path, to: Pointer, default = {}):
        """loads and links a file to a variable. if the file is noneexsistent load default and create file"""
        self.create_if_not_exsisting(file, default)
        with open(file,"r") as loaded_file:
            to.val = json.load(loaded_file)
        self.vars.append(to)
        self.files.append(file)

            

    def save(self,var: Pointer, file = Path):
        """saves a variable to a file"""
        with open(file,"w") as f:
            f.write(json.dumps(var.val,indent=4))
    
    def save_all(self):
        """saves all var:file associations"""
        for i in range(len(self.files)):
            var_pointer = self.vars[i]
            file = self.files[i]
            self.save(var_pointer,file)
    
    def create_if_not_exsisting(self,file,content):
        """if the given file doesnt exist, create it with contet"""
        if not Path.is_file(file):
            filepath = file.parent
            os.makedirs(filepath, exist_ok=True)
            with open(file,"x") as f:
                f.write(json.dumps(content))

class music_player_class:
    """a class for playing files"""
    def __init__(self):
        self.playlist:list = []
        self.counter:int = -1
        self.proc = sp.Popen("echo")
        self.playing:bool = False
        self.timer = 0
    
    def play(self,file:Path):
        self.proc.kill()
        self.proc = sp.Popen(["ffplay", "-v", "0", "-nodisp", "-autoexit", file])
        self.playing = True
        self.timer = 0
    
    def pause(self):
        self.playing = False
        self.proc.send_signal(signal.SIGSTOP)
    
    def continu(self):
        self.playing = True
        self.proc.send_signal(signal.SIGCONT)
    
    def toggle(self):
        if self.playing:
            self.pause()
        else:
            self.continu()
    
    def add(self,file:Path):
        self.playlist.append(file)
        if self.counter == -1:
            self.counter = 0
            self.play(self.playlist[0])
    
    def add_list(self, songs:list[Path]):
        for file in songs:
            self.add(file)
    
    def clear_list(self):
        self.playlist = []
        self.counter = -1
    
    def query(self,seconds: float):
        if self.proc.poll() is not None:
            if self.counter < len(self.playlist) - 1:
                self.counter += 1
                self.play(self.playlist[self.counter])
            else:
                self.playing = False
        else:
            if self.playing:
                self.timer += seconds
    
    def shuffle(self):
        random.shuffle(self.playlist)
        self.counter = 0
        self.play(self.playlist[self.counter])
    
    def next(self):
        if len(self.playlist) > 0:
            self.counter = (self.counter + 1) % len(self.playlist)
            self.play(self.playlist[self.counter])

    def prev(self):
        if len(self.playlist) > 0:
            self.counter = (self.counter - 1) % len(self.playlist)
            self.play(self.playlist[self.counter])


class music_player_with_screen(music_player_class):
    def __init__(self, screen):
        super().__init__()
        self.screen = screen
    
    def disp(self):
        self.screen.clear()
        if self.playing:
            file = self.playlist[self.counter]
            song_id = file.stem
            self.screen.addstr(0,0,info_string(song_data.val[song_id], self.timer))
            self.screen.refresh()
    
    def query(self,seconds):
        super().query(seconds)
        self.disp()
    
    def play(self, file: Path):
        super().play(file)
        self.disp()

music_player: music_player_class # placeholder for musicplayer
data: datamanager          # placeholder for datamanager

def delline(screen, y:int, refresh=False):
    screen.move(y,0)
    screen.clrtoeol()
    if refresh:
        screen.refresh()

def inputchoice(screen, choices:list) -> int:
    """displays a number of choices to the user and returns the chosen number. -1 if exited"""
    maxy, _ = getmax(screen)
    for i,choice in enumerate(choices):
        screen.addstr(maxy-len(choices)+i+1,0,f"{i+1}. {choice}")
    screen.refresh()
    key = -1
    while key < 1 or key > len(choices):
        key = screen.getkey()
        try:
            key = int(key)
        except ValueError:
            if key == "\x1b":
                key = 0
                break
    for i in range(maxy-len(choices),maxy):
        delline(screen, i+1)
    screen.refresh()
    return key - 1

def search(screen):
    """asks and searches for a song on youtube and returns a corresponding song_info dict"""
    search_str = inputstr(screen, "Search Song: ")
    if search_str is None:
        return
    try:
        results = yt.search(search_str, filter="songs", limit = config.val["results"])
    except Exception as e:
        e = str(e).replace('\n','')
        info(screen, f"Something went wrong searching Youtube: {e}")
        return
    num_results = config.val["results"]
    choices = [song_string(results[i]) for i in range(num_results)]
    chosen = inputchoice(screen, choices)
    if chosen == -1:
        return
    chosen = results[chosen]
    download_song(chosen)
    return chosen

def inputstr(screen, question:str) -> str|None:
    """asks for a simple textinput"""
    maxy, _ = getmax(screen)
    delline(screen, maxy)
    screen.addstr(maxy,0,question)
    screen.refresh()
    text = ""
    key = screen.getkey()
    while key != "\n":
        if key == "\x7f": # enter
            text = text[:-1]
        elif key == "\x1b": # escape
            return
        else:
            text += key
        screen.addstr(maxy, len(question), text+"   ")
        screen.refresh()
        key = screen.getkey()
    delline(screen, maxy, True)
    return text

def info(screen, text:str, important = True) -> None:
    """prints a message at the bottom of the screen"""
    maxy, _ = getmax(screen)
    screen.addstr(maxy,0,text + " press any key to continue")
    screen.refresh()
    if important:
        screen.getkey()
        delline(screen, maxy, True)

def download_song(song_info:dict) -> None:
    """downloads a song from a song_info dict returned by yt.search()"""
    song_id = song_info["videoId"]
    if Path.is_file(song_dir.joinpath(f"{song_id}")):
        return
    request = sp.run(
        ["yt-dlp", "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-thumbnail", "--embed-metadata", 
        "-o", f"{song_dir}/{song_id}.mp3", f"https://www.youtube.com/watch?v={song_id}"],
        capture_output=True,
        check = False
        )
    if request.returncode != 0:
        return
    song_data.val[song_info["videoId"]] = song_info
    with open(data_dir.joinpath("data"),"r+") as data_file:
        data_file.write(json.dumps(song_data.val))


def song_file(song_id:str) -> Path:
    """returns the Path to a song by id"""
    return Path(f"{song_dir}/{song_id}.mp3")

def song_string(song_info:dict) -> str:
    """returns a string representation for an song_info dict according to config"""
    string = config.val["songstring"]
    return string_replace(string, song_info)

def info_string(song_info:dict, play_time: float) -> str:
    """returns a string representing the currently playing track"""
    string = config.val["infostring"]

    formatted_time = time.strftime("%H:%M:%S",time.gmtime(int(play_time)))
    prefix = str(re.findall("^[0:]*", formatted_time)[0])
    formatted_time = formatted_time.replace(prefix,"")
    string = string.replace("CURRENT_TIME", formatted_time)

    progress = int(int(play_time) / song_info["duration_seconds"] * config.val["barlenght"])
    bar = "═" * progress + "‣" + "─" * (config.val["barlenght"] - progress - 1)
    string = string.replace("BAR", bar)

    return string_replace(string, song_info)

def string_replace(string: str, song_info) -> str:
    """replaces varoius KEYs in a string like TITLE with the info in the song_info dict"""
    string = string.replace("TITLE",song_info["title"])
    string = string.replace("ARTIST",song_info["artists"][0]["name"])
    string = string.replace("LENGHT",song_info["duration"])
    return string

def getmax(screen) -> tuple[int, int]:
    """returns the bottom most corner of the screen"""
    maxy, maxx = screen.getmaxyx()
    return maxy - 1, maxx - 1