# __main__.py
import logging
import os
import sys
from pathlib import Path
from shutil import copy2, rmtree
from typing import Callable

# these imports are written this way so it works if run as a python module (with python -m catvibes)
try:
    from catvibes import qt_gui, term_ui
    from catvibes import catvibes_lib as lib
except (ImportError, ModuleNotFoundError):
    # but also if the script is run directly
    import term_ui
    import qt_gui
    import catvibes_lib as lib


def main():
    # gets the commandline parameters
    params = sys.argv[1:]

    # initializes the backend and config
    lib.init()

    # the standart help command
    if "-h" in params or "--help" in params:
        print(
            "Catvibes is a Musicplayer using yt-dlp and ytmusicapi\n"
            "Options:\n"
            "    -h / --help: show this help\n"
            "    --clean: delete all songs not in playlists (to save memory)\n"
            "    --reset: completely erases all data\n"
            "    --reset-config: only erase config\n"
            "    --import [/path/to/file]: imports a playlist from a file and downloads all songs\n"
            "    --gui / -g: launch using a Qt GUI\n"
            "    -s / --start [mode]: immediately start playing\n"
            "       mode can be random or r to play all songs shuffled,\n"
            "       start or s to play all songs in order or\n"
            "       a playlistname\n"
            "\n"
            "when launched with no Options a curses based UI will be used\n"
        )
        # important return because if not the musicplayer will run
        return

    # a remove everything option
    if "--reset" in params:
        if input("do you really want to delete ALL data (type 'yes'): ") == "yes":
            rmtree(lib.main_dir)
            rmtree(lib.config_location.parent)
            return

    # only removes the config (and thus resets it on the next run)
    if "--reset-config" in params:
        rmtree(lib.config_location.parent)
        return

    # removes unnecessary files
    if "--clean" in params:
        print("clearing songdir")

        # a list of all songs currently in any playlist
        all_songs: list[str] = []
        for playlist in lib.playlists.val.values():
            all_songs.extend(playlist.val)
        
        # every file in song_dir (where the .mp3s are stored) is checked
        with os.scandir(lib.song_dir) as files:
            for file in files:
                file = Path(file)
                # if the filestem (the name without extension, in this case an UUID like "x4sdfkj5") is not known
                if file.stem not in all_songs:
                    # if metadata about the song is known
                    if file.stem in lib.song_data.val:
                        # print a pretty remove notification
                        print(f"removing {lib.song_data.val[file.stem]['title']}")
                        # and also remove the metadata
                        del lib.song_data.val[file.stem]
                    # if there is no metadata (potentially some download artifacts)
                    else:
                        # just print the name of the file
                        print(f"removing {file}")
                    os.remove(file)
        # every song in song_data -> every song which has metadata
        all_songs_in_db = list(lib.song_data.val.keys())
        for song in all_songs_in_db:
            # if the song is no longer in any playlist
            if song not in all_songs:
                # print a notification
                print(f"removing {lib.song_data.val[song]['title']} from database")
                # and remove metadata
                del lib.song_data.val[song]
        # save the metadata
        lib.data.save_all()
        return

    # an option to point to an playlistfile and add it (with downloading all relevant info)
    if "--import" in params:
        try:
            # the file is the arg after --import
            file = Path(params[params.index("--import") + 1])
        except:
            # hat sogar fancy exceptions
            print("could not find file. try specifying it with eg. --import /path/to/file")
            return
        assert file.is_file(), "please point to a file" # das file sollte auch ein file sein (kein folder)
        # the temporary playlist
        playlist = lib.Pointer([])
        # loads the content of the file to the playlist var
        try:
            lib.data.load(file, playlist)
        except:
            print("Not a valid playlistfile")
            return
        # make sure the loaded playlist is a list[str]
        assert type(playlist.val) == list, "Not a valid playlistfile"
        assert all([type(x) is str for x in playlist.val]), "Not a valid playlistfile"
        # copy the file to the playlist folder
        copy2(file, lib.playlist_dir)
        # downloads each song
        for song in playlist.val:
            song_info = lib.yt.get_song(song)["videoDetails"]
            # also prints the current track to download
            print(f"\rdownloading {song_info['title']}", end="")
            lib.download_song(song_info, wait=True)
            print(" " * (len(song_info['title']) + 13), end="")
        # adds the playlist to the playlists variable
        lib.playlists.val[file.stem] = playlist
        # saves all info
        lib.data.save_all()
        return

    # an option to instantly start playing
    if "--start" in params or "-s" in params:
        # start is a function that is called immediately after everything is run
        global start
        # gets the "mode" to for instant play (eg r for random shuffle or s for ordered)
        try:
            mode = params[params.index("--start") + 1]
        except ValueError:
            mode = params[params.index("-s") + 1]
        # proceed according to mode
        match mode:
            # r -> shuffle all songs
            case "random" | "r":
                def start() -> None:
                    lib.music_player.add_list(list(map(lib.song_file, lib.song_data.val.keys())))
                    lib.music_player.shuffle()
            # s -> play all songs
            case "start" | "s":
                def start() -> None:
                    lib.music_player.add_list(list(map(lib.song_file, lib.song_data.val.keys())))
            # for anything else it is checked if mode matches a playlistname to play (in order)
            case _:
                for playlist in lib.playlists.val.keys():
                    if mode == playlist:
                        def start() -> None:
                            lib.music_player.add_list(list(map(lib.song_file, lib.playlists.val[playlist])))

    # creates a decoy start function
    if 'start' not in globals():
        def start():
            pass

    # the --gui flag determines if a GUi or a terminal based ui is used
    if "--gui" in params or "-g" in params:
        qt_gui.main(start)
    else:
        term_ui.main(start)

# der standart stuff (hier bissl unnötig)
if __name__ == "__main__":
    main()
