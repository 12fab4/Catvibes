import curses
import ytmusicapi
from pathlib import Path
import json
import os
import subprocess as sp


screen: object # placeholdervar to be assigned to the standartscreen

yt = ytmusicapi.YTMusic()
music_player = sp.Popen("echo")

# placeholder vars for maxx and maxy values
maxx = int
maxy = int

main_dir = Path.home().joinpath("Musik/Catvibe")
song_dir = main_dir.joinpath("songs")
data_dir = main_dir.joinpath("data")
playlist_dir = main_dir.joinpath("playlists")

class pointer:
    """a bad implementation of pointers. use .val to retreive or set value"""
    def __init__(self,val):
        self.val = val



playlists = pointer({})
song_data = pointer({})
config = pointer({})

class display_tab:
    """# base_class for other tabs"""

    def __init__(self,title:str, linestart:int = 0, minx = None | int, mymaxx:int = None | int, miny = None, mymaxy = None):
        global maxx, maxy
        self.title = title
        self.keyhandler = {}
        self.line = linestart
        self.maxlines = 0
        self.minx = minx or 0
        self.miny = miny or 1
        self.maxx = mymaxx or maxx
        self.maxy = mymaxy or maxy
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

    def __init__(self, title:str, playlist:pointer, linestart:int = 0):
        super().__init__(title, linestart=linestart)
        self.playlist = playlist
        self.maxlines = len(playlist.val)
        self.on_key("f",self.add_song)
        self.on_key("p",self.play_song)
        self.on_key("\n",self.play_song)
        self.on_key("d", self.remove_song)

    def disp(self):
        for i,song in enumerate(self.playlist.val):
            if i == self.line:
                screen.addstr(i+1,0,song_string(song_data.val[song]),curses.A_REVERSE)
            else:
                screen.addstr(i+1,0,song_string(song_data.val[song]))
        screen.refresh()
    
    def add_song(self):
        result = search()
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
        play_song(self.playlist.val[self.line])

class datamanager():
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
            f.write(json.dumps(var.val))
    
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



def delline(y:int, refresh=False):
    screen.move(y,0)
    screen.clrtoeol()
    if refresh:
        screen.refresh()

def inputchoice(choices:list) -> int:
    """displays a number of choices to the user and returns the chosen number. -1 if exited"""
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
                return -1
    for i in range(maxy-len(choices),maxy):
        delline(i+1)
    return key -1

def search():
    """asks and searches for a song on youtube and returns a corresponding song_info dict"""
    search = inputstr("Search Song: ")
    if search == None:
        return
    try:
        results = yt.search(search, filter="songs")
    except Exception as e:
        e = str(e).replace('\n','')
        info(f"Something went wrong searching Youtube: {e}")
        return
    num_results = config.val["results"]
    choices = [song_string(results[i]) for i in range(num_results)]
    chosen = inputchoice(choices)
    if chosen == -1:
        return
    chosen = results[chosen]
    download_song(chosen)
    return chosen

def inputstr(question:str) -> str|None:
    """asks for a simple textinput"""
    delline(maxy)
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
    delline(maxy,True)
    return text

def info(text:str, important = True) -> None:
    screen.addstr(maxy,0,text + " press any key to continue")
    screen.refresh()
    if important:
        screen.getkey()
        delline(maxy,True)

def download_song(song_info:dict) -> None:
    """downloads a song from a song_info dict returned by yt.search()"""
    song_id = song_info["videoId"]
    if Path.is_file(song_dir.joinpath(f"{song_id}")):
        return
    request = sp.run(["yt-dlp", "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0", "-o", f"{song_dir}/{song_id}.mp3", f"https://www.youtube.com/watch?v={song_id}"],capture_output=True)
    song_data.val[song_info["videoId"]] = song_info
    with open(data_dir.joinpath("data"),"r+") as data_file:
        data_file.write(json.dumps(song_data.val))

def play_song(id:str):
    """plays a song by its title in song_data"""
    global music_player
    music_player.kill()
    music_player = sp.Popen(["ffplay", "-v", "0", "-nodisp", "-autoexit", f"{song_dir}/{id}.mp3"])

def song_string(song_info:dict) -> str:
    """returns a string representation for an song_info dict according to config"""
    string = config.val["Songstring"]
    string = string.replace("TITLE",song_info["title"])
    string = string.replace("ARTIST",song_info["artists"][0]["name"])
    string = string.replace("LENGHT",song_info["duration"])
    return string

