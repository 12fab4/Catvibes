import curses
import ytmusicapi
from pathlib import Path
import json
import os
import subprocess as sp
import signal
import random



yt = ytmusicapi.YTMusic()



# placeholders for directories
main_dir: Path
song_dir: Path
data_dir: Path
playlist_dir: Path

class pointer:
    """a bad implementation of pointers. use .val to retreive or set value"""
    def __init__(self,val):
        self.val = val



playlists = pointer({})
song_data = pointer({})
config = pointer({})

class display_tab:
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
        self.line = (self.line - 1) % self.maxlines
    

    def down(self):
        self.line = (self.line + 1) % self.maxlines
    

    def disp(self):
        pass

    def handle_key(self, key:str):
        if key in self.keyhandler.keys():
            self.keyhandler[key]()

class playlist_tab(display_tab):
    """a tab for simply interacting with playlists"""

    def __init__(self, window, title:str, playlist:pointer, linestart:int = 0):
        super().__init__(window, title, linestart=linestart)
        self.playlist = playlist
        self.maxlines = len(playlist.val)
        self.on_key("f", self.add_song)
        self.on_key("p", self.play_song)
        self.on_key("\n",self.play_song)
        self.on_key("d", self.remove_song)
        self.on_key(" ", self.play_or_pause)
        self.on_key("r", self.shuffle)
        self.on_key("n", self.next)
        self.on_key("b", self.prev) 

    def disp(self):
        start = 0
        end = 0
        playlist_view = []
        self.maxy, self.maxx = self.screen.getmaxyx()
        if self.maxy > len(self.playlist.val):  # is the window big enough for all songs
            start = 0
            end = len(self.playlist.val)
            playlist_view = self.playlist.val
        else:                                      # if not, then
            half = int(self.maxy / 2)
            if self.line < half:
                start = 0
                end = self.maxy
            elif self.line > len(self.playlist.val) - half:
                end = len(self.playlist.val)
                start = end - self.maxy
            else:
                start = self.line - half
                end = self.line + half - 1
            
            playlist_view = self.playlist.val[start:end]

        for i,song in enumerate(playlist_view):
            delline(self.screen, i)
            if i == self.line - start:
                self.screen.addstr(i,0, song_string(song_data.val[song]),curses.A_REVERSE)
            else:
                self.screen.addstr(i,0, song_string(song_data.val[song]))
        if self.maxy - 1 > len(self.playlist.val):
            delline(self.screen, len(self.playlist.val))
        self.screen.refresh()
    
    def add_song(self):
        result = search(self.screen)
        if result != None:
            self.playlist.val.append(result["videoId"])
            self.line = len(self.playlist.val) - 1
        self.maxlines = len(self.playlist.val)
        self.disp()
    
    def remove_song(self):
        del self.playlist.val[self.line]
        self.maxlines = len(self.playlist.val)
        self.line = self.line % self.maxlines
    
    def play_song(self):
        global music_player
        music_player.add_list([song_file(self.playlist.val[i]) for i in range(self.line, self.maxlines)])
    
    def shuffle(self):
        global music_player
        if music_player.playlist == []:
            music_player.add_list([song_file(self.playlist.val[i]) for i in range(self.maxlines)])
        music_player.shuffle()
    
    def play_or_pause(self):
        music_player.toggle()
    
    def next(self):
        global music_player
        music_player.next()
    
    def prev(self):
        global music_player
        music_player.prev()

class songs_tab(playlist_tab):
    def __init__(self,screen):
        super().__init__(screen,"Songs", pointer([]))
        self.playlist.val = list(song_data.val.keys())
        self.maxlines = len(self.playlist.val)


class datamanager:
    """a class for saving and loading variables to files"""
    def __init__(self):
        # files[i] and vars[i] belong together
       self.files = []
       self.vars = []   # contains pointers
    
    def load(self, file: Path, to: pointer, default = "{}"):
        """loads and links a file to a variable. if the file is noneexsistent load default and create file"""
        self.create_if_not_exsisting(file, default)
        with open(file,"r") as loaded_file:
            to.val = json.load(loaded_file)
        self.vars.append(to)
        self.files.append(file)

            

    def save(self,var: pointer, file = Path):
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

class music_player:
    """a class for playing files"""
    def __init__(self):
        self.playlist:list = []
        self.counter:int = -1
        self.proc = sp.Popen("echo")
        self.playing:bool = False
    
    def play(self,file:Path):
        self.proc.kill()
        self.proc = sp.Popen(["ffplay", "-v", "0", "-nodisp", "-autoexit", file])
        self.playing = True
    
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
    
    def query(self):
        if self.proc.poll() != None:
            if self.counter < len(self.playlist) - 1:
                self.counter += 1
                self.play(self.playlist[self.counter])
    
    def shuffle(self):
        random.shuffle(self.playlist)
        self.counter = 0
        self.play(self.playlist[self.counter])
    
    def next(self):
        self.counter = (self.counter + 1) % len(self.playlist)
        self.play(self.playlist[self.counter])

    def prev(self):
        self.counter = (self.counter - 1) % len(self.playlist)
        self.play(self.playlist[self.counter])



music_player = music_player()

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
        except:
            if key == "\x1b":
                key = 0
                break
    for i in range(maxy-len(choices),maxy):
        delline(screen, i+1)
    screen.refresh()
    return key - 1

def search(screen):
    """asks and searches for a song on youtube and returns a corresponding song_info dict"""
    search = inputstr(screen, "Search Song: ")
    if search == None:
        return
    try:
        results = yt.search(search, filter="songs")
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
        if key == "KEY_BACKSPACE":
            text = text[:-1]
        elif key == "\x1b":
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
    request = sp.run(["yt-dlp", "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0", "--embed-thumbnail", "--embed-metadata", "-o", f"{song_dir}/{song_id}.mp3", f"https://www.youtube.com/watch?v={song_id}"],capture_output=True)
    song_data.val[song_info["videoId"]] = song_info
    with open(data_dir.joinpath("data"),"r+") as data_file:
        data_file.write(json.dumps(song_data.val))

def play_song(id:str):
    """plays a song by its title in song_data"""
    global music_player
    music_player.play(f"{song_dir}/{id}.mp3")

def song_file(id:str) -> Path:
    """returns the Path to a song by id"""
    return Path(f"{song_dir}/{id}.mp3")

def song_string(song_info:dict) -> str:
    """returns a string representation for an song_info dict according to config"""
    string = config.val["songstring"]
    string = string.replace("TITLE",song_info["title"])
    string = string.replace("ARTIST",song_info["artists"][0]["name"])
    string = string.replace("LENGHT",song_info["duration"])
    return string

def getmax(screen) -> tuple[int, int]:
    """returns the bottom most corner of the screen"""
    maxy, maxx = screen.getmaxyx()
    return maxy - 1, maxx - 1