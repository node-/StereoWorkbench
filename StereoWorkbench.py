#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
author: Jacob Kosberg
"""

import sys
import argparse

from WorkbenchUI import CameraSettings, MainWindow, Worker
from transformed_stereo_cameras import StereoPair
from PyQt4 import QtGui

def main():
    parser = argparse.ArgumentParser(description="UI utility for point cloud reconstruction.")
    parser.add_argument("devices", type=int, nargs=2, help="Device numbers "
                        "for the cameras that should be accessed in order "
                        " (left, right).")
    args = parser.parse_args()

    with StereoPair(args.devices) as pair:
        app = QtGui.QApplication(['Stereo Imaging'])
        thread = Worker(pair)
        thread.start()
        mainWindow = MainWindow(pair, args.devices[0], args.devices[1], thread)
        mainWindow.show()
        sys.exit(app.exec_())



if __name__ == '__main__':
    main()

