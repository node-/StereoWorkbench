#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
author: Jacob Kosberg
"""

import os
import time
import cv2

from SaveState import guisave, guirestore
from PyQt4 import QtGui, QtCore, uic
from stereovision.ui_utils import find_files, calibrate_folder
from stereovision.blockmatchers import StereoBM, StereoSGBM
from stereovision.calibration import StereoCalibration
from stereovision.stereo_cameras import CalibratedPair

class MainWindow(QtGui.QMainWindow):
    def __init__(self, pair, leftCam, rightCam, worker):
        QtGui.QMainWindow.__init__(self)
        self.ui = uic.loadUi('workbench_ui/main.ui', self)
        self.setWindowTitle("Stereo Workbench")
        self.setFixedSize(self.size())
        self.settings = QtCore.QSettings('workbench_ui/main.ini', QtCore.QSettings.IniFormat)
        guirestore(self)
        self.leftCam = leftCam
        self.rightCam = rightCam
        self.pair = pair
        self.worker = worker

        worker.chessboardCount = self.chessboardCountSpinBox.value()
        worker.scale = self.viewportScaleSpinBox.value()
        worker.interval = self.intervalSpinBox.value()

        self.settingsWindows = [CameraSettings(self.pair, leftCam, isLeft=True),
                                CameraSettings(self.pair, rightCam, isLeft=False)]
        self.setInitPaths()

        # Camera Settings
        self.leftSettingsButton.clicked.connect(lambda: self.openSettings(isLeft=True))
        self.rightSettingsButton.clicked.connect(lambda: self.openSettings(isLeft=False))

        # Viewport Scale
        self.viewportScaleSpinBox.valueChanged.connect(
            lambda: self.changeViewportScale(self.viewportScaleSpinBox.value()))
        self.capturePath.textChanged.connect(
            lambda: self.worker.setImagesPath(str(self.capturePath.text())))

        # Capture Image
        self.leftCaptureButton.clicked.connect(lambda: self.worker.captureImage(isLeft=True))
        self.rightCaptureButton.clicked.connect(lambda: self.worker.captureImage(isLeft=False))
        self.bothCaptureButton.clicked.connect(lambda: self.worker.captureBoth())

        # Interval
        self.intervalSpinBox.valueChanged.connect(
            lambda: self.worker.setInterval(self.intervalSpinBox.value()))
        self.intervalEnabled.stateChanged.connect(
            lambda: self.worker.setIntervalEnabled(self.intervalEnabled.isChecked()))

        """ Stereo Tools """
        # Calibration
        self.chessboardCountSpinBox.valueChanged.connect(
            lambda: self.worker.setChessboardCount(self.chessboardCountSpinBox.value()))

        self.chessboardCapturePath.textChanged.connect(
            lambda: self.worker.setChessboardCapturePath(str(self.chessboardCapturePath.text())))
        self.calibrationPath.textChanged.connect(
            lambda: self.worker.setCalibrationPath(str(self.calibrationPath.text())))
        
        self.captureChessboardButton.clicked.connect(lambda: self.worker.setCaptureChessboards(True))
        self.calibrateButton.clicked.connect(lambda: self.worker.calibrate())

        # Rendering
        self.renderButton.clicked.connect(lambda: self.worker.render(
            str(self.leftImagePath.text()),
            str(self.rightImagePath.text()),
            str(self.outputPointCloudPath.text())))


    def setInitPaths(self):
        self.worker.setChessboardCapturePath(str(self.chessboardCapturePath.text()))
        self.worker.setCalibrationPath(str(self.calibrationPath.text()))
        self.worker.setImagesPath(str(self.capturePath.text()))

    def changeViewportScale(self, scale):
        self.worker.setScale(scale)

    def openSettings(self, isLeft):
        self.settingsWindows[0 if isLeft else 1].show()

    def closeEvent(self, event):
        self.worker.running = False
        for window in self.settingsWindows:
            window.closeEvent(event)
        guisave(self)
        event.accept()


class CameraSettings(QtGui.QWidget):
    def __init__(self, pair, cam, isLeft):
        QtGui.QWidget.__init__(self)
        self.ui = uic.loadUi('workbench_ui/parameters.ui', self)
        self.pair = pair
        self.cam = cam
        self.isLeft = isLeft

        self.setWindowTitle(self.getCameraName())
        self.setFixedSize(self.size())

        # wiring sliders and spin boxes
        self.connectObjs((self.brightnessSlider, self.brightnessSpinBox), self.setBrightness)
        self.connectObjs((self.contrastSlider, self.contrastSpinBox), self.setContrast)
        self.connectObjs((self.gainSlider, self.gainSpinBox), self.setGain)
        self.connectObjs((self.exposureSlider, self.exposureSpinBox), self.setExposure)
        self.connectObjs((self.rotationSlider, self.rotationSpinBox), self.setRotation)

        # restore settings
        self.settings = QtCore.QSettings('workbench_ui/parameters'+str(cam)+'.ini', QtCore.QSettings.IniFormat)
        guirestore(self)

    def getCamIndex(self):
        return 0 if self.isLeft else 1

    def getCameraName(self):
        return ("Left" if self.isLeft else "Right") + " Camera"

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
        self.pair.captures[self.getCamIndex()].set(cv2.CAP_PROP_BRIGHTNESS, self.brightnessSpinBox.value())
        self.changedValue()

    def setContrast(self):
        self.pair.captures[self.getCamIndex()].set(cv2.CAP_PROP_CONTRAST, self.contrastSpinBox.value())
        self.changedValue()

    def setGain(self):
        self.pair.captures[self.getCamIndex()].set(cv2.CAP_PROP_GAIN, self.gainSpinBox.value())
        self.changedValue()

    def setExposure(self):
        # the -1 fixes weird off-by-one openCV bug
        self.pair.captures[self.getCamIndex()].set(cv2.CAP_PROP_EXPOSURE, self.exposureSpinBox.value()-1)
        self.changedValue()

    def setRotation(self):
        self.pair.set_rotation(self.isLeft, self.rotationSpinBox.value())
        self.changedValue()

    def changedValue(self):
        #self.pair.show_frames(1)
        pass

    def closeEvent(self, event):
        guisave(self)
        event.accept()


class Worker(QtCore.QThread):

    def __init__(self, pair, scale=80, chessboardCount=30):
        QtCore.QThread.__init__(self)
        self.scale = scale
        self.chessboardCount = chessboardCount
        self.pair = pair
        self.intervalEnabled = False
        self.captureChessboards = False
        self.interval = 60
        self.running = True
        self.chessboardRows = 6
        self.chessboardColumns = 9
        self.chessboardSize = 0.5571 #cm

    def run(self):
        while self.running:
            if self.captureChessboards:
                for i in range(self.chessboardCount):
                    self.captureAndSaveChessboardPair(i)
                    start = time.time()
                    while time.time() < start + 2:
                        self.show_frames()
                self.captureChessboards = False
                
            elif self.intervalEnabled:
                start = time.time()
                while time.time() < start + self.interval:
                    self.show_frames()
                self.captureBoth()
            else:
                self.show_frames()
                
        self.kill()

    def captureAndSaveChessboardPair(self, imgNum, show=True):
        self.verifyPathExists(self.chessboardCapturePath)
        found_chessboard = [False, False]
        while not all(found_chessboard):
            frames = self.pair.get_frames()
            if show:
                self.show_frames()
            for i, frame in enumerate(frames):
                (found_chessboard[i],
                 corners) = cv2.findChessboardCorners(frame,
                 (self.chessboardRows, self.chessboardColumns),
                 flags=cv2.CALIB_CB_FAST_CHECK)

        for side, frame in zip(("left", "right"), frames):
            number_string = str(imgNum + 1).zfill(len(str(self.chessboardCount)))
            filename = "{}_{}.png".format(side, number_string)
            filepath = os.path.join(self.chessboardCapturePath, filename)
            cv2.imwrite(filepath, frame)
        
    def verifyPathExists(self, path):
        if path in [None, ""]:
            raise ValueError("Path cannot be empty!")

    def show_frames(self):
        self.pair.show_frames(wait=1, scale=self.scale)

    def captureBoth(self):
        for i in [0, 1]:
            self.captureImage(i)

    def captureImage(self, isLeft):
        images = self.pair.get_frames()
        cv2.imwrite(self.getImageFilepath(self.imagesPath, cam), images[0 if isLeft else 1])

    def calibrate(self):
        # stereovision's silly architecture requires argparse. here's a workaround
        args = lambda: None
        args.rows = self.chessboardRows
        args.columns = self.chessboardColumns
        args.square_size = self.chessboardSize
        args.show_chessboards = False
        args.input_files = find_files(self.chessboardCapturePath)
        args.output_folder = self.calibrationPath
        calibrate_folder(args)
        print "Calibrated!"

    def render(self, leftImagePath, rightImagePath, outputPath):
        image_pair = [cv2.imread(os.path.abspath(image)) for image in [leftImagePath, rightImagePath]]
        use_stereobm = False
        if use_stereobm:
            block_matcher = StereoBM()
            blockmatcher.load_settings(args.bm_settings)
        else:
            block_matcher = StereoSGBM()

        camera_pair = CalibratedPair(None,
                                    StereoCalibration(input_folder=self.calibrationPath),
                                    block_matcher)
        rectified_pair = camera_pair.calibration.rectify(image_pair)

        points = camera_pair.get_point_cloud(rectified_pair)
        points = points.filter_infinity()
        points.write_ply(outputPath)
        print "Rendered! output: " + outputPath

    def getImageFilepath(self, path, cam):
        self.verifyPathExists(path)
        date_string = time.strftime("%Y-%m-%d_%H-%M-%S")
        fileName = ["Left", "Right"][cam] + "_"  + date_string + ".png"
        return os.path.join(path, fileName)

    def setIntervalEnabled(self, enabled):
        self.intervalEnabled = enabled

    def setChessboardCount(self, count):
        self.chessboardCount = count

    def setChessboardCapturePath(self, path):
        self.chessboardCapturePath = path

    def setCalibrationPath(self, path):
        self.calibrationPath = path

    def setCaptureChessboards(self, isCapture):
        self.captureChessboards = isCapture

    def setImagesPath(self, path):
        self.imagesPath = path

    def setScale(self, scale):
        self.scale = scale

    def setInterval(self, interval):
        self.interval = interval

    def kill(self):
        self.running = False
        self.terminate()
