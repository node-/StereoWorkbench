#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
author: Jacob Kosberg
"""

import signal
import sys
import argparse
import os
import time
import cv2

from SaveState import guisave, guirestore
from transformed_stereo_cameras import StereoPair
from PyQt4 import QtGui, QtCore, uic

class CameraSettings(QtGui.QWidget):
    def __init__(self, pair, cam):
        QtGui.QWidget.__init__(self)
        uic.loadUi('workbench_ui/parameters.ui', self)
        self.setWindowTitle(self.getCameraName(cam))
        self.setFixedSize(self.size())
        self.pair = pair
        self.cam = cam

        # wiring sliders and spin boxes
        self.connectObjs((self.brightnessSlider, self.brightnessSpinBox), self.setBrightness)
        self.connectObjs((self.contrastSlider, self.contrastSpinBox), self.setContrast)
        self.connectObjs((self.gainSlider, self.gainSpinBox), self.setGain)
        self.connectObjs((self.exposureSlider, self.exposureSpinBox), self.setExposure)

        # get init values
        self.setInitValue(self.brightnessSpinBox, cv2.CAP_PROP_BRIGHTNESS, self.setBrightness)
        self.setInitValue(self.contrastSpinBox, cv2.CAP_PROP_CONTRAST, self.setContrast)
        self.setInitValue(self.gainSpinBox, cv2.CAP_PROP_GAIN, self.setGain)
        self.setInitValue(self.exposureSpinBox, cv2.CAP_PROP_EXPOSURE, self.setExposure)

    def getCameraName(self, cam):
        return ["Left", "Right"][cam] + " Camera"

    def setInitValue(self, obj, cvProperty, setFunction):
        obj.setValue(self.pair.captures[self.cam].get(cvProperty))
        setFunction()

    def connectObjs(self, objTuple, setFunction):
        first, second = objTuple
        first.valueChanged.connect(
            lambda: self.changeValue(first, second, setFunction))
        second.valueChanged.connect(
            lambda: self.changeValue(second, first, setFunction))

    def changeValue(self, fromObj, toObj, setFunction):
        toObj.setValue(fromObj.value())
        setFunction()

    def setBrightness(self):
        self.pair.captures[self.cam].set(cv2.CAP_PROP_BRIGHTNESS, self.brightnessSpinBox.value())
        self.changedValue()

    def setContrast(self):
        self.pair.captures[self.cam].set(cv2.CAP_PROP_CONTRAST, self.contrastSpinBox.value())
        self.changedValue()

    def setGain(self):
        self.pair.captures[self.cam].set(cv2.CAP_PROP_GAIN, self.gainSpinBox.value())
        self.changedValue()

    def setExposure(self):
        # the -1 fixes weird off-by-one openCV bug
        self.pair.captures[self.cam].set(cv2.CAP_PROP_EXPOSURE, self.exposureSpinBox.value()-1)
        self.changedValue()

    def changedValue(self):
        #self.pair.show_frames(1)
        pass

class MainWindow(QtGui.QMainWindow):
    def __init__(self, pair, leftCam, rightCam, worker):
        QtGui.QMainWindow.__init__(self)
        self. ui = uic.loadUi('workbench_ui/main.ui', self)
        self.setWindowTitle("Stereo Workbench")
        self.setFixedSize(self.size())
        self.settings = QtCore.QSettings('saved.ini', QtCore.QSettings.IniFormat)
        guirestore(self)
        self.leftCam = leftCam
        self.rightCam = rightCam
        self.pair = pair
        self.worker = worker
        self.settingsWindows = [CameraSettings(self.pair, leftCam), CameraSettings(self.pair, rightCam)]

        # Camera Settings
        self.leftSettingsButton.clicked.connect(lambda: self.openSettings(leftCam))
        self.rightSettingsButton.clicked.connect(lambda: self.openSettings(rightCam))

        # Viewport Scale
        self.viewportScaleSpinBox.valueChanged.connect(
            lambda: self.changeViewportScale(self.viewportScaleSpinBox.value()))
        self.capturePath.textChanged.connect(
            lambda: self.worker.setDirPath(str(self.capturePath.text())))

        # Capture Image
        self.leftCaptureButton.clicked.connect(lambda: self.worker.captureImage(self.leftCam))
        self.rightCaptureButton.clicked.connect(lambda: self.worker.captureImage(self.rightCam))
        self.bothCaptureButton.clicked.connect(lambda: self.worker.captureBoth())

        # Interval
        self.intervalSpinBox.valueChanged.connect(
            lambda: self.worker.setInterval(self.intervalSpinBox.value()))
        self.intervalEnabled.stateChanged.connect(
            lambda: self.worker.setIntervalEnabled(self.intervalEnabled.isChecked()))

    def changeViewportScale(self, scale):
        self.worker.setScale(scale)

    def openSettings(self, cam):
        self.settingsWindows[cam].show()

    def closeEvent(self, event):
        self.worker.running = False
        guisave(self)
        event.accept()

class Worker(QtCore.QThread):
    def __init__(self, pair):
        QtCore.QThread.__init__(self)
        self.pair = pair
        self.scale = 80
        self.intervalEnabled = False
        self.dirPath = ""
        self.interval = 60
        self.running = True

    def run(self):
        while self.running:
            if self.intervalEnabled:
                start = time.time()
                while time.time() < start + self.interval:
                    self.show_frames()
                self.captureBoth()
            else:
                self.show_frames()
                
        self.kill()

    def show_frames(self):
        self.pair.show_frames(wait=1, scale=self.scale)

    def captureBoth(self):
        for i in [0, 1]:
            self.captureImage(i)

    def captureImage(self, cam):
        images = self.pair.get_frames()
        cv2.imwrite(self.getImageFilepath(self.dirPath, cam), images[cam])

    def getImageFilepath(self, dirPath, cam):
        if dirPath in [None, ""]:
            raise ValueError("Path cannot be empty!")
        camName = ["Left", "Right"]
        date_string = time.strftime("%Y-%m-%d_%H-%M-%S")
        fileName = camName[cam] + "_"  + date_string + ".png"
        return os.path.join(dirPath, fileName)

    def setIntervalEnabled(self, enabled):
        self.intervalEnabled = enabled

    def setDirPath(self, dirPath):
        self.dirPath = dirPath

    def setScale(self, scale):
        self.scale = scale

    def setInterval(self, interval):
        self.interval = interval

    def kill(self):
        self.running = False
        self.terminate()

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

