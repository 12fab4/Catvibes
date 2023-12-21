# __main__.py

import sys

from catvibes import catvibes, qt_gui


def main():
    args = [a for a in sys.argv if a.startswith("-")]
    opts = [o for o in sys.argv if not o.startswith("-")]

    if "--gui" in args:
        qt_gui.main()
    else:
        catvibes.main()


if __name__ == "__main__":
    main()
