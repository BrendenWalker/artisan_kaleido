#
# ABOUT
# Artisan Device Configuration Dialog

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
import time as libtime
import re
import platform
import logging
from PIL import ImageColor
from typing import override, Final, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow # noqa: F401 # pylint: disable=unused-import
    from artisanlib.dialogs import HelpDlg # noqa: F401 # pylint: disable=unused-import

from artisanlib.util import (deltaLabelUTF8, setDeviceDebugLogLevel, argb_colorname2rgba_colorname, rgba_colorname2argb_colorname)
from artisanlib.dialogs import ArtisanResizeablDialog
from artisanlib.widgets import MyContentLimitedQComboBox, MyQComboBox, MyQDoubleSpinBox


_log: Final[logging.Logger] = logging.getLogger(__name__)

from PyQt6.QtCore import (Qt, pyqtSlot, QSettings, QTimer, QRegularExpression)
from PyQt6.QtGui import (QColor, QIntValidator, QRegularExpressionValidator, QStandardItem, QStandardItemModel)
from PyQt6.QtWidgets import (QApplication, QWidget, QCheckBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QSpinBox, QTabWidget, QComboBox, QDialogButtonBox, QGridLayout,
                             QGroupBox, QRadioButton, QButtonGroup,
                             QTableWidget, QMessageBox, QHeaderView, QTableWidgetItem, QSizePolicy)


class DeviceAssignmentDlg(ArtisanResizeablDialog):
    def __init__(self, parent:QWidget, aw:'ApplicationWindow', activeTab:int = 0) -> None:
        super().__init__(parent,aw)
        self.activeTab = activeTab
        self.setWindowTitle(QApplication.translate('Form Caption','Device Assignment'))
        self.setModal(True)

        self.helpdialog:HelpDlg|None = None

        self.org_phidgetRemoteFlag = self.aw.qmc.phidgetRemoteFlag
        self.org_yoctoRemoteFlag = self.aw.qmc.yoctoRemoteFlag
        self.org_kaleidoSerial = self.aw.kaleidoSerial

        self.org_ambientTempSource = self.aw.qmc.ambientTempSource
        self.org_ambientHumiditySource = self.aw.qmc.ambientHumiditySource
        self.org_ambientPressureSource = self.aw.qmc.ambientPressureSource

        ################ TAB 1   WIDGETS
        #ETcurve
        self.ETcurve = QCheckBox(QApplication.translate('CheckBox', 'ET'))
        self.ETcurve.setChecked(self.aw.qmc.ETcurve)
        #BTcurve
        self.BTcurve = QCheckBox(QApplication.translate('CheckBox', 'BT'))
        self.BTcurve.setChecked(self.aw.qmc.BTcurve)
        #ETlcd
        self.ETlcd = QCheckBox(QApplication.translate('CheckBox', 'ET'))
        self.ETlcd.setChecked(self.aw.qmc.ETlcd)
        #BTlcd
        self.BTlcd = QCheckBox(QApplication.translate('CheckBox', 'BT'))
        self.BTlcd.setChecked(self.aw.qmc.BTlcd)
        #swaplcd
        self.swaplcds = QCheckBox(QApplication.translate('CheckBox', 'Swap'))
        self.swaplcds.setChecked(self.aw.qmc.swaplcds)
        self.curveHBox = QHBoxLayout()
        self.curveHBox.setContentsMargins(10,5,10,5)
        self.curveHBox.setSpacing(5)
        self.curveHBox.addWidget(self.ETcurve)
        self.curveHBox.addSpacing(10)
        self.curveHBox.addWidget(self.BTcurve)
        self.curveHBox.addStretch()
        self.curves = QGroupBox(QApplication.translate('GroupBox','Curves'))
        self.curves.setLayout(self.curveHBox)
        self.lcdHBox = QHBoxLayout()
        self.lcdHBox.setContentsMargins(0,5,0,5)
        self.lcdHBox.setSpacing(5)
        self.lcdHBox.addWidget(self.ETlcd)
        self.lcdHBox.addSpacing(10)
        self.lcdHBox.addWidget(self.BTlcd)
        self.lcdHBox.addSpacing(15)
        self.lcdHBox.addWidget(self.swaplcds)
        self.lcds = QGroupBox(QApplication.translate('GroupBox','LCDs'))
        self.lcds.setLayout(self.lcdHBox)

        self.deviceLoggingFlag = QCheckBox(QApplication.translate('Label', 'Logging'))
        self.deviceLoggingFlag.setChecked(self.aw.qmc.device_logging)

        self.controlButtonFlag = QCheckBox(QApplication.translate('Label', 'Control'))
        self.controlButtonFlag.setChecked(self.aw.qmc.Controlbuttonflag)
        self.controlButtonFlag.stateChanged.connect(self.showControlbuttonToggle)
        self.controlButtonFlag.setToolTip(QApplication.translate('Tooltip', 'Enable PID control'))

        self.nonpidButton = QRadioButton(QApplication.translate('Radio Button','Meter'))
        #As a main device, don't show the devices that start with a "+"
        # devices with a first letter "+" are extra devices an depend on another device
        # each device provides 2 curves
        #don't show devices with a "-". Devices with a - at front are either a pid, arduino, or an external program
        dev = self.aw.qmc.devices[:]             #deep copy
        limit = len(dev)
        for _ in range(limit):
            for i, _ in enumerate(dev):
                if dev[i][0] in {'+', '-'}:
                    dev.pop(i)              #note: pop() makes the list smaller that's why there are 2 FOR statements
                    break
        self.sorted_devices = sorted(dev)
        self.devicetypeComboBox = MyContentLimitedQComboBox()

        self.devicetypeComboBox.addItems(self.sorted_devices)
        self.nonpidButton.setChecked(True)
        selected_device_index = 0
        try:
            selected_device_index = self.sorted_devices.index(self.aw.qmc.devices[self.aw.qmc.device - 1])
        except Exception: # pylint: disable=broad-except
            pass
        self.devicetypeComboBox.setCurrentIndex(selected_device_index)

        # hack to access the Qt automatic translation of the RestoreDefaults button
        db_help = QDialogButtonBox(QDialogButtonBox.StandardButton.Help)
        help_button = db_help.button(QDialogButtonBox.StandardButton.Help)
        if help_button is not None:
            help_text_translated = help_button.text()
        else:
            help_text_translated = QApplication.translate('Button','Help')
        # connect the ArtisanDialog standard OK/Cancel buttons
        self.dialogbuttons.accepted.connect(self.okEvent)
        self.dialogbuttons.rejected.connect(self.cancelEvent)

        labelETadvanced = QLabel(QApplication.translate('Label', 'ET Y(x)'))
        labelBTadvanced = QLabel(QApplication.translate('Label', 'BT Y(x)'))
        self.ETfunctionedit = QLineEdit(str(self.aw.qmc.ETfunction))
        self.BTfunctionedit = QLineEdit(str(self.aw.qmc.BTfunction))
        symbolicHelpButton = QPushButton(help_text_translated)
        self.setButtonTranslations(symbolicHelpButton,'Help',QApplication.translate('Button','Help'))
        symbolicHelpButton.setMaximumSize(symbolicHelpButton.sizeHint())
        symbolicHelpButton.setMinimumSize(symbolicHelpButton.minimumSizeHint())
        symbolicHelpButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        symbolicHelpButton.clicked.connect(self.showSymbolicHelp)
        ##########################    TAB 2  WIDGETS   "EXTRA DEVICES"
        #table for showing data
        self.devicetable = QTableWidget()
        self.devicetable.setTabKeyNavigation(True)
        self.copydeviceTableButton = QPushButton(QApplication.translate('Button', 'Copy Table'))
        self.copydeviceTableButton.setToolTip(QApplication.translate('Tooltip','Copy table to clipboard, OPTION or ALT click for tabular text'))
        self.copydeviceTableButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.copydeviceTableButton.clicked.connect(self.copyDeviceTabletoClipboard)
        self.addButton = QPushButton(QApplication.translate('Button','Add'))
        self.addButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.addButton.setMinimumWidth(100)
        #self.addButton.setMaximumWidth(100)
        self.addButton.clicked.connect(self.adddevice)
        # hack to access the Qt automatic translation of the RestoreDefaults button
        db_reset = QDialogButtonBox(QDialogButtonBox.StandardButton.Reset)
        db_reset_button = db_reset.button(QDialogButtonBox.StandardButton.Reset)
        if db_reset_button is not None:
            reset_text_translated = db_reset_button.text()
        else:
            reset_text_translated = QApplication.translate('Button','Reset')
        resetButton = QPushButton(reset_text_translated)
        self.setButtonTranslations(resetButton,'Reset',QApplication.translate('Button','Reset'))
        resetButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        resetButton.setMinimumWidth(100)
        resetButton.clicked.connect(self.resetextradevices)
        extradevHelpButton = QPushButton(help_text_translated)
        self.setButtonTranslations(extradevHelpButton,'Help',QApplication.translate('Button','Help'))
        extradevHelpButton.setMinimumWidth(100)
        extradevHelpButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        extradevHelpButton.clicked.connect(self.showExtradevHelp)
        self.delButton = QPushButton(QApplication.translate('Button','Delete'))
        self.delButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delButton.setMinimumWidth(100)
        #self.delButton.setMaximumWidth(100)
        self.delButton.clicked.connect(self.deldevice)
        self.recalcButton = QPushButton(QApplication.translate('Button','Update Profile'))
        self.recalcButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recalcButton.setMinimumWidth(100)
        self.recalcButton.setToolTip(QApplication.translate('Tooltip','Recaclulates all Virtual Devices and updates their values in the profile'))
        self.recalcButton.clicked.connect(self.updateVirtualdevicesinprofile_clicked)
        self.enableDisableAddDeleteButtons()
        ####################################################
        #Arduino TC4 channel config
        arduinoChannels = ['None','1','2','3','4']
        arduinoETLabel =QLabel(QApplication.translate('Label', 'ET Channel'))
        self.arduinoETComboBox = QComboBox()
        self.arduinoETComboBox.addItems(arduinoChannels)
        arduinoBTLabel =QLabel(QApplication.translate('Label', 'BT Channel'))
        self.arduinoBTComboBox = QComboBox()
        self.arduinoBTComboBox.addItems(arduinoChannels)
        try:
            self.arduinoETComboBox.setCurrentIndex(arduinoChannels.index(self.aw.ser.arduinoETChannel))
        except Exception: # pylint: disable=broad-except
            pass
        try:
            self.arduinoBTComboBox.setCurrentIndex(arduinoChannels.index(self.aw.ser.arduinoBTChannel))
        except Exception: # pylint: disable=broad-except
            pass
        arduinoATLabel =QLabel(QApplication.translate('Label', 'AT Channel'))

        arduinoTemperatures = ['None','T1','T2','T3','T4','T5','T6']
        self.arduinoATComboBox = QComboBox()
        self.arduinoATComboBox.addItems(arduinoTemperatures)
        self.arduinoATComboBox.setCurrentIndex(arduinoTemperatures.index(self.aw.ser.arduinoATChannel))
        self.showControlButton = QCheckBox(QApplication.translate('CheckBox', 'PID Firmware'))
        self.showControlButton.setChecked(self.aw.qmc.PIDbuttonflag)
        self.showControlButton.stateChanged.connect(self.PIDfirmwareToggle)
        FILTLabel =QLabel(QApplication.translate('Label', 'Filter'))
        self.FILTspinBoxes:list[QSpinBox] = []
        for i in range(4):
            spinBox = QSpinBox()
            spinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
            spinBox.setRange(0,99)
            spinBox.setSingleStep(5)
            spinBox.setSuffix(' %')
            spinBox.setValue(int(self.aw.ser.ArduinoFILT[i]))
            self.FILTspinBoxes.append(spinBox)
        ####################################################
        ##########     LAYOUTS

        # create Phidget box
        phidgetProbeTypeItems = ['K', 'J', 'E', 'T']
        phidgetBox1048 = QGridLayout()
        self.asyncCheckBoxes1048 = []
        self.changeTriggerCombos1048 = []
        self.probeTypeCombos = []
        for i in range(1,5):
            changeTriggersCombo = QComboBox()
            changeTriggersCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            model = cast(QStandardItemModel, changeTriggersCombo.model())
            changeTriggerItems = self.createItems(self.aw.qmc.phidget1048_changeTriggersStrings)
            for item in changeTriggerItems:
                model.appendRow(item)
            try:
                changeTriggersCombo.setCurrentIndex(self.aw.qmc.phidget1048_changeTriggersValues.index(self.aw.qmc.phidget1048_changeTriggers[i-1]))
            except Exception: # pylint: disable=broad-except
                pass

            changeTriggersCombo.setMinimumContentsLength(1)
            changeTriggersCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
            changeTriggersCombo.setEnabled(bool(self.aw.qmc.phidget1048_async[i-1]))
            width = changeTriggersCombo.minimumSizeHint().width()
            changeTriggersCombo.setMinimumWidth(width)
            if platform.system() == 'Darwin':
                changeTriggersCombo.setMaximumWidth(width)

            self.changeTriggerCombos1048.append(changeTriggersCombo)
            phidgetBox1048.addWidget(changeTriggersCombo,3,i)
            asyncFlag = QCheckBox()
            self.asyncCheckBoxes1048.append(asyncFlag)
            asyncFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            asyncFlag.setChecked(True)
            phidgetBox1048.addWidget(asyncFlag,2,i)
            asyncFlag.stateChanged.connect(self.asyncFlagStateChanged1048)
            asyncFlag.setChecked(self.aw.qmc.phidget1048_async[i-1])
            probeTypeCombo = QComboBox()
            probeTypeCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            model = cast(QStandardItemModel, probeTypeCombo.model())
            probeTypeItems = self.createItems(phidgetProbeTypeItems)
            for item in probeTypeItems:
                model.appendRow(item)
            try:
                probeTypeCombo.setCurrentIndex(self.aw.qmc.phidget1048_types[i-1]-1)
            except Exception: # pylint: disable=broad-except
                pass

            probeTypeCombo.setMinimumContentsLength(1)
            probeTypeCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
            width = probeTypeCombo.minimumSizeHint().width()
            probeTypeCombo.setMinimumWidth(width)
            if platform.system() == 'Darwin':
                probeTypeCombo.setMaximumWidth(width)

            self.probeTypeCombos.append(probeTypeCombo)
            phidgetBox1048.addWidget(probeTypeCombo,1,i)
            rowLabel = QLabel(str(i-1))
            phidgetBox1048.addWidget(rowLabel,0,i)

        self.dataRateCombo1048 = QComboBox()
        self.dataRateCombo1048.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.dataRateCombo1048.model())
        dataRateItems = self.createItems(self.aw.qmc.phidget_dataRatesStrings)
        for item in dataRateItems:
            model.appendRow(item)
        try:
            self.dataRateCombo1048.setCurrentIndex(self.aw.qmc.phidget_dataRatesValues.index(self.aw.qmc.phidget1048_dataRate))
        except Exception: # pylint: disable=broad-except
            pass
        self.dataRateCombo1048.setMinimumContentsLength(5)
        self.dataRateCombo1048.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToContents
        width = self.dataRateCombo1048.minimumSizeHint().width()
        self.dataRateCombo1048.setMinimumWidth(width)
        if platform.system() == 'Darwin':
            self.dataRateCombo1048.setMaximumWidth(width)

        phidgetBox1048.addWidget(self.dataRateCombo1048,4,1,1,2)
        phidgetBox1048.setSpacing(2)

        typeLabel = QLabel(QApplication.translate('Label','Type'))
        asyncLabel = QLabel(QApplication.translate('Label','Async'))
        changeTriggerLabel = QLabel(QApplication.translate('Label','Change'))
        rateLabel = QLabel(QApplication.translate('Label','Rate'))
        phidgetBox1048.addWidget(typeLabel,1,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1048.addWidget(asyncLabel,2,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1048.addWidget(changeTriggerLabel,3,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1048.addWidget(rateLabel,4,0,Qt.AlignmentFlag.AlignRight)
        phidget1048HBox = QHBoxLayout()
        phidget1048HBox.addStretch()
        phidget1048HBox.addLayout(phidgetBox1048)
        phidget1048HBox.addStretch()
        phidget1048VBox = QVBoxLayout()
        phidget1048VBox.addLayout(phidget1048HBox)
        phidget1048VBox.addStretch()
        phidget1048GroupBox = QGroupBox('1048/1051/TMP1100/TMP1101 TC')
        phidget1048GroupBox.setLayout(phidget1048VBox)
        phidget1048GroupBox.setContentsMargins(0,0,0,0)
        phidget1048HBox.setContentsMargins(0,0,0,0)
        phidget1048VBox.setContentsMargins(0,0,0,0)

        # Phidget IR
        phidgetBox1045 = QGridLayout()
        phidgetBox1045.setSpacing(2)
        self.changeTriggerCombos1045 = QComboBox()
        self.changeTriggerCombos1045.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.changeTriggerCombos1045.model())
        changeTriggerItems = self.createItems(self.aw.qmc.phidget1045_changeTriggersStrings)
        for item in changeTriggerItems:
            model.appendRow(item)
        try:
            self.changeTriggerCombos1045.setCurrentIndex(self.aw.qmc.phidget1045_changeTriggersValues.index(self.aw.qmc.phidget1045_changeTrigger))
        except Exception: # pylint: disable=broad-except
            pass

        self.changeTriggerCombos1045.setMinimumContentsLength(3)
        self.changeTriggerCombos1045.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
        width = self.changeTriggerCombos1045.minimumSizeHint().width()
        self.changeTriggerCombos1045.setMinimumWidth(width)
        if platform.system() == 'Darwin':
            self.changeTriggerCombos1045.setMaximumWidth(width)

        phidgetBox1045.addWidget(self.changeTriggerCombos1045,3,1)
        self.asyncCheckBoxe1045 = QCheckBox()
        phidgetBox1045.addWidget(self.asyncCheckBoxe1045,2,1)
        self.asyncCheckBoxe1045.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.asyncCheckBoxe1045.setChecked(True)
        self.asyncCheckBoxe1045.stateChanged.connect(self.asyncFlagStateChanged1045)
        self.asyncCheckBoxe1045.setChecked(self.aw.qmc.phidget1045_async)
        asyncLabel = QLabel(QApplication.translate('Label','Async'))
        changeTriggerLabel = QLabel(QApplication.translate('Label','Change'))
        rateLabel = QLabel(QApplication.translate('Label','Rate'))

        self.dataRateCombo1045 = QComboBox()
        self.dataRateCombo1045.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.dataRateCombo1045.model())
        dataRateItems = self.createItems(self.aw.qmc.phidget_dataRatesStrings)
        for item in dataRateItems:
            model.appendRow(item)
        try:
            self.dataRateCombo1045.setCurrentIndex(self.aw.qmc.phidget_dataRatesValues.index(self.aw.qmc.phidget1045_dataRate))
        except Exception: # pylint: disable=broad-except
            pass
        self.dataRateCombo1045.setMinimumContentsLength(3)
        self.dataRateCombo1045.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
        width = self.dataRateCombo1045.minimumSizeHint().width()
        self.dataRateCombo1045.setMinimumWidth(width)
        if platform.system() == 'Darwin':
            self.dataRateCombo1045.setMaximumWidth(width)

        EmissivityLabel = QLabel(QApplication.translate('Label','Emissivity'))
        self.emissivitySpinBox = MyQDoubleSpinBox()
        self.emissivitySpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.emissivitySpinBox.setRange(0.,1.)
        self.emissivitySpinBox.setSingleStep(.1)
        self.emissivitySpinBox.setValue(self.aw.qmc.phidget1045_emissivity)

        phidgetBox1045.addWidget(asyncLabel,2,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1045.addWidget(changeTriggerLabel,3,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1045.addWidget(rateLabel,4,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1045.addWidget(EmissivityLabel,5,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1045.addWidget(self.dataRateCombo1045,4,1)
        phidgetBox1045.addWidget(self.emissivitySpinBox,5,1)
        phidget1045VBox = QVBoxLayout()
        phidget1045VBox.addStretch()
        phidget1045VBox.addLayout(phidgetBox1045)
        phidget1045VBox.addStretch()
        phidget1045VBox.addStretch()
        phidget1045GroupBox = QGroupBox('1045 IR')
        phidget1045GroupBox.setLayout(phidget1045VBox)
        phidget1045VBox.setContentsMargins(0,0,0,0)


        # 1046 RTD
        phidgetBox1046 = QGridLayout()
        phidgetBox1046.setSpacing(2)
        phidgetBox1046.setContentsMargins(0,0,0,0)
        self.gainCombos1046 = []
        self.formulaCombos1046 = []
        self.asyncCheckBoxes1046 = []
        for i in range(1,5):
            gainCombo = QComboBox()
            gainCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            model = cast(QStandardItemModel, gainCombo.model())
            gainItems = self.createItems(self.aw.qmc.phidget1046_gainValues)
            for item in gainItems:
                model.appendRow(item)
            try:
                gainCombo.setCurrentIndex(self.aw.qmc.phidget1046_gain[i-1] - 1)
            except Exception: # pylint: disable=broad-except
                pass

            gainCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
            gainCombo.setMinimumContentsLength(1)
            width = gainCombo.minimumSizeHint().width()
            gainCombo.setMinimumWidth(width)
            if platform.system() == 'Darwin':
                gainCombo.setMaximumWidth(width)

            self.gainCombos1046.append(gainCombo)
            phidgetBox1046.addWidget(gainCombo,1,i)

            formulaCombo = QComboBox()
            formulaCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            model = cast(QStandardItemModel, formulaCombo.model())
            formulaItems = self.createItems(self.aw.qmc.phidget1046_formulaValues)
            for item in formulaItems:
                model.appendRow(item)
            try:
                formulaCombo.setCurrentIndex(self.aw.qmc.phidget1046_formula[i-1])
            except Exception: # pylint: disable=broad-except
                pass

            formulaCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
            formulaCombo.setMinimumContentsLength(1)
            width = formulaCombo.minimumSizeHint().width()
            formulaCombo.setMinimumWidth(width)
            if platform.system() == 'Darwin':
                formulaCombo.setMaximumWidth(width)

            self.formulaCombos1046.append(formulaCombo)
            phidgetBox1046.addWidget(formulaCombo,2,i)

            asyncFlag = QCheckBox()
            asyncFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            asyncFlag.setChecked(True)
            asyncFlag.setChecked(self.aw.qmc.phidget1046_async[i-1])
            self.asyncCheckBoxes1046.append(asyncFlag)
            phidgetBox1046.addWidget(asyncFlag,3,i)
            rowLabel = QLabel(str(i-1))
            phidgetBox1046.addWidget(rowLabel,0,i)

        self.dataRateCombo1046 = QComboBox()
        self.dataRateCombo1046.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.dataRateCombo1046.model())
        dataRateItems = self.createItems(self.aw.qmc.phidget_dataRatesStrings)
        for item in dataRateItems:
            model.appendRow(item)
        try:
            self.dataRateCombo1046.setCurrentIndex(self.aw.qmc.phidget_dataRatesValues.index(self.aw.qmc.phidget1046_dataRate))
        except Exception: # pylint: disable=broad-except
            pass
        self.dataRateCombo1046.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
        self.dataRateCombo1046.setMinimumContentsLength(5)
        width = self.dataRateCombo1046.minimumSizeHint().width()
        self.dataRateCombo1046.setMinimumWidth(width)
        if platform.system() == 'Darwin':
            self.dataRateCombo1046.setMaximumWidth(width)

        phidgetBox1046.addWidget(self.dataRateCombo1046,4,1,1,2)


        gainLabel = QLabel(QApplication.translate('Label','Gain'))
        formulaLabel = QLabel(QApplication.translate('Label','Wiring'))
        asyncLabel = QLabel(QApplication.translate('Label','Async'))
        rateLabel = QLabel(QApplication.translate('Label','Rate'))
        phidgetBox1046.addWidget(gainLabel,1,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1046.addWidget(formulaLabel,2,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1046.addWidget(asyncLabel,3,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1046.addWidget(rateLabel,4,0,Qt.AlignmentFlag.AlignRight)
        phidget1046HBox = QHBoxLayout()
        phidget1046HBox.addStretch()
        phidget1046HBox.addLayout(phidgetBox1046)
        phidget1046VBox = QVBoxLayout()
        phidget1046VBox.addLayout(phidget1046HBox)
        phidget1046VBox.addStretch()
        phidget1046GroupBox = QGroupBox('1046 RTD / DAQ1500')
        phidget1046GroupBox.setLayout(phidget1046VBox)
        phidget1046GroupBox.setContentsMargins(0,10,0,0)
        phidget1046HBox.setContentsMargins(0,0,0,0)
        phidget1046VBox.setContentsMargins(0,0,0,0)

        # TMP1200 RTD
        phidgetBox1200 = QGridLayout()
        phidgetBox1200.setSpacing(2)
        phidgetBox1200_2 = QGridLayout()
        phidgetBox1200_2.setSpacing(2)

        self.formulaCombo1200 = QComboBox()
        self.formulaCombo1200.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.formulaCombo1200.model())
        wireItems = self.createItems(self.aw.qmc.phidget1200_formulaValues)
        for item in wireItems:
            model.appendRow(item)
        try:
            self.formulaCombo1200.setCurrentIndex(self.aw.qmc.phidget1200_formula)
        except Exception: # pylint: disable=broad-except
            pass
        self.formulaCombo1200.setMinimumContentsLength(5)
        width = self.formulaCombo1200.minimumSizeHint().width()
        self.formulaCombo1200.setMinimumWidth(width)

        self.wireCombo1200 = QComboBox()
        self.wireCombo1200.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.wireCombo1200.model())
        wireItems = self.createItems(self.aw.qmc.phidget1200_wireValues)
        for item in wireItems:
            model.appendRow(item)
        try:
            self.wireCombo1200.setCurrentIndex(self.aw.qmc.phidget1200_wire)
        except Exception: # pylint: disable=broad-except
            pass
        self.wireCombo1200.setMinimumContentsLength(5)
        width = self.wireCombo1200.minimumSizeHint().width()
        self.wireCombo1200.setMinimumWidth(width)

        self.asyncCheckBoxe1200 = QCheckBox()
        self.asyncCheckBoxe1200.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.asyncCheckBoxe1200.setChecked(self.aw.qmc.phidget1200_async)
        self.asyncCheckBoxe1200.stateChanged.connect(self.asyncFlagStateChanged1200)

        self.changeTriggerCombo1200 = QComboBox()
        self.changeTriggerCombo1200.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.changeTriggerCombo1200.model())
        changeTriggerItems = self.createItems(self.aw.qmc.phidget1200_changeTriggersStrings)
        for item in changeTriggerItems:
            model.appendRow(item)
        try:
            self.changeTriggerCombo1200.setCurrentIndex(self.aw.qmc.phidget1200_changeTriggersValues.index(self.aw.qmc.phidget1200_changeTrigger))
        except Exception: # pylint: disable=broad-except
            pass
        self.changeTriggerCombo1200.setMinimumContentsLength(4)
        width = self.changeTriggerCombo1200.minimumSizeHint().width()
        self.changeTriggerCombo1200.setMinimumWidth(width)
        self.changeTriggerCombo1200.setEnabled(self.aw.qmc.phidget1200_async)

        self.rateCombo1200 = QComboBox()
        self.rateCombo1200.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.rateCombo1200.model())
        dataRateItems = self.createItems(self.aw.qmc.phidget1200_dataRatesStrings)
        for item in dataRateItems:
            model.appendRow(item)
        try:
            self.rateCombo1200.setCurrentIndex(self.aw.qmc.phidget1200_dataRatesValues.index(self.aw.qmc.phidget1200_dataRate))
        except Exception: # pylint: disable=broad-except
            pass
        self.rateCombo1200.setMinimumContentsLength(3)
        width = self.rateCombo1200.minimumSizeHint().width()
        self.rateCombo1200.setMinimumWidth(width)

#---
        self.formulaCombo1200_2 = QComboBox()
        self.formulaCombo1200_2.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.formulaCombo1200_2.model())
        wireItems = self.createItems(self.aw.qmc.phidget1200_formulaValues)
        for item in wireItems:
            model.appendRow(item)
        try:
            self.formulaCombo1200_2.setCurrentIndex(self.aw.qmc.phidget1200_2_formula)
        except Exception: # pylint: disable=broad-except
            pass
        self.formulaCombo1200_2.setMinimumContentsLength(4)
        width = self.formulaCombo1200_2.minimumSizeHint().width()
        self.formulaCombo1200_2.setMinimumWidth(width)

        self.wireCombo1200_2 = QComboBox()
        self.wireCombo1200_2.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.wireCombo1200_2.model())
        wireItems = self.createItems(self.aw.qmc.phidget1200_wireValues)
        for item in wireItems:
            model.appendRow(item)
        try:
            self.wireCombo1200_2.setCurrentIndex(self.aw.qmc.phidget1200_2_wire)
        except Exception: # pylint: disable=broad-except
            pass
        self.wireCombo1200_2.setMinimumContentsLength(4)
        width = self.wireCombo1200_2.minimumSizeHint().width()
        self.wireCombo1200_2.setMinimumWidth(width)

        self.asyncCheckBoxe1200_2 = QCheckBox()
        self.asyncCheckBoxe1200_2.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.asyncCheckBoxe1200_2.setChecked(self.aw.qmc.phidget1200_2_async)
        self.asyncCheckBoxe1200_2.stateChanged.connect(self.asyncFlagStateChanged1200_2)

        self.changeTriggerCombo1200_2 = QComboBox()
        self.changeTriggerCombo1200_2.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.changeTriggerCombo1200_2.model())
        changeTriggerItems = self.createItems(self.aw.qmc.phidget1200_changeTriggersStrings)
        for item in changeTriggerItems:
            model.appendRow(item)
        try:
            self.changeTriggerCombo1200_2.setCurrentIndex(self.aw.qmc.phidget1200_changeTriggersValues.index(self.aw.qmc.phidget1200_2_changeTrigger))
        except Exception: # pylint: disable=broad-except
            pass
        self.changeTriggerCombo1200_2.setMinimumContentsLength(4)
        width = self.changeTriggerCombo1200_2.minimumSizeHint().width()
        self.changeTriggerCombo1200_2.setMinimumWidth(width)
        self.changeTriggerCombo1200_2.setEnabled(self.aw.qmc.phidget1200_async)

        self.rateCombo1200_2 = QComboBox()
        self.rateCombo1200_2.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.rateCombo1200_2.model())
        dataRateItems = self.createItems(self.aw.qmc.phidget1200_dataRatesStrings)
        for item in dataRateItems:
            model.appendRow(item)
        try:
            self.rateCombo1200_2.setCurrentIndex(self.aw.qmc.phidget1200_dataRatesValues.index(self.aw.qmc.phidget1200_2_dataRate))
        except Exception: # pylint: disable=broad-except
            pass
        self.rateCombo1200_2.setMinimumContentsLength(3)
        width = self.rateCombo1200_2.minimumSizeHint().width()
        self.rateCombo1200_2.setMinimumWidth(width)

#---

        typeLabel = QLabel(QApplication.translate('Label','Type'))
        wireLabel = QLabel(QApplication.translate('Label','Wiring'))
        asyncLabel = QLabel(QApplication.translate('Label','Async'))
        changeLabel = QLabel(QApplication.translate('Label','Change'))
        rateLabel = QLabel(QApplication.translate('Label','Rate'))

        typeLabel2 = QLabel(QApplication.translate('Label','Type'))
        wireLabel2 = QLabel(QApplication.translate('Label','Wiring'))
        asyncLabel2 = QLabel(QApplication.translate('Label','Async'))
        changeLabel2 = QLabel(QApplication.translate('Label','Change'))
        rateLabel2 = QLabel(QApplication.translate('Label','Rate'))

        phidgetBox1200.addWidget(typeLabel,1,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200.addWidget(self.formulaCombo1200,1,1)
        phidgetBox1200.addWidget(wireLabel,2,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200.addWidget(self.wireCombo1200,2,1)
        phidgetBox1200.addWidget(asyncLabel,3,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200.addWidget(self.asyncCheckBoxe1200,3,1)
        phidgetBox1200.addWidget(changeLabel,4,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200.addWidget(self.changeTriggerCombo1200,4,1)
        phidgetBox1200.addWidget(rateLabel,5,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200.addWidget(self.rateCombo1200,5,1)

        phidgetBox1200_2.addWidget(typeLabel2,1,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200_2.addWidget(self.formulaCombo1200_2,1,1)
        phidgetBox1200_2.addWidget(wireLabel2,2,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200_2.addWidget(self.wireCombo1200_2,2,1)
        phidgetBox1200_2.addWidget(asyncLabel2,3,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200_2.addWidget(self.asyncCheckBoxe1200_2,3,1)
        phidgetBox1200_2.addWidget(changeLabel2,4,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200_2.addWidget(self.changeTriggerCombo1200_2,4,1)
        phidgetBox1200_2.addWidget(rateLabel2,5,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1200_2.addWidget(self.rateCombo1200_2,5,1)

        phidget1200HBox = QHBoxLayout()
        phidget1200HBox.addStretch()
        phidget1200HBox.addLayout(phidgetBox1200)
        phidget1200HBox.addStretch()
        phidget1200VBox = QVBoxLayout()
        phidget1200VBox.addLayout(phidget1200HBox)
        phidget1200VBox.addStretch()
        phidget1200VBox.setContentsMargins(0,0,0,0)
        phidget1200HBox.setContentsMargins(0,0,0,0)

        phidget1200HBox_2 = QHBoxLayout()
        phidget1200HBox_2.addStretch()
        phidget1200HBox_2.addLayout(phidgetBox1200_2)
        phidget1200HBox_2.addStretch()
        phidget1200VBox_2 = QVBoxLayout()
        phidget1200VBox_2.addLayout(phidget1200HBox_2)
        phidget1200VBox_2.addStretch()
        phidget1200VBox_2.setContentsMargins(0,0,0,0)
        phidget1200HBox_2.setContentsMargins(0,0,0,0)

        phidget1200_tabs = QTabWidget()
        phidget1200_tab1_widget = QWidget()
        phidget1200_tab1_widget.setLayout(phidget1200VBox)
        phidget1200_tabs.addTab(phidget1200_tab1_widget,'A')

        phidget1200_tab2_widget = QWidget()
        phidget1200_tab2_widget.setLayout(phidget1200VBox_2)
        phidget1200_tabs.addTab(phidget1200_tab2_widget,'B')

        phidgetGroupBoxLayout = QVBoxLayout()
        phidgetGroupBoxLayout.addWidget(phidget1200_tabs)

        phidgetGroupBoxLayout.setContentsMargins(0,0,0,0) # left, top, right, bottom

        phidget1200GroupBox = QGroupBox('TMP1200/1202 RTD')
        phidget1200GroupBox.setLayout(phidgetGroupBoxLayout)
        phidget1200GroupBox.setContentsMargins(0,2,0,0) # left, top, right, bottom


        # DAQ1400 VI
        powerLabel = QLabel(QApplication.translate('Label','Power'))
        modeLabel = QLabel(QApplication.translate('Label','Mode'))

        self.powerCombo1400 = QComboBox()
        self.powerCombo1400.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.powerCombo1400.addItems(self.aw.qmc.phidgetDAQ1400_powerSupplyStrings)
        self.powerCombo1400.setCurrentIndex(self.aw.qmc.phidgetDAQ1400_powerSupply)
        self.powerCombo1400.setMinimumContentsLength(3)
        width = self.powerCombo1400.minimumSizeHint().width()
        self.powerCombo1400.setMinimumWidth(width)

        self.modeCombo1400 = QComboBox()
        self.modeCombo1400.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.modeCombo1400.addItems(self.aw.qmc.phidgetDAQ1400_inputModeStrings)
        self.modeCombo1400.setCurrentIndex(self.aw.qmc.phidgetDAQ1400_inputMode)
        self.modeCombo1400.setMinimumContentsLength(3)
        width = self.modeCombo1400.minimumSizeHint().width()
        self.modeCombo1400.setMinimumWidth(width)

        phidgetBox1400 = QGridLayout()
        phidgetBox1400.setSpacing(2)
        phidgetBox1400.setContentsMargins(0,0,0,0)
        phidgetBox1400.addWidget(powerLabel,0,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1400.addWidget(self.powerCombo1400,0,1)
        phidgetBox1400.addWidget(modeLabel,1,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1400.addWidget(self.modeCombo1400,1,1)

        phidget1400HBox = QHBoxLayout()
        phidget1400HBox.addLayout(phidgetBox1400)
        phidget1400VBox = QVBoxLayout()
        phidget1400VBox.addLayout(phidget1400HBox)
        phidget1400VBox.addStretch()

        phidget1400GroupBox = QGroupBox('DAQ1400 VI')
        phidget1400GroupBox.setLayout(phidget1400VBox)
        phidget1400GroupBox.setContentsMargins(0,0,0,0)
        phidget1400VBox.setContentsMargins(0,0,0,0)
        phidget1400HBox.setContentsMargins(0,0,0,0)

        phdget10481045GroupBoxHBox = QHBoxLayout()
        phdget10481045GroupBoxHBox.addWidget(phidget1048GroupBox)
        phdget10481045GroupBoxHBox.addStretch()
        phdget10481045GroupBoxHBox.addWidget(phidget1200GroupBox)
        phdget10481045GroupBoxHBox.addStretch()
        phdget10481045GroupBoxHBox.addWidget(phidget1400GroupBox)
        phdget10481045GroupBoxHBox.addStretch()
        phdget10481045GroupBoxHBox.addWidget(phidget1046GroupBox)
        phdget10481045GroupBoxHBox.setContentsMargins(2,0,0,0) # left, top, right, bottom
        phdget10481045GroupBoxHBox.setSpacing(2)


        # Phidget IO 1018
        # per each of the 8-channels: raw flag / data rate popup / change trigger popup
        phidgetBox1018 = QGridLayout()
        phidgetBox1018.setSpacing(2)
        self.asyncCheckBoxes = []
        self.ratioCheckBoxes = []
        self.dataRateCombos = []
        self.changeTriggerCombos = []
        self.voltageRangeCombos = []
        for i in range(1,9):
            dataRatesCombo = QComboBox()
            dataRatesCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            model = cast(QStandardItemModel, dataRatesCombo.model())
            dataRateItems = self.createItems(self.aw.qmc.phidget_dataRatesStrings)
            for item in dataRateItems:
                model.appendRow(item)
            try:
                dataRatesCombo.setCurrentIndex(self.aw.qmc.phidget_dataRatesValues.index(self.aw.qmc.phidget1018_dataRates[i-1]))
            except Exception: # pylint: disable=broad-except
                pass
            dataRatesCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
            dataRatesCombo.setMinimumContentsLength(4)
            width = dataRatesCombo.minimumSizeHint().width()
            dataRatesCombo.setMinimumWidth(width)
            if platform.system() == 'Darwin':
                dataRatesCombo.setMaximumWidth(width)
            self.dataRateCombos.append(dataRatesCombo)
            phidgetBox1018.addWidget(dataRatesCombo,4,i)

            changeTriggersCombo = QComboBox()
            changeTriggersCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            changeTriggersCombo.setEnabled(bool(self.aw.qmc.phidget1018_async[i-1]))
            model = cast(QStandardItemModel, changeTriggersCombo.model())
            changeTriggerItems = self.createItems(self.aw.qmc.phidget1018_changeTriggersStrings)
            for item in changeTriggerItems:
                model.appendRow(item)
            try:
                changeTriggersCombo.setCurrentIndex(self.aw.qmc.phidget1018_changeTriggersValues.index(self.aw.qmc.phidget1018_changeTriggers[i-1]))
            except Exception: # pylint: disable=broad-except
                pass
            changeTriggersCombo.setMinimumContentsLength(4)
            changeTriggersCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
            width = changeTriggersCombo.minimumSizeHint().width()
            changeTriggersCombo.setMinimumWidth(width)
            if platform.system() == 'Darwin':
                changeTriggersCombo.setMaximumWidth(width)
            self.changeTriggerCombos.append(changeTriggersCombo)
            phidgetBox1018.addWidget(changeTriggersCombo,3,i)

            voltageRangeCombo = QComboBox()
            voltageRangeCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            model = cast(QStandardItemModel, voltageRangeCombo.model())
            voltageRangeItems = self.createItems(self.aw.qmc.phidgetVCP100x_voltageRangeStrings)
            for item in voltageRangeItems:
                model.appendRow(item)
            try:
                voltageRangeCombo.setCurrentIndex(self.aw.qmc.phidgetVCP100x_voltageRangeValues.index(self.aw.qmc.phidgetVCP100x_voltageRanges[i-1]))
            except Exception: # pylint: disable=broad-except
                pass
            voltageRangeCombo.setMinimumContentsLength(4)
            voltageRangeCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
            width = voltageRangeCombo.minimumSizeHint().width()
            voltageRangeCombo.setMinimumWidth(width)
            if platform.system() == 'Darwin':
                voltageRangeCombo.setMaximumWidth(width)
            self.voltageRangeCombos.append(voltageRangeCombo)
            phidgetBox1018.addWidget(voltageRangeCombo,5,i)


            asyncFlag = QCheckBox()
            self.asyncCheckBoxes.append(asyncFlag)
            asyncFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            asyncFlag.setChecked(True)
            asyncFlag.stateChanged.connect(self.asyncFlagStateChanged)
            asyncFlag.setChecked(self.aw.qmc.phidget1018_async[i-1])
            phidgetBox1018.addWidget(asyncFlag,2,i)

            ratioFlag = QCheckBox()
            ratioFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            ratioFlag.setChecked(False)
            ratioFlag.setChecked(self.aw.qmc.phidget1018_ratio[i-1])
            self.ratioCheckBoxes.append(ratioFlag)
            phidgetBox1018.addWidget(ratioFlag,6,i)

            rowLabel = QLabel(str(i-1))
            phidgetBox1018.addWidget(rowLabel,0,i)

        asyncLabel = QLabel(QApplication.translate('Label','Async'))
        dataRateLabel = QLabel(QApplication.translate('Label','Rate'))
        changeTriggerLabel = QLabel(QApplication.translate('Label','Change'))
        ratioLabel = QLabel(QApplication.translate('Label','Ratio'))
        rangeLabel = QLabel(QApplication.translate('Label','Range'))
        phidgetBox1018.addWidget(asyncLabel,2,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1018.addWidget(changeTriggerLabel,3,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1018.addWidget(dataRateLabel,4,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1018.addWidget(rangeLabel,5,0,Qt.AlignmentFlag.AlignRight)
        phidgetBox1018.addWidget(ratioLabel,6,0,Qt.AlignmentFlag.AlignRight)
        phidget1018HBox = QVBoxLayout()
        phidget1018HBox.addLayout(phidgetBox1018)
        phidget1018GroupBox = QGroupBox('1010/1011/1013/1018/1019/HUB0000/SBC/DAQxxxx/VCP100x IO')
        phidget1018GroupBox.setLayout(phidget1018HBox)
        phidget1018HBox.setContentsMargins(0,0,0,0)
        self.phidgetBoxRemoteFlag = QCheckBox()
        self.phidgetBoxRemoteFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.phidgetBoxRemoteFlag.setChecked(self.aw.qmc.phidgetRemoteFlag)
        self.phidgetBoxRemoteFlag.stateChanged.connect(self.phidgetRemoteStateChanged)
        phidgetServerIdLabel = QLabel(QApplication.translate('Label','Host'))
        self.phidgetServerId = QLineEdit(self.aw.qmc.phidgetServerID)
        self.phidgetServerId.textChanged.connect(self.phidgetHostChanged)
        self.phidgetServerId.setMinimumWidth(200)
        self.phidgetServerId.setEnabled(self.aw.qmc.phidgetRemoteFlag)
        phidgetPasswordLabel = QLabel(QApplication.translate('Label','Password'))
        self.phidgetPassword = QLineEdit(self.aw.qmc.phidgetPassword)
        self.phidgetPassword.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.phidgetPassword.setEnabled(self.aw.qmc.phidgetServerID != '')
        self.phidgetPassword.setMinimumWidth(100)
        self.phidgetPassword.setEnabled(self.aw.qmc.phidgetRemoteFlag)
        self.phidgetPassword.setToolTip(QApplication.translate('Tooltip','Phidget server password'))
        phidgetPortLabel = QLabel(QApplication.translate('Label','Port'))
        self.phidgetPort = QLineEdit(str(self.aw.qmc.phidgetPort))
        self.phidgetPort.setMaximumWidth(70)
        self.phidgetPort.setEnabled(self.aw.qmc.phidgetRemoteFlag)
        self.phidgetBoxRemoteOnlyFlag = QCheckBox(QApplication.translate('Label','Remote Only'))
        self.phidgetBoxRemoteOnlyFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.phidgetBoxRemoteOnlyFlag.setChecked(self.aw.qmc.phidgetRemoteOnlyFlag)
        self.phidgetBoxRemoteOnlyFlag.setEnabled(self.aw.qmc.phidgetRemoteFlag)
        phidgetServerBox = QHBoxLayout()
        phidgetServerBox.addWidget(phidgetServerIdLabel)
        phidgetServerBox.addWidget(self.phidgetServerId)
        phidgetServerBox.setContentsMargins(0,0,0,0)
        phidgetServerBox.setSpacing(3)
        phidgetPasswordBox = QHBoxLayout()
        phidgetPasswordBox.addWidget(phidgetPasswordLabel)
        phidgetPasswordBox.addWidget(self.phidgetPassword)
        phidgetPasswordBox.setContentsMargins(0,0,0,0)
        phidgetPasswordBox.setSpacing(3)
        phidgetPortBox = QHBoxLayout()
        phidgetPortBox.addWidget(phidgetPortLabel)
        phidgetPortBox.addWidget(self.phidgetPort)
        phidgetPortBox.setContentsMargins(0,0,0,0)
        phidgetPortBox.setSpacing(3)
        phidgetNetworkGrid = QHBoxLayout()
        phidgetNetworkGrid.addWidget(self.phidgetBoxRemoteFlag)
        phidgetNetworkGrid.addStretch()
        phidgetNetworkGrid.addLayout(phidgetServerBox)
        phidgetNetworkGrid.addLayout(phidgetPortBox)
        phidgetNetworkGrid.addStretch()
        phidgetNetworkGrid.addLayout(phidgetPasswordBox)
        phidgetNetworkGrid.addStretch()
        phidgetNetworkGrid.addWidget(self.phidgetBoxRemoteOnlyFlag)
        phidgetNetworkGrid.setContentsMargins(0,0,0,0)
        phidgetNetworkGrid.setSpacing(20)
        phidgetNetworkGroupBox = QGroupBox(QApplication.translate('GroupBox','Network'))
        phidgetNetworkGroupBox.setLayout(phidgetNetworkGrid)
        phidget10451018HBox = QHBoxLayout()
        phidget10451018HBox.addWidget(phidget1045GroupBox)
        phidget10451018HBox.addStretch()
        phidget10451018HBox.addWidget(phidget1018GroupBox)
        phidget10451018HBox.setSpacing(2)
        phidgetVBox = QVBoxLayout()
        phidgetVBox.addLayout(phdget10481045GroupBoxHBox)
        phidgetVBox.addLayout(phidget10451018HBox)
        phidgetVBox.addWidget(phidgetNetworkGroupBox)
        phidgetVBox.addStretch()
        phidgetVBox.setSpacing(5)
        phidgetVBox.setContentsMargins(0,0,0,0)
        # yoctopuce widgets
        self.yoctoBoxRemoteFlag = QCheckBox()
        self.yoctoBoxRemoteFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.yoctoBoxRemoteFlag.setChecked(self.aw.qmc.yoctoRemoteFlag)
        self.yoctoBoxRemoteFlag.stateChanged.connect(self.yoctoBoxRemoteFlagStateChanged)
        yoctoServerIdLabel = QLabel(QApplication.translate('Label','VirtualHub'))
        self.yoctoServerId = QLineEdit(self.aw.qmc.yoctoServerID)
        self.yoctoServerId.setToolTip(QApplication.translate('Tooltip','Network IP address or name of the remote VirtualHub'))
        self.yoctoServerId.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.yoctoServerId.setMinimumWidth(100)
        self.yoctoServerId.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.yoctoServerId.setEnabled(self.aw.qmc.yoctoRemoteFlag)
        YoctoEmissivityLabel = QLabel(QApplication.translate('Label','Emissivity'))
        self.yoctoEmissivitySpinBox = MyQDoubleSpinBox()
        self.yoctoEmissivitySpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.yoctoEmissivitySpinBox.setRange(0.,1.)
        self.yoctoEmissivitySpinBox.setSingleStep(.1)
        self.yoctoEmissivitySpinBox.setValue(self.aw.qmc.YOCTO_emissivity)
        yoctoServerBox = QHBoxLayout()
        yoctoServerBox.addWidget(yoctoServerIdLabel)
        yoctoServerBox.addSpacing(10)
        yoctoServerBox.addWidget(self.yoctoServerId)
        yoctoServerBox.addStretch()
        yoctoServerBox.setContentsMargins(0,0,0,0)
        yoctoServerBox.setSpacing(10)
        yoctoNetworkGrid = QGridLayout()
        yoctoNetworkGrid.addWidget(self.yoctoBoxRemoteFlag,0,0)
        yoctoNetworkGrid.addLayout(yoctoServerBox,0,1)
        yoctoNetworkGrid.setSpacing(20)
        yoctoNetworkGroupBox = QGroupBox(QApplication.translate('GroupBox','Network'))
        yoctoNetworkGroupBox.setLayout(yoctoNetworkGrid)
        yoctoIRGrid = QGridLayout()
        yoctoIRGrid.addWidget(YoctoEmissivityLabel,0,0)
        yoctoIRGrid.addWidget(self.yoctoEmissivitySpinBox,0,1)
        yoctoIRHorizontalLayout = QHBoxLayout()
        yoctoIRHorizontalLayout.addLayout(yoctoIRGrid)
        yoctoIRHorizontalLayout.addStretch()
        self.yoctoDataRateCombo = QComboBox()
        self.yoctoDataRateCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        model = cast(QStandardItemModel, self.yoctoDataRateCombo.model())
        dataRateItems = self.createItems(self.aw.qmc.YOCTO_dataRatesStrings)
        for item in dataRateItems:
            model.appendRow(item)
        try:
            self.yoctoDataRateCombo.setCurrentIndex(self.aw.qmc.YOCTO_dataRatesValues.index(self.aw.qmc.YOCTO_dataRate))
        except Exception: # pylint: disable=broad-except
            pass
        self.yoctoDataRateCombo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents) # AdjustToMinimumContentsLengthWithIcon
        self.yoctoDataRateCombo.setMinimumContentsLength(5)
        width = self.yoctoDataRateCombo.minimumSizeHint().width()
        self.yoctoDataRateCombo.setMinimumWidth(width)
        self.yoctoAyncChanFlag = QCheckBox()
        self.yoctoAyncChanFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.yoctoAyncChanFlag.setChecked(self.aw.qmc.YOCTO_async[0]) # only one flag for both channels, as running on async and the other sync will disturbe the readings
        yoctoAsyncGrid = QGridLayout()
        yoctoAsyncGrid.addWidget(self.yoctoAyncChanFlag,0,0)
        yoctoAsyncGrid.addWidget(self.yoctoDataRateCombo,0,1)
        yoctoAsyncHorizontalLayout = QHBoxLayout()
        yoctoAsyncHorizontalLayout.addLayout(yoctoAsyncGrid)
        yoctoAsyncHorizontalLayout.addStretch()
        yoctoAsyncGroupBox = QGroupBox(QApplication.translate('GroupBox','Async'))
        yoctoAsyncGroupBox.setLayout(yoctoAsyncHorizontalLayout)
        yoctoIRGroupBox = QGroupBox(QApplication.translate('GroupBox','IR'))
        yoctoIRGroupBox.setLayout(yoctoIRHorizontalLayout)
        yoctoVBox = QVBoxLayout()
        yoctoVBox.addWidget(yoctoNetworkGroupBox)
        yoctoVBox.addWidget(yoctoIRGroupBox)
        yoctoVBox.addWidget(yoctoAsyncGroupBox)
        yoctoVBox.addStretch()
        yoctoVBox.setSpacing(5)
        yoctoVBox.setContentsMargins(0,0,0,0)

        # Ambient Widgets and Layouts

        ambientSourceLabel = QLabel(QApplication.translate('Label', 'Ambient Source'))

        # Ambient Temperature Source Selector (generic ET/BT/extra sources; Kaleido AT via extras)
        self.ambientTempComboBox = QComboBox()
        self.ambientTempComboBox.currentIndexChanged.connect(self.ambientTempComboBoxIndexChanged)
        self.temperatureDeviceCombo = QComboBox()
        self.temperatureDeviceCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.temperatureDeviceCombo.addItems(self.aw.qmc.temperaturedevicefunctionlist)
        self.temperatureDeviceCombo.currentIndexChanged.connect(self.temperatureDeviceComboBoxIndexChanged)
        try:
            self.temperatureDeviceCombo.setCurrentIndex(self.aw.qmc.ambient_temperature_device)
        except Exception: # pylint: disable=broad-except
            pass

        self.ambientHumidityComboBox = QComboBox()
        self.ambientHumidityComboBox.currentIndexChanged.connect(self.ambientHumidityComboBoxIndexChanged)
        self.humidityDeviceCombo = QComboBox()
        self.humidityDeviceCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.humidityDeviceCombo.addItems(self.aw.qmc.humiditydevicefunctionlist)
        self.humidityDeviceCombo.currentIndexChanged.connect(self.humidityDeviceComboBoxIndexChanged)
        try:
            self.humidityDeviceCombo.setCurrentIndex(self.aw.qmc.ambient_humidity_device)
        except Exception: # pylint: disable=broad-except
            pass

        self.ambientPressureComboBox = QComboBox()
        self.ambientPressureComboBox.currentIndexChanged.connect(self.ambientPressureComboBoxIndexChanged)
        self.pressureDeviceCombo = QComboBox()
        self.pressureDeviceCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pressureDeviceCombo.addItems(self.aw.qmc.pressuredevicefunctionlist)
        self.pressureDeviceCombo.currentIndexChanged.connect(self.pressureDeviceComboBoxIndexChanged)
        try:
            self.pressureDeviceCombo.setCurrentIndex(self.aw.qmc.ambient_pressure_device)
        except Exception: # pylint: disable=broad-except
            pass

        self.updateAmbientSourceComboBoxes()

        self.elevationSpinBox = QSpinBox()
        self.elevationSpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.elevationSpinBox.setRange(0,3000)
        self.elevationSpinBox.setSingleStep(1)
        self.elevationSpinBox.setValue(int(self.aw.qmc.elevation))
        self.elevationSpinBox.setSuffix(' ' + QApplication.translate('Label','MASL'))
        temperatureDeviceLabel = QLabel(QApplication.translate('Label','Temperature'))
        humidityDeviceLabel = QLabel(QApplication.translate('Label','Humidity'))
        pressureDeviceLabel = QLabel(QApplication.translate('Label','Pressure'))
        elevationLabel = QLabel(QApplication.translate('Label','Elevation'))
        ambientGrid = QGridLayout()
        ambientGrid.addWidget(ambientSourceLabel,0,2)
        ambientGrid.addWidget(temperatureDeviceLabel,1,0)
        ambientGrid.addWidget(self.temperatureDeviceCombo,1,1)
        ambientGrid.addWidget(self.ambientTempComboBox,1,2)
        ambientGrid.addWidget(humidityDeviceLabel,2,0)
        ambientGrid.addWidget(self.humidityDeviceCombo,2,1)
        ambientGrid.addWidget(self.ambientHumidityComboBox,2,2)
        ambientGrid.addWidget(pressureDeviceLabel,3,0)
        ambientGrid.addWidget(self.pressureDeviceCombo,3,1)
        ambientGrid.addWidget(self.ambientPressureComboBox,3,2)
        ambientGrid.addWidget(elevationLabel,4,0)
        ambientGrid.addWidget(self.elevationSpinBox,4,1)
        ambientHBox = QHBoxLayout()
        ambientHBox.addStretch()
        ambientHBox.addLayout(ambientGrid)
        ambientHBox.addStretch()
        ambientVBox = QVBoxLayout()
        ambientVBox.addStretch()
        ambientVBox.addLayout(ambientHBox)
        ambientVBox.addStretch()
        ambientVBox.setContentsMargins(0,0,0,0)

        #https://stackoverflow.com/questions/106179/regular-expression-to-match-dns-hostname-or-ip-address
        #ValidIpAddressRegex = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$";
        #ValidHostnameRegex = "^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$";
        regexhost = QRegularExpression(r'(^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$)|(^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$)')

        eventFlagLabels = [
            QApplication.translate('Label','CHARGE'),
            QApplication.translate('Label','DRY'),
            QApplication.translate('Label','FCs'),
            QApplication.translate('Label','FCe'),
            QApplication.translate('Label','SCs'),
            QApplication.translate('Label','SCe'),
            QApplication.translate('Label','DROP')
        ]

        kaleidoHostLabel = QLabel(QApplication.translate('Label','Host'))
        self.kaleidoHost = QLineEdit(self.aw.kaleidoHost)
        self.kaleidoHost.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.kaleidoHost.setFixedWidth(150)
        self.kaleidoHost.setValidator(QRegularExpressionValidator(regexhost,self.kaleidoHost))
        self.kaleidoHost.setEnabled(not self.aw.kaleidoSerial)
        kaleidoPortLabel = QLabel(QApplication.translate('Label','Port'))
        self.kaleidoPort = QLineEdit(str(self.aw.kaleidoPort))
        self.kaleidoPort.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.kaleidoPort.setFixedWidth(150)
        self.kaleidoPort.setValidator(QIntValidator(1, 65535,self.kaleidoPort))
        self.kaleidoPort.setEnabled(not self.aw.kaleidoSerial)
        self.kaleidoSerialFlag = QCheckBox(QApplication.translate('Label','WiFi'))
        self.kaleidoSerialFlag.setChecked(not self.aw.kaleidoSerial)
        self.kaleidoSerialFlag.stateChanged.connect(self.kaleidoSerialStateChanged)
        self.kaleidoMachinePIDButton = QRadioButton(QApplication.translate('Radio Button','Machine PID'))
        self.kaleidoSoftwarePIDButton = QRadioButton(QApplication.translate('Radio Button','Software PID'))
        self.kaleidoHybridButton = QRadioButton(QApplication.translate('Radio Button','Hybrid Controller'))
        self.kaleidoHybridButton.setToolTip(
            QApplication.translate('Tooltip','Coordinated heater (RoR) and fan (ET-BT offset) control. Disables machine PID.'))
        if self.aw.kaleidoHybridControl:
            self.kaleidoHybridButton.setChecked(True)
        elif self.aw.kaleidoPID:
            self.kaleidoMachinePIDButton.setChecked(True)
        else:
            self.kaleidoSoftwarePIDButton.setChecked(True)
        self.kaleidoControlButtonGroup = QButtonGroup()
        self.kaleidoControlButtonGroup.addButton(self.kaleidoMachinePIDButton)
        self.kaleidoControlButtonGroup.addButton(self.kaleidoSoftwarePIDButton)
        self.kaleidoControlButtonGroup.addButton(self.kaleidoHybridButton)
        hybridBackendLabel = QLabel(QApplication.translate('Label','Hybrid backend'))
        self.hybridBackendCombo = QComboBox()
        self.hybridBackendCombo.addItem(QApplication.translate('ComboBox','Energy'), 'energy')
        self.hybridBackendCombo.addItem(QApplication.translate('ComboBox','MPC'), 'mpc')
        backend_idx = self.hybridBackendCombo.findData(self.aw.hybridControlBackend)
        self.hybridBackendCombo.setCurrentIndex(backend_idx if backend_idx >= 0 else 0)
        self.hybridBackendCombo.setToolTip(
            QApplication.translate(
                'Tooltip',
                'Energy: shipped Layer-2 controller. MPC: horizon optimizer (falls back to Energy on timeout).'))
        self.hybridBackendCombo.setEnabled(self.aw.kaleidoHybridControl)
        self.kaleidoHybridButton.toggled.connect(self.hybridBackendCombo.setEnabled)
        hybridBackendRow = QHBoxLayout()
        hybridBackendRow.addSpacing(20)
        hybridBackendRow.addWidget(hybridBackendLabel)
        hybridBackendRow.addWidget(self.hybridBackendCombo)
        hybridBackendRow.addStretch()
        kaleidoControlVBox = QVBoxLayout()
        kaleidoControlVBox.addWidget(self.kaleidoMachinePIDButton)
        kaleidoControlVBox.addWidget(self.kaleidoSoftwarePIDButton)
        kaleidoControlVBox.addWidget(self.kaleidoHybridButton)
        kaleidoControlVBox.addLayout(hybridBackendRow)
        self.kaleidoControlGroupBox = QGroupBox(QApplication.translate('GroupBox','Kaleido Control'))
        self.kaleidoControlGroupBox.setLayout(kaleidoControlVBox)
        self.kaleidoControlGroupBox.setToolTip(
            QApplication.translate('Tooltip','Select how Artisan controls the Kaleido roaster when PID is ON'))

        self.kaleidoEventFlags:list[QCheckBox] = [QCheckBox(l) for l in eventFlagLabels]
        for i, cb in enumerate(self.kaleidoEventFlags):
            cb.setToolTip(QApplication.translate('Tooltip','Receive {} event from machine').format(cb.text()))
            if len(self.aw.kaleidoEventFlags) > i:
                cb.setChecked(self.aw.kaleidoEventFlags[i])


        kaleidoNetworkGrid = QGridLayout()
        kaleidoNetworkGrid.addWidget(self.kaleidoSerialFlag,0,0)
        kaleidoNetworkGrid.addWidget(kaleidoHostLabel,0,1)
        kaleidoNetworkGrid.addWidget(self.kaleidoHost,0,2)
        kaleidoNetworkGrid.addWidget(kaleidoPortLabel,1,1)
        kaleidoNetworkGrid.addWidget(self.kaleidoPort,1,2)
        kaleidoNetworkGrid.setSpacing(20)
        kaleidoHBox = QHBoxLayout()
        kaleidoHBox.addLayout(kaleidoNetworkGrid)
        kaleidoHBox.addStretch()

        kaleidoEventFlagHBox = QHBoxLayout()
        kaleidoEventFlagHBox.setSpacing(17)
        kaleidoEventFlagHBox.addStretch()
        kaleidoEventFlagHBox.addSpacing(20)
        for cb in self.kaleidoEventFlags:
            kaleidoEventFlagHBox.addWidget(cb)
        kaleidoEventFlagHBox.addSpacing(20)
        kaleidoEventFlagHBox.addStretch()

        kaleidoVBox = QVBoxLayout()
        kaleidoVBox.addLayout(kaleidoHBox)
        kaleidoVBox.addSpacing(15)
        kaleidoVBox.addLayout(kaleidoEventFlagHBox)
        kaleidoVBox.addStretch()
        kaleidoVBox.setSpacing(5)
        kaleidoVBox.setContentsMargins(7,5,7,5) # left, top, right, bottom

        kaleidoNetworkGroupBox = QGroupBox('Kaleido')
        kaleidoNetworkGroupBox.setLayout(kaleidoVBox)


        #ET BT symbolic adjustments/assignments Box
        self.updateETBTButton = QPushButton(QApplication.translate('Button','Update Profile'))
        self.updateETBTButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.updateETBTButton.setToolTip(QApplication.translate('Tooltip','Recaclulates ET and BT and updates their values in the profile'))
        self.updateETBTButton.clicked.connect(self.updateETBTinprofile)

        adjustmentHelp = QHBoxLayout()
        adjustmentHelp.addWidget(self.updateETBTButton)
        adjustmentHelp.addStretch()
        adjustmentHelp.addWidget(symbolicHelpButton)
        adjustmentGroupBox = QGroupBox(QApplication.translate('GroupBox','Symbolic Assignments'))
        adjustmentsLayout = QVBoxLayout()
        adjustmentsLayout.addWidget(labelETadvanced)
        adjustmentsLayout.addWidget(self.ETfunctionedit)
        adjustmentsLayout.addWidget(labelBTadvanced)
        adjustmentsLayout.addWidget(self.BTfunctionedit)
        adjustmentsLayout.addStretch()

        adjustmentsLayout.addLayout(adjustmentHelp)
        # create arduino box
        filtgrid = QGridLayout()
        for i in range(4):
            filtgrid.addWidget(self.FILTspinBoxes[i],1,i+2)
        filtgridBox = QHBoxLayout()
        filtgridBox.addLayout(filtgrid)
        filtgridBox.addStretch()
        filtgridBox.setContentsMargins(5,5,5,5)
        arduinogrid = QGridLayout()
        arduinogrid.addWidget(arduinoETLabel,1,0,Qt.AlignmentFlag.AlignRight)
        arduinogrid.addWidget(self.arduinoETComboBox,1,1)
        arduinogrid.addWidget(arduinoBTLabel,2,0,Qt.AlignmentFlag.AlignRight)
        arduinogrid.addWidget(self.arduinoBTComboBox,2,1)
        arduinogrid.addWidget(self.arduinoATComboBox,2,3)
        arduinogrid.addWidget(arduinoATLabel,2,4)
        arduinogrid.addWidget(self.showControlButton,2,5)
        arduinogrid.addWidget(FILTLabel,1,3,Qt.AlignmentFlag.AlignRight)
        arduinogrid.addLayout(filtgridBox,1,4,1,2)
        arduinogridBox = QHBoxLayout()
        arduinogridBox.addLayout(arduinogrid)
        arduinogridBox.addStretch()
        arduinogridBox.setContentsMargins(5,5,5,5)
        arduinoBox = QVBoxLayout()
        arduinoBox.addLayout(arduinogridBox)
        arduinoBox.setContentsMargins(5,5,5,5)
        arduinoGroupBox = QGroupBox(QApplication.translate('GroupBox','Arduino TC4'))
        arduinoGroupBox.setLayout(arduinoBox)
        arduinoBox.setContentsMargins(0,0,0,0)
        arduinoGroupBox.setContentsMargins(0,12,0,0)

        adjustmentGroupBox.setLayout(adjustmentsLayout)
        #LAYOUT TAB 1
        deviceSubSelector = QHBoxLayout()
        deviceSubSelector.addWidget(self.controlButtonFlag)
        deviceSubSelector.addSpacing(35)
        deviceSubSelector.addWidget(self.curves)
        deviceSubSelector.addSpacing(15)
        deviceSubSelector.addWidget(self.lcds)

        deviceSelector = QHBoxLayout()
        deviceSelector.addWidget(self.devicetypeComboBox)
        deviceSelector.addStretch()
        deviceSelector.addLayout(deviceSubSelector)

        grid = QGridLayout()
        grid.addWidget(self.nonpidButton,2,0)
        grid.addLayout(deviceSelector,2,1)
        grid.setSpacing(3)
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.deviceLoggingFlag)
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.dialogbuttons)
        buttonLayout.setSpacing(10)
        tab1Layout = QVBoxLayout()
        tab1Layout.addLayout(grid)
        tab1Layout.addWidget(arduinoGroupBox)
        tab1Layout.addWidget(self.kaleidoControlGroupBox)
        tab1Layout.setContentsMargins(5,5,5,5)
        tab1Layout.addStretch()
        bLayout = QHBoxLayout()
        bLayout.addWidget(self.addButton)
        bLayout.addWidget(self.delButton)
        bLayout.addWidget(self.copydeviceTableButton)
        bLayout.addStretch()
        bLayout.addSpacing(10)
        bLayout.addWidget(self.recalcButton)
        bLayout.addStretch()
        bLayout.addSpacing(10)
        bLayout.addWidget(resetButton)
        bLayout.addSpacing(10)
        bLayout.addWidget(extradevHelpButton)
        #LAYOUT TAB 2 (Extra Devices)
        tab2Layout = QVBoxLayout()
        tab2Layout.addWidget(self.devicetable)
        tab2Layout.setSpacing(5)
        tab2Layout.setContentsMargins(0,10,0,5)
        tab2Layout.addLayout(bLayout)
        #LAYOUT TAB 3 (Symb ET/BT)
        tab3Layout = QVBoxLayout()
        tab3Layout.addWidget(adjustmentGroupBox)
        tab3Layout.setContentsMargins(2,10,2,5)
        #LAYOUT TAB 4 (Phidgets)
        tab4Layout = QVBoxLayout()
        tab4Layout.addLayout(phidgetVBox)
        tab4Layout.setContentsMargins(2,10,2,5)
        tab4Layout.setSpacing(3)
        #LAYOUT TAB 5 (Yoctopuce)
        tab5Layout = QVBoxLayout()
        tab5Layout.addLayout(yoctoVBox)
        tab5Layout.setContentsMargins(2,10,2,5)
        #LAYOUT TAB 6 (Ambient)
        tab6Layout = QVBoxLayout()
        tab6Layout.addLayout(ambientVBox)
        tab6Layout.setContentsMargins(2,10,2,5)
        #LAYOUT TAB Networks (Kaleido only)
        tab7Layout = QVBoxLayout()
        tab7Layout.addWidget(kaleidoNetworkGroupBox)
        tab7Layout.addStretch()
        tab7Layout.setContentsMargins(2,10,2,5)

        #main tab widget
        self.TabWidget = QTabWidget()
        C1Widget = QWidget()
        C1Widget.setLayout(tab1Layout)
        self.TabWidget.addTab(C1Widget,QApplication.translate('Tab','ET/BT'))
        C2Widget = QWidget()
        C2Widget.setLayout(tab2Layout)
        self.TabWidget.addTab(C2Widget,QApplication.translate('Tab','Extra Devices'))
        C3Widget = QWidget()
        C3Widget.setLayout(tab3Layout)
        self.TabWidget.addTab(C3Widget,QApplication.translate('Tab','Symb ET/BT'))
        C4Widget = QWidget()
        C4Widget.setLayout(tab4Layout)
        self.TabWidget.addTab(C4Widget,'Phidgets')
        C5Widget = QWidget()
        C5Widget.setLayout(tab5Layout)
        self.TabWidget.addTab(C5Widget,'Yoctopuce')
        C6Widget = QWidget()
        C6Widget.setLayout(tab6Layout)
        self.TabWidget.addTab(C6Widget,QApplication.translate('Tab','Ambient'))
        C7Widget = QWidget()
        C7Widget.setLayout(tab7Layout)
        self.TabWidget.addTab(C7Widget,QApplication.translate('Tab','Networks'))
        self.TabWidget.currentChanged.connect(self.tabSwitched)
        self.devicetypeComboBox.currentIndexChanged.connect(self.updateKaleidoControlVisibility)
        self.nonpidButton.toggled.connect(self.updateKaleidoControlVisibility)
        self.updateKaleidoControlVisibility()
        #incorporate layouts
        Mlayout = QVBoxLayout()
        Mlayout.addWidget(self.TabWidget)
        Mlayout.addLayout(buttonLayout)
        Mlayout.setSpacing(0)
        Mlayout.setContentsMargins(5,10,5,5)
        self.setLayout(Mlayout)
        if platform.system() != 'Windows':
            ok_button: QPushButton|None = self.dialogbuttons.button(QDialogButtonBox.StandardButton.Ok)
            if ok_button is not None:
                ok_button.setFocus()
        else:
            self.TabWidget.setFocus()
        settings = QSettings()
        if settings.contains('DeviceAssignmentGeometry'):
            self.restoreGeometry(settings.value('DeviceAssignmentGeometry'))

        # we set the active tab with a QTimer after the tabbar has been rendered once, as otherwise
        # some tabs are not rendered at all on Windows using Qt v6.5.1 (https://bugreports.qt.io/projects/QTBUG/issues/QTBUG-114204?filter=allissues)
        QTimer.singleShot(50, self.setActiveTab)


    @pyqtSlot(int)
    def temperatureDeviceComboBoxIndexChanged(self, i:int) -> None:
        self.ambientTempComboBox.setEnabled(i == 0)

    @pyqtSlot(int)
    def humidityDeviceComboBoxIndexChanged(self, i:int) -> None:
        self.ambientHumidityComboBox.setEnabled(i == 0)

    @pyqtSlot(int)
    def pressureDeviceComboBoxIndexChanged(self, i:int) -> None:
        self.ambientPressureComboBox.setEnabled(i == 0)

    @pyqtSlot(int)
    def yoctoBoxRemoteFlagStateChanged(self, _:int) -> None:
        self.aw.qmc.yoctoRemoteFlag = not self.aw.qmc.yoctoRemoteFlag
        self.yoctoServerId.setEnabled(self.aw.qmc.yoctoRemoteFlag)

    @pyqtSlot(int)
    def phidgetRemoteStateChanged(self, _:int) -> None:
        self.aw.qmc.phidgetRemoteFlag = not self.aw.qmc.phidgetRemoteFlag
        self.phidgetServerId.setEnabled(self.aw.qmc.phidgetRemoteFlag)
        self.phidgetPassword.setEnabled(self.aw.qmc.phidgetRemoteFlag)
        self.phidgetPort.setEnabled(self.aw.qmc.phidgetRemoteFlag)
        self.phidgetBoxRemoteOnlyFlag.setEnabled(self.aw.qmc.phidgetRemoteFlag)

    @pyqtSlot(str)
    def phidgetHostChanged(self, s:str) -> None:
        self.phidgetPassword.setEnabled(s != '')

    @pyqtSlot(int)
    def asyncFlagStateChanged1048(self, x:int) -> None:
        try:
            sender = cast(QCheckBox, self.sender())
            i = self.asyncCheckBoxes1048.index(sender)
            if x == 0:
                self.changeTriggerCombos1048[i].setEnabled(False)
            else:
                self.changeTriggerCombos1048[i].setEnabled(True)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)

    @pyqtSlot(int)
    def asyncFlagStateChanged1045(self, x:int) -> None:
        if x == 0:
            self.changeTriggerCombos1045.setEnabled(False)
        else:
            self.changeTriggerCombos1045.setEnabled(True)

    @pyqtSlot(int)
    def asyncFlagStateChanged1200(self, x:int) -> None:
        if x == 0:
            self.changeTriggerCombo1200.setEnabled(False)
        else:
            self.changeTriggerCombo1200.setEnabled(True)

    @pyqtSlot(int)
    def asyncFlagStateChanged1200_2(self, x:int) -> None:
        if x == 0:
            self.changeTriggerCombo1200_2.setEnabled(False)
        else:
            self.changeTriggerCombo1200_2.setEnabled(True)

    @pyqtSlot(int)
    def asyncFlagStateChanged(self, x:int) -> None:
        try:
            sender = cast(QCheckBox, self.sender())
            i = self.asyncCheckBoxes.index(sender)
            if x == 0:
                self.changeTriggerCombos[i].setEnabled(False)
            else:
                self.changeTriggerCombos[i].setEnabled(True)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)

    @staticmethod
    def createItems(strs:list[str]) -> list[QStandardItem]:
        items:list[QStandardItem] = []
        for st in strs:
            item = QStandardItem(st)
            items.append(item)
        return items

    @pyqtSlot(int)
    def PIDfirmwareToggle(self, i:int) -> None:
        if i:
            self.aw.qmc.PIDbuttonflag = True
        else:
            self.aw.qmc.PIDbuttonflag = False
        self.aw.showControlButton()

    @pyqtSlot(int)
    def ambientTempComboBoxIndexChanged(self, i:int) -> None:
        self.aw.qmc.ambientTempSource = i

    @pyqtSlot(int)
    def ambientHumidityComboBoxIndexChanged(self, i:int) -> None:
        self.aw.qmc.ambientHumiditySource = i

    @pyqtSlot(int)
    def ambientPressureComboBoxIndexChanged(self, i:int) -> None:
        self.aw.qmc.ambientPressureSource = i

    def buildAmbientTemperatureSourceList(self) -> list[str]:
        extra_names = []
        for i in range(len(self.aw.qmc.extradevices)):
            try:
                name1edit = cast(QLineEdit, self.devicetable.cellWidget(i,3))
                extra_names.append(self.aw.qmc.device_name_subst(name1edit.text()))
            except Exception: # pylint: disable=broad-except
                # on __init__ the device table might not yet have been created to read off the edited names
                extra_names.append(self.aw.qmc.device_name_subst(self.aw.qmc.extraname1[i]))
            try:
                name2edit = cast(QLineEdit, self.devicetable.cellWidget(i,4))
                extra_names.append(self.aw.qmc.device_name_subst(name2edit.text()))
            except Exception: # pylint: disable=broad-except
                # on __init__ the device table might not yet have been created to read off the edited names
                extra_names.append(self.aw.qmc.device_name_subst(self.aw.qmc.extraname2[i]))
        return ['',
                self.aw.qmc.device_name_subst(self.aw.ETname),
                self.aw.qmc.device_name_subst(self.aw.BTname)] + extra_names

    def updateAmbientSourceComboBoxes(self) -> None:
        ambientSensorSourceList = self.buildAmbientTemperatureSourceList()
        #-
        if len(ambientSensorSourceList) <= self.aw.qmc.ambientTempSource:
            self.aw.qmc.ambientTempSource = 0
        self.ambientTempComboBox.blockSignals(True)
        self.ambientTempComboBox.clear()
        self.ambientTempComboBox.addItems(ambientSensorSourceList)
        self.ambientTempComboBox.setCurrentIndex(self.aw.qmc.ambientTempSource)
        self.ambientTempComboBox.blockSignals(False)
        #-
        if len(ambientSensorSourceList) <= self.aw.qmc.ambientHumiditySource:
            self.aw.qmc.ambientHumiditySource = 0
        self.ambientHumidityComboBox.blockSignals(True)
        self.ambientHumidityComboBox.clear()
        self.ambientHumidityComboBox.addItems(ambientSensorSourceList)
        self.ambientHumidityComboBox.setCurrentIndex(self.aw.qmc.ambientHumiditySource)
        self.ambientHumidityComboBox.blockSignals(False)
        #-
        if len(ambientSensorSourceList) <= self.aw.qmc.ambientPressureSource:
            self.aw.qmc.ambientPressureSource = 0
        self.ambientPressureComboBox.blockSignals(True)
        self.ambientPressureComboBox.clear()
        self.ambientPressureComboBox.addItems(ambientSensorSourceList)
        self.ambientPressureComboBox.setCurrentIndex(self.aw.qmc.ambientPressureSource)
        self.ambientPressureComboBox.blockSignals(False)


    @pyqtSlot()
    def setActiveTab(self) -> None:
        self.TabWidget.setCurrentIndex(self.activeTab)
        # we create the device table here instead of __init__ as otherwise setting the columnWidth to the saved defaults has no effect using Qt 6.2.2
        self.createDeviceTable()


    @pyqtSlot(int)
    def kaleidoSerialStateChanged(self, _:int) -> None:
        self.aw.kaleidoSerial = not self.aw.kaleidoSerial
        self.kaleidoHost.setEnabled(not self.aw.kaleidoSerial)
        self.kaleidoPort.setEnabled(not self.aw.kaleidoSerial)

    def showControlbuttonToggle(self, i:int) -> None:
        if i:
            self.aw.qmc.Controlbuttonflag = True
        else:
            self.aw.qmc.Controlbuttonflag = False
        self.aw.showControlButton()

    @pyqtSlot(bool)
    @pyqtSlot(int)
    def updateKaleidoControlVisibility(self, *_args:bool|int) -> None:
        is_kaleido = (self.nonpidButton.isChecked() and
                      str(self.devicetypeComboBox.currentText()) == 'Kaleido BT/ET')
        self.kaleidoControlGroupBox.setVisible(is_kaleido)

    @staticmethod
    def centeredCheckBox() -> tuple[QWidget, QCheckBox]:
        widget = QWidget()
        checkBox = QCheckBox()
        checkBox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QHBoxLayout(widget)
        layout.addWidget(checkBox)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0,0,0,0)
        return widget, checkBox

    @staticmethod
    def centeredCheckBox_isChecked(widget:QWidget|None) -> bool:
        if widget is not None:
            layout = widget.layout()
            if layout is not None:
                item0 = layout.itemAt(0)
                if item0 is not None:
                    checkBox = item0.widget()
                    if checkBox is not None and isinstance(checkBox, QCheckBox):
                        return checkBox.isChecked() # type:ignore[reportAttributeAccessIssue, unused-ignore] # pyright reports isChecked not known for QWidget
        return False

    def createDeviceTable(self) -> None:
        try:
            columns = 15
            if self.devicetable.columnCount() == columns:
                # rows have been already established
                # save the current columnWidth to reset them after table creation
                self.aw.qmc.devicetablecolumnwidths = [self.devicetable.columnWidth(c) for c in range(self.devicetable.columnCount())]

            nddevices = len(self.aw.qmc.extradevices)
            #self.devicetable.clear() # this crashes Ubuntu 16.04
#            if nddevices != 0:
#                self.devicetable.clearContents() # this crashes Ubuntu 16.04 if device table is empty
#            self.devicetable.clearSelection()

            self.devicetable.setRowCount(nddevices)
            self.devicetable.setColumnCount(columns)
            self.devicetable.setHorizontalHeaderLabels([QApplication.translate('Table', 'Device'),
                                                        QApplication.translate('Table', 'Color 1'),
                                                        QApplication.translate('Table', 'Color 2'),
                                                        QApplication.translate('Table', 'Label 1'),
                                                        QApplication.translate('Table', 'Label 2'),
                                                        QApplication.translate('Table', 'y1(x)'),
                                                        QApplication.translate('Table', 'y2(x)'),
                                                        QApplication.translate('Table', 'LCD 1'),
                                                        QApplication.translate('Table', 'LCD 2'),
                                                        QApplication.translate('Table', 'Curve 1'),
                                                        QApplication.translate('Table', 'Curve 2'),
                                                        deltaLabelUTF8 + ' ' + QApplication.translate('GroupBox','Axis') + ' 1',
                                                        deltaLabelUTF8 + ' ' + QApplication.translate('GroupBox','Axis') + ' 2',
                                                        QApplication.translate('Table', 'Fill 1'),
                                                        QApplication.translate('Table', 'Fill 2')])
            self.devicetable.setAlternatingRowColors(True)
            self.devicetable.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.devicetable.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.devicetable.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

#            self.devicetable.setStyleSheet("selection-background-color: transparent;") # avoid the selection color to shine through transparent device color items

            self.devicetable.setShowGrid(True)
            vheader = self.devicetable.verticalHeader()
            if vheader is not None:
                vheader.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

            fixed_size_sections = [7,8,9,10,11,12,13,14]
            if nddevices:
                dev = self.aw.qmc.devices[:]             #deep copy
                limit = len(dev)
                for _ in range(limit):
                    for i, _ in enumerate(dev):
                        if dev[i][0] == '-' or dev[i] == 'NONE': # non manual device or deactivated device in extra device list
                            dev.pop(i)              #note: pop() makes the list smaller
                            break
                devices = sorted(((x[1:] if x.startswith('+') else x) for x in dev), key=lambda x: (x[1:] if x.startswith('+') else x))
                for i in range(nddevices):
                    try:
                        # 0: device type
                        typeComboBox =  MyContentLimitedQComboBox()
#                        typeComboBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow) # default
                        typeComboBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
#                        typeComboBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
                        typeComboBox.addItems(devices[:])
                        try:
                            dev_name = self.aw.qmc.devices[max(0,self.aw.qmc.extradevices[i]-1)]
                            if dev_name[0] == '+':
                                dev_name = dev_name[1:]
                            typeComboBox.setCurrentIndex(devices.index(dev_name))
                        except Exception: # pylint: disable=broad-except
                            pass
                        # 1: color 1
                        color1Button = QPushButton(self.aw.qmc.extradevicecolor1[i])
                        color1Button.clicked.connect(self.setextracolor1)
                        textcolor = self.aw.labelBorW(self.aw.qmc.extradevicecolor1[i])
                        color1Button.setStyleSheet(f"selection-background-color: transparent; border: none; outline: none; background-color: rgba{ImageColor.getcolor(self.aw.qmc.extradevicecolor1[i], 'RGBA')}; color: {textcolor}")
                        color1Button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                        # 2: color 2
                        color2Button = QPushButton(self.aw.qmc.extradevicecolor2[i])
                        color2Button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                        color2Button.clicked.connect(self.setextracolor2)
                        textcolor = self.aw.labelBorW(self.aw.qmc.extradevicecolor2[i])
                        color2Button.setStyleSheet(f"selection-background-color: transparent; border: none; outline: none; background-color: rgba{ImageColor.getcolor(self.aw.qmc.extradevicecolor2[i], 'RGBA')}; color: {textcolor}")
                        # 3+4: name 1 + 2
                        name1edit = QLineEdit(self.aw.qmc.extraname1[i])
                        name2edit = QLineEdit(self.aw.qmc.extraname2[i])
                        # 5+6: math 1 + 2
                        mexpr1edit = QLineEdit(self.aw.qmc.extramathexpression1[i])
                        mexpr2edit = QLineEdit(self.aw.qmc.extramathexpression2[i])
                        mexpr1edit.setToolTip(QApplication.translate('Tooltip','Example: 100 + 2*x'))
                        mexpr2edit.setToolTip(QApplication.translate('Tooltip','Example: 100 + x'))
                        # 7: lcd 1
                        LCD1widget, LCD1visibilityQCheckBox = self.centeredCheckBox()
                        if self.aw.extraLCDvisibility1[i]:
                            LCD1visibilityQCheckBox.setCheckState(Qt.CheckState.Checked)
                        else:
                            LCD1visibilityQCheckBox.setCheckState(Qt.CheckState.Unchecked)
                        LCD1visibilityQCheckBox.stateChanged.connect(self.updateLCDvisibility1)
                        # 8: lcd 2
                        LCD2widget, LCD2visibilityQCheckBox = self.centeredCheckBox()
                        if self.aw.extraLCDvisibility2[i]:
                            LCD2visibilityQCheckBox.setCheckState(Qt.CheckState.Checked)
                        else:
                            LCD2visibilityQCheckBox.setCheckState(Qt.CheckState.Unchecked)
                        LCD2visibilityQCheckBox.stateChanged.connect(self.updateLCDvisibility2)
                        # 9: curve 1
                        Curve1widget, Curve1visibilityQCheckBox = self.centeredCheckBox()
                        if self.aw.extraCurveVisibility1[i]:
                            Curve1visibilityQCheckBox.setCheckState(Qt.CheckState.Checked)
                        else:
                            Curve1visibilityQCheckBox.setCheckState(Qt.CheckState.Unchecked)
                        Curve1visibilityQCheckBox.stateChanged.connect(self.updateCurveVisibility1)
                        # 10: curve 2
                        Curve2widget, Curve2visibilityQCheckBox = self.centeredCheckBox()
                        if self.aw.extraCurveVisibility2[i]:
                            Curve2visibilityQCheckBox.setCheckState(Qt.CheckState.Checked)
                        else:
                            Curve2visibilityQCheckBox.setCheckState(Qt.CheckState.Unchecked)
                        Curve2visibilityQCheckBox.stateChanged.connect(self.updateCurveVisibility2)
                        # 11: delta 1
                        Delta1widget, Delta1QCheckBox = self.centeredCheckBox()
                        if self.aw.extraDelta1[i]:
                            Delta1QCheckBox.setCheckState(Qt.CheckState.Checked)
                        else:
                            Delta1QCheckBox.setCheckState(Qt.CheckState.Unchecked)
                        Delta1QCheckBox.stateChanged.connect(self.updateDelta1)
                        # 12: delta 2
                        Delta2widget, Delta2QCheckBox = self.centeredCheckBox()
                        if self.aw.extraDelta2[i]:
                            Delta2QCheckBox.setCheckState(Qt.CheckState.Checked)
                        else:
                            Delta2QCheckBox.setCheckState(Qt.CheckState.Unchecked)
                        Delta2QCheckBox.stateChanged.connect(self.updateDelta2)
                        # 13: fill 1
                        Fill1SpinBox = QSpinBox()
                        Fill1SpinBox.setSingleStep(1)
                        Fill1SpinBox.setRange(0,100)
                        Fill1SpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
                        Fill1SpinBox.setValue(int(self.aw.extraFill1[i]))
                        Fill1SpinBox.editingFinished.connect(self.updateFill1)
                        # 14: fill 2
                        Fill2SpinBox = QSpinBox()
                        Fill2SpinBox.setSingleStep(1)
                        Fill2SpinBox.setRange(0,100)
                        Fill2SpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
                        Fill2SpinBox.setValue(int(self.aw.extraFill2[i]))
                        Fill2SpinBox.editingFinished.connect(self.updateFill2)
                        #add widgets to the table
                        self.devicetable.setCellWidget(i,0,typeComboBox)
                        self.devicetable.setCellWidget(i,1,color1Button)
                        self.devicetable.setCellWidget(i,2,color2Button)
                        self.devicetable.setCellWidget(i,3,name1edit)
                        self.devicetable.setCellWidget(i,4,name2edit)
                        self.devicetable.setCellWidget(i,5,mexpr1edit)
                        self.devicetable.setCellWidget(i,6,mexpr2edit)
                        self.devicetable.setCellWidget(i,7,LCD1widget)
                        self.devicetable.setCellWidget(i,8,LCD2widget)
                        self.devicetable.setCellWidget(i,9,Curve1widget)
                        self.devicetable.setCellWidget(i,10,Curve2widget)
                        self.devicetable.setCellWidget(i,11,Delta1widget)
                        self.devicetable.setCellWidget(i,12,Delta2widget)
                        self.devicetable.setCellWidget(i,13,Fill1SpinBox)
                        self.devicetable.setCellWidget(i,14,Fill2SpinBox)

                        # we add QTableWidgetItems disable selection of cells and to have tab focus to jump over those cells
                        color1item = QTableWidgetItem()
                        color1item.setFlags(Qt.ItemFlag.NoItemFlags)
                        self.devicetable.setItem(i,1,color1item)
                        color2item = QTableWidgetItem()
                        color2item.setFlags(Qt.ItemFlag.NoItemFlags)
                        self.devicetable.setItem(i,2,color2item)
                        for j in range(7, 13):
                            item = QTableWidgetItem()
                            item.setFlags(Qt.ItemFlag.NoItemFlags)
                            self.devicetable.setItem(i,j,item)

                    except Exception as e: # pylint: disable=broad-except
                        _log.exception(e)
                header = self.devicetable.horizontalHeader()
                if header is not None:
                    header.setStretchLastSection(False)
                    self.devicetable.resizeColumnsToContents()
                    for i in fixed_size_sections:
                        header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                        header.resizeSection(i, header.sectionSize(i) + 5)
            if not self.aw.qmc.devicetablecolumnwidths:
                self.devicetable.setColumnWidth(0, 230)
                self.devicetable.setColumnWidth(1, 80)
                self.devicetable.setColumnWidth(2, 80)
                self.devicetable.setColumnWidth(3, 80)
                self.devicetable.setColumnWidth(4, 80)
                self.devicetable.setColumnWidth(5, 40)
                self.devicetable.setColumnWidth(6, 40)
            else:
                # remember the columnwidth
                for i, _ in enumerate(self.aw.qmc.devicetablecolumnwidths):
                    if i not in fixed_size_sections:
                        try:
                            self.devicetable.setColumnWidth(i, self.aw.qmc.devicetablecolumnwidths[i])
                        except Exception: # pylint: disable=broad-except
                            pass
        except Exception as e: # pylint: disable=broad-except
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' createDeviceTable(): {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))

    @pyqtSlot(bool)
    def copyDeviceTabletoClipboard(self, _:bool = False) -> None:
        import prettytable
        nrows = self.devicetable.rowCount()
        ncols = self.devicetable.columnCount()
        clipboard = ''
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.KeyboardModifier.AltModifier:  #alt click
            tbl = prettytable.PrettyTable()
            fields = []
            re_strip = re.compile('[\u2009]')  #thin space is not read properly by prettytable
            for c in range(ncols):
                item = self.devicetable.horizontalHeaderItem(c)
                if item is not None:
                    fields.append(re_strip.sub('',item.text()))
            tbl.field_names = fields
            for r in range(nrows):
                rows:list[str] = []
                # device type
                typeComboBox = cast(MyQComboBox, self.devicetable.cellWidget(r,0))
                rows.append(typeComboBox.currentText())
                # color 1
                color1Button = cast(QPushButton, self.devicetable.cellWidget(r,1))
                rows.append(color1Button.palette().button().color().name())
                # color 2
                color2Button = cast(QPushButton, self.devicetable.cellWidget(r,2))
                rows.append(color2Button.palette().button().color().name())
                # name 1
                name1edit = cast(QLineEdit, self.devicetable.cellWidget(r,3))
                rows.append(name1edit.text())
                # name 2
                name2edit = cast(QLineEdit, self.devicetable.cellWidget(r,4))
                rows.append(name2edit.text())
                # math 1
                mexpr1edit = cast(QLineEdit, self.devicetable.cellWidget(r,5))
                rows.append(mexpr1edit.text())
                # math 2
                mexpr2edit = cast(QLineEdit, self.devicetable.cellWidget(r,6))
                rows.append(mexpr2edit.text())
                # lcd 1
                rows.append(str(self.centeredCheckBox_isChecked(self.devicetable.cellWidget(r,7))))
                # lcd 2
                rows.append(str(self.centeredCheckBox_isChecked(self.devicetable.cellWidget(r,8))))
                # curve 1
                rows.append(str(self.centeredCheckBox_isChecked(self.devicetable.cellWidget(r,9))))
                # curve 2
                rows.append(str(self.centeredCheckBox_isChecked(self.devicetable.cellWidget(r,10))))
                # delta 1
                rows.append(str(self.centeredCheckBox_isChecked(self.devicetable.cellWidget(r,11))))
                # delta 2
                rows.append(str(self.centeredCheckBox_isChecked(self.devicetable.cellWidget(r,12))))
                # fill 1
                Fill1SpinBox = cast(QSpinBox, self.devicetable.cellWidget(r,13))
                rows.append(str(Fill1SpinBox.value()))
            # fill 2
                Fill2SpinBox = cast(QSpinBox, self.devicetable.cellWidget(r,14))
                rows.append(str(Fill2SpinBox.value()))
                tbl.add_row(rows)
            clipboard = tbl.get_string()
        else:
            for c in range(ncols):
                item = self.devicetable.horizontalHeaderItem(c)
                if item is not None:
                    clipboard += item.text()
                    if c != (ncols-1):
                        clipboard += '\t'
            clipboard += '\n'
            for r in range(nrows):
                # device type
                typeComboBox = cast(MyQComboBox, self.devicetable.cellWidget(r,0))
                clipboard += typeComboBox.currentText() + '\t'
                # color 1
                color1Button = cast(QPushButton, self.devicetable.cellWidget(r,1))
                clipboard += color1Button.palette().button().color().name() + '\t'
                # color 2
                color2Button = cast(QPushButton, self.devicetable.cellWidget(r,2))
                clipboard += color2Button.palette().button().color().name() + '\t'
                # name 1
                name1edit = cast(QLineEdit, self.devicetable.cellWidget(r,3))
                clipboard += name1edit.text() + '\t'
                # name 2
                name2edit = cast(QLineEdit, self.devicetable.cellWidget(r,4))
                clipboard += name2edit.text() + '\t'
                # math 1
                mexpr1edit = cast(QLineEdit, self.devicetable.cellWidget(r,5))
                clipboard += mexpr1edit.text() + '\t'
                # math 2
                mexpr2edit = cast(QLineEdit, self.devicetable.cellWidget(r,6))
                clipboard += mexpr2edit.text() + '\t'
                # lcd 1
                LCD1visibilityWidget = cast(QWidget, self.devicetable.cellWidget(r,7))
                LCD1visibilityLayout = LCD1visibilityWidget.layout()
                if LCD1visibilityLayout is not None:
                    item0 = LCD1visibilityLayout.itemAt(0)
                    if item0 is not None:
                        LCD1visibilityCheckBox = cast(QCheckBox, item0.widget())
                        clipboard += str(LCD1visibilityCheckBox.isChecked()) + '\t'
                # lcde 2
                LCD2visibilityWidget = cast(QWidget, self.devicetable.cellWidget(r,8))
                LCD2visibilityLayout = LCD2visibilityWidget.layout()
                if LCD2visibilityLayout is not None:
                    item0 = LCD2visibilityLayout.itemAt(0)
                    if item0 is not None:
                        LCD2visibilityCheckBox = cast(QCheckBox, item0.widget())
                        clipboard += str(LCD2visibilityCheckBox.isChecked()) + '\t'
                # curve 1
                Curve1visibilityWidget = cast(QWidget, self.devicetable.cellWidget(r,9))
                Curve1visibilityLayout = Curve1visibilityWidget.layout()
                if Curve1visibilityLayout is not None:
                    item0 = Curve1visibilityLayout.itemAt(0)
                    if item0 is not None:
                        Curve1visibilityCheckBox = cast(QCheckBox, item0.widget())
                        clipboard += str(Curve1visibilityCheckBox.isChecked()) + '\t'
                # curve 2
                Curve2visibilityWidget = cast(QWidget, self.devicetable.cellWidget(r,10))
                Curve2visibilityLayout = Curve2visibilityWidget.layout()
                if Curve2visibilityLayout is not None:
                    item0 = Curve2visibilityLayout.itemAt(0)
                    if item0 is not None:
                        Curve2visibilityCheckBox = cast(QCheckBox, item0.widget())
                        clipboard += str(Curve2visibilityCheckBox.isChecked()) + '\t'
                # delta 1
                Delta1Widget = cast(QWidget, self.devicetable.cellWidget(r,11))
                Delta1Layout = Delta1Widget.layout()
                if Delta1Layout is not None:
                    item0 = Delta1Layout.itemAt(0)
                    if item0 is not None:
                        Delta1CheckBox = cast(QCheckBox, item0.widget())
                        clipboard += str(Delta1CheckBox.isChecked()) + '\t'
                # delta 2
                Delta2Widget = cast(QWidget, self.devicetable.cellWidget(r,12))
                Delta2Layout = Delta2Widget.layout()
                if Delta2Layout is not None:
                    item0 = Delta2Layout.itemAt(0)
                    if item0 is not None:
                        Delta2CheckBox = cast(QCheckBox, item0.widget())
                        clipboard += str(Delta2CheckBox.isChecked()) + '\t'
                # fill 1
                Fill1SpinBox = cast(QSpinBox, self.devicetable.cellWidget(r,13))
                clipboard += str(Fill1SpinBox.value()) + '\t'
                # fill 2
                Fill2SpinBox = cast(QSpinBox, self.devicetable.cellWidget(r,14))
                clipboard += str(Fill2SpinBox.value()) + '\n'
        # copy to the system clipboard
        sys_clip = QApplication.clipboard()
        if sys_clip is not None:
            sys_clip.setText(clipboard)
        self.aw.sendmessage(QApplication.translate('Message','Device table copied to clipboard'))

    def enableDisableAddDeleteButtons(self) -> None:
        if len(self.aw.qmc.extradevices) >= self.aw.nLCDS:
            self.addButton.setEnabled(False)
        else:
            self.addButton.setEnabled(True)
        if len(self.aw.qmc.extradevices) > 0:
            self.delButton.setEnabled(True)
        else:
            self.delButton.setEnabled(False)
        if len(self.aw.qmc.timex) > 0:
            self.recalcButton.setEnabled(True)
        else:
            self.recalcButton.setEnabled(False)

    #adds extra device
    @pyqtSlot(bool)
    def adddevice(self, _:bool) -> None:
        try:
            self.savedevicetable()
            #addDevice() is located in aw so that the same function can be used in init after dynamically loading settings
            self.aw.addDevice()
            self.createDeviceTable()
            self.enableDisableAddDeleteButtons()
            self.aw.qmc.resetlinecountcaches()
            self.aw.ser.arduinoETChannel = str(self.arduinoETComboBox.currentText())
            self.aw.ser.arduinoBTChannel = str(self.arduinoBTComboBox.currentText())
            self.aw.ser.arduinoATChannel = str(self.arduinoATComboBox.currentText())
            self.aw.ser.ArduinoFILT = [sb.value() for sb in self.FILTspinBoxes]
            self.aw.qmc.redraw(recomputeAllDeltas=False)
        except Exception as e: # pylint: disable=broad-except
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' adddevice(): {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))

    @pyqtSlot(bool)
    def deldevice(self, _:bool) -> None:
        try:
            self.savedevicetable()
            bindex = len(self.aw.qmc.extradevices)-1
            selected = self.devicetable.selectedRanges()
            if len(selected) > 0:
                bindex = selected[0].topRow()
            if 0 <= bindex < len(self.aw.qmc.extradevices):
                self.delextradevice(bindex)
                self.enableDisableAddDeleteButtons()
        except Exception as e: # pylint: disable=broad-except
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' deldevice(): {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))

    @pyqtSlot(bool)
    def resetextradevices(self, _:bool) -> None:
        try:
            self.aw.resetExtraDevices()
            #update table
            self.createDeviceTable()
            #enable/disable buttons
            self.enableDisableAddDeleteButtons()
            #redraw
            self.aw.qmc.redraw(recomputeAllDeltas=False)
        except Exception as e: # pylint: disable=broad-except
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' resetextradevices(): {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))

    # x the index of the extra device to be deleted
    def delextradevice(self, x:int) -> None:
        try:
            self.aw.qmc.extradevices.pop(x)
            self.aw.qmc.extradevicecolor1.pop(x)
            self.aw.qmc.extradevicecolor2.pop(x)
            self.aw.qmc.extratimex.pop(x)
            self.aw.qmc.extratemp1.pop(x)
            self.aw.qmc.extratemp2.pop(x)
            self.aw.qmc.extrastemp1.pop(x)
            self.aw.qmc.extrastemp2.pop(x)
            self.aw.qmc.extractimex1.pop(x)
            self.aw.qmc.extractimex2.pop(x)
            self.aw.qmc.extractemp1.pop(x)
            self.aw.qmc.extractemp2.pop(x)
            self.aw.qmc.extralinestyles1.pop(x)
            self.aw.qmc.extralinestyles2.pop(x)
            self.aw.qmc.extradrawstyles1.pop(x)
            self.aw.qmc.extradrawstyles2.pop(x)
            self.aw.qmc.extralinewidths1.pop(x)
            self.aw.qmc.extralinewidths2.pop(x)
            self.aw.qmc.extramarkers1.pop(x)
            self.aw.qmc.extramarkers2.pop(x)
            self.aw.qmc.extramarkersizes1.pop(x)
            self.aw.qmc.extramarkersizes2.pop(x)

            # visible curves before this one
            before1 = before2 = 0
            for j in range(x):
                if self.aw.extraCurveVisibility1[j]:
                    before1 = before1 + 1
                if self.aw.extraCurveVisibility2[j]:
                    before2 = before2 + 1
            if self.aw.extraCurveVisibility1[x]:
                self.aw.qmc.extratemp1lines.pop(before1)
            if self.aw.extraCurveVisibility2[x]:
                self.aw.qmc.extratemp2lines.pop(before2)

            # lists of constant length (self.aw.nLCDS)
            self.aw.extraLCDvisibility1.pop(x)
            self.aw.extraLCDvisibility1.append(False) # keep length constant (self.aw.nLCDS)
            self.aw.extraLCDvisibility2.pop(x)
            self.aw.extraLCDvisibility2.append(False) # keep length constant (self.aw.nLCDS)
            self.aw.extraCurveVisibility1.pop(x)
            self.aw.extraCurveVisibility1.append(True) # keep length constant (self.aw.nLCDS)
            self.aw.extraCurveVisibility2.pop(x)
            self.aw.extraCurveVisibility2.append(True) # keep length constant (self.aw.nLCDS)
            self.aw.extraDelta1.pop(x)
            self.aw.extraDelta1.append(False) # keep length constant (self.aw.nLCDS)
            self.aw.extraDelta2.pop(x)
            self.aw.extraDelta2.append(False) # keep length constant (self.aw.nLCDS)
            self.aw.extraFill1.pop(x)
            self.aw.extraFill1.append(0) # keep length constant (self.aw.nLCDS)
            self.aw.extraFill2.pop(x)
            self.aw.extraFill2.append(0) # keep length constant (self.aw.nLCDS)

            self.aw.qmc.extraname1.pop(x)
            self.aw.qmc.extraname2.pop(x)
            self.aw.qmc.extramathexpression1.pop(x)
            self.aw.qmc.extramathexpression2.pop(x)
            self.aw.updateLCDproperties()
            #pop serial port settings
            if len(self.aw.extracomport) > x:
                self.aw.extracomport.pop(x)
            if len(self.aw.extrabaudrate) > x:
                self.aw.extrabaudrate.pop(x)
            if len(self.aw.extrabytesize) > x:
                self.aw.extrabytesize.pop(x)
            if len(self.aw.extraparity) > x:
                self.aw.extraparity.pop(x)
            if len(self.aw.extrastopbits) > x:
                self.aw.extrastopbits.pop(x)
            if len(self.aw.extratimeout) > x:
                self.aw.extratimeout.pop(x)
            if len(self.aw.extraser) > x:
                if self.aw.extraser[x].SP.is_open:
                    self.aw.extraser[x].SP.close()
                    libtime.sleep(0.7) # on OS X opening a serial port too fast after closing the port gets disabled
                self.aw.extraser.pop(x)
            self.createDeviceTable()
            self.aw.qmc.resetlinecountcaches()
            self.aw.ser.arduinoETChannel = str(self.arduinoETComboBox.currentText())
            self.aw.ser.arduinoBTChannel = str(self.arduinoBTComboBox.currentText())
            self.aw.ser.arduinoATChannel = str(self.arduinoATComboBox.currentText())
            self.aw.ser.ArduinoFILT = [sb.value() for sb in self.FILTspinBoxes]
            self.aw.qmc.redraw(recomputeAllDeltas=False)
        except Exception as ex: # pylint: disable=broad-except
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + 'delextradevice(): {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))

    def savedevicetable(self, redraw:bool = True) -> None:
        try:
            for i, _ in enumerate(self.aw.qmc.extradevices):
                typecombobox = cast(MyQComboBox, self.devicetable.cellWidget(i,0))
                #cellWidget(i,1) and cellWidget(i,2) are saved automatically when there is a change. No need to save here.
                name1edit = cast(QLineEdit, self.devicetable.cellWidget(i,3))
                name2edit = cast(QLineEdit, self.devicetable.cellWidget(i,4))
                mexpr1edit = cast(QLineEdit, self.devicetable.cellWidget(i,5))
                mexpr2edit = cast(QLineEdit, self.devicetable.cellWidget(i,6))
                try:
                    self.aw.qmc.extradevices[i] = self.aw.qmc.devices.index(str(typecombobox.currentText())) + 1
                except Exception: # pylint: disable=broad-except
                    try: # might be a +device
                        self.aw.qmc.extradevices[i] = self.aw.qmc.devices.index('+' + str(typecombobox.currentText())) + 1
                    except Exception: # pylint: disable=broad-except
                        self.aw.qmc.extradevices[i] = 0
                self.aw.qmc.extraname1[i] = name1edit.text()
                self.aw.qmc.extraname2[i] = name2edit.text()

                self.aw.extraLCDlabel1[i].setText('<b>' + self.aw.qmc.device_name_subst(self.aw.qmc.extraname1[i]) + '</b>')
                self.aw.extraLCDlabel2[i].setText('<b>' + self.aw.qmc.device_name_subst(self.aw.qmc.extraname2[i]) + '</b>')
                self.aw.qmc.extramathexpression1[i] = mexpr1edit.text()
                self.aw.qmc.extramathexpression2[i] = mexpr2edit.text()
            #update legend with new curves
            if redraw:
                self.aw.qmc.redraw(recomputeAllDeltas=False)
        except Exception as ex: # pylint: disable=broad-except
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + 'savedevicetable(): {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))


    @pyqtSlot(bool)
    def updateVirtualdevicesinprofile_clicked(self, _:bool) -> None:
        self.updateVirtualdevicesinprofile(redraw=True)

    def updateVirtualdevicesinprofile(self, redraw:bool = True) -> None:
        try:
            self.savedevicetable(redraw=False)
            if self.aw.calcVirtualdevices(update=True) and redraw:
                self.aw.qmc.redraw(recomputeAllDeltas=False)
        except Exception as ex: # pylint: disable=broad-except
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + 'updateVirtualdevicesinprofile(): {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))

    @pyqtSlot(bool)
    def updateETBTinprofile(self, _:bool) -> None:
        try:
            # be sure there is an equation to process
            nonempty_ETfunction = bool(len(self.ETfunctionedit.text().strip()))
            nonempty_BTfunction = bool(len(self.BTfunctionedit.text().strip()))
            if (nonempty_ETfunction or nonempty_BTfunction):

                # confirm the action
                string = QApplication.translate('Message', 'Overwrite existing ET and BT values?')
                reply = QMessageBox.warning(None, #self.aw, # only without super this one shows the native dialog on macOS under Qt 6.6.2 and later
                            QApplication.translate('Message', 'Caution - About to overwrite profile data'),string,
                            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)
                if reply == QMessageBox.StandardButton.Cancel:
                    return

                # confirm updating the dependent Virtual Extra Devices?
                updatevirtualextradevices = False
                etorbt = re.compile('Y1|Y2|T1|T2|R1|R2')
                for j in range(len(self.aw.qmc.extradevices)):
                    if (re.search(etorbt,self.aw.qmc.extramathexpression1[j]) or re.search(etorbt,self.aw.qmc.extramathexpression2[j])):
                        string = QApplication.translate('Message', 'At least one Virtual Extra Device depends on ET or BT.  Do you want to update all the Virtual Extra Devices after ET and BT are updated?')
                        reply = QMessageBox.warning(None, #self.aw, # only without super this one shows the native dialog on macOS under Qt 6.6.2 and later
                                    QApplication.translate('Message', 'Caution - About to overwrite profile data'),string,
                                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.Yes:
                            updatevirtualextradevices = True
                        break

                # grab the latest symbolic equations as they may have changed without being saved by an OK
                self.aw.qmc.ETfunction = str(self.ETfunctionedit.text())
                self.aw.qmc.BTfunction = str(self.BTfunctionedit.text())

                # make the updates to ET.BT and Virtual Extra Devices if needed
                if self.aw.updateSymbolicETBT():
                    if updatevirtualextradevices:
                        self.updateVirtualdevicesinprofile(redraw=False)
                    self.aw.qmc.redraw(recomputeAllDeltas=True)
                    self.aw.sendmessage(QApplication.translate('Message', 'Symbolic values updated.'))
                else:
                    self.aw.sendmessage(QApplication.translate('Message', 'Symbolic values were not updated.'))
            else:
                self.aw.sendmessage(QApplication.translate('Message', 'Nothing here to process.'))
        except Exception as ex: # pylint: disable=broad-except
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + 'updateETBTinprofile(): {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))

    @pyqtSlot(int)
    def updateLCDvisibility1(self, x:int) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(),7)
        if r is not None:
            self.aw.extraLCDvisibility1[r] = bool(x)
            self.aw.extraLCDframe1[r].setVisible(bool(x))

    @pyqtSlot(int)
    def updateLCDvisibility2(self, x:int) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(),8)
        if r is not None:
            self.aw.extraLCDvisibility2[r] = bool(x)
            self.aw.extraLCDframe2[r].setVisible(bool(x))

    @pyqtSlot(int)
    def updateCurveVisibility1(self, x:int) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(),9)
        if r is not None:
            self.aw.extraCurveVisibility1[r] = bool(x)
            self.aw.qmc.resetlinecountcaches()
            self.aw.ser.arduinoETChannel = str(self.arduinoETComboBox.currentText())
            self.aw.ser.arduinoBTChannel = str(self.arduinoBTComboBox.currentText())
            self.aw.ser.arduinoATChannel = str(self.arduinoATComboBox.currentText())
            self.aw.ser.ArduinoFILT = [sb.value() for sb in self.FILTspinBoxes]

    @pyqtSlot(int)
    def updateCurveVisibility2(self, x:int) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(),10)
        if r is not None:
            self.aw.extraCurveVisibility2[r] = bool(x)
            self.aw.qmc.resetlinecountcaches()
            self.aw.ser.arduinoETChannel = str(self.arduinoETComboBox.currentText())
            self.aw.ser.arduinoBTChannel = str(self.arduinoBTComboBox.currentText())
            self.aw.ser.arduinoATChannel = str(self.arduinoATComboBox.currentText())
            self.aw.ser.ArduinoFILT = [sb.value() for sb in self.FILTspinBoxes]

    @pyqtSlot(int)
    def updateDelta1(self, x:int) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(),11)
        if r is not None:
            self.aw.extraDelta1[r] = bool(x)

    @pyqtSlot(int)
    def updateDelta2(self, x:int) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(),12)
        if r is not None:
            self.aw.extraDelta2[r] = bool(x)

    @pyqtSlot()
    def updateFill1(self) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(),13)
        if r is not None:
            sender = cast(QSpinBox, self.sender())
            self.aw.extraFill1[r] = sender.value()

    @pyqtSlot()
    def updateFill2(self) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(),14)
        if r is not None:
            sender = cast(QSpinBox, self.sender())
            self.aw.extraFill2[r] = sender.value()

    @pyqtSlot(bool)
    def setextracolor1(self, _:bool) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(), 1)
        if r is not None:
            self.setextracolor(1, r)

    @pyqtSlot(bool)
    def setextracolor2(self, _:bool) -> None:
        r = self.aw.findWidgetsRow(self.devicetable,self.sender(), 2)
        if r is not None:
            self.setextracolor(2, r)

    def setextracolor(self, ll:int, i:int) -> None:
        try:
            #line 1
            if ll == 1:
                # use native no buttons dialog on Mac OS X, blocks otherwise
                colorf = self.aw.colordialog(QColor(rgba_colorname2argb_colorname(self.aw.qmc.extradevicecolor1[i])),True,self, alphasupport=True)
                if colorf.isValid():
                    colorname = argb_colorname2rgba_colorname(colorf.name(QColor.NameFormat.HexArgb))
                    self.aw.qmc.extradevicecolor1[i] = colorname
                    # set LCD label color
                    self.aw.setLabelColor(self.aw.extraLCDlabel1[i], colorname, self.aw.extraCurveVisibility1[i])
                    color1Button = cast(QPushButton, self.devicetable.cellWidget(i,1))
                    color1Button.setStyleSheet(f"border: none; outline: none; background-color: rgba{ImageColor.getcolor(self.aw.qmc.extradevicecolor1[i], 'RGBA')}; color: { self.aw.labelBorW(self.aw.qmc.extradevicecolor1[i])}")
                    color1Button.setText(colorname)
                    self.aw.checkColors([(self.aw.qmc.extraname1[i], self.aw.qmc.extradevicecolor1[i], QApplication.translate('Label','Background'), self.aw.qmc.palette['background'])])
                    self.aw.checkColors([(self.aw.qmc.extraname1[i], self.aw.qmc.extradevicecolor1[i], QApplication.translate('Label','Legend bkgnd'), self.aw.qmc.palette['background'])])
            #line 2
            elif ll == 2:
                # use native no buttons dialog on Mac OS X, blocks otherwise
                colorf = self.aw.colordialog(QColor(rgba_colorname2argb_colorname(self.aw.qmc.extradevicecolor2[i])),True,self, alphasupport=True)
                if colorf.isValid():
                    colorname = argb_colorname2rgba_colorname(colorf.name(QColor.NameFormat.HexArgb))
                    self.aw.qmc.extradevicecolor2[i] = colorname
                    # set LCD label color
                    self.aw.setLabelColor(self.aw.extraLCDlabel2[i],colorname, self.aw.extraCurveVisibility2[i])
                    color2Button = cast(QPushButton, self.devicetable.cellWidget(i,2))
                    color2Button.setStyleSheet(f"border: none; outline: none; background-color: rgba{ImageColor.getcolor(self.aw.qmc.extradevicecolor2[i], 'RGBA')}; color: {self.aw.labelBorW(self.aw.qmc.extradevicecolor2[i])}")
                    color2Button.setText(colorname)
                    self.aw.checkColors([(self.aw.qmc.extraname2[i], self.aw.qmc.extradevicecolor2[i], QApplication.translate('Label','Background'), self.aw.qmc.palette['background'])])
                    self.aw.checkColors([(self.aw.qmc.extraname2[i], self.aw.qmc.extradevicecolor2[i], QApplication.translate('Label','Legend bkgnd'),self.aw.qmc.palette['background'])])
        except Exception as e: # pylint: disable=broad-except
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' setextracolor(): {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))

    # close is called from OK and CANCEL
    @override
    def close(self) -> bool:
        self.closeHelp()
        settings = QSettings()
        #save window geometry
        settings.setValue('DeviceAssignmentGeometry',self.saveGeometry())
        self.aw.DeviceAssignmentDlg_activeTab = self.TabWidget.currentIndex()
        return True

    @pyqtSlot()
    def cancelEvent(self) -> None:
        self.aw.DeviceAssignmentDlg_activeTab = self.TabWidget.currentIndex()
        self.close()
        self.aw.qmc.phidgetRemoteFlag = self.org_phidgetRemoteFlag
        self.aw.qmc.yoctoRemoteFlag = self.org_yoctoRemoteFlag
        self.aw.kaleidoSerial = self.org_kaleidoSerial

        self.aw.qmc.ambientTempSource = self.org_ambientTempSource
        self.aw.qmc.ambientHumiditySource = self.org_ambientHumiditySource
        self.aw.qmc.ambientPressureSource = self.org_ambientPressureSource

        self.reject()

    @pyqtSlot()
    def okEvent(self) -> None: # pyright: ignore [reportGeneralTypeIssues] # Code is too complex to analyze; reduce complexity by refactoring into subroutines or reducing conditional code paths

        try:
            self.aw.qmc.device_logging = self.deviceLoggingFlag.isChecked()
            try:
                setDeviceDebugLogLevel(self.aw.qmc.device_logging)
            except Exception: # pylint: disable=broad-except
                pass

            #save any extra devices here
            self.savedevicetable(redraw=False)
            self.aw.qmc.devicetablecolumnwidths = [self.devicetable.columnWidth(c) for c in range(self.devicetable.columnCount())]

            message = QApplication.translate('Message','Device not set')
            # by default switch PID buttons/LCDs off
            self.aw.buttonCONTROL.setVisible(False)
            self.aw.LCD6frame.setVisible(False)
            self.aw.LCD7frame.setVisible(False)
            self.aw.qmc.resetlinecountcaches()
            self.aw.ser.arduinoETChannel = str(self.arduinoETComboBox.currentText())
            self.aw.ser.arduinoBTChannel = str(self.arduinoBTComboBox.currentText())
            self.aw.ser.arduinoATChannel = str(self.arduinoATComboBox.currentText())
            self.aw.ser.ArduinoFILT = [sb.value() for sb in self.FILTspinBoxes]

            self.aw.kaleidoEventFlags = [cb.isChecked() for cb in self.kaleidoEventFlags]

            if self.nonpidButton.isChecked():
                meter = str(self.devicetypeComboBox.currentText())
                #special device manual mode. No serial settings.
                if meter == 'NONE':
                    self.aw.qmc.device = 18
                    # ensure that events button is shown
                    self.aw.eventsbuttonflag = 1
                    self.aw.buttonEVENT.setVisible(True)
                    message = QApplication.translate('Message','Device set to {0}').format(meter)
                elif meter == 'DUMMY' and self.aw.qmc.device != 50: # including a dummy serial device (can be used for serial commands)
                    self.aw.qmc.device = 50
                    message = QApplication.translate('Message','Device set to {0}').format(meter)
                    self.aw.ser.baudrate = 9600
                    self.aw.ser.bytesize = 8
                    self.aw.ser.parity= 'N'
                    self.aw.ser.stopbits = 1
                    self.aw.ser.timeout = 0.5
                ##########################
                ####  DEVICE 138 is Kaleido BT/ET
                elif meter == 'Kaleido BT/ET':
                    self.aw.qmc.device = 138
                    message = QApplication.translate('Message','Device set to {0}').format(meter)
                ##########################
                ####  DEVICE 139 is +Kaleido ST/AT but +DEVICE cannot be set as main device
                ##########################
                ####  DEVICE 140 is +Kaleido Drum/AH but +DEVICE cannot be set as main device
                ##########################
                ####  DEVICE 141 is +Kaleido Heater/Fan but +DEVICE cannot be set as main device
                ##########################
                elif meter == 'ARDUINOTC4':
                    self.aw.qmc.device = 19
                    self.aw.ser.baudrate = 115200
                    self.aw.ser.bytesize = 8
                    self.aw.ser.parity= 'N'
                    self.aw.ser.stopbits = 1
                    self.aw.ser.timeout = 0.8
                    self.aw.ser.ArduinoIsInitialized = 0
                    message = QApplication.translate('Message','Device set to {0}. Now, check Serial Port settings').format(meter)
                else:
                    try:
                        self.aw.qmc.device = self.aw.qmc.devices.index(meter) + 1
                        message = QApplication.translate('Message','Device set to {0}').format(meter)
                    except Exception: # pylint: disable=broad-except
                        pass
                # ensure that by selecting a real device, the initial sampling rate is set to 3s
                if meter != 'NONE':
                    self.aw.qmc.delay = max(self.aw.qmc.delay,self.aw.qmc.min_delay)
            # update Control button visibility
            self.aw.showControlButton()

    # ADD DEVICE: to add a device you have to modify several places. Search for the tag "ADD DEVICE:"in the code
    # - add an elif entry above to specify the default serial settings
            #extra devices serial config
            #set of different serial settings modes options
            ssettings: list[tuple[int,int,str,int,float]] = [(9600,8,'O',1,0.5),(19200,8,'E',1,0.5),(2400,7,'E',1,1),(9600,8,'N',1,0.5),
                         (19200,8,'N',1,0.5),(2400,8,'N',1,1),(9600,8,'E',1,0.5),(38400,8,'E',1,0.5),(115200,8,'N',1,0.4),(57600,8,'N',1,0.4)]
            #map device index to a setting mode (choose the one that matches the device)
    # ADD DEVICE: to add a device you have to modify several places. Search for the tag "ADD DEVICE:"in the code
    # - add an entry to devsettings below (and potentially to ssettings above)
            devssettings: list[int] = [
                0, # 0
                1, # 1
                2, # 2
                3, # 3
                3, # 4
                3, # 5
                3, # 6
                3, # 7
                3, # 8
                3, # 9
                3, # 10
                3, # 11
                3, # 12
                3, # 13
                3, # 14
                2, # 15
                1, # 16
                3, # 17
                0, # 18
                4, # 19
                5, # 20
                3, # 21
                6, # 22
                5, # 23
                3, # 24
                3, # 25
                6, # 26
                3, # 27
                4, # 28
                8, # 29
                3, # 30
                1, # 31
                4, # 32
                7, # 33
                1, # 34
                1, # 35
                1, # 36
                1, # 37
                1, # 38
                3, # 39
                1, # 40
                1, # 41
                1, # 42
                1, # 43
                4, # 44
                1, # 45
                1, # 46
                1, # 47
                3, # 48
                3, # 49
                3, # 50
                3, # 51
                1, # 52
                8, # 53
                8, # 54
                7, # 55
                3, # 56
                3, # 57
                1, # 58
                1, # 59
                1, # 60
                1, # 61
                1, # 62
                1, # 63
                1, # 64
                1, # 65
                8, # 66
                3, # 67
                1, # 68
                1, # 69
                1, # 70
                1, # 71
                1, # 72
                1, # 73
                1, # 74
                1, # 75
                1, # 76
                3, # 77
                3, # 78
                1, # 79
                1, # 80
                1, # 81
                1, # 82
                1, # 83
                1, # 84
                1, # 85
                1, # 86
                1, # 87
                1, # 88
                1, # 89
                1, # 90
                1, # 91
                1, # 92
                1, # 93
                1, # 94
                1, # 95
                1, # 96
                1, # 97
                1, # 98
                1, # 99
                1, # 100
                9, # 101
                9, # 102
                5, # 103
                9, # 104
                9, # 105
                1, # 106
                1, # 107
                1, # 108
                7, # 109
                1, # 110
                1, # 111
                1, # 112
                1, # 113
                1, # 114
                3, # 115
                3, # 116
                3, # 117
                1, # 118
                1, # 119
                1, # 120
                1, # 121
                1, # 122
                1, # 123
                1, # 124
                1, # 125
                8, # 126
                8, # 127
                8, # 128
                1, # 129
                1, # 130
                1, # 131
                1, # 132
                1, # 133
                1, # 134
                1, # 135
                1, # 136
                1, # 137
                9, # 138
                9, # 139
                9, # 140
                9, # 141
                9, # 142
                9, # 143
                9, # 144
                9, # 145
                1, # 146
                1, # 147
                1, # 148
                1, # 149
                7, # 150
                1, # 151
                1, # 152
                1, # 153
                1, # 154
                1, # 155
                1, # 156
                1, # 157
                1, # 158
                1, # 159
                9, # 160
                3, # 161
                3, # 162
                3, # 163
                1, # 164
                1, # 165
                1, # 166
                1, # 167
                1, # 168
                1, # 169
                3, # 170
                1, # 171
                1, # 172
                1, # 173
                1, # 174
                1, # 175
                1, # 176
                6, # 177
                6, # 178
                1, # 179
                1, # 180
                1, # 181
                1, # 182
                1, # 183
                3, # 184
                3, # 185
                3, # 186
                3, # 187
                3, # 188
                3, # 189
                3, # 190
                3, # 191
                3, # 192
                3, # 193
                3, # 194
                3, # 195
                8, # 196
                8, # 197
                8, # 198
                8, # 199
                8, # 200
                1, # 201
                1, # 202
                1, # 203
                1, # 204
                1, # 205
                1  # 206
                ]
            #init serial settings of extra devices
            for i, _ in enumerate(self.aw.qmc.extradevices):
                if self.aw.qmc.extradevices[i] < len(devssettings) and devssettings[self.aw.qmc.extradevices[i]] < len(ssettings):
                    dsettings: tuple[int,int,str,int,float] = ssettings[devssettings[self.aw.qmc.extradevices[i]]]
                    if i < len(self.aw.extrabaudrate):
                        self.aw.extrabaudrate[i] = dsettings[0]
                    else:
                        self.aw.extrabaudrate.append(dsettings[0])
                    if i < len(self.aw.extrabytesize):
                        self.aw.extrabytesize[i] = dsettings[1]
                    else:
                        self.aw.extrabytesize.append(dsettings[1])
                    if i < len(self.aw.extraparity):
                        self.aw.extraparity[i] = dsettings[2]
                    else:
                        self.aw.extraparity.append(dsettings[2])
                    if i < len(self.aw.extrastopbits):
                        self.aw.extrastopbits[i] = dsettings[3]
                    else:
                        self.aw.extrastopbits.append(dsettings[3])
                    if i < len(self.aw.extratimeout):
                        self.aw.extratimeout[i] = dsettings[4]
                    else:
                        self.aw.extratimeout.append(dsettings[4])
            if self.nonpidButton.isChecked():
                self.aw.buttonSVp5.setVisible(False)
                self.aw.buttonSVp10.setVisible(False)
                self.aw.buttonSVp20.setVisible(False)
                self.aw.buttonSVm20.setVisible(False)
                self.aw.buttonSVm10.setVisible(False)
                self.aw.buttonSVm5.setVisible(False)
                self.aw.LCD6frame.setVisible(False)
                self.aw.LCD7frame.setVisible(False)
            self.aw.qmc.ETfunction = str(self.ETfunctionedit.text())
            self.aw.qmc.BTfunction = str(self.BTfunctionedit.text())
            if self.aw.qmc.BTcurve != bool(self.BTcurve.isChecked()) or self.aw.qmc.ETcurve != bool(self.ETcurve.isChecked()):
                # we reset the cached main event annotation positions as those annotations are now rendered on the other curve
                self.aw.qmc.l_annotations_dict = {}
                self.aw.qmc.l_event_flags_dict = {}
            self.aw.qmc.ETcurve = self.ETcurve.isChecked()
            self.aw.qmc.BTcurve = self.BTcurve.isChecked()
            self.aw.qmc.ETlcd = self.ETlcd.isChecked()
            self.aw.qmc.BTlcd = self.BTlcd.isChecked()

            swap = self.swaplcds.isChecked()
            # swap BT/ET lcds on leaving the dialog
            if self.aw.qmc.swaplcds is not swap:
                tmp = QWidget()
                tmp.setLayout(self.aw.LCD2frame.layout())
                self.aw.LCD2frame.setLayout(self.aw.LCD3frame.layout())
                self.aw.LCD3frame.setLayout(tmp.layout())
                if self.aw.largeLCDs_dialog is not None:
                    self.aw.qmc.swaplcds = swap
                    self.aw.largeLCDs_dialog.reLayout()
            self.aw.qmc.swaplcds = swap
            self.aw.updateLCDproperties()

            # close all ports to force a reopen
            self.aw.qmc.disconnectProbes()

            # Yotopuce configurations
            self.aw.qmc.yoctoRemoteFlag = self.yoctoBoxRemoteFlag.isChecked()
            self.aw.qmc.yoctoServerID = self.yoctoServerId.text()
            self.aw.qmc.YOCTO_emissivity = self.yoctoEmissivitySpinBox.value()
            self.aw.qmc.YOCTO_async[0] = self.yoctoAyncChanFlag.isChecked()
            self.aw.qmc.YOCTO_async[1] = self.yoctoAyncChanFlag.isChecked() # flag for channel 1 is ignored and only that of channel 0 is respected for both channels
            self.aw.qmc.YOCTO_dataRate = self.aw.qmc.YOCTO_dataRatesValues[self.yoctoDataRateCombo.currentIndex()]

            # Ambient confifgurations
            self.aw.qmc.ambient_temperature_device = self.temperatureDeviceCombo.currentIndex()
            self.aw.qmc.ambient_humidity_device = self.humidityDeviceCombo.currentIndex()
            self.aw.qmc.ambient_pressure_device = self.pressureDeviceCombo.currentIndex()
            try:
                self.aw.qmc.elevation = int(self.elevationSpinBox.value())
            except Exception: # pylint: disable=broad-except
                pass

            # Phidget configurations
            for i in range(4):
                self.aw.qmc.phidget1048_types[i] = self.probeTypeCombos[i].currentIndex()+1
                self.aw.qmc.phidget1048_async[i] = self.asyncCheckBoxes1048[i].isChecked()
                self.aw.qmc.phidget1048_changeTriggers[i] = self.aw.qmc.phidget1048_changeTriggersValues[self.changeTriggerCombos1048[i].currentIndex()]
                self.aw.qmc.phidget1046_gain[i] = self.gainCombos1046[i].currentIndex()+1
                self.aw.qmc.phidget1046_formula[i] = self.formulaCombos1046[i].currentIndex()
                self.aw.qmc.phidget1046_async[i] = self.asyncCheckBoxes1046[i].isChecked()
            self.aw.qmc.phidget1048_dataRate = self.aw.qmc.phidget_dataRatesValues[self.dataRateCombo1048.currentIndex()]
            self.aw.qmc.phidget1046_dataRate = self.aw.qmc.phidget_dataRatesValues[self.dataRateCombo1046.currentIndex()]
            self.aw.qmc.phidget1045_async = self.asyncCheckBoxe1045.isChecked()
            self.aw.qmc.phidget1045_changeTrigger = self.aw.qmc.phidget1045_changeTriggersValues[self.changeTriggerCombos1045.currentIndex()]
            self.aw.qmc.phidget1045_emissivity = self.emissivitySpinBox.value()
            self.aw.qmc.phidget1045_dataRate = self.aw.qmc.phidget_dataRatesValues[self.dataRateCombo1045.currentIndex()]

            self.aw.qmc.phidget1200_formula = self.formulaCombo1200.currentIndex()
            self.aw.qmc.phidget1200_wire = self.wireCombo1200.currentIndex()
            self.aw.qmc.phidget1200_async = self.asyncCheckBoxe1200.isChecked()
            self.aw.qmc.phidget1200_changeTrigger = self.aw.qmc.phidget1200_changeTriggersValues[self.changeTriggerCombo1200.currentIndex()]
            self.aw.qmc.phidget1200_dataRate = self.aw.qmc.phidget1200_dataRatesValues[self.rateCombo1200.currentIndex()]

            self.aw.qmc.phidget1200_2_formula = self.formulaCombo1200_2.currentIndex()
            self.aw.qmc.phidget1200_2_wire = self.wireCombo1200_2.currentIndex()
            self.aw.qmc.phidget1200_2_async = self.asyncCheckBoxe1200_2.isChecked()
            self.aw.qmc.phidget1200_2_changeTrigger = self.aw.qmc.phidget1200_changeTriggersValues[self.changeTriggerCombo1200_2.currentIndex()]
            self.aw.qmc.phidget1200_2_dataRate = self.aw.qmc.phidget1200_dataRatesValues[self.rateCombo1200_2.currentIndex()]

            self.aw.qmc.phidgetDAQ1400_powerSupply = self.powerCombo1400.currentIndex()
            self.aw.qmc.phidgetDAQ1400_inputMode = self.modeCombo1400.currentIndex()

            self.aw.qmc.phidgetRemoteFlag = self.phidgetBoxRemoteFlag.isChecked()
            self.aw.qmc.phidgetServerID = self.phidgetServerId.text()
            self.aw.qmc.phidgetPassword = self.phidgetPassword.text()
            self.aw.qmc.phidgetRemoteOnlyFlag = self.phidgetBoxRemoteOnlyFlag.isChecked()
            try:
                self.aw.qmc.phidgetPort = int(self.phidgetPort.text())
            except Exception: # pylint: disable=broad-except
                pass
            for i in range(8):
                self.aw.qmc.phidget1018_async[i] = self.asyncCheckBoxes[i].isChecked()
                self.aw.qmc.phidget1018_ratio[i] = self.ratioCheckBoxes[i].isChecked()
                self.aw.qmc.phidget1018_dataRates[i] = self.aw.qmc.phidget_dataRatesValues[self.dataRateCombos[i].currentIndex()]
                self.aw.qmc.phidget1018_changeTriggers[i] = self.aw.qmc.phidget1018_changeTriggersValues[self.changeTriggerCombos[i].currentIndex()]
                self.aw.qmc.phidgetVCP100x_voltageRanges[i] = self.aw.qmc.phidgetVCP100x_voltageRangeValues[self.voltageRangeCombos[i].currentIndex()]

            # restart PhidgetManager
            try:
                self.aw.qmc.restartPhidgetManager()
            except Exception as e: # pylint: disable=broad-except
                _log.exception(e)

            self.aw.kaleidoHost = self.kaleidoHost.text().strip()
            try:
                self.aw.kaleidoPort = int(self.kaleidoPort.text())
            except Exception: # pylint: disable=broad-except
                pass
            if self.kaleidoHybridButton.isChecked():
                self.aw.kaleidoHybridControl = True
                self.aw.kaleidoPID = False
                backend = self.hybridBackendCombo.currentData()
                from artisanlib.hybrid_controller import normalize_control_backend
                self.aw.hybridControlBackend = normalize_control_backend(
                    str(backend) if backend is not None else 'energy')
            elif self.kaleidoMachinePIDButton.isChecked():
                self.aw.kaleidoHybridControl = False
                self.aw.kaleidoPID = True
            else:
                self.aw.kaleidoHybridControl = False
                self.aw.kaleidoPID = False
            from artisanlib.hybrid_controller import create_controller_backend
            self.aw.hybrid_controller = create_controller_backend(
                self.aw.hybridControlBackend, self.aw.buildHybridControllerConfig())

            # LCD visibility
            self.aw.LCD2frame.setVisible(self.aw.qmc.BTlcd if self.aw.qmc.swaplcds else self.aw.qmc.ETlcd)
            self.aw.LCD3frame.setVisible(self.aw.qmc.ETlcd if self.aw.qmc.swaplcds else self.aw.qmc.BTlcd)
            if self.aw.largeLCDs_dialog:
                self.aw.largeLCDs_dialog.updateVisiblitiesETBT()
            if self.aw.largePIDLCDs_dialog:
                self.aw.largePIDLCDs_dialog.updateVisiblitiesPID()
            if self.aw.largeExtraLCDs_dialog:
                self.aw.largeExtraLCDs_dialog.reLayout() # names, styles and visibilties might have changed

            self.aw.qmc.intChannel.cache_clear() # device type and thus int channels might have been changed
            self.aw.qmc.clearLCDs()
            self.aw.qmc.redraw(recomputeAllDeltas=False)
            self.aw.sendmessage(message)
            #open serial conf Dialog
            #if device is not None or not external-program (don't need serial settings config)
            if (self.aw.qmc.device not in self.aw.qmc.nonSerialDevices or
                (self.aw.qmc.device == 138 and self.aw.kaleidoSerial)) and (self.aw.qmc.device != 50) and self.TabWidget.currentIndex() in {0,1,6}:
                QTimer.singleShot(700, self.aw.setcommport)
            self.close()
            self.accept()
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            _t, _e, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' device accept(): {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))

    @pyqtSlot(bool)
    def showExtradevHelp(self, _checked:bool = False) -> None:
        from help import symbolic_help # type: ignore [attr-defined,unused-ignore]  # pylint: disable=no-name-in-module
        self.helpdialog = self.aw.showHelpDialog(
                self,            # this dialog as parent
                self.helpdialog, # the existing help dialog
                QApplication.translate('Form Caption','Symbolic Formulas Help'),
                symbolic_help.content())

    @pyqtSlot(bool)
    def showSymbolicHelp(self, _checked:bool = False) -> None:
        from help import symbolic_help # type: ignore [attr-defined,unused-ignore]  # pylint: disable=no-name-in-module
        self.helpdialog = self.aw.showHelpDialog(
                self,            # this dialog as parent
                self.helpdialog, # the existing help dialog
                QApplication.translate('Form Caption','Symbolic Formulas Help'),
                symbolic_help.content())

    def closeHelp(self) -> None:
        self.aw.closeHelpDialog(self.helpdialog)

    @pyqtSlot(int)
    def tabSwitched(self, idx:int) -> None:
        self.closeHelp()
        if idx == 5: # Ambient Tab
            self.updateAmbientSourceComboBoxes()
