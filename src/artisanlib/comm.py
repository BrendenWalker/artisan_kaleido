#
# ABOUT
# Artisan Device Communication

# LICENSE
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version. It is
# provided for educational purposes and is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
# the GNU General Public License for more details.

# AUTHOR
# Marko Luther, 2023

import sys
import os
import struct
import numpy
import math
import threading
import time as libtime
import platform
import logging
from collections.abc import Callable
from typing import override, Final, Any, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow # pylint: disable=unused-import
    import serial # noqa: F401 # pylint: disable=unused-import
    from Phidget22.Phidget import Phidget # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_voltageoutput import YVoltageOutput # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_currentloopoutput import YCurrentLoopOutput # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_relay import YRelay # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_servo import YServo # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_pwmoutput import YPwmOutput # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_api import YSensor # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_genericsensor import YGenericSensor # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_power import YPower # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_voltage import YVoltage # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_current import YCurrent # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_temperature import YTemperature # type: ignore[import-untyped] # pylint: disable=unused-import
    from yoctopuce.yocto_api import YMeasure # pylint: disable=unused-import

from artisanlib.util import cmd2str, fromCtoFstrict, fromFtoCstrict, hex2int, str2cmd

from PyQt6.QtCore import Qt, QDateTime, QSemaphore, pyqtSlot
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog, QGridLayout, QHBoxLayout, QVBoxLayout,
                             QLabel, QLineEdit,QPushButton, QWidget)
from PyQt6 import sip

from Phidget22.DeviceID import DeviceID # type: ignore[import-untyped]
from Phidget22.Devices.TemperatureSensor import TemperatureSensor as PhidgetTemperatureSensor # type: ignore[import-untyped]
from Phidget22.Devices.HumiditySensor import HumiditySensor as PhidgetHumiditySensor # type: ignore[import-untyped]
from Phidget22.Devices.PressureSensor import PressureSensor as PhidgetPressureSensor # type: ignore[import-untyped]
from Phidget22.Devices.VoltageRatioInput import VoltageRatioInput  # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.VoltageInput import VoltageInput # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.DigitalInput import DigitalInput # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.DigitalOutput import DigitalOutput # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.VoltageOutput import VoltageOutput, VoltageOutputRange # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.RCServo import RCServo # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.Stepper import Stepper # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.CurrentInput import CurrentInput # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.FrequencyCounter import FrequencyCounter # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.DCMotor import DCMotor # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.Devices.BLDCMotor import BLDCMotor # type: ignore[import-untyped] # @UnusedWildImport
from Phidget22.PhidgetException import PhidgetException # type: ignore[import-untyped]

from yoctopuce.yocto_api import YAPI, YRefParam



_log: Final[logging.Logger] = logging.getLogger(__name__)


# maps Artisan thermocouple types (order as listed in the menu; see phidget1048_types) to Phidget thermocouple types
# 1 => k-type (default)
# 2 => j-type
# 3 => e-type
# 4 => t-type
def PHIDGET_THERMOCOUPLE_TYPE(tp:int) -> int:
    from Phidget22.ThermocoupleType import ThermocoupleType # type: ignore[import-untyped]
    if tp == 2:
        return int(ThermocoupleType.THERMOCOUPLE_TYPE_J)
    if tp == 3:
        return int(ThermocoupleType.THERMOCOUPLE_TYPE_E)
    if tp == 4:
        return int(ThermocoupleType.THERMOCOUPLE_TYPE_T)
    return int(ThermocoupleType.THERMOCOUPLE_TYPE_K)

# maps Artisan RTD wire setups (order as listed in the menu; see phidget1200_wireValues) to Phdiget wire setups
# 0 => 2-wire (default)
# 2 => 3-wire
# 3 => 4-wire
def PHIDGET_RTD_WIRE(tp:int) -> int:
    from Phidget22.RTDWireSetup import RTDWireSetup # type: ignore[import-untyped]
    if tp == 1:
        return int(RTDWireSetup.RTD_WIRE_SETUP_3WIRE)
    if tp == 2:
        return int(RTDWireSetup.RTD_WIRE_SETUP_4WIRE)
    return int(RTDWireSetup.RTD_WIRE_SETUP_2WIRE)

# maps Artisan RTD types (order as listed in the menu; see phidget1200_formulaValues) to Phdiget RTD types
# 0 => PT100 3850 (default)
# 2 => PT100 3920
# 3 => PT1000 3850
# 4 => PT1000 3920
def PHIDGET_RTD_TYPE(tp:int) -> int:
    from Phidget22.RTDType import RTDType # type: ignore[import-untyped]
    if tp == 1:
        return int(RTDType.RTD_TYPE_PT100_3920)
    if tp == 2:
        return int(RTDType.RTD_TYPE_PT1000_3850)
    if tp == 3:
        return int(RTDType.RTD_TYPE_PT1000_3920)
    return int(RTDType.RTD_TYPE_PT100_3850)

# maps Artisan gain values (see phidget1046_gainValues) to Phidgets gain values
# defaults to no gain (BRIDGE_GAIN_1)
# not supported:
#   2x Amplification => BRIDGE_GAIN_2
#   4x Amplification => BRIDGE_GAIN_4
def PHIDGET_GAIN_VALUE(gv:int) -> int:
    from Phidget22.BridgeGain import BridgeGain as BG # type: ignore[import-untyped] # @UnusedImport
    if gv == 2:
        return int(BG.BRIDGE_GAIN_8) # 8x Amplification
    if gv == 3:
        return int(BG.BRIDGE_GAIN_16) # 16x Amplification
    if gv == 4:
        return int(BG.BRIDGE_GAIN_32) # 32x Amplification
    if gv == 5:
        return int(BG.BRIDGE_GAIN_64) # 64x Amplification
    if gv == 6:
        return int(BG.BRIDGE_GAIN_128) # 128x Amplification
    return int(BG.BRIDGE_GAIN_1) # no gain

class YoctoThread(threading.Thread):
    def __init__(self) -> None:
        self._stopevent = threading.Event()
        threading.Thread.__init__(self)

    @override
    def run(self) -> None:
        errmsg = YRefParam()
        while not self._stopevent.is_set():
            YAPI.UpdateDeviceList(errmsg)  # traps plug/unplug events
            YAPI.Sleep(500, errmsg)  # traps others events

    @override
    def join(self, timeout:float|None = None) -> None:
        self._stopevent.set()
        threading.Thread.join(self, timeout)



#########################################################################
#############  NONE DEVICE DIALOG #######################################
#########################################################################

#inputs temperature
class nonedevDlg(QDialog):

    __slots__ = ['etEdit','btEdit','ETbox','okButton','cancelButton'] # save some memory by using slots

    def __init__(self, parent:QWidget, aw:'ApplicationWindow') -> None:
        super().__init__(parent)

        self.aw = aw

        self.setWindowTitle(QApplication.translate('Form Caption','Manual Temperature Logger'))
        if len(self.aw.qmc.timex):
            if self.aw.qmc.manuallogETflag:
                etval = str(int(round(aw.qmc.temp1[-1])))
            else:
                etval = '0'
            btval = str(int(round(aw.qmc.temp2[-1])))
        else:
            etval = '0'
            btval = '0'
        self.etEdit = QLineEdit(etval)
        btlabel = QLabel(QApplication.translate('Label', 'BT'))
        self.btEdit = QLineEdit(btval)
        self.etEdit.setValidator(QIntValidator(0, 1000, self.etEdit))
        self.btEdit.setValidator(QIntValidator(0, 1000, self.btEdit))
        self.btEdit.setFocus()
        self.ETbox = QCheckBox(QApplication.translate('CheckBox','ET'))
        if self.aw.qmc.manuallogETflag:
            self.ETbox.setChecked(True)
        else:
            self.ETbox.setChecked(False)
            self.etEdit.setVisible(False)
        self.ETbox.stateChanged.connect(self.changemanuallogETflag)
        self.okButton = QPushButton(QApplication.translate('Button','OK'))
        self.cancelButton = QPushButton(QApplication.translate('Button','Cancel'))
        self.cancelButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.okButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)
        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.cancelButton)
        buttonLayout.addWidget(self.okButton)
        grid = QGridLayout()
        grid.addWidget(self.ETbox,0,0)
        grid.addWidget(self.etEdit,0,1)
        grid.addWidget(btlabel,1,0)
        grid.addWidget(self.btEdit,1,1)
        mainLayout = QVBoxLayout()
        mainLayout.addLayout(grid)
        mainLayout.addStretch()
        mainLayout.addLayout(buttonLayout)
        self.setLayout(mainLayout)

    @pyqtSlot(int)
    def changemanuallogETflag(self, _:int) -> None:
        if self.ETbox.isChecked():
            self.aw.qmc.manuallogETflag = 1
            self.etEdit.setVisible(True)
            self.etEdit.setFocus()
        else:
            self.aw.qmc.manuallogETflag = 0
            self.etEdit.setVisible(False)
            self.btEdit.setFocus()


###########################################################################################
##################### SERIAL PORT #########################################################
###########################################################################################

class serialport:
    """ this class handles the communications with all the devices"""

    __slots__ = ['aw', 'platf', 'default_comport', 'comport','baudrate','bytesize','parity','stopbits','timeout','SP','COMsemaphore', \
        'PhidgetTemperatureSensor','Phidget1048values','Phidget1048lastvalues','Phidget1048semaphores',\
        'PhidgetIRSensor','PhidgetIRSensorIC','Phidget1045values','Phidget1045lastvalue','Phidget1045tempIRavg',\
        'Phidget1045semaphore','PhidgetBridgeSensor','Phidget1046values','Phidget1046lastvalues','Phidget1046semaphores',\
        'PhidgetIO','PhidgetIOvalues','PhidgetIOlastvalues','PhidgetIOsemaphores','PhidgetDigitalOut',\
        'PhidgetDigitalOutLastPWM','PhidgetDigitalOutLastToggle','PhidgetDigitalOutHub','PhidgetDigitalOutLastPWMhub',\
        'PhidgetDigitalOutLastToggleHub','PhidgetAnalogOut','PhidgetDCMotor','PhidgetRCServo','PhidgetStepperMotor',\
        'YOCTOlibImported','YOCTOsensor','YOCTOchan1','YOCTOchan2','YOCTOtempIRavg','YOCTOvalues','YOCTOlastvalues','YOCTOsemaphores',\
        'YOCTOthread','YOCTOvoltageOutputs','YOCTOcurrentOutputs','YOCTOrelays','YOCTOservos','YOCTOpwmOutputs',\
        'controlETpid','readBTpid','useModbusPort','showFujiLCDs','arduinoETChannel','arduinoBTChannel','arduinoATChannel',\
        'ArduinoIsInitialized','ArduinoFILT','R1','devicefunctionlist','externalprogram',\
        'externaloutprogram','externaloutprogramFlag','PhidgetHUMtemp','PhidgetHUMhum','PhidgetPREpre','TMP1000temp']

    def __init__(self, aw:'ApplicationWindow') -> None:

        self.aw = aw

        self.platf = platform.system()

        #default initial settings. They are changed by settingsload() at initiation of program according to the device chosen
        self.default_comport:Final[str] = 'COM4'
        self.comport:str = self.default_comport      #NOTE: this string should not be translated. It is an argument for lib Pyserial
        self.baudrate:int = 9600
        self.bytesize:int = 8
        self.parity:str = 'O'
        self.stopbits:int = 1
        self.timeout:float = 0.4
        #serial port for ET/BT
        import serial  # @UnusedImport
        self.SP:serial.Serial = serial.Serial()
        #used only in devices that also control the roaster like PIDs or Arduino (possible to receive asynchrous commands from GUI commands and thread sample()).
        self.COMsemaphore:QSemaphore = QSemaphore(1)
        ##### SPECIAL METER FLAGS ########
        #stores the Phidget 1048 TemperatureSensor object (None if not initialized)
        self.PhidgetTemperatureSensor:list[PhidgetTemperatureSensor]|None = None # type:ignore[no-any-unimported] # either None or a list containing one PhidgetTemperatureSensor() object per channel
        self.Phidget1048values:list[list[tuple[float,float]]] = [[],[],[],[]] # the values for each of the 4 channels as (value, time) tuples gathered by registered change triggers in the last period
        self.Phidget1048lastvalues:list[float] = [-1.0]*4 # the last async values returned
        self.Phidget1048semaphores:list[QSemaphore] = [QSemaphore(1),QSemaphore(1),QSemaphore(1),QSemaphore(1)] # semaphores protecting the access to self.Phidget1048values per channel
        # list of (serial,port) tuples filled on attaching the corresponding main device and consumed on attaching the other channel pairs
        #stores the Phidget 1045 TemperatureSensor object (None if not initialized)
        self.PhidgetIRSensor:PhidgetTemperatureSensor|None = None # type:ignore[no-any-unimported]
        self.PhidgetIRSensorIC:PhidgetTemperatureSensor|None = None # type:ignore[no-any-unimported]
        self.Phidget1045values:list[tuple[float, float]] = [] # async values of the one channel
        self.Phidget1045lastvalue:float = -1
        self.Phidget1045tempIRavg:float|None = None
        self.Phidget1045semaphore:QSemaphore = QSemaphore(1) # semaphore protecting the access to self.Phidget1045values per channel
        #stores the Phidget BridgeSensor object (None if not initialized)
        self.PhidgetBridgeSensor:list[VoltageRatioInput]|None = None # type:ignore[no-any-unimported]
        self.Phidget1046values:list[list[tuple[float,float]]] = [[],[],[],[]] # the values for each of the 4 channels, as (value, time) tuples, gathered by registered change triggers in the last period
        self.Phidget1046lastvalues:list[float] = [-1.0]*4 # the last async values returned
        self.Phidget1046semaphores:list[QSemaphore] = [QSemaphore(1),QSemaphore(1),QSemaphore(1),QSemaphore(1)] # semaphores protecting the access to self.Phidget1046values per channel
        #stores the Phidget IO object (None if not initialized)
        self.PhidgetIO:list[DigitalInput|VoltageInput|VoltageRatioInput|FrequencyCounter|CurrentInput]|None = None # type:ignore[no-any-unimported]
        self.PhidgetIOvalues:list[list[tuple[float,float]]] = [[], [], [], [], [], [], [], []] # the values gathered by registered change triggers for channel 0 - 8
        self.PhidgetIOlastvalues:list[float] = [-1.0]*8 # the values gathered by registered change triggers
        self.PhidgetIOsemaphores:list[QSemaphore] = [QSemaphore(1),QSemaphore(1),QSemaphore(1),QSemaphore(1)] # semaphores protecting the access to self.Phidget1048values per channel
        #stores the Phidget Digital Output PMW objects (None if not initialized)
        self.PhidgetDigitalOut:dict[str|None, list[Phidget]] = {} # type:ignore[no-any-unimported] # a dict associating out serials with lists of channels
        self.PhidgetDigitalOutLastPWM:dict[str|None, list[float]] = {} # a dict associating out serials with the list of last PWMs per channel
        self.PhidgetDigitalOutLastToggle:dict[str|None, list[float|None]] = {} # a dict associating out serials with the list of last 'PWM'-toggles per channel; if not None, channel was last toggled OFF and the value indicates that lastPWM on switching OFF
        self.PhidgetDigitalOutHub:dict[str|None, list[Phidget]] = {} # type:ignore[no-any-unimported] # a dict associating hub serials with lists of channels
        self.PhidgetDigitalOutLastPWMhub:dict[str|None, list[float]] = {} # a dict associating hub serials with the list of last PWMs per port of the hub
        self.PhidgetDigitalOutLastToggleHub:dict[str|None, list[float|None]] = {} # a dict associating hub serials with the list of last toggles per port of the hub; if not None, channel was last toggled OFF and the value indicates that lastPWM on switching OFF
        #store the Phidget Analog Output objects
        self.PhidgetAnalogOut:dict[str|None, list[Phidget]] = {} # type:ignore[no-any-unimported] # a dict associating serials with lists of channels
        #store the servo objects
        self.PhidgetRCServo:dict[str|None, list[Phidget]] = {} # type:ignore[no-any-unimported] # a dict associating serials with lists of channels
        #store the Phidget StepperMotor objects
        self.PhidgetStepperMotor:dict[str|None, list[Phidget]] = {} # type:ignore[no-any-unimported] # a dict associating serials with lists of channels
        #store the Phidget DCMotor objects
        self.PhidgetDCMotor:dict[str|None, list[Phidget]] = {} # type:ignore[no-any-unimported] # a dict associating serials with lists of channels
        # Phidget Ambient Sensor Channels
        self.PhidgetHUMtemp:PhidgetTemperatureSensor|None = None # type:ignore[no-any-unimported]
        self.PhidgetHUMhum:PhidgetHumiditySensor|None = None     # type:ignore[no-any-unimported]
        self.PhidgetPREpre:PhidgetPressureSensor|None = None     # type:ignore[no-any-unimported]
        self.TMP1000temp:PhidgetTemperatureSensor|None = None    # type:ignore[no-any-unimported]
        #Yoctopuce channels
        self.YOCTOlibImported:bool = False # ensure that the YOCTOlib is only imported once
        self.YOCTOsensor:YSensor|None = None # type:ignore[no-any-unimported]
        self.YOCTOchan1:YSensor|None = None  # type:ignore[no-any-unimported]
        self.YOCTOchan2:YSensor|None = None  # type:ignore[no-any-unimported]
        self.YOCTOtempIRavg:float|None = None # averages IR module temperature channel to eliminate noise

        self.YOCTOvalues:list[list[tuple[float,float]]] = [[],[]] # the values for each of the 2 channels gathered by registered change triggers in the last period
        self.YOCTOlastvalues:list[float] = [-1.0]*2 # the last async values returned
        self.YOCTOsemaphores:list[QSemaphore] = [QSemaphore(1),QSemaphore(1)] # semaphores protecting the access to YOCTO per channel
        self.YOCTOthread:YoctoThread|None = None

        self.YOCTOvoltageOutputs:list[YVoltageOutput] = [] # type:ignore[no-any-unimported]
        self.YOCTOcurrentOutputs:list[YCurrentLoopOutput] = [] # type:ignore[no-any-unimported]
        self.YOCTOrelays:list[YRelay] = [] # type:ignore[no-any-unimported]
        self.YOCTOservos:list[YServo] = [] # type:ignore[no-any-unimported]
        self.YOCTOpwmOutputs:list[YPwmOutput] = [] # type:ignore[no-any-unimported]

        #select PID type that controls the roaster.
        # Reads/Controls ET
        self.controlETpid:list[int] = [0,1]        # index 0: type of pid: 0 = FujiPXG, 1 = FujiPXR3, 2 = DTA, 3 = not used, 4 = PXF
#                                                  # index 1: RS485 unitID: Can be changed in device menu.
        # Reads BT
        self.readBTpid:list[int] = [1,2]           # index 0: type of pid: 0 = FujiPXG, 1 = FujiPXR3, 2 = None, 3 = DTA, 4 = PXF
#                                                  # index 1: RS485 unitID. Can be changed in device menu.
        # Reuse Modbus-meter port
        self.useModbusPort:bool = False
        self.showFujiLCDs:bool = True
        #Initialization for ARDUINO and TC4 meter (kept so settings load does not AttributeError)
        self.arduinoETChannel:str = '1'
        self.arduinoBTChannel:str = '2'
        self.arduinoATChannel = 'None' # the channel the Ambient Temperature of the Arduino TC4 is reported as (this value will overwrite the corresponding real channel)
        self.ArduinoIsInitialized = 0
        self.ArduinoFILT = [70,70,70,70] # Arduino Filter settings per channel in %
        self.R1:Any = None
        #list of functions calls to read temperature for devices.
        # Device IDs 0..206 must remain the same length. Unused IDs map to DUMMY.
        # Keep-set: 18 NONE, 22 piddutycycle, 25 virtual, 50 DUMMY,
        # 90 slider_01, 91 slider_23, 138 Kaleido_BTET, 139 Kaleido_SVAT,
        # 140 Kaleido_DrumAH, 141 Kaleido_HeaterFan, 177 pidPtermIterm, 178 pidDtermError
        self.devicefunctionlist:list[Callable[..., tuple[float,float,float]]] = [self.DUMMY] * 207
        self.devicefunctionlist[18] = self.NONE
        self.devicefunctionlist[22] = self.piddutycycle
        self.devicefunctionlist[25] = self.virtual
        self.devicefunctionlist[90] = self.slider_01
        self.devicefunctionlist[91] = self.slider_23
        self.devicefunctionlist[138] = self.Kaleido_BTET
        self.devicefunctionlist[139] = self.Kaleido_SVAT
        self.devicefunctionlist[140] = self.Kaleido_DrumAH
        self.devicefunctionlist[141] = self.Kaleido_HeaterFan
        self.devicefunctionlist[177] = self.pidPtermIterm
        self.devicefunctionlist[178] = self.pidDtermError

        self.devicefunctionlist[19] = self.ARDUINOTC4
        self.devicefunctionlist[28] = self.ARDUINOTC4_34
        self.devicefunctionlist[32] = self.ARDUINOTC4_56
        self.devicefunctionlist[34] = self.PHIDGET1048
        self.devicefunctionlist[35] = self.PHIDGET1048_34
        self.devicefunctionlist[36] = self.PHIDGET1048_AT
        self.devicefunctionlist[37] = self.PHIDGET1046
        self.devicefunctionlist[38] = self.PHIDGET1046_34
        self.devicefunctionlist[40] = self.PHIDGET1018
        self.devicefunctionlist[41] = self.PHIDGET1018_34
        self.devicefunctionlist[42] = self.PHIDGET1018_56
        self.devicefunctionlist[43] = self.PHIDGET1018_78
        self.devicefunctionlist[44] = self.ARDUINOTC4_78
        self.devicefunctionlist[45] = self.YOCTO_thermo
        self.devicefunctionlist[46] = self.YOCTO_pt100
        self.devicefunctionlist[47] = self.PHIDGET1045
        self.devicefunctionlist[52] = self.PHIDGET1051
        self.devicefunctionlist[58] = self.PHIDGET_TMP1101
        self.devicefunctionlist[59] = self.PHIDGET_TMP1101_34
        self.devicefunctionlist[60] = self.PHIDGET_TMP1101_AT
        self.devicefunctionlist[61] = self.PHIDGET_TMP1100
        self.devicefunctionlist[62] = self.PHIDGET1011
        self.devicefunctionlist[63] = self.PHIDGET_HUB0000
        self.devicefunctionlist[64] = self.PHIDGET_HUB0000_34
        self.devicefunctionlist[65] = self.PHIDGET_HUB0000_56
        self.devicefunctionlist[68] = self.PHIDGET_TMP1200
        self.devicefunctionlist[69] = self.PHIDGET1018_D
        self.devicefunctionlist[70] = self.PHIDGET1018_D_34
        self.devicefunctionlist[71] = self.PHIDGET1018_D_56
        self.devicefunctionlist[72] = self.PHIDGET1018_D_78
        self.devicefunctionlist[73] = self.PHIDGET1011_D
        self.devicefunctionlist[74] = self.PHIDGET_HUB0000_D
        self.devicefunctionlist[75] = self.PHIDGET_HUB0000_D_34
        self.devicefunctionlist[76] = self.PHIDGET_HUB0000_D_56
        self.devicefunctionlist[95] = self.PHIDGET_DAQ1400_CURRENT
        self.devicefunctionlist[96] = self.PHIDGET_DAQ1400_FREQUENCY
        self.devicefunctionlist[97] = self.PHIDGET_DAQ1400_DIGITAL
        self.devicefunctionlist[98] = self.PHIDGET_DAQ1400_VOLTAGE
        self.devicefunctionlist[100] = self.YOCTO_IR
        self.devicefunctionlist[106] = self.PHIDGET_HUB0000_0
        self.devicefunctionlist[107] = self.PHIDGET_HUB0000_D_0
        self.devicefunctionlist[108] = self.Yocto_4_20mA_Rx
        self.devicefunctionlist[114] = self.PHIDGET_TMP1200_2
        self.devicefunctionlist[120] = self.Yocto_0_10V_Rx
        self.devicefunctionlist[121] = self.Yocto_milliVolt_Rx
        self.devicefunctionlist[122] = self.Yocto_Serial
        self.devicefunctionlist[123] = self.PHIDGET_VCP1000
        self.devicefunctionlist[124] = self.PHIDGET_VCP1001
        self.devicefunctionlist[125] = self.PHIDGET_VCP1002
        self.devicefunctionlist[129] = self.Yocto_Power
        self.devicefunctionlist[130] = self.Yocto_Energy
        self.devicefunctionlist[131] = self.Yocto_Voltage
        self.devicefunctionlist[132] = self.Yocto_Current
        self.devicefunctionlist[133] = self.Yocto_Sensor
        self.devicefunctionlist[137] = self.PHIDGET_DAQ1500
        self.devicefunctionlist[146] = self.PHIDGET_DAQ1000_01
        self.devicefunctionlist[147] = self.PHIDGET_DAQ1000_23
        self.devicefunctionlist[148] = self.PHIDGET_DAQ1000_45
        self.devicefunctionlist[149] = self.PHIDGET_DAQ1000_67
        self.devicefunctionlist[152] = self.PHIDGET_DAQ1200_01
        self.devicefunctionlist[153] = self.PHIDGET_DAQ1200_23
        self.devicefunctionlist[154] = self.PHIDGET_DAQ1300_01
        self.devicefunctionlist[155] = self.PHIDGET_DAQ1300_23
        self.devicefunctionlist[156] = self.PHIDGET_DAQ1301_01
        self.devicefunctionlist[157] = self.PHIDGET_DAQ1301_23
        self.devicefunctionlist[158] = self.PHIDGET_DAQ1301_45
        self.devicefunctionlist[159] = self.PHIDGET_DAQ1301_67
        self.devicefunctionlist[168] = self.PHIDGET_TMP1202
        self.devicefunctionlist[169] = self.PHIDGET_TMP1202_2
        self.devicefunctionlist[191] = self.Phidget_TMP1000
        self.devicefunctionlist[192] = self.Phidget_HUM1000_HumTemp
        self.devicefunctionlist[193] = self.Phidget_PRE1000
        self.devicefunctionlist[194] = self.Yocto_Meteo_HumTemp
        self.devicefunctionlist[195] = self.Yocto_Meteo_Pressure
        #string with the name of the program for device #27
        self.externalprogram:str = 'test.py'
        self.externaloutprogram:str = 'out.py' # this program is called with arguments <ET>,<BT>,<ETB>,<BTB> values on each sampling
        self.externaloutprogramFlag:bool = False # if true the externaloutprogram will be called on each sample()

#####################  FUNCTIONS  ############################
    #especial function that collects extra duty cycle % and SV
    def piddutycycle(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        if self.aw.qmc.device == 0: # FUJI
            #return saved readings from device 0
            return self.aw.qmc.dutycycleTX, self.aw.qmc.dutycycle, self.aw.qmc.currentpidsv
        if not self.aw.pidcontrol.pidActive:
            self.aw.qmc.updateLargePIDLCDs(sv='', duty='')
            return self.aw.qmc.timeclock.elapsedMilli(),-1,-1
        lcdformat = ('%.1f' if self.aw.qmc.LCDdecimalplaces else '%.0f')
        if (self.aw.qmc.device == 19 and not self.aw.pidcontrol.externalPIDControl()) or \
                (self.aw.qmc.device in {29, 79} and not self.aw.pidcontrol.externalPIDControl()):
                # TC4 (19) or MODBUS/S7 (29/79) with Artisan Software PID
            duty = self.aw.qmc.pid.getDuty()
            duty = (-1.0 if duty is None else min(100.0, max(-100.0, duty)))
            self.aw.qmc.updateLargePIDLCDs(sv=lcdformat%self.aw.qmc.pid.target, duty=lcdformat%duty)
            return self.aw.qmc.timeclock.elapsedMilli(), duty, self.aw.qmc.pid.target
        sv = self.aw.pidcontrol.sv if self.aw.pidcontrol.sv is not None else -1
        if self.aw.qmc.device == 29: # external MODBUS PID
            duty = -1
        else:
            duty = self.aw.qmc.pid.getDuty()
            duty = (-1.0 if duty is None else min(100.0, max(-100.0, duty)))
        self.aw.qmc.updateLargePIDLCDs(sv=lcdformat%sv, duty=lcdformat%duty)
        return tx, duty, sv

    def pidPtermIterm(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        return tx, self.aw.qmc.pid.getIterm(), self.aw.qmc.pid.getPterm()

    def pidDtermError(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        return tx, self.aw.qmc.pid.getError(), self.aw.qmc.pid.getDterm()

    def slider_01(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t1 = self.aw.slider1.value()
        t2 = self.aw.slider2.value()
        return tx,t2,t1

    def slider_23(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t1 = self.aw.slider3.value()
        t2 = self.aw.slider4.value()
        return tx,t2,t1

    def virtual(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        return tx,1.,1.

    def DUMMY(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        return tx,0,0

    def NONE(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.NONEtmp()
        return tx,t2,t1

    def Kaleido_BTET(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t1:float = -1
        t2:float = -1
#        _sid:int = 0
        if self.aw.kaleido is not None:
            t1, t2, _sid = self.aw.kaleido.getBTET()
# it remains unclear what those machine exactly report and when. In some cases processingn this event flag can lead to unfavorable situations so we do not process them at all
# now the syncing of those event flags can be user configurable and is by default OFF
            if self.aw.qmc.flagstart:
                try:
                    event_flag:int = _sid & 15 # last 4 bits of the sid
                    if len(self.aw.kaleidoEventFlags)>0 and self.aw.kaleidoEventFlags[0] and event_flag == 1 and self.aw.qmc.timeindex[0] == -1:
                        self.aw.qmc.markChargeSignal.emit(True) # CHARGE
    #                elif event_flag == 2 and self.aw.qmc.TPalarmtimeindex is None:
    #                    self.aw.qmc.markTPSignal.emit() # TP
                    elif len(self.aw.kaleidoEventFlags)>1 and self.aw.kaleidoEventFlags[1] and event_flag == 3 and self.aw.qmc.timeindex[1] == 0:
                        self.aw.qmc.markDRYSignal.emit(True) # DRY
                    elif len(self.aw.kaleidoEventFlags)>2 and self.aw.kaleidoEventFlags[2] and event_flag == 4 and self.aw.qmc.timeindex[2] == 0:
                        self.aw.qmc.markFCsSignal.emit(True) # FCs
                    elif len(self.aw.kaleidoEventFlags)>3 and self.aw.kaleidoEventFlags[3] and event_flag == 5 and self.aw.qmc.timeindex[3] == 0:
                        self.aw.qmc.markFCeSignal.emit(True) # FCe
                    elif len(self.aw.kaleidoEventFlags)>4 and self.aw.kaleidoEventFlags[4] and event_flag == 6 and self.aw.qmc.timeindex[4] == 0:
                        self.aw.qmc.markSCsSignal.emit(True) # SCs
                    elif len(self.aw.kaleidoEventFlags)>5 and self.aw.kaleidoEventFlags[5] and event_flag == 7 and self.aw.qmc.timeindex[5] == 0:
                        self.aw.qmc.markSCeSignal.emit(True) # SCe
                    elif len(self.aw.kaleidoEventFlags)>6 and self.aw.kaleidoEventFlags[6] and (event_flag == 8 and self.aw.qmc.timeindex[6] == 0 and
                        self.aw.qmc.timeindex[0] > -1 and self.aw.qmc.autoDropIdx == 0 and
                        (self.aw.qmc.timex[-1] - self.aw.qmc.timex[self.aw.qmc.timeindex[0]]) > 7*60):
                        # only after 7min into the roast and if CHARGE is marked
                        self.aw.qmc.autoDropIdx = len(self.aw.qmc.timex) - 2
                        self.aw.qmc.markDropSignal.emit(True) # DROP
    #                elif event_flag == 9 and self.aw.qmc.timeindex[0] > -1 and self.aw.qmc.timeindex[6] >= 0 and self.aw.qmc.timeindex[7] == 0:
    #                    self.aw.qmc.markCoolSignal.emit(True) # COOL
                except Exception as e: # pylint: disable=broad-except
                    _log.error(e)
        return tx,t2,t1 # time, ET (chan2), BT (chan1)



    def Kaleido_SVAT(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        if self.aw.kaleido is not None:
            t1,t2 = self.aw.kaleido.getSVAT()
            # if in Kaleido PID mode, we turn adjust the SV if TS data changes to sync with the machine state
            if self.aw.kaleidoPID:
                try:
                    ts = int(round(t1))
                    self.aw.setSVSignal.emit(ts)
                except Exception as e: # pylint: disable=broad-except
                    _log.error(e)
        else:
            t1 = t2 = -1
        return tx,t2,t1 # time, AT (chan2), SV (chan1)

    def Kaleido_DrumAH(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        if self.aw.kaleido is not None:
            t1,t2 = self.aw.kaleido.getDrumAH()
            # if in Kaleido PID mode, we turn ArtisanPID ON/OFF if AH signal changes to sync with the machine state
            if self.aw.kaleidoPID:
                try:
                    ah = bool(round(t2))
                    if ah and not self.aw.pidcontrol.pidActive:
                        # machine says its PID is on, we reflect this on the Artisan side
                        self.aw.pidOnSignal.emit()
                    elif not ah and self.aw.pidcontrol.pidActive:
                        # machine says its PID is off, we reflect this on the Artisan side
                        self.aw.pidOffSignal.emit()
                except Exception as e: # pylint: disable=broad-except
                    _log.error(e)
        else:
            t1 = t2 = -1
        return tx,t2,t1 # time), AH (chan2), Drum (chan1)

    def Kaleido_HeaterFan(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        if self.aw.kaleido is not None:
            t1,t2 = self.aw.kaleido.getHeaterFan()
        else:
            t1 = t2 = -1
        return tx,t2,t1 # time, Fan (chan2), Heater (chan1)

############################################################################
    def Yocto_Meteo_HumTemp(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        hum:float|None = self.YoctoMeteoHUM()
        temp:float|None = self.YoctoMeteoTEMP()
        return tx,(-1 if temp is None else (fromCtoFstrict(temp) if self.aw.qmc.mode == 'F' else temp)),(1 if hum is None else hum)


    def Yocto_Meteo_Pressure(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        press:float|None = self.YoctoMeteoPRESS()
        pressure:float = -1
        temp:float = 23. # assume room temperature
        if press is not None:
            if self.aw.qmc.ambientTemp != 0:
                temp = (fromFtoCstrict(self.aw.qmc.ambientTemp) if self.aw.qmc.mode == 'F' else self.aw.qmc.ambientTemp)
            pressure = self.aw.qmc.barometricPressure(pressure, temp, self.aw.qmc.elevation)
        return tx,pressure,pressure


    def Phidget_TMP1000(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        temp:float|None = self.PhidgetHUM1000temperature()
        temperature:float = (-1 if temp is None else (fromCtoFstrict(temp) if self.aw.qmc.mode == 'F' else temp))
        return tx,temperature,temperature


    def Phidget_HUM1000_HumTemp(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        hum:float|None = self.PhidgetHUM1000humidity()
        temp:float|None = self.PhidgetHUM1000temperature()
        return tx,(-1 if temp is None else (fromCtoFstrict(temp) if self.aw.qmc.mode == 'F' else temp)),(1 if hum is None else hum)


    def Phidget_PRE1000(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        pre:float|None = self.PhidgetPRE1000pressure()
        pressure:float = -1.
        temp:float = 23. # assume room temperature
        if pre is not None:
            pressure = pre * 10. # convert to hPa/mbar
            if self.aw.qmc.ambientTemp != 0:
                temp = (fromFtoCstrict(self.aw.qmc.ambientTemp) if self.aw.qmc.mode == 'F' else self.aw.qmc.ambientTemp)
            pressure = self.aw.qmc.barometricPressure(pressure, temp, self.aw.qmc.elevation)
        return tx,temp,pressure


    def PHIDGET1045(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t,a = self.PHIDGET1045temperature(DeviceID.PHIDID_1045)
        return tx,a,t


    def PHIDGET1048(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.PHIDGET1048temperature(DeviceID.PHIDID_1048,0)
        return tx,t1,t2 # time, ET (chan2), BT (chan1)


    def PHIDGET1048_34(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.PHIDGET1048temperature(DeviceID.PHIDID_1048,1)
        return tx,t1,t2


    def PHIDGET1048_AT(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.PHIDGET1048temperature(DeviceID.PHIDID_1048,2)
        return tx,t1,t2


    def PHIDGET1046(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.PHIDGET1046temperature(0)
        return tx,t1,t2


    def PHIDGET1046_34(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.PHIDGET1046temperature(1)
        return tx,t1,t2


    def PHIDGET_DAQ1500(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.PHIDGET1046temperature(0,device_type=1)
        return tx,t1,t2


    def PHIDGET1051(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t,a = self.PHIDGET1045temperature(DeviceID.PHIDID_1051)
        return tx,a,t


    def PHIDGET1011(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1011,0,'voltage')
        return tx,v1,v2


    def PHIDGET1018(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1010_1013_1018_1019,0,'voltage')
        return tx,v1,v2


    def PHIDGET1018_34(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1010_1013_1018_1019,1,'voltage')
        return tx,v1,v2


    def PHIDGET1018_56(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1010_1013_1018_1019,2,'voltage')
        return tx,v1,v2


    def PHIDGET1018_78(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1010_1013_1018_1019,3,'voltage')
        return tx,v1,v2


    def PHIDGET_DAQ1000_01(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1000,0,'voltage')
        return tx,v1,v2


    def PHIDGET_DAQ1000_23(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1000,1,'voltage')
        return tx,v1,v2


    def PHIDGET_DAQ1000_45(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1000,2,'voltage')
        return tx,v1,v2


    def PHIDGET_DAQ1000_67(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1000,3,'voltage')
        return tx,v1,v2


    def PHIDGET1011_D(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1011,0,'digital')
        return tx,v1,v2


    def PHIDGET1018_D(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1010_1013_1018_1019,0,'digital')
        return tx,v1,v2


    def PHIDGET1018_D_34(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1010_1013_1018_1019,1,'digital')
        return tx,v1,v2


    def PHIDGET1018_D_56(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1010_1013_1018_1019,2,'digital')
        return tx,v1,v2


    def PHIDGET1018_D_78(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_1010_1013_1018_1019,3,'digital')
        return tx,v1,v2


    def PHIDGET_DAQ1200_01(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1200,0,'digital')
        return tx,v1,v2


    def PHIDGET_DAQ1200_23(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1200,1,'digital')
        return tx,v1,v2


    def PHIDGET_DAQ1300_01(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1300,0,'digital')
        return tx,v1,v2


    def PHIDGET_DAQ1300_23(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1300,1,'digital')
        return tx,v1,v2


    def PHIDGET_DAQ1301_01(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1301,0,'digital')
        return tx,v1,v2


    def PHIDGET_DAQ1301_23(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1301,1,'digital')
        return tx,v1,v2


    def PHIDGET_DAQ1301_45(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1301,2,'digital')
        return tx,v1,v2


    def PHIDGET_DAQ1301_67(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1301,3,'digital')
        return tx,v1,v2


    def PHIDGET_HUB0000_D(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_HUB0000,0,'digital')
        return tx,v1,v2


    def PHIDGET_HUB0000_D_34(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_HUB0000,1,'digital')
        return tx,v1,v2


    def PHIDGET_HUB0000_D_56(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_HUB0000,2,'digital')
        return tx,v1,v2


    def PHIDGET_HUB0000_D_0(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_HUB0000,0,API='digital',retry=False,single=True)
        return tx,v1,v2


    def PHIDGET_TMP1101(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.PHIDGET1048temperature(DeviceID.PHIDID_TMP1101,0)
        return tx,t1,t2 # time, ET (chan2), BT (chan1)


    def PHIDGET_TMP1101_34(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.PHIDGET1048temperature(DeviceID.PHIDID_TMP1101,1)
        return tx,t1,t2


    def PHIDGET_TMP1101_AT(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.PHIDGET1048temperature(DeviceID.PHIDID_TMP1101,2)
        return tx,t1,t2


    def PHIDGET_TMP1100(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t,a = self.PHIDGET1045temperature(DeviceID.PHIDID_TMP1100)
        return tx,a,t


    def PHIDGET_TMP1200(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t,a = self.PHIDGET1045temperature(DeviceID.PHIDID_TMP1200)
        return tx,a,t


    def PHIDGET_TMP1200_2(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t,a = self.PHIDGET1045temperature(DeviceID.PHIDID_TMP1200,alternative_conf=True)
        return tx,a,t


    def PHIDGET_TMP1202(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t,a = self.PHIDGET1045temperature(
            158) #DeviceID.PHIDID_TMP1202)
        return tx,a,t


    def PHIDGET_TMP1202_2(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        t,a = self.PHIDGET1045temperature(
            158, #DeviceID.PHIDID_TMP1202,
            alternative_conf=True)
        return tx,a,t


    def PHIDGET_HUB0000(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1  = self.PHIDGET1018values(DeviceID.PHIDID_HUB0000,0,'voltage')
        return tx,v1,v2


    def PHIDGET_HUB0000_34(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_HUB0000,1,'voltage')
        return tx,v1,v2


    def PHIDGET_HUB0000_56(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_HUB0000,2,'voltage')
        return tx,v1,v2


    def PHIDGET_HUB0000_0(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1  = self.PHIDGET1018values(DeviceID.PHIDID_HUB0000,0,API='voltage',retry=False,single=True)
        return tx,v1,v2


    def PHIDGET_DAQ1400_CURRENT(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1400,0,'current')
        return tx,v1,v2


    def PHIDGET_DAQ1400_FREQUENCY(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1400,0,'frequency')
        return tx,v1,v2


    def PHIDGET_DAQ1400_DIGITAL(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1400,0,'digital')
        return tx,v1,v2


    def PHIDGET_DAQ1400_VOLTAGE(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_DAQ1400,0,'voltage')
        return tx,v1,v2


    def PHIDGET_VCP1000(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_VCP1000, 0, 'voltage', single=True)
        return tx,v1,v2


    def PHIDGET_VCP1001(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_VCP1001, 0, 'voltage', single=True)
        return tx,v1,v2


    def PHIDGET_VCP1002(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.PHIDGET1018values(DeviceID.PHIDID_VCP1002, 0, 'voltage', single=True)
        return tx,v1,v2


    def ARDUINOTC4(self) -> tuple[float,float,float]:
        self.aw.qmc.extraArduinoTX = self.aw.qmc.timeclock.elapsedMilli()
        t2,t1 = self.ARDUINOTC4temperature()
        return self.aw.qmc.extraArduinoTX,t2,t1


    def ARDUINOTC4_34(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.extraArduinoTX
        t1 = self.aw.qmc.extraArduinoT1
        t2 = self.aw.qmc.extraArduinoT2
        return tx,t2,t1


    def ARDUINOTC4_56(self) -> tuple[float,float,float]: # heater / fan DUTY %
        tx = self.aw.qmc.extraArduinoTX
        t1 = self.aw.qmc.extraArduinoT3
        t2 = self.aw.qmc.extraArduinoT4
        return tx,t2,t1


    def ARDUINOTC4_78(self) -> tuple[float,float,float]: # PID SV / internal temp
        tx = self.aw.qmc.extraArduinoTX
        t1 = self.aw.qmc.extraArduinoT5
        t2 = self.aw.qmc.extraArduinoT6
        return tx,t2,t1


    def YOCTO_thermo(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(0)
        return tx,v1,v2


    def Yocto_4_20mA_Rx(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(4,'Yocto-4-20mA-Rx')
        return tx,v1,v2


    def Yocto_0_10V_Rx(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(4,'Yocto-0-10V-Rx')
        return tx,v1,v2


    def Yocto_milliVolt_Rx(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(4,'Yocto-milliVolt-Rx')
        return tx,v1,v2


    def Yocto_Serial(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(4,'Yocto-Serial')
        return tx,v1,v2


    def Yocto_Power(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(5)
        return tx,v1,v2


    def Yocto_Energy(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(6)
        return tx,v1,v2


    def Yocto_Voltage(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(7)
        return tx,v1,v2


    def Yocto_Current(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(8)
        return tx,v1,v2


    def Yocto_Sensor(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(9)
        return tx,v1,v2


    def YOCTO_pt100(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(1)
        return tx,v1,v2


    def YOCTO_IR(self) -> tuple[float,float,float]:
        tx = self.aw.qmc.timeclock.elapsedMilli()
        v2,v1 = self.YOCTOtemperatures(2)
        return tx,v2,v1


    def YoctoMeteoHUM(self) -> float|None:
        try:
            self.YOCTOimportLIB() # first import the lib
            from yoctopuce.yocto_humidity import YHumidity # type: ignore[import-untyped]
            HUMsensor = YHumidity.FirstHumidity()
            if HUMsensor is not None and HUMsensor.isOnline():
                return float(cast(float, HUMsensor.get_currentValue()))
            return None
        except Exception: # pylint: disable=broad-except
            return None


    def YoctoMeteoTEMP(self) -> float|None:
        try:
            self.YOCTOimportLIB() # first via import the lib
            from yoctopuce.yocto_temperature import YTemperature
            METEOsensor = self.getNextYOCTOsensorOfType(3,[],YTemperature.FirstTemperature()) # pyright:ignore[reportUnknownArgumentType]
            if METEOsensor is not None and METEOsensor.isOnline():
                serial = METEOsensor.get_module().get_serialNumber()
                tempCh = YTemperature.FindTemperature(serial + '.temperature')
                if tempCh.isOnline():
                    return float(cast(float, tempCh.get_currentValue()))
                return None
            return None
        except Exception: # pylint: disable=broad-except
            return None


    def YoctoMeteoPRESS(self) -> float|None:
        try:
            self.YOCTOimportLIB() # first via import the lib
            from yoctopuce.yocto_pressure import YPressure # type: ignore[import-untyped]
            PRESSsensor = YPressure.FirstPressure()
            if PRESSsensor is not None and PRESSsensor.isOnline():
                return float(cast(float, PRESSsensor.get_currentValue()))
            return None
        except Exception: # pylint: disable=broad-except
            return None


    def PhidgetTMP1000temperature(self) -> float|None:
        _log.debug('PhidgetTMP1000temperature')
        try:
            # Temperature
            if self.aw.ser.TMP1000temp is None:
                self.aw.ser.TMP1000temp = PhidgetTemperatureSensor()
            if not self.aw.ser.TMP1000temp.getAttached() and self.aw.qmc.phidgetManager is not None:
                ser, port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(
                    'PhidgetTemperatureSensor',
                    DeviceID.PHIDID_TMP1000,
                    remote=self.aw.qmc.phidgetRemoteFlag,
                    remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser:
                    self.aw.ser.TMP1000temp.setDeviceSerialNumber(ser)
                    self.aw.ser.TMP1000temp.setHubPort(port)  # explicitly set the port to where the HUM is attached
                    if self.aw.qmc.phidgetRemoteFlag:
                        self.addPhidgetServer()
                    if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                        self.aw.ser.TMP1000temp.setIsRemote(True)
                        self.aw.ser.TMP1000temp.setIsLocal(False)
                    self.aw.ser.TMP1000temp.openWaitForAttachment(1500)
                    if self.aw.ser.TMP1000temp.getAttached():
                        _log.debug('Phidget TMP1000 temperature channel attached')
                        libtime.sleep(0.3)
                        # note that we do not register the attach in the aw.qmc.phidgetManager as we only support one of those devices
                    else:
                        _log.debug('Phidget TEMP1000 temperature could not be attached')
            if self.aw.ser.TMP1000temp.getAttached():
                res = float(self.aw.ser.TMP1000temp.getTemperature())
                _log.debug('Phidget TMP1000 temperature received: %s', res)
                return res
            return None
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            if self.aw.ser.TMP1000temp is not None:
                try:
                    self.aw.ser.TMP1000temp.close()
                except Exception: # pylint: disable=broad-except
                    pass
                self.aw.ser.TMP1000temp = None
            return None


    def PhidgetHUM1000temperature(self) -> float|None:
        _log.debug('PhidgetHUM1000temperature')
        try:
            # HUM Temperature
            if self.aw.ser.PhidgetHUMtemp is None:
                self.aw.ser.PhidgetHUMtemp = PhidgetTemperatureSensor()
            if not self.aw.ser.PhidgetHUMtemp.getAttached() and self.aw.qmc.phidgetManager is not None:
                ser, port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(
                    'PhidgetTemperatureSensor',
                    DeviceID.PHIDID_HUM1000,
                    remote=self.aw.qmc.phidgetRemoteFlag,
                    remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser is None:
                    ser, port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(
                        'PhidgetTemperatureSensor',
                        DeviceID.PHIDID_HUM1001,
                        remote=self.aw.qmc.phidgetRemoteFlag,
                        remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser:
                    self.aw.ser.PhidgetHUMtemp.setDeviceSerialNumber(ser)
                    self.aw.ser.PhidgetHUMtemp.setHubPort(port)  # explicitly set the port to where the HUM is attached
                    if self.aw.qmc.phidgetRemoteFlag:
                        self.addPhidgetServer()
                    if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                        self.aw.ser.PhidgetHUMtemp.setIsRemote(True)
                        self.aw.ser.PhidgetHUMtemp.setIsLocal(False)
                    self.aw.ser.PhidgetHUMtemp.openWaitForAttachment(1500)
                    if self.aw.ser.PhidgetHUMtemp.getAttached():
                        _log.debug('Phidget HUM100x temperature channel attached')
                        libtime.sleep(0.3)
                        # note that we do not register the attach in the aw.qmc.phidgetManager as we only support one of those devices
                    else:
                        _log.debug('Phidget HUM100x temperature could not be attached')
            if self.aw.ser.PhidgetHUMtemp.getAttached():
                res = float(self.aw.ser.PhidgetHUMtemp.getTemperature())
                _log.debug('Phidget HUM100x temperature received: %s', res)
                # we don't close the HUM here, but in closePhidgetAMBIENTs
                return res
            return None
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            if self.aw.ser.PhidgetHUMhum is not None:
                try:
                    self.aw.ser.PhidgetHUMhum.close()
                except Exception: # pylint: disable=broad-except
                    pass
                self.aw.ser.PhidgetHUMhum = None
            return None


    def PhidgetHUM1000humidity(self) -> float|None:
        _log.debug('PhidgetHUM1000humidity')
        try:
            # HUM Humidity
            if self.aw.ser.PhidgetHUMhum is None:
                self.aw.ser.PhidgetHUMhum = PhidgetHumiditySensor()
            if not self.aw.ser.PhidgetHUMhum.getAttached() and self.aw.qmc.phidgetManager is not None:
                ser, port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(
                    'PhidgetTemperatureSensor',
                    DeviceID.PHIDID_HUM1000,
                    remote=self.aw.qmc.phidgetRemoteFlag,
                    remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser is None:
                    ser, port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(
                        'PhidgetTemperatureSensor',
                        DeviceID.PHIDID_HUM1001,
                        remote=self.aw.qmc.phidgetRemoteFlag,
                        remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser:
                    self.aw.ser.PhidgetHUMhum.setDeviceSerialNumber(ser)
                    self.aw.ser.PhidgetHUMhum.setHubPort(port)  # explicitly set the port to where the HUM is attached
                    if self.aw.qmc.phidgetRemoteFlag:
                        self.addPhidgetServer()
                    if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                        self.aw.ser.PhidgetHUMhum.setIsRemote(True)
                        self.aw.ser.PhidgetHUMhum.setIsLocal(False)
                    self.aw.ser.PhidgetHUMhum.openWaitForAttachment(1500)
                    if self.aw.ser.PhidgetHUMhum.getAttached():
                        _log.debug('Phidget HUM100x humidity channel attached')
                        libtime.sleep(0.3)
                        # note that we do not register the attach in the aw.qmc.phidgetManager as we only support one of those devices
                    else:
                        _log.debug('Phidget HUM100x humidity could not be attached')
            if self.aw.ser.PhidgetHUMhum.getAttached():
                res = float(self.aw.ser.PhidgetHUMhum.getHumidity())
                _log.debug('Phidget HUM100x humidity received: %s', res)
                # we don't close the HUM here, but in closePhidgetAMBIENTs
                return res
            return None
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            if self.aw.ser.PhidgetHUMhum is not None:
                try:
                    self.aw.ser.PhidgetHUMhum.close()
                except Exception: # pylint: disable=broad-except
                    pass
                self.aw.ser.PhidgetHUMhum = None
            return None


    def PhidgetPRE1000pressure(self) -> float|None:
        _log.debug('PhidgetPRE1000pressure')
        try:
            # PRE Pressure
            if self.aw.ser.PhidgetPREpre is None:
                self.aw.ser.PhidgetPREpre = PhidgetPressureSensor()
            if not self.aw.ser.PhidgetPREpre.getAttached() and self.aw.qmc.phidgetManager is not None:
                ser, port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(
                    'PhidgetPressureSensor',
                    DeviceID.PHIDID_PRE1000,
                    remote=self.aw.qmc.phidgetRemoteFlag,
                    remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser:
                    self.aw.ser.PhidgetPREpre.setDeviceSerialNumber(ser)
                    self.aw.ser.PhidgetPREpre.setHubPort(port)     # explicitly set the port to where the HUM is attached
                    if self.aw.qmc.phidgetRemoteFlag:
                        self.addPhidgetServer()
                    if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                        self.aw.ser.PhidgetPREpre.setIsRemote(True)
                        self.aw.ser.PhidgetPREpre.setIsLocal(False)
                    self.aw.ser.PhidgetPREpre.openWaitForAttachment(1500)
                    if self.aw.ser.PhidgetPREpre.getAttached():
                        _log.debug('Phidget PRE1000 pressure channel attached')
                        libtime.sleep(0.3)
                        # note that we do not register the attach in the aw.qmc.phidgetManager as we only support one of those devices
                    else:
                        _log.debug('Phidget PRE1000 pressure could not be attached')
            if self.aw.ser.PhidgetPREpre.getAttached():
                res = float(self.aw.ser.PhidgetPREpre.getPressure())
                _log.debug('Phidget PRE1000 pressure received: %s', res)
                # we don't close the PRE here, but in closePhidgetAMBIENTs
                return res
            return None
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            if self.aw.ser.PhidgetPREpre is not None:
                try:
                    self.aw.ser.PhidgetPREpre.close()
                except Exception: # pylint: disable=broad-except
                    pass
                self.aw.ser.PhidgetPREpre = None
            return None


    def phidget1045TemperatureChanged(self,_:float , t:float) -> None:
        try:
            #### lock shared resources #####
            self.Phidget1045semaphore.acquire(1)
            self.Phidget1045values.append((t, self.aw.qmc.timeclock.elapsedMilli()))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
        finally:
            if self.Phidget1045semaphore.available() < 1:
                self.Phidget1045semaphore.release(1)


    @staticmethod
    def IRtemp(emissivity:float, temp:float, ambient:float) -> float:
        return (temp - ambient) * emissivity + ambient


    def configure1045(self) -> None:
        self.Phidget1045values = []
        self.Phidget1045lastvalue = -1
        self.Phidget1045tempIRavg = None
        if self.PhidgetIRSensor is not None:
            try:
                if self.aw.qmc.phidget1045_async:
                    self.PhidgetIRSensor.setTemperatureChangeTrigger(self.aw.qmc.phidget1045_changeTrigger)
                else:
                    self.PhidgetIRSensor.setTemperatureChangeTrigger(0)
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            try:
                if self.aw.qmc.phidget1045_async:
                    self.PhidgetIRSensor.setOnTemperatureChangeHandler(self.phidget1045TemperatureChanged)
                else:
                    self.PhidgetIRSensor.setOnTemperatureChangeHandler(lambda *_:None)
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            # set rate
            try:
                self.PhidgetIRSensor.setDataInterval(self.aw.qmc.phidget1045_dataRate)
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def configureOneTC(self) -> None:
        self.Phidget1045values = []
        self.Phidget1045lastvalue = -1
        if self.PhidgetIRSensor is not None:
            try:
                self.PhidgetIRSensor.setThermocoupleType(PHIDGET_THERMOCOUPLE_TYPE(self.aw.qmc.phidget1048_types[0]))
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            if self.aw.qmc.phidget1048_async[0]:
                self.PhidgetIRSensor.setTemperatureChangeTrigger(self.aw.qmc.phidget1048_changeTriggers[0])
            else:
                self.PhidgetIRSensor.setTemperatureChangeTrigger(0)
            if self.aw.qmc.phidget1048_async[0]:
                self.PhidgetIRSensor.setOnTemperatureChangeHandler(self.phidget1045TemperatureChanged)
            else:
                self.PhidgetIRSensor.setOnTemperatureChangeHandler(lambda *_:None)
            # set rate
            try:
                self.PhidgetIRSensor.setDataInterval(self.aw.qmc.phidget1048_dataRate)
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def configureOneRTD(self) -> None:
        self.Phidget1045values = []
        self.Phidget1045lastvalue = -1
        if self.PhidgetIRSensor is not None:
            try:
                self.PhidgetIRSensor.setRTDType(PHIDGET_RTD_TYPE(self.aw.qmc.phidget1200_formula))
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            try:
                self.PhidgetIRSensor.setRTDWireSetup(PHIDGET_RTD_WIRE(self.aw.qmc.phidget1200_wire))
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            if self.aw.qmc.phidget1200_async:
                self.PhidgetIRSensor.setTemperatureChangeTrigger(self.aw.qmc.phidget1200_changeTrigger)
                self.PhidgetIRSensor.setOnTemperatureChangeHandler(self.phidget1045TemperatureChanged)
            else:
                self.PhidgetIRSensor.setTemperatureChangeTrigger(0)
                self.PhidgetIRSensor.setOnTemperatureChangeHandler(lambda *_:None)
            # set rate
            try:
                self.PhidgetIRSensor.setDataInterval(max(self.PhidgetIRSensor.getMinDataInterval(),self.aw.qmc.phidget1200_dataRate))
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def configureOneRTD_2(self) -> None:
        self.Phidget1045values = []
        self.Phidget1045lastvalue = -1
        if self.PhidgetIRSensor is not None:
            try:
                self.PhidgetIRSensor.setRTDType(PHIDGET_RTD_TYPE(self.aw.qmc.phidget1200_2_formula))
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            try:
                self.PhidgetIRSensor.setRTDWireSetup(PHIDGET_RTD_WIRE(self.aw.qmc.phidget1200_2_wire))
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            if self.aw.qmc.phidget1200_async:
                self.PhidgetIRSensor.setTemperatureChangeTrigger(self.aw.qmc.phidget1200_2_changeTrigger)
                self.PhidgetIRSensor.setOnTemperatureChangeHandler(self.phidget1045TemperatureChanged)
            else:
                self.PhidgetIRSensor.setTemperatureChangeTrigger(0)
                self.PhidgetIRSensor.setOnTemperatureChangeHandler(lambda *_:None)
            # set rate
            try:
                self.PhidgetIRSensor.setDataInterval(self.aw.qmc.phidget1200_2_dataRate)
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def phidget1045attached(self,serial:int, port:int|None, deviceType:int, alternative_conf:bool = False) -> None:
        _log.debug('phidget1045attached(%s,%s,%s,%s)',serial,port,deviceType,alternative_conf)
        try:
            if self.aw.qmc.phidgetManager is not None:
                self.aw.qmc.phidgetManager.reserveSerialPort(serial,port,0,'PhidgetTemperatureSensor',deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if deviceType not in {DeviceID.PHIDID_TMP1200, 158}: #DeviceID.PHIDID_TMP1202}:
                    self.aw.qmc.phidgetManager.reserveSerialPort(serial,port,1,'PhidgetTemperatureSensor',deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if deviceType == DeviceID.PHIDID_1045:
                    self.configure1045()
                    self.aw.sendmessage(QApplication.translate('Message','Phidget Temperature Sensor IR attached'))
                elif deviceType == DeviceID.PHIDID_1051:
                    self.configureOneTC()
                    self.aw.sendmessage(QApplication.translate('Message','Phidget Temperature Sensor 1-input attached'))
                elif deviceType == DeviceID.PHIDID_TMP1100:
                    self.configureOneTC()
                    self.aw.sendmessage(QApplication.translate('Message','Phidget Isolated Thermocouple 1-input attached'))
                elif deviceType in {DeviceID.PHIDID_TMP1200, 158}: #DeviceID.PHIDID_TMP1202}:
                    if alternative_conf:
                        self.configureOneRTD_2()
                    else:
                        self.configureOneRTD()
                    self.aw.sendmessage(QApplication.translate('Message','Phidget VINT RTD 1-input attached'))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def phidget1045detached(self, serial:int, port:int|None, deviceType:int) -> None:
        _log.debug('phidget1045detached(%s,%s,%s)',serial,port,deviceType)
        try:
            if self.aw.qmc.phidgetManager is not None:
                self.aw.qmc.phidgetManager.releaseSerialPort(serial,port,0,'PhidgetTemperatureSensor',deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if deviceType not in {DeviceID.PHIDID_TMP1200, 158}: #DeviceID.PHIDID_TMP1202}:
                    self.aw.qmc.phidgetManager.releaseSerialPort(serial,port,1,'PhidgetTemperatureSensor',deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if deviceType == DeviceID.PHIDID_1045:
                    self.aw.sendmessage(QApplication.translate('Message','Phidget Temperature Sensor IR detached'))
                elif deviceType == DeviceID.PHIDID_1051:
                    self.aw.sendmessage(QApplication.translate('Message','Phidget Temperature Sensor 1-input detached'))
                elif deviceType == DeviceID.PHIDID_TMP1100:
                    self.aw.sendmessage(QApplication.translate('Message','Phidget Isolated Thermocouple 1-input detached'))
                elif deviceType in {DeviceID.PHIDID_TMP1200, 158}: #DeviceID.PHIDID_TMP1202}:
                    self.aw.sendmessage(QApplication.translate('Message','Phidget VINT RTD 1-input detached'))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def PHIDGET1045temperature(self, deviceType:int=DeviceID.PHIDID_1045, retry:bool = True, alternative_conf:bool = False) -> tuple[float, float]:
        try:
            if self.PhidgetIRSensor is None and self.aw.qmc.phidgetManager is not None:
                ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetTemperatureSensor',deviceType,
                            remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser is not None:
                    self.PhidgetIRSensor = PhidgetTemperatureSensor()
                    if deviceType in {DeviceID.PHIDID_TMP1200, 158}: #DeviceID.PHIDID_TMP1202}:
                        self.PhidgetIRSensorIC = None # the TMP1200/TMP1202 does not has an internal temperature sensor
                    else:
                        self.PhidgetIRSensorIC = PhidgetTemperatureSensor()
                    try:
                        self.PhidgetIRSensor.setOnAttachHandler(lambda _:self.phidget1045attached(ser,port,deviceType,alternative_conf))
                        self.PhidgetIRSensor.setOnDetachHandler(lambda _:self.phidget1045detached(ser,port,deviceType))
                        if self.aw.qmc.phidgetRemoteFlag:
                            self.addPhidgetServer()
                        if port is not None:
                            self.PhidgetIRSensor.setHubPort(port)
                            if self.PhidgetIRSensorIC is not None and deviceType not in {DeviceID.PHIDID_TMP1200, 158}: #DeviceID.PHIDID_TMP1202}:
                                self.PhidgetIRSensorIC.setHubPort(port)
                        self.PhidgetIRSensor.setDeviceSerialNumber(ser)
                        self.PhidgetIRSensor.setChannel(0) # attached to the IR channel
                        try:
                            if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                                self.PhidgetIRSensor.setIsRemote(True)
                                self.PhidgetIRSensor.setIsLocal(False)
                            self.PhidgetIRSensor.open() #.openWaitForAttachment(timeout) # wait attach for the TMP1200 takes about 1sec on USB
                        except Exception: # pylint: disable=broad-except
                            pass
                        if self.PhidgetIRSensorIC is not None and deviceType not in {DeviceID.PHIDID_TMP1200, 158}: #DeviceID.PHIDID_TMP1202}:
                            self.PhidgetIRSensorIC.setDeviceSerialNumber(ser)
                            self.PhidgetIRSensorIC.setChannel(1) # attached to the IC channel
                            if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                                self.PhidgetIRSensorIC.setIsRemote(True)
                                self.PhidgetIRSensorIC.setIsLocal(False)
                            try:
                                self.PhidgetIRSensorIC.open() #.openWaitForAttachment(timeout)
                            except Exception: # pylint: disable=broad-except
                                pass
                        # we need to give this device a bit time to attach, otherwise it will be considered for another Artisan channel of the same type
                        if self.aw.qmc.phidgetRemoteOnlyFlag:
                            libtime.sleep(.8)
                        else:
                            libtime.sleep(.5)
                    except Exception as ex: # pylint: disable=broad-except
                        _log.exception(ex)
                        _, _, exc_tb = sys.exc_info()
                        self.aw.qmc.adderror((QApplication.translate('Error Message','Exception:') + ' PHIDGET1045temperature() {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
                        try:
                            if self.PhidgetIRSensor.getAttached():
                                self.PhidgetIRSensor.close()
                            if self.PhidgetIRSensorIC is not None and self.PhidgetIRSensorIC.getAttached():
                                self.PhidgetIRSensorIC.close()
                        except Exception: # pylint: disable=broad-except
                            pass
                        self.PhidgetIRSensor = None
                        self.Phidget1045values = []
                        self.Phidget1045lastvalue = -1
                        self.PhidgetIRSensorIC = None
                        self.Phidget1045tempIRavg = None
            if self.PhidgetIRSensor is not None and self.PhidgetIRSensor.getAttached():
                res:float = -1
                ambient:float = -1
                probe:float = -1
                try:
                    if (deviceType == DeviceID.PHIDID_1045 and self.aw.qmc.phidget1045_async) or \
                        (deviceType in [DeviceID.PHIDID_1051,DeviceID.PHIDID_TMP1100] and self.aw.qmc.phidget1048_async[0]) or \
                        (deviceType in {DeviceID.PHIDID_TMP1200, 158} #DeviceID.PHIDID_TMP1202}
                            and ((alternative_conf and self.aw.qmc.phidget1200_2_async) or self.aw.qmc.phidget1200_async)):
                        async_res:float|None = None
                        try:
                            #### lock shared resources #####
                            self.Phidget1045semaphore.acquire(1)
                            now = self.aw.qmc.timeclock.elapsedMilli()
                            start_of_interval = now-self.aw.qmc.delay/1000
                            # 1. just consider async readings taken within the previous sampling interval
                            # and associate them with the (arrival) time since the begin of that interval
                            valid_readings = [(r,t) for (r,t) in self.Phidget1045values if t > start_of_interval]
                            if len(valid_readings) > 0:

                                # 2. calculate the value

#                                # we take the median of all valid_readings weighted by the time of arrival, preferrring newer readings
                                readings = numpy.array([r for (r,_) in valid_readings])
                                times = numpy.array([t for (_,t) in valid_readings])

                                # average by calculating the weighted median
                                import wquantiles # type: ignore[import-untyped]
                                async_res = float(wquantiles.median(readings, times)) # pyright: ignore[reportArgumentType]

#                                # alternative to the use of the median is to use a polyfit
#                                with warnings.catch_warnings():
#                                    warnings.simplefilter('ignore')
#                                    # using stable polyfit from numpy polyfit module
#                                    if len(readings)>1:
#                                        LS_fit = numpy.polynomial.polynomial.polyfit(times, readings, 1)
#                                        tx = (valid_readings[-2][1] + valid_readings[-1][1])/2.0
#                                        async_res = LS_fit[1]*tx+LS_fit[0]
#                                    else:
#                                        async_res = readings[-1]

                                # 3. consume old readings
                                self.Phidget1045values = []
                        except Exception as e: # pylint: disable=broad-except
                            _log.exception(e)
                            self.Phidget1045values = []
                        finally:
                            if self.Phidget1045semaphore.available() < 1:
                                self.Phidget1045semaphore.release(1)
                        if async_res is None:
                            if self.Phidget1045lastvalue == -1: # there is no last value yet, we take a sync value
                                probe = self.PhidgetIRSensor.getTemperature()
                                self.Phidget1045lastvalue = self.PhidgetIRSensor.getTemperature()
                            else:
                                probe = self.Phidget1045lastvalue
                        else:
                            self.Phidget1045lastvalue = async_res
                            probe = async_res
                    else:
                        probe = self.PhidgetIRSensor.getTemperature()
                    if self.aw.qmc.mode == 'F':
                        probe = fromCtoFstrict(probe)
                    res = probe
                except PhidgetException:
                    pass # the value might be still unknown. This can happen right after attach.
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                if res != -1:
                    try:
                        if self.PhidgetIRSensorIC is not None and self.PhidgetIRSensorIC.getAttached():
                            ambient = self.PhidgetIRSensorIC.getTemperature()
                            # we heavily average this ambient temperature IC readings not to introduce additional noise via emissivity calc to the IR reading
                            if self.Phidget1045tempIRavg is None:
                                self.Phidget1045tempIRavg = ambient
                            else:
                                self.Phidget1045tempIRavg = (20*self.Phidget1045tempIRavg + ambient) / 21.0
                                ambient = self.Phidget1045tempIRavg
                            if self.aw.qmc.mode == 'F':
                                ambient = fromCtoFstrict(ambient)
                    except PhidgetException:
                        pass # the value might be still unknown. This can happen right after attach.
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                    if deviceType in {DeviceID.PHIDID_TMP1200, 158}: #DeviceID.PHIDID_TMP1202}:
                        ambient = res
                    if ambient == -1:
                        return -1,-1
                    if deviceType == DeviceID.PHIDID_1045:
                        return self.IRtemp(self.aw.qmc.phidget1045_emissivity,res,ambient), ambient
                    return res, ambient
            if retry:
                libtime.sleep(0.1)
                return self.PHIDGET1045temperature(deviceType,retry=False,alternative_conf=alternative_conf)
            return -1,-1
        except Exception as ex: # pylint: disable=broad-except
            _log.exception(ex)
            try:
                if self.PhidgetIRSensor and self.PhidgetIRSensor.getAttached():
                    self.PhidgetIRSensor.close()
                if self.PhidgetIRSensorIC and self.PhidgetIRSensorIC.getAttached():
                    self.PhidgetIRSensorIC.close()
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            self.PhidgetIRSensor = None
            self.Phidget1045values = []
            self.Phidget1045lastvalue = -1
            self.PhidgetIRSensorIC = None
            self.Phidget1045tempIRavg = None
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message','Exception:') + ' PHIDGET1045temperature() {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
            return -1, -1


    def phidget1048TemperatureChanged(self, t:float, channel:int) -> None:
        try:
            #### lock shared resources #####
            self.Phidget1048semaphores[channel].acquire(1)
            self.Phidget1048values[channel].append((t,libtime.time()))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
        finally:
            if self.Phidget1048semaphores[channel].available() < 1:
                self.Phidget1048semaphores[channel].release(1)


    def phidget1048getSensorReading(self, channel:int, idx:int) -> float:
        if self.aw.qmc.phidget1048_async[channel]:
            res:float|None = None
            try:
                #### lock shared resources #####
                self.Phidget1048semaphores[channel].acquire(1)

                now = libtime.time()
                start_of_interval = now-self.aw.qmc.delay/1000
                # 1. just consider async readings taken within the previous sampling interval
                # and associate them with the (arrival) time since the begin of that interval
                valid_readings = [(r,t - start_of_interval) for (r,t) in self.Phidget1048values[channel] if t > start_of_interval]
                if len(valid_readings) > 0:
                    # 2. calculate the value
                    # we take the median of all valid_readings weighted by the time of arrival, preferrring newer readings
                    readings = [r for (r,t) in valid_readings]
                    weights = [t for (r,t) in valid_readings]
                    import wquantiles
                    res = float(wquantiles.median(numpy.array(readings),numpy.array(weights))) # pyright: ignore[reportArgumentType]
#                    res = numpy.median(numpy.array(readings))
                    # 3. consume old readings
                    self.Phidget1048values[channel] = []

#                if len(self.Phidget1048values[channel]) > 0:
##                    res = numpy.average(self.Phidget1048values[channel])
#                    res = numpy.median(self.Phidget1048values[channel])
#
##                    data = self.Phidget1048values[channel]
##                    data_mean, data_std = numpy.mean(data), numpy.std(data)
##                    if data_std > 0:
##                        cut_off = data_std * 0.9
##                        lower, upper = data_mean - cut_off, data_mean + cut_off
##                        outliers_removed = [x for x in data if x > lower and x < upper]
##                        if len(outliers_removed) < 3:
##                            outliers_removed = data
##                    else:
##                        outliers_removed = data
##                    res = numpy.average(outliers_removed)
#
#                    self.Phidget1048values[channel] = self.Phidget1048values[channel][-round((self.aw.qmc.delay/self.aw.qmc.phidget1048_dataRate)):]
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
                self.Phidget1048values[channel] = []
            finally:
                if self.Phidget1048semaphores[channel].available() < 1:
                    self.Phidget1048semaphores[channel].release(1)
            if res is None:
                if self.PhidgetTemperatureSensor is not None and self.Phidget1048lastvalues[channel] == -1: # there is no last value yet, we take a sync value
                    temp_sensor:PhidgetTemperatureSensor = self.PhidgetTemperatureSensor[idx] # type:ignore[no-any-unimported]
                    assert isinstance(temp_sensor, PhidgetTemperatureSensor)
                    r = float(temp_sensor.getTemperature())
                    self.Phidget1048lastvalues[channel] = r
                    return r
                return float(self.Phidget1048lastvalues[channel]) # return the previous result
            self.Phidget1048lastvalues[channel] = res
            return res
        if self.PhidgetTemperatureSensor is None:
            return -1
        sensor:PhidgetTemperatureSensor = self.PhidgetTemperatureSensor[idx] # type:ignore[no-any-unimported,unused-ignore]
        return float(sensor.getTemperature())


    def configure1048(self, idx:int) -> None:
        if self.PhidgetTemperatureSensor is not None and len(self.PhidgetTemperatureSensor) > idx:
            # reset async values
            channel:int = self.PhidgetTemperatureSensor[idx].getChannel()
            if channel < 4: # the ambient temperature sensor does not need to be configured
                # set probe type
                self.PhidgetTemperatureSensor[idx].setThermocoupleType(PHIDGET_THERMOCOUPLE_TYPE(self.aw.qmc.phidget1048_types[channel]))
                # set rate
                try:
                    self.PhidgetTemperatureSensor[idx].setDataInterval(self.aw.qmc.phidget1048_dataRate)
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                # set change trigger
                try:
                    if self.aw.qmc.phidget1048_async[channel]:
                        self.PhidgetTemperatureSensor[idx].setTemperatureChangeTrigger(self.aw.qmc.phidget1048_changeTriggers[channel])
                        self.PhidgetTemperatureSensor[idx].setOnTemperatureChangeHandler(lambda _,t: self.phidget1048TemperatureChanged(t,channel)) # pyright:ignore[reportUnknownArgumentType]
                    else:
                        self.PhidgetTemperatureSensor[idx].setTemperatureChangeTrigger(0)
                        self.PhidgetTemperatureSensor[idx].setOnTemperatureChangeHandler(lambda *_:None)
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                self.Phidget1048values[channel] = []
                self.Phidget1048lastvalues[channel] = -1


    def phidget1048attached(self, serial:int, port:int|None, deviceType:int, idx:int) -> None:
        _log.debug('phidget1048attached(%s,%s,%s,%s)',serial,port,deviceType,idx)
        try:
            self.configure1048(idx)
            channel:int
            if self.PhidgetTemperatureSensor is not None and len(self.PhidgetTemperatureSensor) > idx and self.aw.qmc.phidgetManager is not None:
                channel = self.PhidgetTemperatureSensor[idx].getChannel()
                self.aw.qmc.phidgetManager.reserveSerialPort(serial,port,channel,'PhidgetTemperatureSensor',deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if channel == 0:
                    self.aw.sendmessage(QApplication.translate('Message','Phidget Temperature Sensor 4-input attached'))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def phidget1048detached(self, serial:int, port:int|None, deviceType:int, idx:int) -> None:
        _log.debug('phidget1048detached(%s,%s,%s,%s)',serial,port,deviceType,idx)
        try:
            if self.PhidgetTemperatureSensor is not None and len(self.PhidgetTemperatureSensor) > idx and self.aw.qmc.phidgetManager is not None:
                channel:int = self.PhidgetTemperatureSensor[idx].getChannel()
                self.aw.qmc.phidgetManager.releaseSerialPort(serial,port,channel,'PhidgetTemperatureSensor',deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if channel == 0:
                    self.aw.sendmessage(QApplication.translate('Message','Phidget Temperature Sensor 4-input detached'))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def PHIDGET1048temperature(self, deviceType:int = DeviceID.PHIDID_1048, mode:int = 0, retry:bool = True) -> tuple[float, float]:
        try:
            if not self.PhidgetTemperatureSensor and self.aw.qmc.phidgetManager is not None:
                ser = None
                port = None
                if mode == 0:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetTemperatureSensor',deviceType,0,
                        remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                # in all other cases, we check for existing serial/port pairs from attaching the main channels 1+2 of the device
                elif mode == 1:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetTemperatureSensor',deviceType,2,
                        remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                elif mode == 2:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetTemperatureSensor',deviceType,4,
                        remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser is not None:
                    self.PhidgetTemperatureSensor = [PhidgetTemperatureSensor()]
                    if mode != 2:
                        self.PhidgetTemperatureSensor.append(PhidgetTemperatureSensor())
                    try:
                        self.PhidgetTemperatureSensor[0].setOnAttachHandler(lambda _:self.phidget1048attached(ser,port,deviceType,0))
                        self.PhidgetTemperatureSensor[0].setOnDetachHandler(lambda _:self.phidget1048detached(ser,port,deviceType,0))
                        if mode != 2:
                            self.PhidgetTemperatureSensor[1].setOnAttachHandler(lambda _:self.phidget1048attached(ser,port,deviceType,1))
                            self.PhidgetTemperatureSensor[1].setOnDetachHandler(lambda _:self.phidget1048detached(ser,port,deviceType,1))
                        if self.aw.qmc.phidgetRemoteFlag:
                            self.addPhidgetServer()
                        if port is not None:
                            self.PhidgetTemperatureSensor[0].setHubPort(port)
                            if mode != 2:
                                self.PhidgetTemperatureSensor[1].setHubPort(port)
                        self.PhidgetTemperatureSensor[0].setDeviceSerialNumber(ser)
                        self.PhidgetTemperatureSensor[0].setChannel(mode*2)
                        if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                            self.PhidgetTemperatureSensor[0].setIsRemote(True)
                            self.PhidgetTemperatureSensor[0].setIsLocal(False)
                        try:
                            self.PhidgetTemperatureSensor[0].open() #.openWaitForAttachment(timeout)
                        except Exception: # pylint: disable=broad-except
                            pass
                        if mode != 2:
                            self.PhidgetTemperatureSensor[1].setDeviceSerialNumber(ser)
                            self.PhidgetTemperatureSensor[1].setChannel(mode*2 + 1)
                            if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                                self.PhidgetTemperatureSensor[1].setIsRemote(True)
                                self.PhidgetTemperatureSensor[1].setIsLocal(False)
                            try:
                                self.PhidgetTemperatureSensor[1].open() # .openWaitForAttachment(timeout)
                            except Exception: # pylint: disable=broad-except
                                pass
                        # we need to give this device a bit time to attach, otherwise it will be considered for another Artisan channel of the same type
                        if self.aw.qmc.phidgetRemoteOnlyFlag:
                            libtime.sleep(.8)
                        else:
                            libtime.sleep(.5)
                    except Exception as ex: # pylint: disable=broad-except
                        _log.exception(ex)
                        #_, _, exc_tb = sys.exc_info()
                        #self.aw.qmc.adderror((QApplication.translate("Error Message","Exception:") + " PHIDGET1048temperature() {0}").format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
                        try:
                            if self.PhidgetTemperatureSensor and self.PhidgetTemperatureSensor[0].getAttached():
                                self.PhidgetTemperatureSensor[0].close()
                            if mode != 2 and self.PhidgetTemperatureSensor and len(self.PhidgetTemperatureSensor)> 1 and self.PhidgetTemperatureSensor[1].getAttached():
                                self.PhidgetTemperatureSensor[1].close()
                        except Exception as e: # pylint: disable=broad-except
                            _log.exception(e)
                        self.Phidget1048values = [[],[],[],[]]
                        self.Phidget1048lastvalues = [-1.0]*4
                        self.PhidgetTemperatureSensor = None
            if self.PhidgetTemperatureSensor and ((mode == 2) or (len(self.PhidgetTemperatureSensor)>1 and self.PhidgetTemperatureSensor[0].getAttached() and self.PhidgetTemperatureSensor[1].getAttached())):
                # now just harvest both temps (or one in case type is 2)
                if mode in {0, 1}:
                    probe1:float = -1.
                    probe2:float = -1.
                    try:
                        probe1 = self.phidget1048getSensorReading(mode*2,0)
                        if self.aw.qmc.mode == 'F':
                            probe1 = fromCtoFstrict(probe1)
                    except PhidgetException:
                        pass  # the value might be still unknown. This can happen right after attach.
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                    try:
                        probe2 = self.phidget1048getSensorReading(mode*2 + 1,1)
                        if self.aw.qmc.mode == 'F':
                            probe2 = fromCtoFstrict(probe2)
                    except PhidgetException:
                        pass  # the value might be still unknown. This can happen right after attach.
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                    return probe1, probe2
                if mode == 2:
                    try:
                        at = self.PhidgetTemperatureSensor[0].getTemperature()
                        if self.aw.qmc.mode == 'F':
                            at = fromCtoFstrict(at)
                        return at,-1
                    except PhidgetException:
                        pass  # the value might be still unknown. This can happen right after attach.
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                        return -1,-1
                return -1,-1
            if retry:
                libtime.sleep(0.1)
                return self.PHIDGET1048temperature(deviceType,mode,False)
            return -1,-1
        except Exception as ex: # pylint: disable=broad-except
            _log.exception(ex)
            try:
                if self.PhidgetTemperatureSensor and self.PhidgetTemperatureSensor[0].getAttached():
                    self.PhidgetTemperatureSensor[0].close()
                if mode != 2 and self.PhidgetTemperatureSensor and len(self.PhidgetTemperatureSensor)>1 and self.PhidgetTemperatureSensor[1].getAttached():
                    self.PhidgetTemperatureSensor[1].close()
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            self.Phidget1048values = [[],[],[],[]]
            self.Phidget1048lastvalues = [-1.0]*4
            self.PhidgetTemperatureSensor = None
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message','Exception:') + ' PHIDGET1048temperature() {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
            return -1,-1


    @staticmethod
    def R_RTD_WS(bv:float) -> float:
        return (1000 * (1000 - 2 * bv))/(1000 + 2 * bv)


    @staticmethod
    def R_RTD_DIV(bv:float) -> float:
        return (2000 * bv) / (1000 - bv)


    @staticmethod
    def rRTD2PT100temp(R_RTD:float) -> float:
        Z1 = -3.9083e-03
        Z2 = 1.76e-05
        Z3 = -2.31e-08
        Z4 = -1.155e-06
        try:
            return (Z1 + math.sqrt(abs(Z2 + (Z3 * R_RTD))))/Z4
        except Exception: # pylint: disable=broad-except
            return -1


    def phidget1046TemperatureChanged(self, v:float, channel:int) -> None:
        try:
            #### lock shared resources #####
            self.Phidget1046semaphores[channel].acquire(1)
            temp = self.bridgeValue2Temperature(channel,v*1000) # Note in Phidgets API v22 this factor 1000 has to be added
            if self.aw.qmc.mode == 'F' and self.aw.qmc.phidget1046_formula[channel] != 2:
                temp = fromCtoFstrict(temp)
            self.Phidget1046values[channel].append((temp,libtime.time()))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
        finally:
            if self.Phidget1046semaphores[channel].available() < 1:
                self.Phidget1046semaphores[channel].release(1)


    def bridgeValue2Temperature(self, i:int, bv:float) -> float:
        v:float = -1.
        try:
            if self.aw.qmc.phidget1046_formula[i] == 0:
                v = self.rRTD2PT100temp(self.R_RTD_WS(abs(bv)))  # we add the abs() here to support inverted wirings
            elif self.aw.qmc.phidget1046_formula[i] == 1:
                v = self.rRTD2PT100temp(self.R_RTD_DIV(abs(bv)))  # we add the abs() here to support inverted wirings
            elif self.aw.qmc.phidget1046_formula[i] == 2:
                v = bv # no abs() for raw values
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' bridgeValue2Temperature(): {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))
        return v


    def phidget1046getTemperature(self, i:int, idx:int) -> float:
        v:float = -1.
        if self.PhidgetBridgeSensor is not None:
            try:
                bv:float = self.PhidgetBridgeSensor[idx].getVoltageRatio() * 1000 # Note in Phidgets API v22 this factor 1000 has to be added

# test values for the bridge value to temperature conversion
#            bv = 51.77844 # about room temperature for Voltage Divider wiring
#            bv = 400.2949 # about room temperature for Wheatstone Bridge

                v = self.bridgeValue2Temperature(i,bv)
                if self.aw.qmc.mode == 'F' and self.aw.qmc.phidget1046_formula[i] != 2:
                    v = fromCtoFstrict(v)
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
                v = -1
        return v


    def phidget1046getSensorReading(self, channel:int, idx:int) -> float:
        if self.aw.qmc.phidget1046_async[channel]:
            res:float|None = None
            try:
                #### lock shared resources #####
                self.Phidget1046semaphores[channel].acquire(1)
                now = libtime.time()
                start_of_interval = now-self.aw.qmc.delay/1000
                # 1. just consider async readings taken within the previous sampling interval
                # and associate them with the (arrival) time since the begin of that interval
                valid_readings = [(r,t - start_of_interval) for (r,t) in self.Phidget1046values[channel] if t > start_of_interval]
                if len(valid_readings) > 0:
                    # 2. calculate the value
                    # we take the median of all valid_readings weighted by the time of arrival, preferrring newer readings
                    readings = [r for (r, _) in valid_readings]
                    weights = [t for (_, t) in valid_readings]
                    import wquantiles
                    res = float(wquantiles.median(numpy.array(readings),numpy.array(weights))) # pyright: ignore[reportArgumentType]
                    # 3. consume old readings
                    self.Phidget1046values[channel] = []

#                if len(self.Phidget1046values[channel]) > 0:
##                    res = numpy.average(self.Phidget1046values[channel])
#                    res = numpy.median(self.Phidget1046values[channel])
#                    self.Phidget1046values[channel] = self.Phidget1046values[channel][-round((self.aw.qmc.delay/self.aw.qmc.phidget1046_dataRate)):]
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
                self.Phidget1046values[channel] = []
            finally:
                if self.Phidget1046semaphores[channel].available() < 1:
                    self.Phidget1046semaphores[channel].release(1)
            if res is None:
                if self.Phidget1046lastvalues[channel] == -1: # there is no last value yet, we take a sync value
                    res = self.phidget1046getTemperature(channel,idx)
                    self.Phidget1046lastvalues[channel] = res
                    return res
                return float(self.Phidget1046lastvalues[channel])
            self.Phidget1046lastvalues[channel] = res
            return res
        return self.phidget1046getTemperature(channel,idx)


    def configure1046(self, idx:int) -> None:
        if self.PhidgetBridgeSensor is not None and len(self.PhidgetBridgeSensor) > idx:
            channel:int = self.PhidgetBridgeSensor[idx].getChannel()
            if channel < 4:
                # set gain
                try:
                    self.PhidgetBridgeSensor[idx].setBridgeGain(PHIDGET_GAIN_VALUE(self.aw.qmc.phidget1046_gain[channel]))
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                # set rate
                try:
                    self.PhidgetBridgeSensor[idx].setDataInterval(self.aw.qmc.phidget1046_dataRate)
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                # set voltage ratio change trigger to 0 (fire every DataInterval)
                try:
                    self.PhidgetBridgeSensor[idx].setVoltageRatioChangeTrigger(0)
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                # enable channel
                try:
                    self.PhidgetBridgeSensor[idx].setBridgeEnabled(True)
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                if self.aw.qmc.phidget1046_async[channel]:
                    self.PhidgetBridgeSensor[idx].setOnVoltageRatioChangeHandler(lambda _,v:self.phidget1046TemperatureChanged(v,channel)) # pyright:ignore[reportUnknownArgumentType]
                else:
                    self.PhidgetBridgeSensor[idx].setOnVoltageRatioChangeHandler(lambda *_:None)
                # reset async value
                self.Phidget1046values[channel] = []
                self.Phidget1046lastvalues[channel] = -1


    def phidget1046attached(self, serial:int, port:int|None, deviceType:int, idx:int) -> None:
        _log.debug('phidget1046attached(%s,%s,%s,%s)',serial,port,deviceType,idx)
        try:
            self.configure1046(idx)
            if self.PhidgetBridgeSensor is not None and self.aw.qmc.phidgetManager is not None:
                channel:int = self.PhidgetBridgeSensor[idx].getChannel()
                self.aw.qmc.phidgetManager.reserveSerialPort(serial,port,channel,'PhidgetVoltageRatioInput',deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if channel == 0:
                    if deviceType == DeviceID.PHIDID_1046:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget 1046 attached'))
                    else:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1500 attached'))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def phidget1046detached(self, serial:int, port:int|None, deviceType:int, idx:int) -> None:
        _log.debug('phidget1046detached(%s,%s,%s,%s)',serial,port,deviceType,idx)
        try:
            if self.PhidgetBridgeSensor is not None and self.aw.qmc.phidgetManager is not None:
                channel:int = self.PhidgetBridgeSensor[idx].getChannel()
                self.aw.qmc.phidgetManager.releaseSerialPort(serial,port,channel,'PhidgetVoltageRatioInput',deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if channel == 0:
                    if deviceType == DeviceID.PHIDID_1046:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget 1046 detached'))
                    else:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1500 detached'))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def PHIDGET1046temperature(self, mode:int = 0, retry:bool = True, device_type:int = 0) -> tuple[float, float]:
        deviceType = DeviceID.PHIDID_1046
        if device_type == 1:
            deviceType = DeviceID.PHIDID_DAQ1500
        try:
            if not self.PhidgetBridgeSensor and self.aw.qmc.phidgetManager is not None:
                ser = None
                port = None
                if mode == 0:
                    # we scan for available main device
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetVoltageRatioInput',deviceType,0,
                        remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                # in all other cases, we check for existing serial/port pairs from attaching the main channels 1+2 of the device
                elif mode == 1:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetVoltageRatioInput',deviceType,2,
                        remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser is not None:
                    self.PhidgetBridgeSensor = [VoltageRatioInput(),VoltageRatioInput()]

                    try:
                        for i in [0,1]:
                            if self.aw.qmc.phidgetRemoteFlag:
                                self.addPhidgetServer()
                            if port is not None:
                                self.PhidgetBridgeSensor[i].setHubPort(port)
                            self.PhidgetBridgeSensor[i].setDeviceSerialNumber(ser)
                            self.PhidgetBridgeSensor[i].setChannel(mode*2+i)
                            if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                                self.PhidgetBridgeSensor[i].setIsRemote(True)
                                self.PhidgetBridgeSensor[i].setIsLocal(False)
                            self.PhidgetBridgeSensor[i].setOnAttachHandler(lambda _,x=i:self.phidget1046attached(ser,port,deviceType,x))
                            self.PhidgetBridgeSensor[i].setOnDetachHandler(lambda _,x=i:self.phidget1046detached(ser,port,deviceType,x))
                            libtime.sleep(.1)
                            try:
                                if len(self.PhidgetBridgeSensor)>i:
                                    self.PhidgetBridgeSensor[i].open() #.openWaitForAttachment(timeout)
                            except Exception: # pylint: disable=broad-except
                                pass
                        # we need to give this device a bit time to attach, otherwise it will be considered for another Artisan channel of the same type
                        if self.aw.qmc.phidgetRemoteOnlyFlag:
                            libtime.sleep(.8)
                        else:
                            libtime.sleep(.5)
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                        #_, _, exc_tb = sys.exc_info()
                        #self.aw.qmc.adderror((QApplication.translate("Error Message","Exception:") + " PHIDGET1046temperature() {0}").format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
                        try:
                            if self.PhidgetBridgeSensor and self.PhidgetBridgeSensor[0].getAttached():
                                self.PhidgetBridgeSensor[0].close()
                            if self.PhidgetBridgeSensor and len(self.PhidgetBridgeSensor)>1 and self.PhidgetBridgeSensor[1].getAttached():
                                self.PhidgetBridgeSensor[1].close()
                        except Exception: # pylint: disable=broad-except
                            pass
                        self.Phidget1046values = [[],[],[],[]]
                        self.Phidget1046lastvalues = [-1.0]*4
                        self.PhidgetBridgeSensor = None
            if self.PhidgetBridgeSensor and len(self.PhidgetBridgeSensor) == 2 and self.PhidgetBridgeSensor[0].getAttached() and self.PhidgetBridgeSensor[1].getAttached():
                if mode in {0, 1}:
                    probe1:float = -1.
                    probe2:float = -1.
                    try:
                        probe1 = self.phidget1046getSensorReading(mode*2,0)
                    except PhidgetException:
                        pass  # the value might be still unknown. This can happen right after attach.
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                    try:
                        probe2 = self.phidget1046getSensorReading(mode*2+1,1)
                    except PhidgetException:
                        pass  # the value might be still unknown. This can happen right after attach.
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                    return probe1, probe2
                return -1,-1
            if retry:
                libtime.sleep(0.1)
                return self.PHIDGET1046temperature(mode,False)
            return -1,-1
        except Exception as ex: # pylint: disable=broad-except
            _log.exception(ex)
            try:
                if self.PhidgetBridgeSensor and self.PhidgetBridgeSensor[0].getAttached():
                    self.PhidgetBridgeSensor[0].close()
                if self.PhidgetBridgeSensor and len(self.PhidgetBridgeSensor)>1 and self.PhidgetBridgeSensor[1].getAttached():
                    self.PhidgetBridgeSensor[1].close()
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            self.Phidget1046values = [[],[],[],[]]
            self.Phidget1046lastvalues = [-1.0]*4
            self.PhidgetBridgeSensor = None
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message','Exception:') + ' PHIDGET1046temperature() {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
            return -1,-1


    @staticmethod
    def serialString2serialPort(serial:str|None) -> tuple[int|None, int|None]:
        if serial is None:
            return None, None
        serial_split = serial.split(':')
        s = None
        p = None
        try:
            s = int(serial_split[0])
        except Exception: # pylint: disable=broad-except
            pass
        try:
            p = int(serial_split[1])
        except Exception: # pylint: disable=broad-except
            pass
        return s,p


    @staticmethod
    def serialPort2serialString(serial:int|None, port:int|None) -> str|None:
        if serial is None and port is None:
            return None
        if port is None:
            return str(serial)
        return str(serial) + ':' + str(port)


    def phidgetOUTattached(self, ch:'Phidget') -> None: # type:ignore[no-any-unimported,unused-ignore]
        _log.debug('phidgetOUTattached(%s)',ch)
        if self.aw.qmc.phidgetManager is not None:
            self.aw.qmc.phidgetManager.reserveSerialPort(
                ch.getDeviceSerialNumber(), # serial
                ch.getHubPort(), # port
                ch.getChannel(), # channel
                ch.getChannelClassName(), # phidget_class_name
                ch.getDeviceID(), # device_id
                remote=self.aw.qmc.phidgetRemoteFlag,
                remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)


    def phidgetOUTdetached(self,ch:'Phidget') -> None: # type:ignore[no-any-unimported,unused-ignore]
        _log.debug('phidgetOUTdetached(%s)',ch)
        if self.aw.qmc.phidgetManager is not None:
            self.aw.qmc.phidgetManager.releaseSerialPort(
                ch.getDeviceSerialNumber(), # serial
                ch.getHubPort(), # port
                ch.getChannel(), # channel
                ch.getChannelClassName(), # phidget_class_name
                ch.getDeviceID(), # device_id
                remote=self.aw.qmc.phidgetRemoteFlag,
                remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)


    def phidgetBinaryOUTattach(self, channel:int, serial:str|None = None) -> None:
        _log.debug('phidgetBinaryOUTattach(%s,%s)',channel,serial)
        if serial not in self.aw.ser.PhidgetDigitalOut:
            if self.aw.qmc.phidgetManager is None:
                self.aw.qmc.startPhidgetManager()
            if self.aw.qmc.phidgetManager is not None:
                ser:int|None = None
                s,p = self.serialString2serialPort(serial)
                for phidget_id in [DeviceID.PHIDID_1014,DeviceID.PHIDID_OUT1100,DeviceID.PHIDID_REL1000,DeviceID.PHIDID_REL1100]:
                    if ser is None:
                        ser,_ = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDigitalOutput',phidget_id,channel,
                                remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                ports = 4
                if ser is None:
                    ser,_ = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDigitalOutput',DeviceID.PHIDID_1017,
                                remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 8
                # try to attach up to 8 IO channels of the first Phidget 1010, 1013, 1018, 1019 module
                if ser is None:
                    ser,_ = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDigitalOutput',DeviceID.PHIDID_1010_1013_1018_1019,
                                remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 8
                # try to attach up to 16 IO channels of the first Phidget REL1101 module
                if ser is None:
                    ser,_ = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDigitalOutput',DeviceID.PHIDID_REL1101,
                                remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 16
                if ser is not None:
                    self.aw.ser.PhidgetDigitalOut[serial] = []
                    for i in range(ports):
                        do = DigitalOutput()
                        do.setChannel(i)
                        do.setDeviceSerialNumber(ser)
                        if self.aw.qmc.phidgetRemoteFlag:
                            do.setIsRemote(True)
                            do.setIsLocal(False)
                        elif not self.aw.qmc.phidgetRemoteFlag:
                            do.setIsRemote(False)
                            do.setIsLocal(True)
                        self.aw.ser.PhidgetDigitalOut[serial].append(do)
        try:
            ch = self.aw.ser.PhidgetDigitalOut[serial][channel]
            ch.setOnAttachHandler(self.phidgetOUTattached)
            ch.setOnDetachHandler(self.phidgetOUTdetached)
            if not ch.getAttached():
                if self.aw.qmc.phidgetRemoteFlag:
                    ch.openWaitForAttachment(3000)
                else:
                    ch.openWaitForAttachment(1000)
                if serial is None and ch.getAttached():
                    # we make this also accessible via its serial number + port
                    si = self.serialPort2serialString(ch.getDeviceSerialNumber(),ch.getHubPort()) # NOTE: ch.getHubPort() returns -1 if not yet attached
                    if si is not None:
                        self.aw.ser.PhidgetDigitalOut[si] = self.aw.ser.PhidgetDigitalOut[None]
        except Exception: # pylint: disable=broad-except
            pass


    def phidgetBinaryOUTpulse(self, channel:int, millis:float, serial:str|None = None) -> None:
        self.phidgetBinaryOUTset(channel, True, serial)
#        QTimer.singleShot(int(round(millis)),lambda : self.phidgetBinaryOUTset(channel,0))
        # QTimer (which does not work being called from a QThread) call replaced by the next 2 lines (event actions are now started in an extra thread)
        # the following solution has the drawback to block the eventaction thread
#        libtime.sleep(millis/1000.)
#        self.phidgetBinaryOUTset(channel,0)
        # so we use a QTimer.singleShot running in the main thread
        if serial is None:
            self.aw.singleShotPhidgetsPulseOFF.emit(channel,millis,'BinaryOUTset')
        else:
            self.aw.singleShotPhidgetsPulseOFFSerial.emit(channel,millis,'BinaryOUTset',serial)


    def phidgetBinaryOUTset(self, channel:int, value:bool, serial:str|None = None) -> bool:
        _log.debug('phidgetBinaryOUTset(%s,%s,%s)',channel,value,serial)
        res = False
        self.phidgetBinaryOUTattach(channel,serial)
        if serial in self.aw.ser.PhidgetDigitalOut:
            # set state of the given channel
            out = self.aw.ser.PhidgetDigitalOut[serial]
            try:
                if len(out) > channel and out[channel] and out[channel].getAttached():
                    cast(DigitalOutput, out[channel]).setState(value) # type:ignore[no-any-unimported]
                    res = True
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
                res = False
        return res


    def phidgetBinaryOUTget(self, channel:int, serial:str|None = None) -> bool:
        _log.debug('phidgetBinaryOUTget(%s,%s)',channel,serial)
        self.phidgetBinaryOUTattach(channel,serial)
        res = False
        if serial in self.aw.ser.PhidgetDigitalOut:
            # get state of the given channel
            out = self.aw.ser.PhidgetDigitalOut[serial]
            try:
                if len(out) > channel and out[channel] and out[channel].getAttached():
                    res = cast(DigitalOutput, out[channel]).getState() # type:ignore[no-any-unimported]
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
        _log.debug(' => phidgetBinaryOUTget: %s',res)
        return res


    def phidgetBinaryOUTtoggle(self, channel:int, serial:str|None = None) -> bool:
        _log.debug('phidgetBinaryOUTtoggle(%s,%s)',channel,serial)
        return self.phidgetBinaryOUTset(channel,not self.phidgetBinaryOUTget(channel,serial),serial)


    def phidgetBinaryOUTclose(self) -> None:
        _log.debug('phidgetBinaryOUTclose')
        for o in self.aw.ser.PhidgetDigitalOut:
            out = self.aw.ser.PhidgetDigitalOut[o]
            for i, _ in enumerate(out):
                try:
                    if out[i].getAttached():
                        self.phidgetOUTdetached(out[i])
                    out[i].close()
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
        self.aw.ser.PhidgetDigitalOut = {}


    def phidgetOUTattach(self, channel:int, serial:str|None = None) -> None:
        _log.debug('phidgetOUTattach(%s,%s)',channel,serial)
        if serial not in self.aw.ser.PhidgetDigitalOut:
            if self.aw.qmc.phidgetManager is None:
                self.aw.qmc.startPhidgetManager()
            if self.aw.qmc.phidgetManager is not None:
                # try to attach the 4 channels of the Phidget OUT1100 module
                ser:int|None = None
                s,p = self.serialString2serialPort(serial)
                port = None
                for phidget_id in [DeviceID.PHIDID_OUT1100,DeviceID.PHIDID_REL1100]:
                    if ser is None:
                        ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDigitalOutput',phidget_id,channel,
                                remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    else:
                        break
                ports = 4
                if ser is None:
                    ports = 16
                    for phidget_id in [DeviceID.PHIDID_REL1101]:
                        if ser is None:
                            ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDigitalOutput',phidget_id,channel,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                        else:
                            break
                if ser is not None:
                    self.aw.ser.PhidgetDigitalOut[serial] = []
                    self.aw.ser.PhidgetDigitalOutLastPWM[serial] = [0.0]*ports # 0-100
                    self.aw.ser.PhidgetDigitalOutLastToggle[serial] = [None]*ports
                    for i in range(ports):
                        do = DigitalOutput()
                        if port is not None:
                            do.setHubPort(port)
                        do.setChannel(i)
                        do.setDeviceSerialNumber(ser)
                        if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                            do.setIsRemote(True)
                            do.setIsLocal(False)
                        elif not self.aw.qmc.phidgetRemoteFlag:
                            do.setIsRemote(False)
                            do.setIsLocal(True)
                        self.aw.ser.PhidgetDigitalOut[serial].append(do)

        try:
            ch = self.aw.ser.PhidgetDigitalOut[serial][channel]
            if not ch.getAttached():
                ch.setOnAttachHandler(self.phidgetOUTattached)
                ch.setOnDetachHandler(self.phidgetOUTdetached)
                if self.aw.qmc.phidgetRemoteFlag:
                    ch.openWaitForAttachment(3000)
                else:
                    ch.openWaitForAttachment(1200)
                if serial is None and ch.getAttached():
                    # we make this also accessible via its serial number + port
                    si = self.serialPort2serialString(ch.getDeviceSerialNumber(),ch.getHubPort())
                    if si is not None:
                        self.aw.ser.PhidgetDigitalOut[si] = self.aw.ser.PhidgetDigitalOut[None]
                        self.aw.ser.PhidgetDigitalOutLastPWM[si] = self.aw.ser.PhidgetDigitalOutLastPWM[None]
                        self.aw.ser.PhidgetDigitalOutLastToggle[si] = self.aw.ser.PhidgetDigitalOutLastToggle[None]
        except Exception: # pylint: disable=broad-except
            pass


    def phidgetOUTtogglePWM(self, channel:int, serial:str|None = None) -> None:
        _log.debug('phidgetOUTtogglePWM(%s,%s)',channel,serial)
        self.phidgetOUTattach(channel,serial) # this is to ensure that the lastToggle/lastPWM structures are allocated
        if serial in self.aw.ser.PhidgetDigitalOut:
            lastPWM = self.aw.ser.PhidgetDigitalOutLastPWM[serial][channel]
            lastToggle = self.aw.ser.PhidgetDigitalOutLastToggle[serial][channel]
            if lastPWM == 0:
                # we switch on
                if lastToggle is None:
                    self.phidgetOUTsetPWM(channel,100,serial)
                else:
                    # we have a lastPWM from before toggling off
                    self.phidgetOUTsetPWM(channel,lastToggle,serial)
            else:
                # we switch off
                self.phidgetOUTsetPWM(channel,0,serial)
                self.aw.ser.PhidgetDigitalOutLastToggle[serial][channel] = lastPWM # remember lastPWM to be able to switch on again
                if serial is None:
                    # also establish for the entry with serial number
                    s = self.aw.ser.PhidgetDigitalOut[serial][channel].getDeviceSerialNumber()
                    ser = self.serialPort2serialString(s,self.aw.ser.PhidgetDigitalOut[serial][channel].getHubPort())
                    try:
                        self.aw.ser.PhidgetDigitalOutLastToggle[ser][channel] = lastPWM # remember lastPWM to be able to switch on again
                    except Exception:  # pylint: disable=broad-except
                        pass
                    try:
                        self.aw.ser.PhidgetDigitalOutLastToggle[str(s)][channel] = lastPWM # remember lastPWM to be able to switch on again
                    except Exception:  # pylint: disable=broad-except
                        pass


    def phidgetOUTpulsePWM(self, channel:int, millis:float, serial:str|None = None) -> None:
        _log.debug('phidgetOUTpulsePWM(%s,%s,%s)',channel,millis,serial)
        self.phidgetOUTsetPWM(channel,100,serial)
        if serial is None:
            self.aw.singleShotPhidgetsPulseOFF.emit(channel,millis,'OUTsetPWM')
        else:
            self.aw.singleShotPhidgetsPulseOFFSerial.emit(channel,millis,'OUTsetPWM',serial)


    def phidgetOUTsetPWM(self, channel:int, value:float, serial:str|None = None) -> None:
        _log.debug('phidgetOUTsetPWM(%s,%s,%s)',channel,value,serial)
        self.phidgetOUTattach(channel,serial)
        if serial in self.aw.ser.PhidgetDigitalOut:
            out = self.aw.ser.PhidgetDigitalOut[serial]
            # set PWM of the given channel
            try:
                if len(out) > channel and out[channel].getAttached():
                    cast(DigitalOutput, out[channel]).setDutyCycle(value/100.) # type:ignore[no-any-unimported]
                    self.aw.ser.PhidgetDigitalOutLastPWM[serial][channel] = value
                    self.aw.ser.PhidgetDigitalOutLastToggle[serial][channel] = None # clears the lastToggle value
                    if serial is None:
                        # also establish for the entry with serial number
                        s = out[channel].getDeviceSerialNumber()
                        sr = self.serialPort2serialString(s, out[channel].getHubPort())
                        try:
                            self.aw.ser.PhidgetDigitalOutLastPWM[sr][channel] = value
                            self.aw.ser.PhidgetDigitalOutLastToggle[sr][channel] = None # clears the lastToggle value
                        except Exception: # pylint: disable=broad-except
                            pass
                        try:
                            self.aw.ser.PhidgetDigitalOutLastPWM[str(s)][channel] = value
                            self.aw.ser.PhidgetDigitalOutLastToggle[str(s)][channel] = None # clears the lastToggle value
                        except Exception: # pylint: disable=broad-except
                            pass
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def phidgetOUTsetPWMfrequency(self, channel:int, value:float, serial:str|None = None) -> None:
        _log.debug('phidgetOUTsetPWMfrequency(%s,%s,%s)',channel,value,serial)
        self.phidgetOUTattach(channel,serial)
        if serial in self.aw.ser.PhidgetDigitalOut:
            out = self.aw.ser.PhidgetDigitalOut[serial]
            # set PWM frequency for all channels of the module
            try:
                v = max(100.0, min(20000.0, value))
                if len(out) > channel and out[channel].getAttached():
                    cast(DigitalOutput, out[channel]).setFrequency(v) # type:ignore[no-any-unimported]
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def phidgetOUTclose(self) -> None:
        _log.debug('phidgetOUTclose()')
        for m in self.aw.ser.PhidgetDigitalOut:
            out = self.aw.ser.PhidgetDigitalOut[m]
            for i, _ in enumerate(out):
                try:
                    if out[i].getAttached():
                        self.phidgetOUTdetached(out[i])
                    out[i].close()
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
        self.aw.ser.PhidgetDigitalOut = {}
        self.aw.ser.PhidgetDigitalOutLastPWM = {}
        self.aw.ser.PhidgetDigitalOutLastToggle = {}


    def phidgetOUTattachHub(self, channel:int, serial:str|None = None) -> None:
        _log.debug('phidgetOUTattachHub(%s,%s)',channel,serial)
        if serial not in self.aw.ser.PhidgetDigitalOutHub:
            if self.aw.qmc.phidgetManager is None:
                self.aw.qmc.startPhidgetManager()
            if self.aw.qmc.phidgetManager is not None:
                # try to attach the 6 channels of the Phidget HUB module
                s,p = self.serialString2serialPort(serial)
                ser,_ = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDigitalOutput',DeviceID.PHIDID_DIGITALOUTPUT_PORT,channel,
                            remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                if ser is not None:
                    self.aw.ser.PhidgetDigitalOutHub[serial] = [DigitalOutput(),DigitalOutput(),DigitalOutput(),DigitalOutput(),DigitalOutput(),DigitalOutput()]
                    self.aw.ser.PhidgetDigitalOutLastPWMhub[serial] = [0.0]*6 # 0-100
                    self.aw.ser.PhidgetDigitalOutLastToggleHub[serial] = [None]*6
                    for i in range(6):
                        self.aw.ser.PhidgetDigitalOutHub[serial][i].setChannel(0)
                        self.aw.ser.PhidgetDigitalOutHub[serial][i].setHubPort(i)
                        self.aw.ser.PhidgetDigitalOutHub[serial][i].setDeviceSerialNumber(ser)
                        self.aw.ser.PhidgetDigitalOutHub[serial][i].setIsHubPortDevice(True)
                        if self.aw.qmc.phidgetRemoteFlag and self.aw.qmc.phidgetRemoteOnlyFlag:
                            self.aw.ser.PhidgetDigitalOutHub[serial][i].setIsRemote(True)
                            self.aw.ser.PhidgetDigitalOutHub[serial][i].setIsLocal(False)
                    if serial is None:
                        # we make this also accessible via its serial number
                        self.aw.ser.PhidgetDigitalOutHub[str(ser)] = self.aw.ser.PhidgetDigitalOutHub[None]
                        self.aw.ser.PhidgetDigitalOutLastPWMhub[str(ser)] = self.aw.ser.PhidgetDigitalOutLastPWMhub[None]
                        self.aw.ser.PhidgetDigitalOutLastToggleHub[str(ser)] = self.aw.ser.PhidgetDigitalOutLastToggleHub[None]
        try:
            ch = self.aw.ser.PhidgetDigitalOutHub[serial][channel]
            ch.setOnAttachHandler(self.phidgetOUTattached)
            ch.setOnDetachHandler(self.phidgetOUTdetached)
            if not ch.getAttached():
                if self.aw.qmc.phidgetRemoteFlag:
                    ch.openWaitForAttachment(3000)
                else:
                    ch.openWaitForAttachment(1000)
        except Exception: # pylint: disable=broad-except
            pass


    def phidgetOUTtogglePWMhub(self, channel:int, serial:str|None = None) -> None:
        _log.debug('phidgetOUTtogglePWMhub(%s,%s)',channel,serial)
        self.phidgetOUTattachHub(channel,serial) # this is to ensure that the lastToggle/lastPWM structures are allocated
        if serial in self.aw.ser.PhidgetDigitalOutHub:
            lastToggle = self.aw.ser.PhidgetDigitalOutLastToggleHub[serial][channel]
            lastPWM = self.aw.ser.PhidgetDigitalOutLastPWMhub[serial][channel]
            if lastPWM == 0:
                # we switch on
                if lastToggle is None:
                    self.phidgetOUTsetPWMhub(channel,100,serial)
                else:
                    # we have a lastPWM from before toggling off
                    self.phidgetOUTsetPWMhub(channel,lastToggle,serial)
            else:
                # we switch off
                self.phidgetOUTsetPWMhub(channel,0,serial)
                self.aw.ser.PhidgetDigitalOutLastToggleHub[serial][channel] = lastPWM # remember lastPWM to be able to switch on again
                if serial is None:
                    # also establish for the entry with serial number
                    ser:str = str(self.aw.ser.PhidgetDigitalOutHub[serial][channel].getDeviceSerialNumber())
                    self.aw.ser.PhidgetDigitalOutLastToggleHub[ser][channel] = lastPWM # remember lastPWM to be able to switch on again


    def phidgetOUTpulsePWMhub(self, channel:int, millis:float, serial:str|None = None) -> None:
        _log.debug('phidgetOUTpulsePWMhub(%s,%s,%s)',channel,millis,serial)
        self.phidgetOUTsetPWMhub(channel,100,serial)
#        QTimer.singleShot(int(round(millis)),lambda : self.phidgetOUTsetPWMhub(channel,0))
        # QTimer (which does not work being called from a QThread) call replaced by the next 2 lines (event actions are now started in an extra thread)
        # the following solution has the drawback to block the eventaction thread
#        libtime.sleep(millis/1000.)
#        self.phidgetOUTsetPWMhub(channel,0)
        if serial is None:
            self.aw.singleShotPhidgetsPulseOFF.emit(channel,millis,'OUTsetPWMhub')
        else:
            self.aw.singleShotPhidgetsPulseOFFSerial.emit(channel,millis,'OUTsetPWMhub',serial)


    def phidgetOUTsetPWMhub(self, channel:int, value:float, serial:str|None = None) -> None:
        _log.debug('phidgetOUTsetPWMhub(%s,%s,%s)',channel,value,serial)
        self.phidgetOUTattachHub(channel,serial)
        if serial in self.aw.ser.PhidgetDigitalOutHub:
            outHub = self.aw.ser.PhidgetDigitalOutHub[serial]
            # set PWM of the given channel
            try:
                if len(outHub) > channel and outHub[channel] and outHub[channel].getAttached():
                    cast(DigitalOutput, outHub[channel]).setDutyCycle(value/100.) # type:ignore[no-any-unimported]
                    self.aw.ser.PhidgetDigitalOutLastPWMhub[serial][channel] = value
                    self.aw.ser.PhidgetDigitalOutLastToggleHub[serial][channel] = None # clears the lastToggle value
                    if serial is None:
                        # also establish for the entry with serial number
                        sr:str = str(outHub[channel].getDeviceSerialNumber())
                        self.aw.ser.PhidgetDigitalOutLastPWMhub[sr][channel] = value
                        self.aw.ser.PhidgetDigitalOutLastToggleHub[sr][channel] = None # clears the lastToggle value
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def phidgetOUTcloseHub(self) -> None:
        _log.debug('phidgetOUTcloseHub')
        for h in self.aw.ser.PhidgetDigitalOutHub:
            outHub = self.aw.ser.PhidgetDigitalOutHub[h]
            for i, _ in enumerate(outHub):
                try:
                    if outHub[i].getAttached():
                        self.phidgetOUTdetached(outHub[i])
                    outHub[i].close()
                except Exception: # pylint: disable=broad-except
                    pass
        self.aw.ser.PhidgetDigitalOutHub = {}
        self.aw.ser.PhidgetDigitalOutLastPWMhub = {}
        self.aw.ser.PhidgetDigitalOutLastToggleHub = {}


    def phidgetVOUTattach(self, channel:int, serial:str|None) -> None:
        _log.debug('phidgetVOUTattach(%s,%s)',channel,serial)
        s = None
        p = None
        if serial not in self.aw.ser.PhidgetAnalogOut:
            if self.aw.qmc.phidgetManager is None:
                self.aw.qmc.startPhidgetManager()
            if self.aw.qmc.phidgetManager is not None:
                # try to attach the Phidget OUT100x module
                s,p = self.serialString2serialPort(serial)
                ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetVoltageOutput',DeviceID.PHIDID_OUT1000,
                            remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                ports = 1
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetVoltageOutput',DeviceID.PHIDID_OUT1001,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 1
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetVoltageOutput',DeviceID.PHIDID_OUT1002,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 1
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetVoltageOutput',DeviceID.PHIDID_1002,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 4
                if ser is not None:
                    self.aw.ser.PhidgetAnalogOut[serial] = []
                    for i in range(ports):
                        vo = VoltageOutput()
                        if port is not None:
                            vo.setHubPort(port)
                        vo.setDeviceSerialNumber(ser)
                        vo.setChannel(i)
                        if self.aw.qmc.phidgetRemoteOnlyFlag and self.aw.qmc.phidgetRemoteFlag:
                            vo.setIsRemote(True)
                            vo.setIsLocal(False)
                        elif not self.aw.qmc.phidgetRemoteFlag:
                            vo.setIsRemote(False)
                            vo.setIsLocal(True)
                        self.aw.ser.PhidgetAnalogOut[serial].append(vo)
        try:
            ch = self.aw.ser.PhidgetAnalogOut[serial][channel]
            ch.setOnAttachHandler(self.phidgetOUTattached)
            ch.setOnDetachHandler(self.phidgetOUTdetached)
            if not ch.getAttached():
                if self.aw.qmc.phidgetRemoteFlag:
                    ch.openWaitForAttachment(3000)
                else:
                    ch.openWaitForAttachment(1200)
                if serial is None and ch.getAttached():
                    # we make this also accessible via its serial number + port
                    si = self.serialPort2serialString(ch.getDeviceSerialNumber(),ch.getHubPort())
                    if si is not None:
                        self.aw.ser.PhidgetAnalogOut[si] = self.aw.ser.PhidgetAnalogOut[None]
            try:
                cast(VoltageOutput, self.aw.ser.PhidgetAnalogOut[str(s)][channel]).setEnabled(True) # type:ignore[no-any-unimported] # the output on this device is always enabled
            except Exception: # pylint: disable=broad-except
                pass # the OUT1001/OUT1002 do not offer this API and are always enabled
        except Exception: # pylint: disable=broad-except
            pass


    def phidgetVOUTsetVOUT(self, channel:int, value:float, serial:str|None = None) -> bool:
        _log.debug('phidgetVOUTsetVOUT(%s,%s,%s)',channel,value,serial)
        res = False
        self.phidgetVOUTattach(channel,serial)
        if serial in self.aw.ser.PhidgetAnalogOut:
            out = self.aw.ser.PhidgetAnalogOut[serial]
            # set voltage output
            try:
                if len(out) > channel and out[channel].getAttached():
                    cast(VoltageOutput, out[channel]).setVoltage(value) # type:ignore[no-any-unimported]
                    res = True
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
                res = False
        return res


    def phidgetVOUTsetRange(self, channel:int, value:int, serial:str|None = None) -> bool:
        _log.debug('phidgetVOUTsetRange(%s,%s,%s)',channel,value,serial)
        res = False
        self.phidgetVOUTattach(channel,serial)
        if serial in self.aw.ser.PhidgetAnalogOut:
            out = self.aw.ser.PhidgetAnalogOut[serial]
            # set voltage output
            try:
                if len(out) > channel and out[channel].getAttached():
                    out_channel:VoltageOutput = cast(VoltageOutput, out[channel]) # type:ignore[no-any-unimported]
                    if value == 5:
                        out_channel.setVoltageOutputRange(VoltageOutputRange.VOLTAGE_OUTPUT_RANGE_5V)
                    else:
                        out_channel.setVoltageOutputRange(VoltageOutputRange.VOLTAGE_OUTPUT_RANGE_10V)
                    res = True
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
                res = False
        return res


    def phidgetVOUTclose(self) -> None:
        _log.debug('phidgetVOUTclose')
        for c in self.aw.ser.PhidgetAnalogOut:
            out = self.aw.ser.PhidgetAnalogOut[c]
            for i, _ in enumerate(out):
                try:
                    if out[i].getAttached():
                        try:
                            cast(VoltageOutput, out[i]).setEnabled(False) # type:ignore[no-any-unimported] # the output on this device is always enabled
                        except Exception: # pylint: disable=broad-except
                            pass # the OUT1001/OUT1002 do not offer this API and are always enabled
                        self.phidgetOUTdetached(out[i])
                    out[i].close()
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
        self.aw.ser.PhidgetAnalogOut = {}


    def phidgetDCMotorAttach(self, channel:int, serial:str|None = None) -> None:
        _log.debug('phidgetDCMotorAttach(%s,%s)', channel, serial)
        if serial not in self.aw.ser.PhidgetDCMotor:
            if self.aw.qmc.phidgetManager is None:
                self.aw.qmc.startPhidgetManager()
            if self.aw.qmc.phidgetManager is not None:
                # try to attach the DCMotor modules
                s,p = self.serialString2serialPort(serial)
                ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDCMotor',DeviceID.PHIDID_DCC1000,
                            remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                ports:int = 1
                brushless:bool = False
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDCMotor',DeviceID.PHIDID_DCC1002,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 1
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDCMotor',DeviceID.PHIDID_DCC1003,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 2
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetDCMotor',DeviceID.PHIDID_DCC1020,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 1
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetBLDCMotor',DeviceID.PHIDID_DCC1100,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 1
                    brushless = True
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetBLDCMotor',DeviceID.PHIDID_DCC1120,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 1
                    brushless = True
                if ser is not None:
                    self.aw.ser.PhidgetDCMotor[serial] = []
                    for i in range(ports):
                        dcm:BLDCMotor|DCMotor = (BLDCMotor() if brushless else DCMotor()) # type:ignore[no-any-unimported]
                        if port is not None:
                            dcm.setHubPort(port)
                        dcm.setDeviceSerialNumber(ser)
                        dcm.setChannel(i)
                        if self.aw.qmc.phidgetRemoteOnlyFlag and self.aw.qmc.phidgetRemoteFlag:
                            dcm.setIsRemote(True)
                            dcm.setIsLocal(False)
                        elif not self.aw.qmc.phidgetRemoteFlag:
                            dcm.setIsRemote(False)
                            dcm.setIsLocal(True)
                        self.aw.ser.PhidgetDCMotor[serial].append(dcm)
        try:
            ch = self.aw.ser.PhidgetDCMotor[serial][channel]
            ch.setOnAttachHandler(self.phidgetOUTattached)
            ch.setOnDetachHandler(self.phidgetOUTdetached)
            if not ch.getAttached():
                if self.aw.qmc.phidgetRemoteFlag:
                    ch.openWaitForAttachment(3000)
                else:
                    ch.openWaitForAttachment(1200)
                if serial is None and ch.getAttached():
                    # we make this also accessible via its serial number + port
                    si = self.serialPort2serialString(ch.getDeviceSerialNumber(),ch.getHubPort())
                    if si is not None:
                        self.aw.ser.PhidgetDCMotor[si] = self.aw.ser.PhidgetDCMotor[None]
        except Exception: # pylint: disable=broad-except
            pass


    def phidgetDCMotorSetAcceleration(self, channel:int, value:float, serial:str|None = None) -> None:
        _log.debug('phidgetDCMotorSetAcceleration(%s,%s,%s)',channel,value,serial)
        self.phidgetDCMotorAttach(channel,serial)
        if serial in self.aw.ser.PhidgetDCMotor:
            dcm = self.aw.ser.PhidgetDCMotor[serial]
            # set velocity
            try:
                if len(dcm) > channel and dcm[channel].getAttached():
                    cast(DCMotor, dcm[channel]).setAcceleration(value) # type:ignore[no-any-unimported]
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def phidgetDCMotorSetVelocity(self, channel:int, value:float, serial:str|None = None) -> None:
        _log.debug('phidgetDCMotorSetVelocity(%s,%s,%s)',channel,value,serial)
        self.phidgetDCMotorAttach(channel,serial)
        if serial in self.aw.ser.PhidgetDCMotor:
            dcm = self.aw.ser.PhidgetDCMotor[serial]
#            self.aw.sendmessage('dcm found')
            # set velocity
            try:
                if len(dcm) > channel and dcm[channel].getAttached():
                    cast(DCMotor, dcm[channel]).setTargetVelocity(value) # type:ignore[no-any-unimported]
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def phidgetDCMotorSetCurrentLimit(self, channel:int, value:float, serial:str|None = None) -> None:
        _log.debug('phidgetDCMotorSetCurrentLimit(%s,%s,%s)',channel,value,serial)
        self.phidgetDCMotorAttach(channel,serial)
        if serial in self.aw.ser.PhidgetDCMotor:
            dcm = self.aw.ser.PhidgetDCMotor[serial]
            # set current limit
            try:
                if len(dcm) > channel and dcm[channel].getAttached():
                    cast(DCMotor, dcm[channel]).setCurrentLimit(value) # type:ignore[no-any-unimported]
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def phidgetDCMotorClose(self) -> None:
        _log.debug('phidgetDCMotorClose')
        for c in self.aw.ser.PhidgetDCMotor:
            dcm = self.aw.ser.PhidgetDCMotor[c]
            for i, _ in enumerate(dcm):
                try:
                    if dcm[i].getAttached():
                        self.phidgetOUTdetached(dcm[i])
                    dcm[i].close()
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
        self.aw.ser.PhidgetDCMotor = {}


    def yoctoVOUTattach(self, c:int, module_id:str|None) -> 'YVoltageOutput|None': # type:ignore[no-any-unimported,unused-ignore]
        _log.debug('yoctoVOUTattach(%s,%s)',c,module_id)
        # check if VoltageOutput object for channel c and module_id is already attached
        voltageOutputs = self.aw.ser.YOCTOvoltageOutputs
        m = next((x for x in voltageOutputs if
                x.get_functionId() == 'voltageOutput'+str(c) and
                (module_id is None or module_id == x.get_serialNumber() or module_id == x.get_logicalName())),
                None)
        if m is not None:
            return m
        # the module/channel is not yet attached search for it
        self.YOCTOimportLIB() # first import the lib
        from yoctopuce.yocto_voltageoutput import YVoltageOutput
        if module_id is None:
            vout = YVoltageOutput.FirstVoltageOutput()
            if vout is None:
                return None
            m = vout.get_module()
            target = m.get_serialNumber()
        else:
            target = module_id
        theYOCTOvoltageOutput = YVoltageOutput.FindVoltageOutput(target + '.voltageOutput' + str(c))
        if theYOCTOvoltageOutput.isOnline():
            self.aw.ser.YOCTOvoltageOutputs.append(theYOCTOvoltageOutput) # pyright:ignore[reportUnknownArgumentType]
            return theYOCTOvoltageOutput
        return None


    def yoctoVOUTsetVOUT(self, c:int, v:float, module_id:str|None = None) -> None:
        _log.debug('yoctoVOUTsetVOUT(%s,%s,%s)',c,v,module_id)
        try:
            m = self.yoctoVOUTattach(c,module_id)
            if m is not None and m.isOnline():
                m.set_currentVoltage(v) # with v a voltage in V [0.0-10.0]
        except Exception: # pylint: disable=broad-except
            pass


    def yoctoVOUTclose(self) -> None:
        self.aw.ser.YOCTOvoltageOutputs = []
        try:
            YAPI.FreeAPI()
        except Exception: # pylint: disable=broad-except
            pass


    def yoctoCOUTattach(self, module_id:str|None) -> 'YCurrentLoopOutput|None': # type:ignore[no-any-unimported,unused-ignore]
        _log.debug('yoctoCOUTattach(%s)',module_id)
        # check if YOCTOcurrentOutput object for module_id is already attached
        currentOutputs = self.aw.ser.YOCTOcurrentOutputs
        m = next((x for x in currentOutputs if
                x.get_functionId() == 'currentLoopOutput' and
                (module_id is None or module_id == x.get_serialNumber() or module_id == x.get_logicalName())),
                None)
        if m is not None:
            return m
        # the module/channel is not yet attached search for it
        self.YOCTOimportLIB() # first import the lib
        from yoctopuce.yocto_currentloopoutput import YCurrentLoopOutput
        if module_id is None:
            cout = YCurrentLoopOutput.FirstCurrentLoopOutput()
            if cout is None:
                return None
            m = cout.get_module()
            target = m.get_serialNumber()
        else:
            target = module_id
        theYOCTOcurrentOutput = YCurrentLoopOutput.FindCurrentLoopOutput(target + '.currentLoopOutput')
        if theYOCTOcurrentOutput.isOnline():
            self.aw.ser.YOCTOcurrentOutputs.append(theYOCTOcurrentOutput) # pyright:ignore[reportUnknownArgumentType]
            return theYOCTOcurrentOutput
        return None


    def yoctoCOUTsetCOUT(self, c:float, module_id:str|None = None) -> None:
        _log.debug('yoctoCOUTsetCOUT(%s,%s)',c,module_id)
        try:
            m = self.yoctoCOUTattach(module_id)
            if m is not None and m.isOnline():
                m.set_current(c) # with c a current in mA [3.0-21.0]
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoCOUTclose(self) -> None:
        _log.debug('yoctoCOUTclose')
        self.aw.ser.YOCTOcurrentOutputs = []
        try:
            YAPI.FreeAPI()
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoPWMattach(self, c:int, module_id:str|None) -> 'YPwmOutput|None': # type:ignore[no-any-unimported,unused-ignore]
        _log.debug('yoctoPWMattach(%s,%s)',c,module_id)
        # check if YPwmOutput object for channel c and module_id is already attached
        pwmOutputs = self.aw.ser.YOCTOpwmOutputs
        m = next((x for x in pwmOutputs if
                x.get_functionId() == 'pwmOutput'+str(c) and
                (module_id is None or module_id == x.get_serialNumber() or module_id == x.get_logicalName())),
                None)
        if m is not None:
            return m
        # the module/channel is not yet attached search for it
        self.YOCTOimportLIB() # first import the lib
        from yoctopuce.yocto_pwmoutput import YPwmOutput
        if module_id is None:
            vout = YPwmOutput.FirstPwmOutput()
            if vout is None:
                return None
            m = vout.get_module()
            target = m.get_serialNumber()
        else:
            target = module_id
        theYOCTOpwmOutput = YPwmOutput.FindPwmOutput(target + '.pwmOutput' + str(c))
        if theYOCTOpwmOutput.isOnline():
            self.aw.ser.YOCTOpwmOutputs.append(theYOCTOpwmOutput) # pyright:ignore[reportUnknownArgumentType]
            return theYOCTOpwmOutput
        return None


    def yoctoPWMenabled(self, c:int, b:bool, module_id:str|None = None) -> None:
        _log.debug('yoctoPWMenabled(%s,%s,%s)',c,b,module_id)
        try:
            m = self.yoctoPWMattach(c,module_id)
            if m is not None and m.isOnline():
                from yoctopuce.yocto_pwmoutput import YPwmOutput
                if b:
                    m.set_enabled(YPwmOutput.ENABLED_TRUE)
                else:
                    m.set_enabled(YPwmOutput.ENABLED_FALSE)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoPWMsetFrequency(self, c:int, f:float, module_id:str|None = None) -> None:
        _log.debug('yoctoPWMsetFrequency(%s,%s,%s)',c,f,module_id)
        try:
            m = self.yoctoPWMattach(c,module_id)
            if m is not None and m.isOnline():
                m.set_frequency(f) # with f the frequency in Hz as an integer [0-1000000]
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoPWMsetDuty(self, c:int, d:float, module_id:str|None = None) -> None:
        _log.debug('yoctoPWMsetDuty(%s,%s,%s)',c,d,module_id)
        try:
            m = self.yoctoPWMattach(c,module_id)
            if m is not None and m.isOnline():
                m.set_dutyCycle(d) # d the duty cycle in % as a float [0.0-100.0]
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoPWMmove(self, c:int, d:float, t:int, module_id:str|None = None) -> None:
        _log.debug('yoctoPWMmove(%s,%s,%s,%s)',c,d,t,module_id)
        try:
            m = self.yoctoPWMattach(c,module_id)
            if m is not None and m.isOnline():
                m.dutyCycleMove(d,t) # d the duty cycle in % as a float [0.0-100.0] and t the time as an integer in milliseconds
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoPWMclose(self) -> None:
        _log.debug('yoctoPWMclose')
        self.aw.ser.YOCTOpwmOutputs = []
        try:
            YAPI.FreeAPI()
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoRELattach(self, c:int, module_id:str|None) -> 'YRelay|None': # type:ignore[no-any-unimported,unused-ignore]
        _log.debug('yoctoRELattach(%s,%s)',c,module_id)
        # check if Relay object for channel c and module_id is already attached
        relays = self.aw.ser.YOCTOrelays
        m = next((x for x in relays if
                x.get_functionId() == 'relay'+str(c) and
                (module_id is None or module_id == x.get_serialNumber() or module_id == x.get_logicalName())),
                None)
        if m is not None:
            return m
        # the module/channel is not yet attached search for it
        self.YOCTOimportLIB() # first import the lib
        from yoctopuce.yocto_relay import YRelay
        if module_id is None:
            rel = YRelay.FirstRelay()
            if rel is None:
                return None
            m = rel.get_module()
            target = m.get_serialNumber()
        else:
            target = module_id
        theYOCTOrelay = YRelay.FindRelay(target + '.relay' + str(c))
        module = theYOCTOrelay.get_module()
        module.isOnline()
        if theYOCTOrelay.isOnline():
            self.aw.ser.YOCTOrelays.append(theYOCTOrelay) # pyright:ignore[reportUnknownArgumentType]
            return theYOCTOrelay
        return None


    def yoctoRELon(self, c:int, module_id:str|None = None) -> None:
        _log.debug('yoctoRELon(%s,%s)',c,module_id)
        try:
            m = self.yoctoRELattach(c,module_id)
            if m is not None and m.isOnline():
                from yoctopuce.yocto_relay import YRelay
                m.set_state(YRelay.STATE_B)
                #m.set_output(YRelay.OUTPUT_ON)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoRELoff(self, c:int, module_id:str|None = None) -> None:
        _log.debug('yoctoRELoff(%s,%s)',c,module_id)
        try:
            m = self.yoctoRELattach(c,module_id)
            if m is not None and m.isOnline():
                from yoctopuce.yocto_relay import YRelay
                m.set_state(YRelay.STATE_A)
                #m.set_output(YRelay.OUTPUT_OFF)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoRELflip(self, c:int, module_id:str|None = None) -> None:
        _log.debug('yoctoRELflip(%s,%s)',c,module_id)
        try:
            m = self.yoctoRELattach(c,module_id)
            if m is not None and m.isOnline():
                m.toggle()
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoRELpulse(self, c:int, delay:int, duration:int, module_id:str|None = None) -> None:
        _log.debug('yoctoRELpulse(%s,%s,%s,%s)',c,delay,duration,module_id)
        try:
            m = self.yoctoRELattach(c,module_id)
            if m is not None and m.isOnline():
                m.delayedPulse(delay, duration)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoRELclose(self) -> None:
        _log.debug('yoctoRELclose')
        self.aw.ser.YOCTOrelays = []
        try:
            YAPI.FreeAPI()
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def getYoctoPOWER(self, module_id:str|None) -> 'YPower|None': # type:ignore[no-any-unimported,unused-ignore]
        _log.debug('yoctoPOWERattach(%s)',module_id)
        # the module/channel is not yet attached search for it
        self.YOCTOimportLIB() # first import the lib
        from yoctopuce.yocto_power import YPower
        if module_id is None:
            power = YPower.FirstPower()
            if power is None:
                return None
            m = power.get_module()
            target = m.get_serialNumber()
        else:
            target = module_id
        theYOCTOpower = YPower.FindPower(target + '.power')
        module = theYOCTOpower.get_module()
        module.isOnline()
        if theYOCTOpower.isOnline():
            return theYOCTOpower
        return None


    def yoctoPowerReset(self, module_id:str|None = None) -> None:
        _log.debug('yoctoPowerReset(%s)',module_id)
        try:
            m = self.getYoctoPOWER(module_id)
            if m is not None and m.isOnline():
                m.reset()
                _log.debug('yoctoPowerReset suceeded')
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoSERVOattach(self, c:int, module_id:str|None) -> 'YServo|None': # type:ignore[no-any-unimported,unused-ignore]
        _log.debug('yoctoSERVOattach(%s,%s)',c,module_id)
        # check if Servo object for channel c and module_id is already attached
        servos = self.aw.ser.YOCTOservos
        m = next((x for x in servos if
                x.get_functionId() == 'servo'+str(c) and
                (module_id is None or module_id == x.get_serialNumber() or module_id == x.get_logicalName())),
                None)
        if m is not None:
            return m
        # the module/channel is not yet attached search for it
        self.YOCTOimportLIB() # first import the lib
        from yoctopuce.yocto_servo import YServo
        if module_id is None:
            srv = YServo.FirstServo()
            if srv is None:
                return None
            m = srv.get_module()
            target = m.get_serialNumber()
        else:
            target = module_id
        theYOCTOservo = YServo.FindServo(target + '.servo' + str(c))
        module = theYOCTOservo.get_module()
        module.isOnline()
        if theYOCTOservo.isOnline():
            self.aw.ser.YOCTOservos.append(theYOCTOservo) # pyright:ignore[reportUnknownArgumentType]
            return theYOCTOservo
        return None


    def yoctoSERVOenabled(self, c:int, b:bool, module_id:str|None = None) -> None:
        _log.debug('yoctoSERVOenabled(%s,%s,%s)',c,b,module_id)
        try:
            m = self.yoctoSERVOattach(c,module_id)
            if m is not None and m.isOnline():
                m.set_enabled(b)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoSERVOposition(self, c:int, p:int, module_id:str|None = None) -> None:
        _log.debug('yoctoSERVOposition(%s,%s,%s)',c,p,module_id)
        try:
            m = self.yoctoSERVOattach(c,module_id)
            if m is not None and m.isOnline():
                m.set_position(p)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoSERVOmove(self, c:int, p:int, t:int, module_id:str|None = None) -> None:
        _log.debug('yoctoSERVOmove(%s,%s,%s,%s)',c,p,t,module_id)
        try:
            m = self.yoctoSERVOattach(c,module_id)
            if m is not None and m.isOnline():
                m.move(p,t)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoSERVOneutral(self, c:int, n:int, module_id:str|None = None) -> None:
        _log.debug('yoctoSERVOmove(%s,%s,%s)',c,n,module_id)
        try:
            m = self.yoctoSERVOattach(c,module_id)
            if m is not None and m.isOnline():
                m.set_neutral(n)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoSERVOrange(self, c:int, r:int, module_id:str|None = None) -> None:
        _log.debug('yoctoSERVOrange(%s,%s,%s)',c,r,module_id)
        try:
            m = self.yoctoSERVOattach(c,module_id)
            if m is not None and m.isOnline():
                m.set_range(r)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def yoctoSERVOclose(self) -> None:
        _log.debug('yoctoSERVOclose')
        self.aw.ser.YOCTOservos = []
        try:
            YAPI.FreeAPI()
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def phidgetStepperAttach(self, channel:int, serial:str|None = None) -> None:
        if serial not in self.aw.ser.PhidgetStepperMotor:
            if self.aw.qmc.phidgetManager is None:
                self.aw.qmc.startPhidgetManager()
            if self.aw.qmc.phidgetManager is not None:
                s,p = self.serialString2serialPort(serial)
                # try to attach a Phidget STC1005 module
                ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetStepper',DeviceID.PHIDID_STC1005,
                            remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                ports = 1
                # try to attach an Phidget STC1002 module
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetRCServo',DeviceID.PHIDID_STC1002,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 1

                if ser is not None:
                    self.aw.ser.PhidgetStepperMotor[serial] = []
                    for i in range(ports):
                        stepper = Stepper()
                        if port is not None:
                            stepper.setHubPort(port)
                        stepper.setDeviceSerialNumber(ser)
                        stepper.setChannel(i)
                        if self.aw.qmc.phidgetRemoteOnlyFlag and self.aw.qmc.phidgetRemoteFlag:
                            stepper.setIsRemote(True)
                            stepper.setIsLocal(False)
                        self.aw.ser.PhidgetStepperMotor[serial].append(stepper)
        try:
            ch = self.aw.ser.PhidgetStepperMotor[serial][channel]
            ch.setOnAttachHandler(self.phidgetOUTattached)
            ch.setOnDetachHandler(self.phidgetOUTdetached)
            if not ch.getAttached():
                if self.aw.qmc.phidgetRemoteFlag:
                    ch.openWaitForAttachment(3000)
                else:
                    ch.openWaitForAttachment(1500)
                if serial is None and ch.getAttached():
                    # we make this also accessible via its serial number + port
                    si = self.serialPort2serialString(ch.getDeviceSerialNumber(),ch.getHubPort())
                    if si is not None:
                        self.aw.ser.PhidgetStepperMotor[si] = self.aw.ser.PhidgetStepperMotor[None]
        except Exception: # pylint: disable=broad-except
            pass


    def phidgetStepperRescale(self, channel:int, value:float, serial:str|None = None) -> None:
        _log.debug('phidgetStepperRescale(%s,%s,%s)',channel,value,serial)
        self.phidgetStepperAttach(channel,serial)
        if serial in self.aw.ser.PhidgetStepperMotor and len(self.aw.ser.PhidgetStepperMotor[serial])>channel:
            cast(Stepper, self.aw.ser.PhidgetStepperMotor[serial][channel]).setRescaleFactor(value) # type:ignore[no-any-unimported]


    def phidgetStepperSet(self, channel:int, value:float, serial:str|None = None) -> None:
        _log.debug('phidgetStepperSet(%s,%s,%s)',channel,value,serial)
        self.phidgetStepperAttach(channel,serial)
        if serial in self.aw.ser.PhidgetStepperMotor and len(self.aw.ser.PhidgetStepperMotor[serial])>channel:
            cast(Stepper, self.aw.ser.PhidgetStepperMotor[serial][channel]).setTargetPosition(value) # type:ignore[no-any-unimported]


    def phidgetStepperEngaged(self, channel:int, state:bool, serial:str|None = None) -> None:
        _log.debug('phidgetStepperEngaged(%s,%s,%s)',channel,state,serial)
        self.phidgetStepperAttach(channel,serial)
        if serial in self.aw.ser.PhidgetStepperMotor and len(self.aw.ser.PhidgetStepperMotor[serial])>channel:
            cast(Stepper, self.aw.ser.PhidgetStepperMotor[serial][channel]).setEngaged(state) # type:ignore[no-any-unimported]


    def phidgetStepperClose(self) -> None:
        _log.debug('phidgetStepperClose')
        for c in self.aw.ser.PhidgetStepperMotor:
            st = self.aw.ser.PhidgetStepperMotor[c]
            for i, _ in enumerate(st):
                try:
                    if st[i].getAttached():
                        cast(Stepper, st[i]).setEngaged(False) # type:ignore[no-any-unimported]
                        self.phidgetOUTdetached(st[i])
                    st[i].close()
                except Exception: # pylint: disable=broad-except
                    pass
        self.aw.ser.PhidgetStepperMotor = {}


    def phidgetRCattach(self, channel:int, serial:str|None = None) -> None:
        _log.debug('phidgetRCattach(%s,%s)',channel,serial)
        if serial not in self.aw.ser.PhidgetRCServo:
            if self.aw.qmc.phidgetManager is None:
                self.aw.qmc.startPhidgetManager()
            if self.aw.qmc.phidgetManager is not None:
                # try to attach an Phidget RCC1000 module
                s,p = self.serialString2serialPort(serial)
                ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetRCServo',DeviceID.PHIDID_RCC1000,
                            remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                ports = 16
                # try to attach an Phidget RCC0004 module
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetRCServo',DeviceID.PHIDID_RCC0004,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 8
                # try to attach an Phidget RCC1061 module
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetRCServo',DeviceID.PHIDID_1061,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 8
                # try to attach an Phidget RCC1066 module
                if ser is None:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget('PhidgetRCServo',DeviceID.PHIDID_1066,
                                    remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag,serial=s,hubport=p)
                    ports = 1
                if ser is not None:
                    self.aw.ser.PhidgetRCServo[serial] = []
                    for i in range(ports):
                        rcservo = RCServo()
                        if port is not None:
                            rcservo.setHubPort(port)
                        rcservo.setDeviceSerialNumber(ser)
                        rcservo.setChannel(i)
                        if self.aw.qmc.phidgetRemoteOnlyFlag and self.aw.qmc.phidgetRemoteFlag:
                            rcservo.setIsRemote(True)
                            rcservo.setIsLocal(False)
                        self.aw.ser.PhidgetRCServo[serial].append(rcservo)
        try:
            ch = self.aw.ser.PhidgetRCServo[serial][channel]
            ch.setOnAttachHandler(self.phidgetOUTattached)
            ch.setOnDetachHandler(self.phidgetOUTdetached)
            if not ch.getAttached():
                if self.aw.qmc.phidgetRemoteFlag:
                    ch.openWaitForAttachment(3000)
                else:
                    ch.openWaitForAttachment(1500)
                if serial is None and ch.getAttached():
                    # we make this also accessible via its serial number + port
                    si = self.serialPort2serialString(ch.getDeviceSerialNumber(),ch.getHubPort())
                    if si is not None:
                        self.aw.ser.PhidgetRCServo[si] = self.aw.ser.PhidgetRCServo[None]
        except Exception: # pylint: disable=broad-except
            pass


    def phidgetRCpulse(self, channel:int, min_pulse:int, max_pulse:int, serial:str|None = None) -> None:
        _log.debug('phidgetRCpulse(%s,%s,%s,%s)',channel,min_pulse,max_pulse,serial)
        self.phidgetRCattach(channel,serial)
        if serial in self.aw.ser.PhidgetRCServo and len(self.aw.ser.PhidgetRCServo[serial])>channel:
            servo:RCServo = cast(RCServo, self.aw.ser.PhidgetRCServo[serial][channel]) # type:ignore[no-any-unimported]
            servo.setMinPulseWidth(min_pulse)
            servo.setMaxPulseWidth(max_pulse)


    def phidgetRCpos(self, channel:int, min_pos:float, max_pos:float, serial:str|None = None) -> None:
        _log.debug('phidgetRCpos(%s,%s,%s,%s)',channel,min_pos,max_pos,serial)
        self.phidgetRCattach(channel,serial)
        if serial in self.aw.ser.PhidgetRCServo and len(self.aw.ser.PhidgetRCServo[serial])>channel:
            servo:RCServo = cast(RCServo, self.aw.ser.PhidgetRCServo[serial][channel]) # type:ignore[no-any-unimported]
            servo.setMinPosition(min_pos)
            servo.setMaxPosition(max_pos)


    def phidgetRCengaged(self, channel:int, state:bool, serial:str|None = None) -> None:
        _log.debug('phidgetRCengaged(%s,%s,%s)',channel,state,serial)
        self.phidgetRCattach(channel,serial)
        if serial in self.aw.ser.PhidgetRCServo and len(self.aw.ser.PhidgetRCServo[serial])>channel:
            cast(RCServo, self.aw.ser.PhidgetRCServo[serial][channel]).setEngaged(state) # type:ignore[no-any-unimported]


    def phidgetRCset(self, channel:int, position:float, serial:str|None = None) -> None:
        _log.debug('phidgetRCset(%s,%s,%s)',channel,position,serial)
        self.phidgetRCattach(channel,serial)
        if serial in self.aw.ser.PhidgetRCServo and len(self.aw.ser.PhidgetRCServo[serial])>channel:
            cast(RCServo, self.aw.ser.PhidgetRCServo[serial][channel]).setTargetPosition(position) # type:ignore[no-any-unimported]


    def phidgetRCspeedRamping(self, channel:int, state:bool, serial:str|None = None) -> None:
        _log.debug('phidgetRCspeedRamping(%s,%s,%s)',channel,state,serial)
        self.phidgetRCattach(channel,serial)
        if serial in self.aw.ser.PhidgetRCServo and len(self.aw.ser.PhidgetRCServo[serial])>channel:
            cast(RCServo, self.aw.ser.PhidgetRCServo[serial][channel]).setSpeedRampingState(state) # type:ignore[no-any-unimported]


    def phidgetRCvoltage(self, channel:int, volt:float, serial:str|None = None) -> None:
        _log.debug('phidgetRCvoltage(%s,%s,%s)',channel,volt,serial)
        self.phidgetRCattach(channel,serial)
        if serial in self.aw.ser.PhidgetRCServo and len(self.aw.ser.PhidgetRCServo[serial])>channel:
            from Phidget22.RCServoVoltage import RCServoVoltage # type: ignore[import-untyped]
            if volt>6:
                # set to 7.4V
                v = RCServoVoltage.RCSERVO_VOLTAGE_7_4V
            elif volt < 6:
                # set to 5V
                v = RCServoVoltage.RCSERVO_VOLTAGE_5V
            else:
                # set to 6V
                v = RCServoVoltage.RCSERVO_VOLTAGE_6V
            cast(RCServo, self.aw.ser.PhidgetRCServo[serial][channel]).setVoltage(v) # type:ignore[no-any-unimported]


    def phidgetRCaccel(self, channel:int, accel:float, serial:str|None = None) -> None:
        _log.debug('phidgetRCaccel(%s,%s,%s)',channel,accel,serial)
        self.phidgetRCattach(channel,serial)
        if serial in self.aw.ser.PhidgetRCServo and len(self.aw.ser.PhidgetRCServo[serial])>channel:
            cast(RCServo, self.aw.ser.PhidgetRCServo[serial][channel]).setAcceleration(accel) # type:ignore[no-any-unimported]


    def phidgetRCveloc(self, channel:int, veloc:float, serial:str|None = None) -> None:
        _log.debug('phidgetRCveloc(%s,%s,%s)',channel,veloc,serial)
        self.phidgetRCattach(channel,serial)
        if serial in self.aw.ser.PhidgetRCServo and len(self.aw.ser.PhidgetRCServo[serial])>channel:
            cast(RCServo, self.aw.ser.PhidgetRCServo[serial][channel]).setVelocityLimit(veloc) # type:ignore[no-any-unimported]


    def phidgetRCclose(self) -> None:
        _log.debug('phidgetRCclose')
        for c in self.aw.ser.PhidgetRCServo:
            rc = self.aw.ser.PhidgetRCServo[c]
            for i, _ in enumerate(rc):
                try:
                    if rc[i].getAttached():
                        cast(RCServo, rc[i]).setEngaged(False) # type:ignore[no-any-unimported]
                        self.phidgetOUTdetached(rc[i])
                    rc[i].close()
                except Exception: # pylint: disable=broad-except
                    pass
        self.aw.ser.PhidgetRCServo = {}


    def phidget1018SensorChanged(self, v:float, channel:int, idx:int, API:str) -> None:
        if self.PhidgetIO and len(self.PhidgetIO) > idx:
            if API == 'current' or (API == 'voltage' and not self.aw.qmc.phidget1018_ratio[channel]):
                v = v * self.aw.qmc.phidget1018valueFactor
            try:
                #### lock shared resources #####
                self.PhidgetIOsemaphores[channel].acquire(1)
                self.PhidgetIOvalues[channel].append((v,libtime.time()))
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            finally:
                if self.PhidgetIOsemaphores[channel].available() < 1:
                    self.PhidgetIOsemaphores[channel].release(1)


    def phidget1018getSensorReading(self, i:int, idx:int, deviceType:int, API:str='voltage') -> float:
        if self.PhidgetIO and len(self.PhidgetIO) > idx:
            if API != 'digital' and self.aw.qmc.phidget1018_async[i]:
                res:float|None = None
                try:
                    #### lock shared resources #####
                    self.PhidgetIOsemaphores[i].acquire(1)
                    now = libtime.time()
                    start_of_interval = now-self.aw.qmc.delay/1000
                    # 1. just consider async readings taken within the previous sampling interval
                    # and associate them with the (arrival) time since the begin of that interval
                    valid_readings = [(r,t - start_of_interval) for (r,t) in self.PhidgetIOvalues[i] if t > start_of_interval]
                    if len(valid_readings) > 0:
                        # 2. calculate the value
                        # we take the median of all valid_readings weighted by the time of arrival, preferrring newer readings
                        readings = [r for (r,t) in valid_readings]
                        weights = [t for (r,t) in valid_readings]
                        import wquantiles
                        res = float(wquantiles.median(numpy.array(readings),numpy.array(weights))) # pyright: ignore[reportArgumentType]
                        # 3. consume old readings
                        self.PhidgetIOvalues[i] = []
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                    self.PhidgetIOvalues[i] = []
                finally:
                    if self.PhidgetIOsemaphores[i].available() < 1:
                        self.PhidgetIOsemaphores[i].release(1)
                if res is None:
                    if self.PhidgetIOlastvalues[i] == -1: # there is no last value yet, we take a sync value
                        if API == 'current':
                            res = float(cast(CurrentInput, self.PhidgetIO[idx]).getCurrent()) * self.aw.qmc.phidget1018valueFactor # type:ignore[no-any-unimported]
                        elif API == 'frequency':
                            res = float(cast(FrequencyCounter, self.PhidgetIO[idx]).getFrequency()) # type:ignore[no-any-unimported]
                        elif self.aw.qmc.phidget1018_ratio[i] and deviceType != DeviceID.PHIDID_DAQ1400:
                            res = float(cast(VoltageRatioInput, self.PhidgetIO[idx]).getVoltageRatio()) # type:ignore[no-any-unimported]
                        else:
                            res = float(cast(VoltageInput, self.PhidgetIO[idx]).getVoltage()) * self.aw.qmc.phidget1018valueFactor # type:ignore[no-any-unimported]
                        self.PhidgetIOlastvalues[i] = res # pyright: ignore[reportCallIssue, reportArgumentType]
                        return res # pyright: ignore[reportReturnType]
                    return self.PhidgetIOlastvalues[i] # return the previous result
                self.PhidgetIOlastvalues[i] = res
                return res
            if API == 'digital':
                return int(cast(DigitalInput, self.PhidgetIO[idx]).getState()) # type:ignore[no-any-unimported]
            if API == 'current':
                return float(cast(CurrentInput, self.PhidgetIO[idx]).getCurrent()) * self.aw.qmc.phidget1018valueFactor # type:ignore[no-any-unimported]
            if API == 'frequency':
                return float(cast(FrequencyCounter, self.PhidgetIO[idx]).getFrequency()) # type:ignore[no-any-unimported]
            if self.aw.qmc.phidget1018_ratio[i] and deviceType != DeviceID.PHIDID_DAQ1400:
                return float(cast(VoltageRatioInput, self.PhidgetIO[idx]).getVoltageRatio()) # type:ignore[no-any-unimported]
            return float(cast(VoltageInput, self.PhidgetIO[idx]).getVoltage()) * self.aw.qmc.phidget1018valueFactor # type:ignore[no-any-unimported]
        return -1


    def configure1018(self, deviceType:int, idx:int, API:str = 'voltage') -> None:
        # set data rates of all active inputs to 4ms
        if self.PhidgetIO is not None and len(self.PhidgetIO) > idx:
            # reset async values
            channel:int
            if deviceType in [DeviceID.PHIDID_HUB0000]:
                # on VINT HUBs we use the
                channel = self.PhidgetIO[idx].getHubPort()
            else:
                channel = self.PhidgetIO[idx].getChannel()
            # set rate
            try:
                if API != 'digital':
                    cast(VoltageInput|VoltageRatioInput|FrequencyCounter|CurrentInput, self.PhidgetIO[idx]).setDataInterval(self.aw.qmc.phidget1018_dataRates[channel]) # type:ignore[no-any-unimported]
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            # set VCP100x voltage range
            if deviceType in [DeviceID.PHIDID_VCP1000, DeviceID.PHIDID_VCP1001, DeviceID.PHIDID_VCP1002]:
                try:
                    voltageRangeIdx = self.aw.qmc.phidgetVCP100x_voltageRanges[channel]
                    cast(VoltageInput, self.PhidgetIO[idx]).setVoltageRange(self.aw.qmc.phidgetVCP100x_voltageRangeValues[voltageRangeIdx]) # type:ignore[no-any-unimported]
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
            # set the PowerSupply for the DAQ1400
            if deviceType == DeviceID.PHIDID_DAQ1400:
                try:
                    from Phidget22.PowerSupply import PowerSupply # type: ignore[import-untyped]
                    power_idx = self.aw.qmc.phidgetDAQ1400_powerSupply
                    if power_idx == 0:
                        power = PowerSupply.POWER_SUPPLY_OFF
                    elif power_idx == 1:
                        power = PowerSupply.POWER_SUPPLY_12V
                    else: # power_idx == 2:
                        power = PowerSupply.POWER_SUPPLY_24V
                    cast(DigitalInput|VoltageInput|FrequencyCounter|CurrentInput, self.PhidgetIO[idx]).setPowerSupply(power) # type:ignore[no-any-unimported]
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
            if API == 'voltage':
                if self.aw.qmc.phidget1018_async[channel]:
                    try:
                        if self.aw.qmc.phidget1018_ratio[channel] and deviceType != DeviceID.PHIDID_DAQ1400:
                            ct = max(min(float(self.aw.qmc.phidget1018_changeTriggers[channel]/100.0),
                                cast(VoltageRatioInput, self.PhidgetIO[idx]).getMaxVoltageRatioChangeTrigger()), # type:ignore[no-any-unimported]
                                cast(VoltageRatioInput, self.PhidgetIO[idx]).getMinVoltageRatioChangeTrigger()) # type:ignore[no-any-unimported]
                            cast(VoltageRatioInput, self.PhidgetIO[idx]).setVoltageRatioChangeTrigger(ct) # type:ignore[no-any-unimported]
                        else:
                            ct = max(min(float(
                                self.aw.qmc.phidget1018_changeTriggers[channel]/100.0),
                                cast(VoltageInput, self.PhidgetIO[idx]).getMaxVoltageChangeTrigger()), # type:ignore[no-any-unimported]
                                cast(VoltageInput, self.PhidgetIO[idx]).getMinVoltageChangeTrigger()) # type:ignore[no-any-unimported]
                            cast(VoltageInput, self.PhidgetIO[idx]).setVoltageChangeTrigger(ct) # type:ignore[no-any-unimported]
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                    if self.aw.qmc.phidget1018_ratio[channel] and deviceType != DeviceID.PHIDID_DAQ1400:
                        cast(VoltageRatioInput, self.PhidgetIO[idx]).setOnVoltageRatioChangeHandler(lambda _,t: self.phidget1018SensorChanged(t,channel,idx,API)) # type:ignore[no-any-unimported]
                    else:
                        cast(VoltageInput, self.PhidgetIO[idx]).setOnVoltageChangeHandler(lambda _,t: self.phidget1018SensorChanged(t,channel,idx,API)) # type:ignore[no-any-unimported]
                else:
                    if self.aw.qmc.phidget1018_ratio[channel] and deviceType != DeviceID.PHIDID_DAQ1400:
                        cast(VoltageRatioInput, self.PhidgetIO[idx]).setVoltageRatioChangeTrigger(0.0) # type:ignore[no-any-unimported]
                    else:
                        cast(VoltageInput, self.PhidgetIO[idx]).setVoltageChangeTrigger(0.0) # type:ignore[no-any-unimported]
                    if self.aw.qmc.phidget1018_ratio[channel] and deviceType != DeviceID.PHIDID_DAQ1400:
                        cast(VoltageRatioInput, self.PhidgetIO[idx]).setOnVoltageRatioChangeHandler(lambda *_:None) # type:ignore[no-any-unimported]
                    else:
                        cast(VoltageInput, self.PhidgetIO[idx]).setOnVoltageChangeHandler(lambda *_:None) # type:ignore[no-any-unimported]
            elif API == 'current':
                if self.aw.qmc.phidget1018_async[channel]:
                    ct = max(min(float(self.aw.qmc.phidget1018_changeTriggers[channel]/100.0),
                        cast(CurrentInput, self.PhidgetIO[idx]).getMaxCurrentChangeTrigger()), # type:ignore[no-any-unimported]
                        cast(CurrentInput, self.PhidgetIO[idx]).getMinCurrentChangeTrigger())  # type:ignore[no-any-unimported]
                    cast(CurrentInput, self.PhidgetIO[idx]).setCurrentChangeTrigger(ct)  # type:ignore[no-any-unimported]
                    cast(CurrentInput, self.PhidgetIO[idx]).setOnCurrentChangeHandler(lambda _,t: self.phidget1018SensorChanged(t,channel,idx,API))  # type:ignore[no-any-unimported]
                else:
                    cast(CurrentInput, self.PhidgetIO[idx]).setCurrentChangeTrigger(0.0)  # type:ignore[no-any-unimported]
                    cast(CurrentInput, self.PhidgetIO[idx]).setOnCurrentChangeHandler(lambda *_:None)  # type:ignore[no-any-unimported]
            elif API == 'frequency':
                if deviceType == DeviceID.PHIDID_DAQ1400:
                    # set the InputMode for the DAQ1400
                    self.setDAQ1400inputMode(idx)
                if self.aw.qmc.phidget1018_async[channel]:
                    cast(FrequencyCounter, self.PhidgetIO[idx]).setOnFrequencyChangeHandler(lambda _,t: self.phidget1018SensorChanged(t,channel,idx,API))  # type:ignore[no-any-unimported]
                else:
                    cast(FrequencyCounter, self.PhidgetIO[idx]).setOnFrequencyChangeHandler(lambda *_:None)  # type:ignore[no-any-unimported]
            elif API == 'digital' and deviceType == DeviceID.PHIDID_DAQ1400:
                # set the InputMode for the DAQ1400
                self.setDAQ1400inputMode(idx)
            self.PhidgetIOvalues[channel] = []
            self.PhidgetIOlastvalues = [-1.0]*8


    def setDAQ1400inputMode(self, idx:int) -> None:
        if self.PhidgetIO is not None:
            try:
                from Phidget22.InputMode import InputMode # type: ignore[import-untyped]
                mode_idx = self.aw.qmc.phidgetDAQ1400_inputMode
                if mode_idx == 0:
                    mode = InputMode.INPUT_MODE_NPN
                else: #if mode_idx == 1:
                    mode = InputMode.INPUT_MODE_PNP
                cast(FrequencyCounter|DigitalInput, self.PhidgetIO[idx]).setInputMode(mode)  # type:ignore[no-any-unimported]
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)


    def phidget1018attached(self, serial:int, port:int|None, className:str, deviceType:int, idx:int, API:str='voltage') -> None:
        _log.debug('phidget1018attached(%s,%s,%s,%s,%s,%s)',serial,port,className,deviceType,idx,API)
        try:
            self.configure1018(deviceType,idx,API)
            if self.PhidgetIO is not None and self.aw.qmc.phidgetManager is not None:
                channel:int = self.PhidgetIO[idx].getChannel()
                self.aw.qmc.phidgetManager.reserveSerialPort(serial,port,channel,className,deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if channel == 0:
                    if deviceType == DeviceID.PHIDID_1011:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget IO 2/2/2 attached'))
                    elif deviceType == DeviceID.PHIDID_HUB0000:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget IO 6/6/6 attached'))
                    elif deviceType == DeviceID.PHIDID_1010_1013_1018_1019:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget IO 8/8/8 attached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1000:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1000 attached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1200:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1200 attached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1300:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1300 attached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1301:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1301 attached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1400:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1400 attached'))
                    elif deviceType == DeviceID.PHIDID_VCP1000:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget VCP1000 attached'))
                    elif deviceType == DeviceID.PHIDID_VCP1001:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget VCP1001 attached'))
                    elif deviceType == DeviceID.PHIDID_VCP1002:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget VCP1002 attached'))
                    else:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget IO attached'))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def phidget1018detached(self,serial:int, port:int|None, className:str, deviceType:int, idx:int) -> None:
        _log.debug('phidget1018detached(%s,%s,%s,%s,%s)',serial,port,className,deviceType,idx)
        try:
            if self.PhidgetIO is not None and self.aw.qmc.phidgetManager is not None:
                channel:int = self.PhidgetIO[idx].getChannel()
                self.aw.qmc.phidgetManager.releaseSerialPort(serial,port,channel,className,deviceType,remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if channel == 0:
                    if deviceType == DeviceID.PHIDID_1011:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget IO 2/2/2 detached'))
                    elif deviceType == DeviceID.PHIDID_HUB0000:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget IO 6/6/6 detached'))
                    elif deviceType == DeviceID.PHIDID_1010_1013_1018_1019:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget IO 8/8/8 detached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1000:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1000 detached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1200:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1200 detached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1300:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1300 detached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1301:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1301 detached'))
                    elif deviceType == DeviceID.PHIDID_DAQ1400:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget DAQ1400 detached'))
                    elif deviceType == DeviceID.PHIDID_VCP1000:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget VCP1000 detached'))
                    elif deviceType == DeviceID.PHIDID_VCP1001:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget VCP1001 detached'))
                    elif deviceType == DeviceID.PHIDID_VCP1002:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget VCP1002 detached'))
                    else:
                        self.aw.sendmessage(QApplication.translate('Message','Phidget IO detached'))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)


    def PHIDGET1018values(self, deviceType:int = DeviceID.PHIDID_1010_1013_1018_1019, mode:int = 0, API:str = 'voltage', retry:bool = True, single:bool = False) -> tuple[float, float]:

        try:
            if self.PhidgetIO is None and self.aw.qmc.phidgetManager is not None:
                ser:int|None = None
                port:int|None = None
                if API == 'digital':
                    tp = 'PhidgetDigitalInput'
                elif API == 'current':
                    tp = 'PhidgetCurrentInput'
                elif API == 'frequency':
                    tp = 'PhidgetFrequencyCounter'
                elif self.aw.qmc.phidget1018_ratio[mode*2] and deviceType != DeviceID.PHIDID_DAQ1400:
                    tp = 'PhidgetVoltageRatioInput'
                else:
                    tp = 'PhidgetVoltageInput'
                if mode == 0:
                    # we scan for available main device
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(tp,deviceType,0,
                        remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                elif mode == 1:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(tp,deviceType,2,
                        remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                elif mode == 2:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(tp,deviceType,4,
                        remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                elif mode == 3:
                    ser,port = self.aw.qmc.phidgetManager.getFirstMatchingPhidget(tp,deviceType,6,
                        remote=self.aw.qmc.phidgetRemoteFlag,remoteOnly=self.aw.qmc.phidgetRemoteOnlyFlag)
                if ser is not None:
                    if API == 'digital':
                        self.PhidgetIO = [DigitalInput(),DigitalInput()]
                    elif API == 'current':
                        self.PhidgetIO = [CurrentInput(),CurrentInput()]
                    elif API == 'frequency':
                        self.PhidgetIO = [FrequencyCounter(),FrequencyCounter()]
                    else: # voltage
                        if self.aw.qmc.phidget1018_ratio[mode*2] and deviceType != DeviceID.PHIDID_DAQ1400:
                            ch1 = VoltageRatioInput()
                        else:
                            ch1 = VoltageInput()
                        if self.aw.qmc.phidget1018_ratio[mode*2+1] and deviceType != DeviceID.PHIDID_DAQ1400:
                            ch2 = VoltageRatioInput()
                        else:
                            ch2 = VoltageInput()
                        self.PhidgetIO = [ch1,ch2]
                    try:
                        if len(self.PhidgetIO)>0:
                            self.PhidgetIO[0].setOnAttachHandler(lambda _:self.phidget1018attached(ser,port,tp,deviceType,0,API))
                            self.PhidgetIO[0].setOnDetachHandler(lambda _:self.phidget1018detached(ser,port,tp,deviceType,0))
                        if deviceType != DeviceID.PHIDID_DAQ1400 and not single and len(self.PhidgetIO)>1:
                            self.PhidgetIO[1].setOnAttachHandler(lambda _:self.phidget1018attached(ser,port,tp,deviceType,1,API))
                            self.PhidgetIO[1].setOnDetachHandler(lambda _:self.phidget1018detached(ser,port,tp,deviceType,1))
                        if deviceType in [DeviceID.PHIDID_HUB0000]:
                            # we are looking to attach a HUB port
                            if len(self.PhidgetIO)>0:
                                self.PhidgetIO[0].setIsHubPortDevice(1)
                            if len(self.PhidgetIO)>1:
                                self.PhidgetIO[1].setIsHubPortDevice(1)
                            # on VINT HUB devices we have to set the port
                            if len(self.PhidgetIO)>0:
                                self.PhidgetIO[0].setHubPort(mode*2)
                            if len(self.PhidgetIO)>1:
                                self.PhidgetIO[1].setHubPort(mode*2+1)
                        else:
                            if len(self.PhidgetIO)>0:
                                self.PhidgetIO[0].setChannel(mode*2)
                            if len(self.PhidgetIO)>1:
                                self.PhidgetIO[1].setChannel(mode*2+1)
                            if port is not None:
                                if len(self.PhidgetIO)>0:
                                    self.PhidgetIO[0].setHubPort(port)
                                if len(self.PhidgetIO)>1:
                                    self.PhidgetIO[1].setHubPort(port)
                        if self.aw.qmc.phidgetRemoteFlag:
                            self.addPhidgetServer()
                        self.PhidgetIO[0].setDeviceSerialNumber(ser)
                        try:
                            if len(self.PhidgetIO)>0:
                                self.PhidgetIO[0].open() #.openWaitForAttachment(timeout)
                        except Exception: # pylint: disable=broad-except
                            pass
                        self.PhidgetIO[1].setDeviceSerialNumber(ser)
                        if deviceType != DeviceID.PHIDID_DAQ1400 and not single and len(self.PhidgetIO)>1:
                            try:
                                self.PhidgetIO[1].open() #.openWaitForAttachment(timeout)
                            except Exception: # pylint: disable=broad-except
                                pass
                        # we need to give this device a bit time to attach, otherwise it will be considered for another Artisan channel of the same type
                        if self.aw.qmc.phidgetRemoteOnlyFlag:
                            libtime.sleep(.8)
                        else:
                            libtime.sleep(.5)
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                        #_, _, exc_tb = sys.exc_info()
                        #self.aw.qmc.adderror((QApplication.translate("Error Message","Exception:") + " PHIDGET1018values() {0}").format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
                        try:
                            if self.PhidgetIO and self.PhidgetIO[0].getAttached():
                                self.PhidgetIO[0].close()
                            if self.PhidgetIO and len(self.PhidgetIO)> 1 and self.PhidgetIO[1].getAttached():
                                self.PhidgetIO[1].close()
                        except Exception: # pylint: disable=broad-except
                            pass
                        self.PhidgetIO = None
                        self.PhidgetIOvalues = [[], [], [], [], [], [], [], []]
                        self.PhidgetIOlastvalues = [-1.0]*8
            if deviceType == DeviceID.PHIDID_DAQ1400 and self.PhidgetIO is not None and self.PhidgetIO and self.PhidgetIO[0].getAttached():
                probe:float = -1
                try:
                    probe = self.phidget1018getSensorReading(0,0,deviceType,API)
                except PhidgetException:
                    pass  # the value might be still unknown. This can happen right after attach.
                except Exception: # pylint: disable=broad-except
                    pass
                return probe, -1
            if deviceType != DeviceID.PHIDID_DAQ1400 and self.PhidgetIO is not None and self.PhidgetIO and len(self.PhidgetIO)>1 and self.PhidgetIO[0].getAttached() and (single or self.PhidgetIO[1].getAttached()):
                probe1:float = -1.
                probe2:float = -1.
                try:
                    probe1 = self.phidget1018getSensorReading(mode*2,0,deviceType,API)
                except PhidgetException:
                    pass  # the value might be still unknown. This can happen right after attach.
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                if not single:
                    try:
                        probe2 = self.phidget1018getSensorReading(mode*2 + 1,1,deviceType,API)
                    except PhidgetException:
                        pass  # the value might be still unknown. This can happen right after attach.
                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                return probe1, probe2
            if retry:
                libtime.sleep(0.1)
                return self.PHIDGET1018values(deviceType,mode,API,False)
            return -1,-1
        except Exception as ex: # pylint: disable=broad-except
            _log.exception(ex)
            try:
                if self.PhidgetIO and self.PhidgetIO[0].getAttached():
                    self.PhidgetIO[0].close()
                if not single and self.PhidgetIO and len(self.PhidgetIO)> 1 and self.PhidgetIO[1].getAttached():
                    self.PhidgetIO[1].close()
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            self.PhidgetIO = None
            self.PhidgetIOlastvalues = [-1.0]*8
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message','Exception:') + ' PHIDGET1018values() {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
            return -1,-1


    def getNextYOCTOsensorOfType(self,  # type:ignore[no-any-unimported] # pyright: ignore[reportUnknownParameterType]
                    mode:int,
                    connected_yoctos:list[str],
                    YOCTOsensor:'YGenericSensor|YPower|YVoltage|YCurrent|YSensor|YTemperature|None', # pyright: ignore[reportUnknownParameterType]
                    productNameFilter:str|None = None) -> 'YGenericSensor|YPower|YVoltage|YCurrent|YSensor|YTemperature|None':
        if YOCTOsensor is not None:
            productName = YOCTOsensor.get_module().get_productName()
            if (YOCTOsensor.get_hardwareId() not in connected_yoctos) and  \
                ((mode == 0 and productName.startswith('Yocto-Thermocouple')) or (mode == 1 and productName.startswith('Yocto-PT100')) or \
                 (mode == 2 and productName.startswith('Yocto-Temperature-IR')) or \
                 (mode == 3 and productName.startswith('Yocto-Meteo')) or \
                 (mode == 4 and productName is not None and productName.startswith(productNameFilter)) or # pyrefly: ignore[bad-argument-type] # pyright: ignore[reportArgumentType]
                 (mode in {5, 6, 7, 8} and productName.startswith('Yocto-Watt')) or \
                 (mode == 9)):
                return YOCTOsensor
            if mode == 4:
                from yoctopuce.yocto_genericsensor import YGenericSensor
                return self.getNextYOCTOsensorOfType(mode,connected_yoctos,YGenericSensor.nextGenericSensor(cast(YGenericSensor, YOCTOsensor)),productNameFilter) # type:ignore[no-any-unimported]
            if mode in {5, 6}:
                from yoctopuce.yocto_power import YPower
                return self.getNextYOCTOsensorOfType(mode,connected_yoctos,YPower.nextPower(cast(YPower, YOCTOsensor)),productNameFilter) # type:ignore[no-any-unimported]
            if mode == 7:
                from yoctopuce.yocto_voltage import YVoltage
                return self.getNextYOCTOsensorOfType(mode,connected_yoctos,YVoltage.nextVoltage(cast(YVoltage, YOCTOsensor)),productNameFilter) # type:ignore[no-any-unimported]
            if mode == 8:
                from yoctopuce.yocto_current import YCurrent
                return self.getNextYOCTOsensorOfType(mode,connected_yoctos,YCurrent.nextCurrent(cast(YCurrent, YOCTOsensor)),productNameFilter) # type:ignore[no-any-unimported]
            if mode == 9:
                from yoctopuce.yocto_api import YSensor
                return self.getNextYOCTOsensorOfType(mode,connected_yoctos,YSensor.nextSensor(cast(YSensor, YOCTOsensor)),productNameFilter) # type:ignore[no-any-unimported] # ty:ignore[redundant-cast]
            from yoctopuce.yocto_temperature import YTemperature
            return self.getNextYOCTOsensorOfType(mode,connected_yoctos,YTemperature.nextTemperature(cast(YTemperature, YOCTOsensor)),productNameFilter) # type:ignore[no-any-unimported]
        return None


    def YOCTOimportLIB(self) -> None:
        errmsg=YRefParam()
        if not self.YOCTOlibImported:
            # import Yoctopuce Python library (installed form PyPI)
            #self.aw.sendmessage(str(errmsg))
            YAPI.DisableExceptions()
        try:
            if self.aw.qmc.yoctoRemoteFlag:
                YAPI.RegisterHub(self.aw.qmc.yoctoServerID,errmsg)
            else:
                YAPI.RegisterHub('usb', errmsg)
            self.YOCTOlibImported = True
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            self.aw.sendmessage(str(e))


    def yoctoTimedCallback(self,_:Callable[[], None] , measure:'YMeasure', channel:int) -> None:  # type:ignore[no-any-unimported,unused-ignore]
        try:
            #### lock shared resources #####
            self.YOCTOsemaphores[channel].acquire(1)
            self.YOCTOvalues[channel].append((measure.get_averageValue(),libtime.time()))
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
        finally:
            if self.YOCTOsemaphores[channel].available() < 1:
                self.YOCTOsemaphores[channel].release(1)


    def YOCTOtemperatures(self, mode:int = 0, productNameFilter:str|None = None) -> tuple[float, float]:
        try:
            if self.YOCTOsensor is None:
                self.YOCTOimportLIB()
                try:
                    YAPI.DisableExceptions()
                    # already connected YOCTO sensor channels?
                    connected_yoctos:list[str] = []
                    # check for connected main device
                    if self.aw.ser.YOCTOsensor is not None:
                        if self.aw.ser.YOCTOchan1 is not None and self.aw.ser.YOCTOchan1.isOnline():
                            connected_yoctos.append(self.aw.ser.YOCTOchan1.get_hardwareId())
                        if self.aw.ser.YOCTOchan2 is not None and self.aw.ser.YOCTOchan2.isOnline():
                            connected_yoctos.append(self.aw.ser.YOCTOchan2.get_hardwareId())
                    # check for connected extra devices
                    for s in self.aw.extraser:
                        if s.YOCTOsensor is not None:
                            if s.YOCTOchan1 is not None and s.YOCTOchan1.isOnline():
                                connected_yoctos.append(s.YOCTOchan1.get_hardwareId())
                            if s.YOCTOchan2 is not None and s.YOCTOchan2.isOnline():
                                connected_yoctos.append(s.YOCTOchan2.get_hardwareId())
                    # search for the next one of the required type, but not yet connected
                    if mode == 4:
                        from yoctopuce.yocto_genericsensor import YGenericSensor
                        self.YOCTOsensor = self.getNextYOCTOsensorOfType(mode,connected_yoctos,YGenericSensor.FirstGenericSensor(),productNameFilter) # pyright:ignore[reportUnknownArgumentType]
                    elif mode == 5:
                        from yoctopuce.yocto_power import YPower
                        self.YOCTOsensor = self.getNextYOCTOsensorOfType(mode,connected_yoctos,YPower.FirstPower()) # pyright:ignore[reportUnknownArgumentType]
                    elif mode == 6:
                        # NOTE: as we do not know which functions (mode 5 or 6) are used per power module, we restrict the "Energy" function to report always for the first connected unit only
                        from yoctopuce.yocto_power import YPower
                        self.YOCTOsensor = self.getNextYOCTOsensorOfType(mode,[],YPower.FirstPower()) # pyright:ignore[reportUnknownArgumentType]
                    elif mode == 7:
                        from yoctopuce.yocto_voltage import YVoltage
                        self.YOCTOsensor = self.getNextYOCTOsensorOfType(mode,connected_yoctos,YVoltage.FirstVoltage()) # pyright:ignore[reportUnknownArgumentType]
                    elif mode == 8:
                        from yoctopuce.yocto_current import YCurrent
                        self.YOCTOsensor = self.getNextYOCTOsensorOfType(mode,connected_yoctos,YCurrent.FirstCurrent()) # pyright:ignore[reportUnknownArgumentType]
                    elif mode == 9:
                        from yoctopuce.yocto_api import YSensor
                        self.YOCTOsensor = self.getNextYOCTOsensorOfType(mode,connected_yoctos,YSensor.FirstSensor()) # pyright:ignore[reportUnknownArgumentType]
                    else:
                        from yoctopuce.yocto_temperature import YTemperature
                        self.YOCTOsensor = self.getNextYOCTOsensorOfType(mode,connected_yoctos,YTemperature.FirstTemperature()) # pyright:ignore[reportUnknownArgumentType]

                    yocto_res = 0.0001 # while 0.001 seems to be the maximum accepted (equal to raw resolution), but just returning mostly 2 decimals (as the regular reading is still rounded by that one decimal)!?
                    if mode in {0, 2} and self.YOCTOsensor is not None and self.YOCTOsensor.isOnline():
                        serial = self.YOCTOsensor.get_module().get_serialNumber()
                        from yoctopuce.yocto_temperature import YTemperature
                        self.YOCTOchan1 = YTemperature.FindTemperature(serial + '.temperature1')
                        self.YOCTOchan2 = YTemperature.FindTemperature(serial + '.temperature2')
                        if mode == 0:
                            self.aw.sendmessage(f"{QApplication.translate('Message','Yocto Thermocouple attached')} ({self.YOCTOsensor.get_serialNumber()})")
                        elif mode == 2:
                            self.aw.sendmessage(f"{QApplication.translate('Message','Yocto IR attached')} ({self.YOCTOsensor.get_serialNumber()})")
                        # increase the resolution
                        try:
                            if self.YOCTOchan1 is not None:
                                self.YOCTOchan1.set_resolution(yocto_res)
                        except Exception: # pylint: disable=broad-except
                            pass
                        try:
                            if self.YOCTOchan2 is not None:
                                self.YOCTOchan2.set_resolution(yocto_res)
                        except Exception: # pylint: disable=broad-except
                            pass
                        # get units
                        try:
                            if self.YOCTOchan1 is not None:
                                unit1:str = cast(str, self.YOCTOchan1.get_unit())
                                if len(unit1) > 0 and unit1[-1] != 'C':
                                    self.aw.qmc.YOCTOchan1Unit = 'F'
                                else:
                                    self.aw.qmc.YOCTOchan1Unit = 'C'
                            if self.YOCTOchan2 is not None:
                                unit2:str = cast(str, self.YOCTOchan2.get_unit())
                                if len(unit2) > 0 and unit2[-1] != 'C':
                                    self.aw.qmc.YOCTOchan2Unit = 'F'
                                else:
                                    self.aw.qmc.YOCTOchan2Unit = 'C'
                        except Exception as e: # pylint: disable=broad-except
                            _log.exception(e)
                        if self.aw.qmc.YOCTO_dataRate > 1000:
                            reportFrequency = '60/m' # in this mode the average of a measurements over the last second is returned
                        else:
                            reportFrequency = f'{int(round(1000/self.aw.qmc.YOCTO_dataRate))}/s'   # 30/s => 30ms
                            # if reportFrequency is set to "1/s", every second the last measurement sampled by the device is returned
                            # note that this is different from "60/m" which returns an average over many values

                        if self.YOCTOchan1 is not None:
                            if self.aw.qmc.YOCTO_async[0]:
                                self.YOCTOchan1.set_reportFrequency(reportFrequency)
                                self.YOCTOchan1.registerTimedReportCallback(lambda fct, measure: self.yoctoTimedCallback(fct, measure, 0))  # pyright:ignore[reportUnknownArgumentType]
                            else:
                                self.YOCTOchan1.registerTimedReportCallback(lambda *_:None)
                        if self.YOCTOchan2 is not None:
                            if self.aw.qmc.YOCTO_async[0]: # flag for channel 1 is ignored and only that of channel 0 is respected for both channels
                                self.YOCTOchan2.set_reportFrequency(reportFrequency)
                                self.YOCTOchan2.registerTimedReportCallback(lambda fct,measure: self.yoctoTimedCallback(fct,measure,1)) # pyright:ignore[reportUnknownArgumentType]
                            else:
                                self.YOCTOchan2.registerTimedReportCallback(lambda *_:None)
                        if self.aw.qmc.YOCTO_async[0]:# or self.aw.qmc.YOCTO_async[1]: # flag for channel 1 is ignored and only that of channel 0 is respected for both channels
                            if self.YOCTOthread is None:
                                self.YOCTOthread = YoctoThread()
                            self.YOCTOthread.start()
                    elif mode == 1 and self.YOCTOsensor is not None and self.YOCTOsensor.isOnline():
                        from yoctopuce.yocto_temperature import YTemperature
                        serial = self.YOCTOsensor.get_module().get_serialNumber()
                        self.YOCTOchan1 = YTemperature.FindTemperature(serial + '.temperature')
                        self.YOCTOchan2 = None

                        self.aw.sendmessage(f"{QApplication.translate('Message','Yocto PT100 attached')} ({self.YOCTOsensor.get_serialNumber()})")
                        # increase the resolution
                        try:
                            self.YOCTOsensor.set_resolution(yocto_res)
                        except Exception as e: # pylint: disable=broad-except
                            _log.exception(e)
                        try:
                            self.YOCTOsensor.set_resolution(yocto_res)
                        except Exception as e: # pylint: disable=broad-except
                            _log.exception(e)
                        # get units
                        try:
                            unit:str = cast(str, self.YOCTOsensor.get_unit())
                            if len(unit) > 0 and unit[-1] != 'C':
                                self.aw.qmc.YOCTOchanUnit = 'F'
                            else:
                                self.aw.qmc.YOCTOchanUnit = 'C'
                        except Exception as e: # pylint: disable=broad-except
                            _log.exception(e)
                        if self.aw.qmc.YOCTO_async[0]:
                            if self.aw.qmc.YOCTO_dataRate > 1000:
                                reportFrequency = '60/m' # in this mode the average of a measurements over the last second is returned
                            else:
                                reportFrequency = f'{int(round(1000/self.aw.qmc.YOCTO_dataRate))}/s'   # 30/s => 30ms
                                # if reportFrequency is set to "1/s", every second the last measurement sampled by the device is returned
                                # note that this is different from "60/m" which returns an average over many values
                            self.YOCTOsensor.set_reportFrequency(reportFrequency)
                            self.YOCTOsensor.registerTimedReportCallback(lambda fct,measure: self.yoctoTimedCallback(fct, measure, 0)) # pyright:ignore[reportUnknownArgumentType]
                            if self.YOCTOthread is None:
                                self.YOCTOthread = YoctoThread()
                            self.YOCTOthread.start()
                    elif mode == 4 and self.YOCTOsensor is not None and self.YOCTOsensor.isOnline():
                        from yoctopuce.yocto_genericsensor import YGenericSensor
                        serial=self.YOCTOsensor.get_module().get_serialNumber()
                        self.YOCTOchan1 = YGenericSensor.FindGenericSensor(serial + '.genericSensor1')
                        self.YOCTOchan2 = YGenericSensor.FindGenericSensor(serial + '.genericSensor2')
                        if productNameFilter is not None:
                            self.aw.sendmessage(QApplication.translate('Message',f'{productNameFilter} attached'))
                        else:
                            self.aw.sendmessage(QApplication.translate('Message','Yocto Sensor attached'))
                    elif mode == 5 and self.YOCTOsensor is not None and self.YOCTOsensor.isOnline():
                        from yoctopuce.yocto_power import YPower
                        serial=self.YOCTOsensor.get_module().get_serialNumber()
                        self.YOCTOchan1 = YPower.FindPower(serial + '.power')
                        self.YOCTOchan2 = None
                        self.aw.sendmessage(QApplication.translate('Message','Yocto Watt Power attached'))
                    elif mode == 6 and self.YOCTOsensor is not None and self.YOCTOsensor.isOnline():
                        from yoctopuce.yocto_power import YPower
                        serial=self.YOCTOsensor.get_module().get_serialNumber()
                        self.YOCTOchan1 = YPower.FindPower(serial + '.power')
                        self.YOCTOchan2 = None
                        self.aw.sendmessage(QApplication.translate('Message','Yocto Watt Energy attached'))
                    elif mode == 7 and self.YOCTOsensor is not None and self.YOCTOsensor.isOnline():
                        from yoctopuce.yocto_voltage import YVoltage
                        serial=self.YOCTOsensor.get_module().get_serialNumber()
                        self.YOCTOchan1 = YVoltage.FindVoltage(serial + '.voltage1')
                        self.YOCTOchan2 = YVoltage.FindVoltage(serial + '.voltage2')
                        # increase the resolution
                        try:
                            if self.YOCTOchan1 is not None:
                                self.YOCTOchan1.set_resolution(yocto_res)
                        except Exception: # pylint: disable=broad-except
                            pass
                        try:
                            if self.YOCTOchan2 is not None:
                                self.YOCTOchan2.set_resolution(yocto_res)
                        except Exception: # pylint: disable=broad-except
                            pass
                        self.aw.sendmessage(QApplication.translate('Message','Yocto Watt Voltage attached'))
                    elif mode == 8 and self.YOCTOsensor is not None and self.YOCTOsensor.isOnline():
                        from yoctopuce.yocto_current import YCurrent
                        serial=self.YOCTOsensor.get_module().get_serialNumber()
                        self.YOCTOchan1 = YCurrent.FindCurrent(serial + '.current1')
                        self.YOCTOchan2 = YCurrent.FindCurrent(serial + '.current2')
                        # increase the resolution
                        try:
                            if self.YOCTOchan1 is not None:
                                self.YOCTOchan1.set_resolution(yocto_res)
                        except Exception: # pylint: disable=broad-except
                            pass
                        try:
                            if self.YOCTOchan2 is not None:
                                self.YOCTOchan2.set_resolution(yocto_res)
                        except Exception: # pylint: disable=broad-except
                            pass
                        self.aw.sendmessage(QApplication.translate('Message','Yocto Watt Current attached'))
                    elif mode == 9 and self.YOCTOsensor is not None and self.YOCTOsensor.isOnline():
                        from yoctopuce.yocto_api import YSensor
                        serial=self.YOCTOsensor.get_module().get_serialNumber()
                        self.YOCTOchan1 = self.YOCTOsensor
                        self.YOCTOchan2 = YSensor.nextSensor(self.YOCTOsensor)
                        # increase the resolution
                        try:
                            self.YOCTOchan1.set_resolution(yocto_res)
                        except Exception: # pylint: disable=broad-except
                            pass
                        try:
                            if self.YOCTOchan2 is not None:
                                self.YOCTOchan2.set_resolution(yocto_res)
                        except Exception: # pylint: disable=broad-except
                            pass
                        self.aw.sendmessage(QApplication.translate('Message','Yocto Sensor attached'))
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                    if self.YOCTOthread is not None:
                        self.YOCTOthread.join()
                        self.YOCTOthread = None
            probe1:float = -1
            probe2:float = -1
            if mode in {0, 2}:
                try:
                    if self.aw.qmc.YOCTO_async[0]:
                        try:
                            #### lock shared resources #####
                            self.YOCTOsemaphores[0].acquire(1)
                            now = libtime.time()
                            start_of_interval = now-self.aw.qmc.delay/1000
                            # 1. just consider async readings taken within the previous sampling interval
                            # and associate them with the (arrival) time since the begin of that interval
                            valid_readings = [(r,t - start_of_interval) for (r,t) in self.YOCTOvalues[0] if t > start_of_interval]
                            if len(valid_readings) > 0:
                                # 2. calculate the value
                                # we take the median of all valid_readings weighted by the time of arrival, preferrring newer readings
                                readings = [r for (r,t) in valid_readings]
                                weights = [t for (r,t) in valid_readings]
                                import wquantiles
                                probe1 = float(wquantiles.median(numpy.array(readings),numpy.array(weights))) # pyright: ignore[reportArgumentType]
                                # 3. consume old readings
                                self.YOCTOvalues[0] = []
#                            if len(self.YOCTOvalues[0]) > 0:
##                                probe1 = numpy.average(self.YOCTOvalues[0])
#                                probe1 = numpy.median(self.YOCTOvalues[0])
#                                self.YOCTOvalues[0] = self.YOCTOvalues[0][-max(1,round((self.aw.qmc.delay/self.aw.qmc.YOCTO_dataRate))):]
                        except Exception as e: # pylint: disable=broad-except
                            _log.exception(e)
                            self.YOCTOvalues[0] = []
                        finally:
                            if self.YOCTOsemaphores[0].available() < 1:
                                self.YOCTOsemaphores[0].release(1)
                        if len(self.YOCTOlastvalues)>0:
                            if probe1 == -1:
                                probe1 = self.YOCTOlastvalues[0]
                            else:
                                self.YOCTOlastvalues[0] = probe1
                    if probe1 == -1 and self.YOCTOchan1 and self.YOCTOchan1.isOnline():
                        probe1 = cast(float, self.YOCTOchan1.get_currentValue()) # pyrefly:ignore[redundant-cast]
                    if probe1 != -1:
                        if mode == 2:
                            # we average this module temperature channel for the IR module to remove noise
                            if self.YOCTOtempIRavg is None:
                                self.YOCTOtempIRavg = probe1
                            else:
                                self.YOCTOtempIRavg = (20* self.YOCTOtempIRavg + probe1) / 21.0
                                probe1 = self.YOCTOtempIRavg
                        # convert temperature scale
                        if self.aw.qmc.YOCTOchan1Unit == 'C' and self.aw.qmc.mode == 'F':
                            probe1 = fromCtoFstrict(probe1)
                        elif self.aw.qmc.YOCTOchan1Unit == 'F' and self.aw.qmc.mode == 'C':
                            probe1 = fromFtoCstrict(probe1)
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                try:
                    if self.aw.qmc.YOCTO_async[0]: # flag for channel 1 is ignored and only that of channel 0 is respected for both channels
                        try:
                            #### lock shared resources #####
                            self.YOCTOsemaphores[1].acquire(1)
                            now = libtime.time()
                            start_of_interval = now-self.aw.qmc.delay/1000
                            # 1. just consider async readings taken within the previous sampling interval
                            # and associate them with the (arrival) time since the begin of that interval
                            valid_readings = [(r,t - start_of_interval) for (r,t) in self.YOCTOvalues[1] if t > start_of_interval]
                            if len(valid_readings) > 0:
                                # 2. calculate the value
                                # we take the median of all valid_readings weighted by the time of arrival, preferrring newer readings
                                readings = [r for (r,t) in valid_readings]
                                weights = [t for (r,t) in valid_readings]
                                import wquantiles # @Reimport
                                probe2 = float(wquantiles.median(numpy.array(readings),numpy.array(weights))) # pyright: ignore[reportArgumentType]
                                # 3. consume old readings
                                self.YOCTOvalues[1] = []
#                            if len(self.YOCTOvalues[1]) > 0:
##                                probe2 = numpy.average(self.YOCTOvalues[1])
#                                probe2 = numpy.median(self.YOCTOvalues[1])
#                                self.YOCTOvalues[1] = self.YOCTOvalues[1][-round((self.aw.qmc.delay/self.aw.qmc.YOCTO_dataRate)):]
                        except Exception as e: # pylint: disable=broad-except
                            _log.exception(e)
                            self.YOCTOvalues[1] = []
                        finally:
                            if self.YOCTOsemaphores[1].available() < 1:
                                self.YOCTOsemaphores[1].release(1)
                        if len(self.YOCTOlastvalues)>1:
                            if probe2 == -1:
                                probe2 = self.YOCTOlastvalues[1]
                            else:
                                self.YOCTOlastvalues[1] = probe2
                    if probe2 == -1 and self.YOCTOchan2 and self.YOCTOchan2.isOnline():
                        probe2 = cast(float, self.YOCTOchan2.get_currentValue()) # pyrefly:ignore[redundant-cast]
                    if probe2 != -1:
                        # convert temperature scale
                        if self.aw.qmc.YOCTOchan2Unit == 'C' and self.aw.qmc.mode == 'F':
                            probe2 = fromCtoFstrict(probe2)
                        elif self.aw.qmc.YOCTOchan2Unit == 'F' and self.aw.qmc.mode == 'C':
                            probe2 = fromFtoCstrict(probe2)
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
            elif mode == 1:
                try:
                    if self.aw.qmc.YOCTO_async[0]:
                        try:
                            #### lock shared resources #####
                            self.YOCTOsemaphores[0].acquire(1)
                            if len(self.YOCTOvalues[0]) > 0:
#                                probe1 = float(numpy.average(self.YOCTOvalues[0]))
                                probe1 = cast(float, numpy.median(self.YOCTOvalues[0])) # pyright: ignore[reportGeneralTypeIssues]
                                self.YOCTOvalues[0] = self.YOCTOvalues[0][-round(self.aw.qmc.delay/self.aw.qmc.YOCTO_dataRate):]
                        except Exception as e: # pylint: disable=broad-except
                            _log.exception(e)
                            self.YOCTOvalues[0] = []
                        finally:
                            if self.YOCTOsemaphores[0].available() < 1:
                                self.YOCTOsemaphores[0].release(1)
                        if probe1 == -1:
                            probe1 = self.YOCTOlastvalues[0]
                        else:
                            self.YOCTOlastvalues[0] = probe1
                    if probe1 == -1 and self.YOCTOsensor and self.YOCTOsensor.isOnline():
                        probe1 = cast(float, self.YOCTOsensor.get_currentValue())
                    if probe1 != -1:
                        # convert temperature scale
                        if self.aw.qmc.YOCTOchanUnit == 'C' and self.aw.qmc.mode == 'F':
                            probe1 = fromCtoFstrict(probe1)
                        elif self.aw.qmc.YOCTOchanUnit == 'F' and self.aw.qmc.mode == 'C':
                            probe1 = fromFtoCstrict(probe1)
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
            elif mode == 5:
                try:
                    from yoctopuce.yocto_power import YPower
                    if self.YOCTOchan1 and self.YOCTOchan1.isOnline() and isinstance(self.YOCTOchan1, YPower):
                        probe1 = cast(float, self.YOCTOchan1.get_currentValue())  # pyrefly:ignore[redundant-cast]
                        probe2 = cast(float, self.YOCTOchan1.get_meter())  # pyrefly:ignore[redundant-cast]
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
            elif mode == 6:
                try:
                    from yoctopuce.yocto_power import YPower
                    if self.YOCTOchan1 and self.YOCTOchan1.isOnline() and isinstance(self.YOCTOchan1, YPower):
                        probe1 = cast(float, self.YOCTOchan1.get_deliveredEnergyMeter())  # pyrefly:ignore[redundant-cast]
                        probe2 = cast(float, self.YOCTOchan1.get_receivedEnergyMeter())  # pyrefly:ignore[redundant-cast]
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
            elif mode in {4, 7, 8, 9}:
                try:
                    if self.YOCTOchan1 and self.YOCTOchan1.isOnline():
                        probe1 = cast(float, self.YOCTOchan1.get_currentValue())  # pyrefly:ignore[redundant-cast]
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
                try:
                    if self.YOCTOchan2 and self.YOCTOchan2.isOnline():
                        probe2 = cast(float, self.YOCTOchan2.get_currentValue())  # pyrefly:ignore[redundant-cast]
                except Exception as e: # pylint: disable=broad-except
                    _log.exception(e)
            # apply the emissivity to the IR value
            if mode == 2 and probe1 != -1 and probe2 != -1:
                probe2 = self.IRtemp(self.aw.qmc.YOCTO_emissivity, probe2, probe1)
            return probe1, probe2
        except Exception as ex: # pylint: disable=broad-except
            _log.exception(ex)
            try:
                if self.YOCTOthread is not None:
                    self.YOCTOthread.join()
                    self.YOCTOthread = None
                self.YOCTOsensor = None
                self.YOCTOchan1 = None
                self.YOCTOchan2 = None
                self.YOCTOtempIRavg = None
                self.YOCTOvalues = [[],[]]
                self.YOCTOlastvalues = [-1.0]*2
                YAPI.FreeAPI()
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message','Exception:') + ' YOCTOtemperatures() {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
            return -1,-1


    def ARDUINOTC4temperature(self, chan:str|None = None) -> tuple[float, float]:
        t1:float = -1.
        t2:float = -1.
        res:list[str] = []
        command = ''
        try:
            #### lock shared resources #####
            self.COMsemaphore.acquire(1)
            result = ''
            if not self.SP.is_open:
                self.openport()
                #libtime.sleep(1)
                #Reinitialize Arduino in case communication was interrupted
                self.ArduinoIsInitialized = 0
            if self.SP.is_open:
                #INITIALIZE (ONLY ONCE)
                if not self.ArduinoIsInitialized or chan is not None:
                    self.SP.reset_input_buffer()
                    self.SP.reset_output_buffer()
                    #build initialization command
                    if chan is None:
                        et_channel = self.arduinoETChannel
                        if et_channel == 'None':
                            et_channel = '0'
                        bt_channel = self.arduinoBTChannel
                        if bt_channel == 'None':
                            bt_channel = '0'
                        #If extra device +ArduinoTC4_XX present. read all 4 Ts
                        if 28 in self.aw.qmc.extradevices: # +ArduinoTC4_34
                            vals = ['1','2','3','4']
                            try:
                                if self.arduinoETChannel and self.arduinoETChannel != 'None' and self.arduinoETChannel in vals:
                                    vals.pop(vals.index(self.arduinoETChannel))
                                if self.arduinoBTChannel and self.arduinoBTChannel != 'None' and self.arduinoBTChannel in vals:
                                    vals.pop(vals.index(self.arduinoBTChannel))
                            except Exception: # pylint: disable=broad-except
                                pass
                            command = 'CHAN;' + et_channel + bt_channel + vals[0] + vals[1]
                        else:
                        #no extra device +ArduinoTC4_XX present. reads ambient T, ET, BT
                            command = 'CHAN;' + et_channel + bt_channel + '00'
                    else:
                        command = f'CHAN;{chan}'
                        self.ArduinoIsInitialized = 1
                    #libtime.sleep(0.3)
                    self.SP.write(str2cmd(command + '\n'))       #send command
                    self.SP.flush()
                    libtime.sleep(.1)
                    result = ''
                    try:
                        result = self.SP.readline().decode('utf-8')[:-2]  #read
                    except Exception: # pylint: disable=broad-except
                        pass
                    if (not len(result) == 0 and not result.startswith('#')):
                        raise Exception(QApplication.translate('Error Message','Arduino could not set channels')) # pylint: disable=broad-exception-raised

                    if self.aw.seriallogflag:
                        settings = str(self.comport) + ',' + str(self.baudrate) + ',' + str(self.bytesize)+ ',' + str(self.parity) + ',' + str(self.stopbits) + ',' + str(self.timeout)
                        self.aw.addserial('ArduinoTC4: ' + settings + ' || Tx = ' + str(command) + ' || Rx = ' + str(result))

                    if result.startswith('#') and chan is None:
                        #OK. NOW SET UNITS
                        self.SP.reset_input_buffer()
                        self.SP.reset_output_buffer()
                        command = 'UNITS;' + self.aw.qmc.mode + '\n'   #Set units
                        self.SP.write(str2cmd(command))
                        self.SP.flush()
                        libtime.sleep(.1)
                        result = self.SP.readline().decode('utf-8')[:-2]
                        if (not len(result) == 0 and not result.startswith('#')):
                            raise Exception(QApplication.translate('Error Message','Arduino could not set temperature unit')) # pylint: disable=broad-exception-raised
                        #OK. NOW SET FILTER
                        self.SP.reset_input_buffer()
                        self.SP.reset_output_buffer()
#                        filt =  ','.join(map(str,self.aw.ser.ArduinoFILT))
                        filt =  ','.join([str(f) for f in self.aw.ser.ArduinoFILT])
                        command = 'FILT;' + filt + '\n'   #Set filters
                        self.SP.write(str2cmd(command))
                        result = self.SP.readline().decode('utf-8')[:-2]
                        if (not len(result) == 0 and not result.startswith('#')):
                            raise Exception(QApplication.translate('Error Message','Arduino could not set filters')) # pylint: disable=broad-exception-raised
                        ### EVERYTHING OK  ###
                        self.ArduinoIsInitialized = 1
                        self.aw.sendmessage(QApplication.translate('Message','TC4 initialized'))
                #READ TEMPERATURE
                command = 'READ\n'  #Read command.
                self.SP.reset_input_buffer()
                self.SP.reset_output_buffer()
                self.SP.write(str2cmd(command))
                self.SP.flush()
                libtime.sleep(.1)
                rl = self.SP.readline().decode('utf-8', 'ignore')[:-2]
                res = [('-1' if el.strip() == '' else el) for el in rl.rsplit(',')]

                if self.aw.seriallogflag:
                    self.aw.addserial('ArduinoTC4: Tx = ' + str(command) + ' || Rx = ' + str(rl))
#                _log.debug("command: %s",command)
#                _log.debug("res: %s",res)

                #response: list ["t0","t1","t2"]  with t0 = internal temp; t1 = ET; t2 = BT on "CHAN;1200"
                #response: list ["t0","t1","t2","t3","t4"]  with t0 = internal temp; t1 = ET; t2 = BT, t3 = chan3, t4 = chan4 on "CHAN;1234" if ArduinoTC4_34 is configured
                # after PID_ON: + [,"Heater", "Fan", "SV"]
                if self.arduinoETChannel == 'None':
                    t1 = -1
                else:
                    try:
                        t1 = float(res[1])
                    except Exception: # pylint: disable=broad-except
                        t1 = -1
                if self.arduinoBTChannel == 'None':
                    t2 = -1
                else:
                    try:
                        t2 = float(res[2])
                    except Exception: # pylint: disable=broad-except
                        t2 = -1
                #if extra device +ArduinoTC4_34
                if chan is None and 28 in self.aw.qmc.extradevices:
                    #set the other values to extra temp variables
                    try:
                        self.aw.qmc.extraArduinoT1 = float(res[3])
                        self.aw.qmc.extraArduinoT2 = float(res[4])
                    except Exception: # pylint: disable=broad-except
                        self.aw.qmc.extraArduinoT1 = 0
                        self.aw.qmc.extraArduinoT2 = 0
                    if 32 in self.aw.qmc.extradevices: # +ArduinoTC4_56
                        try:
                            self.aw.qmc.extraArduinoT3 = float(res[5])
                            self.aw.qmc.extraArduinoT4 = float(res[6])
                        except Exception: # pylint: disable=broad-except
                            self.aw.qmc.extraArduinoT3 = 0
                            self.aw.qmc.extraArduinoT4 = 0
                    if 44 in self.aw.qmc.extradevices: # +ArduinoTC4_78
                        # report SV as extraArduinoT5
                        try:
                            self.aw.qmc.extraArduinoT5 = float(res[7])
                        except Exception: # pylint: disable=broad-except
                            self.aw.qmc.extraArduinoT5 = 0
                        # report Ambient Temperature as extraArduinoT6
                        try:
                            self.aw.qmc.extraArduinoT6 = float(res[0])
                        except Exception: # pylint: disable=broad-except
                            self.aw.qmc.extraArduinoT6 = 0
                else:
                    if chan is None or len(res)<5:
                        self.aw.qmc.extraArduinoT1 = -1.
                        self.aw.qmc.extraArduinoT2 = -1.
                    else:
                        try:
                            self.aw.qmc.extraArduinoT1 = float(res[3])
                            self.aw.qmc.extraArduinoT2 = float(res[4])
                        except Exception: # pylint: disable=broad-except
                            self.aw.qmc.extraArduinoT1 = 0
                            self.aw.qmc.extraArduinoT2 = 0
                    if 32 in self.aw.qmc.extradevices: # +ArduinoTC4_56
                        try:
                            self.aw.qmc.extraArduinoT3 = float(res[3])
                            self.aw.qmc.extraArduinoT4 = float(res[4])
                        except Exception: # pylint: disable=broad-except
                            self.aw.qmc.extraArduinoT3 = 0
                            self.aw.qmc.extraArduinoT4 = 0
                    else:
                        self.aw.qmc.extraArduinoT3 = -1.
                        self.aw.qmc.extraArduinoT4 = -1.
                    if 44 in self.aw.qmc.extradevices or 117 in self.aw.qmc.extradevices: # +ArduinoTC4_78 or +HB AT
                        # report SV as extraArduinoT5
                        try:
                            self.aw.qmc.extraArduinoT5 = float(res[5])
                        except Exception: # pylint: disable=broad-except
                            self.aw.qmc.extraArduinoT5 = 0
                        # report Ambient Temperature as extraArduinoT6
                        try:
                            self.aw.qmc.extraArduinoT6 = float(res[0])
                        except Exception: # pylint: disable=broad-except
                            self.aw.qmc.extraArduinoT6 = 0
                # overwrite temps by AT internal Ambient Temperature
                if self.aw.ser.arduinoATChannel != 'None':
                    if self.aw.ser.arduinoATChannel == 'T1':
                        t1 = float(res[0])
                    elif self.aw.ser.arduinoATChannel == 'T2':
                        t2 = float(res[0])
                    elif (28 in self.aw.qmc.extradevices or (32 in self.aw.qmc.extradevices and 28 not in self.aw.qmc.extradevices)) and self.aw.ser.arduinoATChannel == 'T3':
                        self.aw.qmc.extraArduinoT1 = float(res[0])
                    elif (28 in self.aw.qmc.extradevices or (32 in self.aw.qmc.extradevices and 28 not in self.aw.qmc.extradevices)) and self.aw.ser.arduinoATChannel == 'T4':
                        self.aw.qmc.extraArduinoT2 = float(res[0])
                    elif (28 in self.aw.qmc.extradevices and 32 in self.aw.qmc.extradevices) and self.aw.ser.arduinoATChannel == 'T5':
                        self.aw.qmc.extraArduinoT3 = float(res[0])
                    elif (28 in self.aw.qmc.extradevices and 32 in self.aw.qmc.extradevices) and self.aw.ser.arduinoATChannel == 'T6':
                        self.aw.qmc.extraArduinoT4 = float(res[0])
                if chan is not None:
                    if ((len(res)==4 and res[3] == 'F') or (len(res)==6 and res[5] == 'F')) and self.aw.qmc.mode != 'F':
                        # data is given in F, we convert it back to C
                        t1 = fromFtoCstrict(t1)
                        t2 = fromFtoCstrict(t2)
                        self.aw.qmc.extraArduinoT1 = fromFtoCstrict(self.aw.qmc.extraArduinoT1)
                        self.aw.qmc.extraArduinoT2 = fromFtoCstrict(self.aw.qmc.extraArduinoT2)
                        self.aw.qmc.extraArduinoT6 = fromFtoCstrict(self.aw.qmc.extraArduinoT6)
                    elif ((len(res)==4 and res[3] != 'F') or (len(res)==6 and res[5] != 'F')) and self.aw.qmc.mode == 'F':
                        # data is given in C, we convert it back to F
                        t1 = fromCtoFstrict(t1)
                        t2 = fromCtoFstrict(t2)
                        self.aw.qmc.extraArduinoT1 = fromCtoFstrict(self.aw.qmc.extraArduinoT1)
                        self.aw.qmc.extraArduinoT2 = fromCtoFstrict(self.aw.qmc.extraArduinoT2)
                        self.aw.qmc.extraArduinoT6 = fromCtoFstrict(self.aw.qmc.extraArduinoT6)
            return t1, t2
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            # self.closeport() # closing the port on error is to serve as the Arduino needs time to restart and has to be reinitialized!
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' ser.ARDUINOTC4temperature(): {0}').format(str(e)),(exc_tb.tb_lineno if exc_tb is not None else 0))
            return -1.,-1.
        finally:
            if self.COMsemaphore.available() < 1:
                self.COMsemaphore.release(1)
            if self.aw.seriallogflag:
                settings = str(self.comport) + ',' + str(self.baudrate) + ',' + str(self.bytesize)+ ',' + str(self.parity) + ',' + str(self.stopbits) + ',' + str(self.timeout)
                self.aw.addserial(f'ArduinoTC4: {settings} || Tx = {command} || Rx = {res} || Ts= {t1:.2f}, {t2:.2f}, {self.aw.qmc.extraArduinoT1:.2f}, {self.aw.qmc.extraArduinoT2:.2f}, {self.aw.qmc.extraArduinoT3:.2f}, {self.aw.qmc.extraArduinoT4:.2f}')


    def openport(self) -> None:
        try:
            #open port
            if not self.SP.is_open:
                self.confport()
                self.SP.open()
                libtime.sleep(.1) # avoid possible hickups on startup
                if self.aw.seriallogflag:
                    settings = str(self.comport) + ',' + str(self.baudrate) + ',' + str(self.bytesize)+ ',' + str(self.parity) + ',' + str(self.stopbits) + ',' + str(self.timeout)
                    self.aw.addserial('serial port opened: ' + settings)
        except Exception: # pylint: disable=broad-except
            self.SP.close()
            error = QApplication.translate('Error Message','Serial Exception:') + ' ' + QApplication.translate('Error Message','Unable to open serial port')
            self.aw.qmc.adderror(error)

    #loads configuration to ports
    def confport(self) -> None:
        self.SP.port = self.comport
        self.SP.baudrate = self.baudrate
        self.SP.bytesize = self.bytesize
        self.SP.parity = self.parity
        self.SP.stopbits = self.stopbits
        self.SP.timeout = self.timeout
        if self.platf != 'Windows':
            self.SP.exclusive = True

    def closeport(self) -> None:
        try:
            if self.SP.is_open:
                self.SP.close()
        except Exception: # pylint: disable=broad-except
            pass

    def NONEtmp(self) -> tuple[float, float]:
        dialogx = nonedevDlg(self.aw, self.aw)

        # NOT CORRECT:
        ##from sys import getsizeof  # getsizesof not reporting the full size here!
        ##print(getsizeof(dialogx)) # 192bytes using slots; 152bytes without slots;

        # # sudo -H python3 -m pip install pympler
        #from pympler import asizeof
        #print(asizeof.asizeof(dialogx)) # 2440 using slots; 2568 without using slots
        if dialogx.exec():
            try:
                ETraw = dialogx.etEdit.text().split('.')
                ET = (int(str(ETraw[0])) * 10)/10.
            except Exception: # pylint: disable=broad-except
                ET = -1
            try:
                BTraw = dialogx.btEdit.text().split('.')
                BT = (int(str(BTraw[0])) * 10)/10.
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)
                BT = -1
            try:
                dialogx.okButton.clicked.disconnect()
                dialogx.cancelButton.clicked.disconnect()
                QApplication.processEvents() # we ensure events concerning this dialog are processed before deletion
                try: # sip not supported on older PyQt versions (RPi!)
                    sip.delete(dialogx)
                    #print(sip.isdeleted(dialogx))
                except Exception: # pylint: disable=broad-except
                    pass
                del dialogx
            except Exception: # pylint: disable=broad-except
                pass
            return ET, BT
        try:
            dialogx.okButton.clicked.disconnect()
            dialogx.cancelButton.clicked.disconnect()
            QApplication.processEvents() # we ensure events concerning this dialog are processed before deletion
            try: # sip not supported on older PyQt versions (RPi!)
                sip.delete(dialogx)
                #print(sip.isdeleted(dialogx))
            except Exception: # pylint: disable=broad-except
                pass
            del dialogx
        except Exception: # pylint: disable=broad-except
            pass
        return -1, -1

    #sends a command to the ET/BT device. (used by eventaction to send serial command)
    def sendTXcommand(self, command:bytes|str) -> None:
        try:
            #### lock shared resources #####
            self.aw.qmc.samplingSemaphore.acquire(1)
            if not self.SP.is_open:
                self.openport()
            if self.SP.is_open:
                self.SP.reset_input_buffer()
                self.SP.reset_output_buffer()
                if isinstance(command, str):
                    self.SP.write(str2cmd(command))
                elif isinstance(command, bytes):
                    self.SP.write(command)
                #self.SP.flush()
        except Exception as ex:  # pylint: disable=broad-except
            _log.exception(ex)
            #self.closeport() # do not close the serial port as reopening might take too long
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message','Exception:') + ' ser.sendTXcommand() {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
        finally:
            if self.aw.qmc.samplingSemaphore.available() < 1:
                self.aw.qmc.samplingSemaphore.release(1)
            #note: logged chars should not be binary
            if self.aw.seriallogflag:
                settings = str(self.comport) + ',' + str(self.baudrate) + ',' + str(self.bytesize)+ ',' + str(self.parity) + ',' + str(self.stopbits) + ',' + str(self.timeout)
                self.aw.addserial(f'Serial Command: {settings} || Tx = {command!r} || Rx = No answer needed')



#########################################################################
#############  Extra Serial Ports #######################################
#########################################################################

class extraserialport:

    __slots__ = ['aw', 'comport', 'baudrate', 'bytesize', 'parity', 'stopbits', 'timeout', 'devicefunctionlist', 'device', 'SP']

    def __init__(self, aw:'ApplicationWindow') -> None:
        self.aw = aw

        #default initial settings. They are changed by settingsload() at initiation of program according to the device chosen
        self.comport:str = '/dev/cu.usbserial-FTFKDA5O'      #NOTE: this string should not be translated.
        self.baudrate:int = 19200
        self.bytesize:int = 8
        self.parity:str= 'N'
        self.stopbits:int = 1
        self.timeout:float = 0.4
        self.devicefunctionlist:dict[str, Callable[[], tuple[float,float,float]]|None] = {}
        self.device:str|None = None
        self.SP:serial.Serial|None = None

    def confport(self) -> None:
        if self.SP is not None:
            self.SP.port = self.comport
            self.SP.baudrate = self.baudrate
            self.SP.bytesize = self.bytesize
            self.SP.parity = self.parity
            self.SP.stopbits = self.stopbits
            self.SP.timeout = self.timeout
            if platform.system() != 'Windows':
                self.SP.exclusive = True

    def openport(self) -> None:
        try:
            self.confport()
            #open port
            if self.SP is not None and not self.SP.is_open:
                self.SP.open()
        except Exception:  # pylint: disable=broad-except
            if self.SP is not None:
                self.SP.close()
            error = QApplication.translate('Error Message','Serial Exception:')
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror(error + ' Unable to open serial port',getattr(exc_tb, 'tb_lineno', '?'))

    def closeport(self) -> None:
        if self.SP is not None:
            self.SP.close()

    # this one is called from scale and color meter code
    def connect(self,error:bool=True) -> bool:
        if self.SP is None:
            try:
                import serial  # @UnusedImport
                self.SP = serial.Serial()
            except Exception as e:  # pylint: disable=broad-except
                if error:
                    _, _, exc_tb = sys.exc_info()
                    self.aw.qmc.adderror((QApplication.translate('Error Message','Serial Exception:') + ' connect() {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))
        if self.SP is not None:
            try:
                self.openport()
                return bool(self.SP.is_open)
            except Exception as e:  # pylint: disable=broad-except
                if error:
                    _, _, exc_tb = sys.exc_info()
                    self.aw.qmc.adderror((QApplication.translate('Error Message','Serial Exception:') + ' connect() {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))
                return False
        else:
            return False
