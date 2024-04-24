It is currently not recommended to install catvibes via 

# Catvibes
A simple music player offering not only a terminal based frontend but also a Qt based one.

# GUI
![](https://github.com/12fab4/Catvibes/blob/b3356e4f0aa264cc761f2efe57dec02606d43a51/images/GUI.png)
# CLI
![](https://github.com/12fab4/Catvibes/blob/b3356e4f0aa264cc761f2efe57dec02606d43a51/images/CLI.png)


# Installation

there is a package available on PyPI but just downloading an executable from the releases is recommended for now
```
    pip install Catvibes
```

## Requirements:

in order to play music an existing installation of the [VLC media player](https://www.videolan.org/vlc/) is required.

if the executable is used the following dependencies can be skipped

python and the following packages (will be installed as dependencies with pip):

    pip install ytmusicapi eyed3 yt-dlp PyQt6

it also requires ffmpeg

On linux install ffmpeg which is available on debian-based and arch-based distros and probably already installed

On Windows follow this [tutorial](https://phoenixnap.com/kb/ffmpeg-windows)


# Controls
## GUI:
launch with the --gui flag

## commandline:
f: find a song by typing a searchterm (ideally songname and bandname). Shows 3 results by default (select with the number keys).

esc: terminates searching usw and also exits the program

r: random shuffle, shuffles the queue randomly and adds the whole playlist to the queue when empty

p: play the whole playlist

a: add current song to the playlist

space: play / pause

n: next song

b: previous song

l: create a new playlist

# Building the executables
I use pyinstaller to create the existing executables and the entire buildprocess is automated in the [buildscript](./buildscript)

the buildscript is written in bash (the default shell on nearly all Linux distributions) and also available on Windows via WSL. In order to produce the Windowsexecutables I use [Wine](https://www.winehq.org/) with a default 64-bit Wineprefix which has python and the VLC media player installed (the creation of this prefix has to be done manually as the script wont do it for you). Due to the use of Wine I would not recommend trying to build the executables on Windows (emulating a linux environment emulating a Windows environment sounds pretty slow)