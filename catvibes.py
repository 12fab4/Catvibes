import os
from pathlib import Path
import curses
import shutil

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

# creates a default favorites playlist
lib.data.create_if_not_exsisting(lib.playlist_dir.joinpath("favorites"),[])

# handels import of playlists (favorites is playlists)
with os.scandir(lib.playlist_dir) as files:
    for f in files:
        with open(f,"r") as loaded_file:
            name = Path(f).stem
            temp = lib.Pointer([])
            lib.data.load(f,temp)
            playlists.val[name] = temp



def ui(screen):
    """the main function running the UI"""
    screen.clear()
    screen.refresh()
    maxy, maxx = screen.getmaxyx()
    maxy, maxx = maxy - 1, maxx - 1
    curses.curs_set(0)
    curses.use_default_colors()

    # first value is space from top, second from bottom
    y_restrictions = (2,1)
    playlist_screen = screen.derwin(maxy - sum(y_restrictions), maxx, y_restrictions[0], 0)
    music_player_screen = screen.derwin(maxy,0)

    tabs = [lib.SongsTab(playlist_screen)]
    tabs.extend(
        [lib.PlaylistTab(playlist_screen,name,playlist) for name,playlist in playlists.val.items()]
        )
    tab = 0

    lib.music_player = lib.music_player_class(music_player_screen)


    def tabbar():
        """draws the tabbar and seperator lines"""
        cursor = 0
        for t in tabs:
            if tabs[tab] == t:
                screen.addstr(0,cursor,t.title,curses.A_REVERSE)
            else:
                screen.addstr(0,cursor,t.title)
            cursor += len(t.title)+4
            if t != tabs[-1]:
                screen.addstr(0,cursor - 2 ,"|")

        screen.hline(1,0,"-", maxx)
        screen.hline(maxy - 1,0,"-", maxx)

    def resize():
        nonlocal maxx, maxy
        maxy, maxx = screen.getmaxyx()
        maxy, maxx = maxy - 1, maxx - 1
        playlist_screen.resize(maxy - sum(y_restrictions), maxx)
        music_player_screen.resize(1,maxx)
        music_player_screen.mvwin(maxy,0)


    tabbar()
    tabs[tab].disp()
    key = " "
    while key not in ("q", "\x1b"):   # UI mainloop
        if key == "KEY_RIGHT":
            tab = (tab +1) % len(tabs)
        elif key == "KEY_LEFT":
            tab = (tab -1) % len(tabs)
        elif key == "l":
            name = lib.inputstr(playlist_screen, "Name of the playlist: ")
            temp = lib.Pointer([])
            lib.data.load(lib.playlist_dir.joinpath(name),temp, default=[])
            playlists.val[name] = temp
            tabs.append(lib.PlaylistTab(playlist_screen, name, temp))
        else:
            tabs[tab].handle_key(key)
        tabs[tab].disp()

        screen.timeout(100)

        resize()
        tabbar()

        key = -1
        while key == -1:
            try:
                key = screen.getkey()
            except curses.error:
                key = -1
            lib.music_player.query(0.1)
        screen.timeout(-1)



if __name__ =="__main__":
    try:
        curses.wrapper(ui)
    finally:
        lib.music_player.proc.kill()
        curses.curs_set(1)
        lib.data.save_all()
