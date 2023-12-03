import ytmusicapi
from ytmusicapi import YTMusic
import subprocess as sp
import os
from pathlib import Path
import curses
import json
import catvibes_lib as lib
import shutil

workdir = Path.cwd()
default_config_location = workdir.joinpath("config")
config_location = Path.home().joinpath(".config/Catvibes/config")
if not Path.is_file(config_location):
    shutil.copy2(default_config_location, config_location)

data = lib.datamanager()

config:lib.pointer = lib.config
data.load(config_location,config)

lib.main_dir = Path.home().joinpath(config.val["maindirectory"])
lib.song_dir = lib.main_dir.joinpath("songs")
lib.data_dir = lib.main_dir.joinpath("data")
lib.playlist_dir = lib.main_dir.joinpath("playlists")

playlists:lib.pointer = lib.playlists
song_data:lib.pointer = lib.song_data




data.load(lib.data_dir.joinpath("data"), song_data,{})                   # loads the song db

data.create_if_not_exsisting(lib.playlist_dir.joinpath("favorites"),[])  # creates a default favorites playlist

with os.scandir(lib.playlist_dir) as files:                # handels import of playlists (favorites is playlists)
    for f in files:
        with open(f,"r") as loaded_file:
            name = loaded_file.name[loaded_file.name.rfind("/")+1:]
            temp = lib.pointer([])
            data.load(f,temp)
            playlists.val[name] = temp



def ui(screen):
    """the main function running the UI"""
    lib.screen = screen
    lib.maxx, lib.maxy = curses.COLS - 1, curses.LINES - 1
    curses.curs_set(0)

    tabs = [lib.playlist_tab(name,playlist) for name,playlist in playlists.val.items()]
    tab = 0

    def tabbar():
        """draws the tabbar"""
        cursor = 0
        for t in tabs:
            if tabs[tab] == t:
                screen.addstr(0,cursor,t.title,curses.A_REVERSE)
            else:
                screen.addstr(0,cursor,t.title)
            cursor += len(t.title)+1
    
    tabbar()
    tabs[tab].disp()
    key = " "
    while not key in ("q", "\x1b"):   # UI mainloop
        if key == "KEY_RIGHT":
            tab = (tab +1) % len(tabs)
            tabbar()
        elif key == "KEY_LEFT":
            tab = (tab -1) % len(tabs)
            tabbar()
        else:
            tabs[tab].handle_key(key)
        tabs[tab].disp()
        key = screen.getkey()


if __name__ =="__main__":
    try:
        curses.wrapper(ui)
    finally:
        lib.music_player.proc.kill()
        curses.curs_set(1)
        data.save_all()
