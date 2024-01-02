# __main__.py
import os
import sys
from pathlib import Path
from shutil import copy2, rmtree

try:
    from catvibes import catvibes, qt_gui, catvibes_lib as lib
except ImportError:
    import catvibes, qt_gui, catvibes_lib as lib


def main():
    params = sys.argv[1:]

    lib.init()

    if "-h" in params or "--help" in params:
        print(
            "Catvibes is a Musicplayer using yt-dlp and ytmusicapi\n"
            "Options:\n"
            "    -h / --help: show this help\n"
            "    --clean: delete all songs not in playlists (to save memory)\n"
            "    --reset: completely erases all data\n"
            "    --import [/path/to/file]: imports a playlist from a file and downloads all songs\n"
            "    --gui: launch using a Qt GUI\n"
            "\n"
            "when launched with no Options a curses based UI will be used\n"
        )

    if "--reset" in params:
        if input("do you really want to delete ALL data (type 'yes'): ") == "yes":
            rmtree(lib.main_dir)
            rmtree(lib.config_location.parent)
            return

    if "--clean" in params:
        all_songs = []
        for playlist in lib.playlists.val.values():
            all_songs.extend(playlist.val)
        with os.scandir(lib.song_dir) as files:
            for file in files:
                if Path(file).stem not in all_songs:
                    os.remove(file)

    if "--import" in params:
        try:
            file = Path(params[params.index("--import") + 1])
            assert file.is_file(), "please point to a file"
        except:
            print("could not find file. try specifying it with eg. --import /path/to/file")
            return
        playlist = lib.Pointer([])
        lib.data.load(file, playlist)
        assert type(playlist.val) == list, "Not a valid playlistfile"
        assert all([type(x) == str for x in playlist.val]), "Not a valid playlistfile"
        copy2(file, lib.playlist_dir)
        for song in playlist.val:
            song_info = lib.yt.get_song(song)["videoDetails"]
            print(f"\rdownloading {song_info['title']}", end = "")
            lib.download_song(song_info ,wait=True)
        lib.playlists.val[file.stem] = playlist

    if "--gui" in params:
        qt_gui.main()
    if params == []:
        catvibes.main()


if __name__ == "__main__":
    main()
