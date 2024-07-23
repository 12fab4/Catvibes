import curses
from typing import Callable

# these imports are run this way so they work if run as a module
try:
    from catvibes import catvibes_lib as lib
except (ModuleNotFoundError, ImportError):
    import catvibes_lib as lib  # or by executing the file directly


def ui(screen, on_start: Callable):
    """the main function running the UI"""
    # establishes a empty base screen
    screen.clear()
    screen.refresh()
    maxy, maxx = screen.getmaxyx()
    maxy, maxx = maxy - 1, maxx - 1
    curses.curs_set(0)
    curses.use_default_colors()

    # first value is space from top, second from bottom to reserve for UI elements like the tabbar and the musicplayer
    y_restrictions = (2, 1)

    playlist_screen = screen.derwin(maxy - sum(y_restrictions), maxx, y_restrictions[0], 0)  # reserves space for the playlists
    music_player_screen = screen.derwin(maxy, 0)  # and for the musicplayer

    # a list of all tabs to display (initially with an overwiev of all songs)
    tabs: list[lib.DisplayTab] = [lib.SongsTab(playlist_screen)]
    # and then with a tab for each pplaylistfile
    tabs.extend(
        [lib.PlaylistTab(playlist_screen, name, playlist) for name, playlist in playlists.val.items()]
    )
    tab = 0  # the selected tab

    lib.music_player = lib.MusicPlayerWithScreen(music_player_screen)

    def tabbar():
        """draws the tabbar and seperator lines"""
        cursor = 0  # where the cursor is currently placed
        for t in tabs:  # draw every tab
            if tabs[tab] == t:
                lib.addstr(screen, 0, cursor, t.title, curses.A_REVERSE)  # and the selected tab is highlighted
            else:
                lib.addstr(screen, 0, cursor, t.title)
            cursor += len(t.title) + 4
            if t != tabs[-1]:
                lib.addstr(screen, 0, cursor - 2, "│")  # with a seperator between the tabs

        # also draw some horizontal lines to seperate tabbar, the tab itself and the musicplayer
        screen.hline(1, 0, curses.ACS_HLINE, maxx)
        screen.hline(maxy - 1, 0, curses.ACS_HLINE, maxx)

    def resize():
        """handles the event if the window resizes"""
        nonlocal maxx, maxy
        maxy, maxx = screen.getmaxyx()  # adjust the dimensions
        maxy, maxx = maxy - 1, maxx - 1
        playlist_screen.resize(maxy - sum(y_restrictions), maxx)  # adjust subscreens
        playlist_screen.mvwin(y_restrictions[0], 0)
        music_player_screen.resize(1, maxx)
        music_player_screen.mvwin(maxy, 0)

    tabbar()  # show the tabbar
    tabs[tab].disp()  # and the current screen
    key = " "
    on_start()  # run potential on_start code (like auto start playing)
    lib.music_player.toggle()  # is a hack to allow instantplay but should not have negative sideeffects
    while key not in ("q", "\x1b"):  # UI mainloop (exitable wit q or Esc)
        if key == "KEY_RIGHT":  # with <- and -> go to the adjacend tabs
            tab = (tab + 1) % len(tabs)
        elif key == "KEY_LEFT":
            tab = (tab - 1) % len(tabs)
        elif key == "l":  # l creates a new playlist
            # asks for the name of the playlist
            name = lib.inputstr(playlist_screen, "Name of the playlist: ")
            if name is not None:
                # creates the new playlist and a corresponding file
                temp = lib.Pointer([])
                lib.data.load(lib.playlist_dir.joinpath(name), temp, default=[])
                playlists.val[name] = temp
                # and adds a new tab
                tabs.append(lib.PlaylistTab(playlist_screen, name, temp))
        else:  # all other key presses are passed down to the tab to handle accordingly
            tabs[tab].handle_key(key)
        tabs[tab].disp()

        screen.timeout(100)

        # check for windowchanges
        resize()
        tabbar()

        # waits for the next keypress but periodically refreshes the screen and musicplayer
        key = -1
        while key == -1:
            resize()
            try:
                key = screen.getkey()
            except curses.error:
                key = -1
            lib.music_player.query()
        screen.timeout(-1)


def main(on_start: Callable = lambda: None):
    """initialises the terminal UI. on_start is executed right before the mainloop"""
    global config, playlists, song_data

    config = lib.config
    playlists = lib.playlists
    song_data = lib.song_data

    try:
        curses.wrapper(ui, on_start)  # runs the mainloop
    finally:
        lib.music_player.proc.stop()  # stops the music
        curses.curs_set(1)  # makes the cursor visible again (for further terminal using purposes)
        lib.data.save_all()  # saves everything


if __name__ == "__main__":
    main()
