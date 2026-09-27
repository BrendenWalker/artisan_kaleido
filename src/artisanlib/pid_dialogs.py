#
# ABOUT
# Artisan PID Dialog (software, Kaleido, Hybrid)

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
import logging
from typing import override, Final, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow # noqa: F401 # pylint: disable=unused-import
    from PyQt6.QtWidgets import QWidget # pylint: disable=unused-import
    from PyQt6.QtGui import QCloseEvent # pylint: disable=unused-import

from artisanlib.util import toInt, float2float
from artisanlib.dialogs import ArtisanDialog
from artisanlib.widgets import MyQComboBox, MyQDoubleSpinBox

from PyQt6.QtCore import Qt, pyqtSlot, QSettings, QTimer
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
    QComboBox, QHBoxLayout, QVBoxLayout, QCheckBox, QGridLayout, QGroupBox, QLineEdit,
    QRadioButton, QSpinBox, QTabWidget, QDoubleSpinBox,
    QTimeEdit, QLayout, QSizePolicy, QButtonGroup, QFrame)


_log: Final[logging.Logger] = logging.getLogger(__name__)

############################################################################
######################## Artisan PID CONTROL DIALOG ########################
############################################################################

class PID_DlgControl(ArtisanDialog):
    def __init__(self, parent:QWidget, aw:'ApplicationWindow', activeTab:int = 0) -> None:
        super().__init__(parent, aw)
        self.activeTab = activeTab
        self.setModal(True)
        #self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose) # default is True and this is set by default in ArtisanDialog!

        pid_controller = self.aw.pidcontrol.externalPIDControl()

        if pid_controller == 5:
            self.setWindowTitle(QApplication.translate('Form Caption','Hybrid PID Control'))
        elif pid_controller == 4:
            self.setWindowTitle(QApplication.translate('Form Caption','Kaleido PID Control'))
        else:
            self.setWindowTitle(QApplication.translate('Form Caption','PID Control'))

        # PID tab
        tab1Layout = QVBoxLayout()
        pidGrp = QGroupBox(QApplication.translate('GroupBox','p-i-d'))

        self.pidScheduleModeLabel = QLabel()
        self.pidSchedule0 = QSpinBox()
        self.pidSchedule0.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidSchedule0.setRange(0,999)
        self.pidSchedule0.setSingleStep(10)
        self.pidSchedule0.setValue(int(round(self.aw.pidcontrol.pidSchedule0)))
        self.pidSchedule1 = QSpinBox()
        self.pidSchedule1.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidSchedule1.setRange(0,999)
        self.pidSchedule1.setSingleStep(10)
        self.pidSchedule1.setValue(int(round(self.aw.pidcontrol.pidSchedule1)))
        self.pidSchedule2 = QSpinBox()
        self.pidSchedule2.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidSchedule2.setRange(0,999)
        self.pidSchedule2.setSingleStep(10)
        self.pidSchedule2.setValue(int(round(self.aw.pidcontrol.pidSchedule2)))

        pidKpLabel = QLabel('kp')

        self.pidKp = QDoubleSpinBox()
        self.pidKp.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidKp.setRange(.0,9999.)
        self.pidKp.setSingleStep(.1)
        self.pidKp.setDecimals(3)
        self.pidKp.setValue(self.aw.pidcontrol.pidKp)

        self.pidKp1 = QDoubleSpinBox()
        self.pidKp1.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidKp1.setRange(.0,9999.)
        self.pidKp1.setSingleStep(.1)
        self.pidKp1.setDecimals(3)
        self.pidKp1.setValue(self.aw.pidcontrol.pidKp1)

        self.pidKp2 = QDoubleSpinBox()
        self.pidKp2.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidKp2.setRange(.0,9999.)
        self.pidKp2.setSingleStep(.1)
        self.pidKp2.setDecimals(3)
        self.pidKp2.setValue(self.aw.pidcontrol.pidKp2)


        pidKiLabel = QLabel('ki')

        self.pidKi = QDoubleSpinBox()
        self.pidKi.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidKi.setRange(.0,9999.)
        self.pidKi.setSingleStep(.1)
        self.pidKi.setDecimals(3)
        self.pidKi.setValue(self.aw.pidcontrol.pidKi)

        self.pidKi1 = QDoubleSpinBox()
        self.pidKi1.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidKi1.setRange(.0,9999.)
        self.pidKi1.setSingleStep(.1)
        self.pidKi1.setDecimals(3)
        self.pidKi1.setValue(self.aw.pidcontrol.pidKi1)

        self.pidKi2 = QDoubleSpinBox()
        self.pidKi2.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidKi2.setRange(.0,9999.)
        self.pidKi2.setSingleStep(.1)
        self.pidKi2.setDecimals(3)
        self.pidKi2.setValue(self.aw.pidcontrol.pidKi2)


        pidKdLabel = QLabel('kd')

        self.pidKd = QDoubleSpinBox()
        self.pidKd.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidKd.setRange(.0,9999.)
        self.pidKd.setSingleStep(.1)
        self.pidKd.setDecimals(3)
        self.pidKd.setValue(self.aw.pidcontrol.pidKd)

        self.pidKd1 = QDoubleSpinBox()
        self.pidKd1.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidKd1.setRange(.0,9999.)
        self.pidKd1.setSingleStep(.1)
        self.pidKd1.setDecimals(3)
        self.pidKd1.setValue(self.aw.pidcontrol.pidKd1)

        self.pidKd2 = QDoubleSpinBox()
        self.pidKd2.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidKd2.setRange(.0,9999.)
        self.pidKd2.setSingleStep(.1)
        self.pidKd2.setDecimals(3)
        self.pidKd2.setValue(self.aw.pidcontrol.pidKd2)

        schedule_hline = QFrame()
        schedule_hline.setLineWidth(2)
        schedule_hline.setMidLineWidth(1)
        schedule_hline.setFrameShape(QFrame.Shape.HLine)
        schedule_hline.setFrameShadow(QFrame.Shadow.Raised)

        self.pidSchedulingFlag = QCheckBox(QApplication.translate('Label','Scheduling'))
        self.pidSchedulingFlag.setToolTip(QApplication.translate('Tooltip', 'Activates p-i-d gain scheduling'))
        self.pidSchedulingFlag.setChecked(self.aw.pidcontrol.pidGainScheduling)
        self.pidSchedulingPV = QRadioButton(QApplication.translate('Label','PV'))
        self.pidSchedulingPV.setToolTip(QApplication.translate('Tooltip', 'Scheduling by process value input temperature'))
        self.pidSchedulingPV.setChecked(not self.aw.pidcontrol.pidGainSchedulingSV)
        self.pidSchedulingSV = QRadioButton(QApplication.translate('Label','SV'))
        self.pidSchedulingSV.setToolTip(QApplication.translate('Tooltip', 'Scheduling by set value target temperature'))
        self.pidSchedulingLinear = QRadioButton('x')
        self.pidSchedulingLinear.setToolTip(QApplication.translate('Tooltip', 'Scheduling based on linear regression of two points'))
        self.pidSchedulingLinear.toggled.connect(self.scheduling_method_changed)
        self.pidSchedulingQuadratic = QRadioButton('x\xb2')
        self.pidSchedulingQuadratic.setToolTip(QApplication.translate('Tooltip', 'Scheduling based on quadratic regression of three points'))

        self.pidSchedulingFlag.stateChanged.connect(self.scheduling_state_changed)
        self.pidSchedulingPV.toggled.connect(self.scheduling_input_changed)
        self.pidSchedulingSV.setChecked(self.aw.pidcontrol.pidGainSchedulingSV)
        self.pidSchedulingLinear.setChecked(not self.aw.pidcontrol.pidGainSchedulingQuadratic)
        self.pidSchedulingQuadratic.setChecked(self.aw.pidcontrol.pidGainSchedulingQuadratic)

        pidScheudlingSource = QButtonGroup(self)
        pidScheudlingSource.addButton(self.pidSchedulingPV)
        pidScheudlingSource.addButton(self.pidSchedulingSV)

        pidScheudlingMapping = QButtonGroup(self)
        pidScheudlingMapping.addButton(self.pidSchedulingLinear)
        pidScheudlingMapping.addButton(self.pidSchedulingQuadratic)

        pidSchedulingLayout = QHBoxLayout()
        pidSchedulingLayout.addStretch()
        pidSchedulingLayout.addWidget(self.pidSchedulingFlag)
        pidSchedulingLayout.addSpacing(10)
        pidSchedulingLayout.addWidget(self.pidSchedulingPV)
        pidSchedulingLayout.addWidget(self.pidSchedulingSV)
        pidSchedulingLayout.addSpacing(10)
        pidSchedulingLayout.addWidget(self.pidSchedulingLinear)
        pidSchedulingLayout.addWidget(self.pidSchedulingQuadratic)
        pidSchedulingLayout.addStretch()


        pidGrid = QGridLayout()
        pidGrid.setSpacing(5)
        if pid_controller == 0:
            pidGrid.addWidget(self.pidScheduleModeLabel,0,0, alignment=Qt.AlignmentFlag.AlignRight)
            pidGrid.addWidget(self.pidSchedule0,0,1)
            pidGrid.addWidget(self.pidSchedule1,0,2)
            pidGrid.addWidget(self.pidSchedule2,0,3)
            pidGrid.addWidget(schedule_hline,1,1,1,3)
            pidGrid.addWidget(self.pidKp1,2,2)
            pidGrid.addWidget(self.pidKp2,2,3)
            pidGrid.addWidget(self.pidKi1,3,2)
            pidGrid.addWidget(self.pidKi2,3,3)
            pidGrid.addWidget(self.pidKd1,4,2)
            pidGrid.addWidget(self.pidKd2,4,3)
        pidGrid.addWidget(pidKpLabel,2,0, alignment=Qt.AlignmentFlag.AlignRight)
        pidGrid.addWidget(self.pidKp,2,1)
        pidGrid.addWidget(pidKiLabel,3,0, alignment=Qt.AlignmentFlag.AlignRight)
        pidGrid.addWidget(self.pidKi,3,1)
        pidGrid.addWidget(pidKdLabel,4,0, alignment=Qt.AlignmentFlag.AlignRight)
        pidGrid.addWidget(self.pidKd,4,1)

        self.updateSchedulingInput()
        self.updateSchedulingWidgetsEnableStatus()


        self.pidCycle = QSpinBox()
        self.pidCycle.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidCycle.setRange(0,99999)
        self.pidCycle.setSingleStep(100)
        self.pidCycle.setValue(int(self.aw.pidcontrol.pidCycle))
        self.pidCycle.setSuffix(' ms')
        pidCycleLabel = QLabel(QApplication.translate('Label','Cycle'))

        pidCycleBox = QHBoxLayout()
        pidCycleBox.addStretch()
        if pid_controller != 4:
            pidCycleBox.addWidget(pidCycleLabel)
            pidCycleBox.addWidget(self.pidCycle)
        pidCycleBox.addStretch()


        pidGridVBox = QVBoxLayout()
        pidVBox = QVBoxLayout()
        if pid_controller in {0, 4}: # internal PID and Kaleido
            self.pidSource = QComboBox()
            self.pidSource.setToolTip(QApplication.translate('Tooltip', 'PID input signal'))
            pidSourceItems = self.getCurveNames()
            self.pidSource.addItems(pidSourceItems)

            # pidSource = 1 is interpreted as BT and 2 as ET, 3 as 0xT1, 4 as 0xT2, 5 as 1xT1, ...
            if self.aw.pidcontrol.pidSource in {0,1}:
                self.pidSource.setCurrentIndex(1)
            elif self.aw.pidcontrol.pidSource == 2:
                self.pidSource.setCurrentIndex(0)
            elif self.aw.pidcontrol.pidSource-1 < len(pidSourceItems):
                self.pidSource.setCurrentIndex(self.aw.pidcontrol.pidSource-1)
            else:
                self.pidSource.setCurrentIndex(1)

            pidSourceLabel = QLabel(QApplication.translate('Label','Input'))
            pidSourceBox = QHBoxLayout()
            pidSourceBox.addStretch()
            pidSourceBox.addWidget(pidSourceLabel)
            pidSourceBox.addWidget(self.pidSource)
            pidSourceBox.addStretch()
            pidGridVBox.addLayout(pidSourceBox)
            if pid_controller == 4: # Kaleido
                pidVBox.addLayout(pidCycleBox)
        if pid_controller != 0:
            # no setPID button for SoftwarePID (conf is set autommatically on leaving the dialog)
            pidSetPID = QPushButton(QApplication.translate('Button','Set'))
            pidSetPID.clicked.connect(self.pidConf)
            pidSetPID.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            pidSetBox = QHBoxLayout()
            pidSetBox.addStretch()
            pidSetBox.addWidget(pidSetPID)
            pidVBox.addStretch()
            pidVBox.addLayout(pidSetBox)
            pidVBox.setAlignment(pidSetBox,Qt.AlignmentFlag.AlignRight)

        if pid_controller != 4:
            if pid_controller == 0:
                pidGridVBox.addLayout(pidSchedulingLayout)
            pidGridVBox.addLayout(pidGrid)
        pidGridVBox.addStretch()
        pidGridBox = QHBoxLayout()
        pidGridBox.addLayout(pidGridVBox)
        pidGridBox.addLayout(pidVBox)
        if pid_controller == 0: # Output configuration only for internal PID
            #PID target (only shown if internal software PID is active
            controlItems = ['None',self.aw.qmc.etypesf(0),self.aw.qmc.etypesf(1),self.aw.qmc.etypesf(2),self.aw.qmc.etypesf(3)]
            #positiveControl
            positiveControlLabel = QLabel(QApplication.translate('Label','Positive'))
            self.positiveControlCombo = QComboBox()
            self.positiveControlCombo.addItems(controlItems)
            self.positiveControlCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.positiveControlCombo.setCurrentIndex(self.aw.pidcontrol.pidPositiveTarget)
            self.positiveControlCombo.currentIndexChanged.connect(self.updatePositiveTargetLimits)
            self.positiveControlCombo.setToolTip(QApplication.translate('Tooltip', 'Slider to be set by the positive PID duty signal'))
            #negativeControl
            negativeControlLabel = QLabel(QApplication.translate('Label','Negative'))
            self.negativeControlCombo = QComboBox()
            self.negativeControlCombo.addItems(controlItems)
            self.negativeControlCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.negativeControlCombo.setCurrentIndex(self.aw.pidcontrol.pidNegativeTarget)
            self.negativeControlCombo.currentIndexChanged.connect(self.updateNegativeTargetLimits)
            self.negativeControlCombo.setToolTip(QApplication.translate('Tooltip', 'Slider to be set by the negative PID duty signal'))

            targetSliderLabel = QLabel(QApplication.translate('Label', 'Slider'))
            rangeLimitLabel = QLabel(QApplication.translate('Label', 'Limit'))
            rangeLimitMinLabel = QLabel(QApplication.translate('Label', 'Min'))
            rangeLimitMaxLabel = QLabel(QApplication.translate('Label', 'Max'))
            self.positiveTargetRangeLimitFlag = QCheckBox()
            self.positiveTargetRangeLimitFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.positiveTargetRangeLimitFlag.setChecked(self.aw.pidcontrol.positiveTargetRangeLimit)
            self.positiveTargetRangeLimitFlag.stateChanged.connect(self.positiveTargetRangeLimitSlot)
            self.positiveTargetRangeLimitFlag.setToolTip(QApplication.translate('Tooltip', 'Activate range limit for positive PID output slider'))
            self.negativeTargetRangeLimitFlag = QCheckBox()
            self.negativeTargetRangeLimitFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.negativeTargetRangeLimitFlag.setChecked(self.aw.pidcontrol.negativeTargetRangeLimit)
            self.negativeTargetRangeLimitFlag.stateChanged.connect(self.negativeTargetRangeLimitSlot)
            self.negativeTargetRangeLimitFlag.setToolTip(QApplication.translate('Tooltip', 'Activate range limit for negative PID output slider'))

            self.positiveTargetMin = QSpinBox()
            self.positiveTargetMin.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.positiveTargetMin.setRange(0,100)
            self.positiveTargetMin.setSingleStep(10)
            self.positiveTargetMin.setEnabled(self.aw.pidcontrol.positiveTargetRangeLimit)
            self.positiveTargetMin.setToolTip(QApplication.translate('Tooltip', 'Positive output slider value at 0% duty'))

            self.positiveTargetMax = QSpinBox()
            self.positiveTargetMax.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.positiveTargetMax.setRange(0,100)
            self.positiveTargetMax.setSingleStep(10)
            self.positiveTargetMax.setEnabled(self.aw.pidcontrol.positiveTargetRangeLimit)
            self.positiveTargetMax.setToolTip(QApplication.translate('Tooltip', 'Positive output slider value at 100% duty'))

            self.updatePositiveTargetLimits(self.aw.pidcontrol.pidPositiveTarget)
            self.positiveTargetMin.setValue(self.aw.pidcontrol.positiveTargetMin)
            self.positiveTargetMax.setValue(self.aw.pidcontrol.positiveTargetMax)

            self.negativeTargetMin = QSpinBox()
            self.negativeTargetMin.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.negativeTargetMin.setRange(0,100)
            self.negativeTargetMin.setSingleStep(10)
            self.negativeTargetMin.setEnabled(self.aw.pidcontrol.negativeTargetRangeLimit)
            self.negativeTargetMin.setToolTip(QApplication.translate('Tooltip', 'Negative output slider value at 0% duty'))

            self.negativeTargetMax = QSpinBox()
            self.negativeTargetMax.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.negativeTargetMax.setRange(0,100)
            self.negativeTargetMax.setSingleStep(10)
            self.negativeTargetMax.setEnabled(self.aw.pidcontrol.negativeTargetRangeLimit)
            self.negativeTargetMax.setToolTip(QApplication.translate('Tooltip', 'Negative output slider value at -100% duty'))

            self.updateNegativeTargetLimits(self.aw.pidcontrol.pidNegativeTarget)
            self.negativeTargetMin.setValue(self.aw.pidcontrol.negativeTargetMin)
            self.negativeTargetMax.setValue(self.aw.pidcontrol.negativeTargetMax)

            controlSelectorLayout = QGridLayout()
            controlSelectorLayout.addWidget(targetSliderLabel,0,1,Qt.AlignmentFlag.AlignCenter)
            controlSelectorLayout.addWidget(rangeLimitLabel,0,2,Qt.AlignmentFlag.AlignCenter)
            controlSelectorLayout.addWidget(rangeLimitMinLabel,0,3,Qt.AlignmentFlag.AlignCenter)
            controlSelectorLayout.addWidget(rangeLimitMaxLabel,0,4,Qt.AlignmentFlag.AlignCenter)
            controlSelectorLayout.addWidget(positiveControlLabel,1,0)
            controlSelectorLayout.addWidget(self.positiveControlCombo,1,1)
            controlSelectorLayout.addWidget(self.positiveTargetRangeLimitFlag,1,2)
            controlSelectorLayout.addWidget(self.positiveTargetMin,1,3)
            controlSelectorLayout.addWidget(self.positiveTargetMax,1,4)
            controlSelectorLayout.addWidget(negativeControlLabel,2,0)
            controlSelectorLayout.addWidget(self.negativeControlCombo,2,1)
            controlSelectorLayout.addWidget(self.negativeTargetRangeLimitFlag,2,2)
            controlSelectorLayout.addWidget(self.negativeTargetMin,2,3)
            controlSelectorLayout.addWidget(self.negativeTargetMax,2,4)

            self.invertControlFlag = QCheckBox(QApplication.translate('Label', 'Invert Control'))
            self.invertControlFlag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.invertControlFlag.setChecked(self.aw.pidcontrol.invertControl)
            self.invertControlFlag.setToolTip(QApplication.translate('Tooltip', 'If active, positive duties set negative outputs and negative ones the positive outputs'))

            controlVBox = QVBoxLayout()
            controlVBox.addLayout(controlSelectorLayout)
            controlVBox.addWidget(self.invertControlFlag)

            controlHBox = QHBoxLayout()
            controlHBox.addStretch()
            controlHBox.addLayout(controlVBox)
            controlHBox.addStretch()

            pidTargetGrp = QGroupBox(QApplication.translate('GroupBox','Output'))
            pidTargetGrp.setLayout(controlHBox)
            pidTargetGrp.setContentsMargins(0,10,0,0)
            pidGridBox.addStretch()
            pidGridBox.addWidget(pidTargetGrp)
        pidGridBox.addStretch()

        pidGridVBox2 = QVBoxLayout()
        pidGridVBox2.addLayout(pidGridBox)
        pidGridVBox2.setContentsMargins(5,5,5,5) # left, top, right, bottom
        pidGrp.setLayout(pidGridVBox2)
        pidGrp.setContentsMargins(0,10,0,0)

        self.pidSV = QSpinBox()
        self.pidSV.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidSV.setRange(0,999)
        self.pidSV.setSingleStep(10)
        self.pidSV.setValue(toInt(self.aw.pidcontrol.svValue))
        self.pidSV.setToolTip(QApplication.translate('Tooltip', 'Manual set value (SV)'))
        pidSVLabel = QLabel(QApplication.translate('Label','SV'))

        self.pidSVLookahead = QSpinBox()
        self.pidSVLookahead.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidSVLookahead.setRange(0,999)
        self.pidSVLookahead.setSingleStep(1)
        self.pidSVLookahead.setValue(int(round(self.aw.pidcontrol.svLookahead)))
        self.pidSVLookahead.setSuffix(' s')
        self.pidSVLookahead.setToolTip(QApplication.translate('Tooltip', 'In background follow mode the set value (SV) is taken\nfrom the selected source signal with a positive time offset\nspecified by the lookahead'))
        pidSVLookaheadLabel = QLabel(QApplication.translate('Label','Lookahead'))



        pidSetSV = QPushButton(QApplication.translate('Button','Set'))
        pidSetSV.clicked.connect(self.setSV)
        pidSetSV.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        pidSVModeLabel = QLabel(QApplication.translate('Label','Mode'))
        pidModeItems = [
            QApplication.translate('Label', 'Manual'),
            QApplication.translate('Label', 'Ramp/Soak'),
            QApplication.translate('Label', 'Background')]
        self.pidMode = QComboBox()
        self.pidMode.addItems(pidModeItems)
        self.pidMode.setCurrentIndex(self.aw.pidcontrol.svMode)
        self.pidMode.currentIndexChanged.connect(self.updatePidMode)
        self.pidMode.setToolTip(QApplication.translate('Tooltip', 'PID mode, taking the target value from the manual set value (SV),\nthe specified Ramp/Soak pattern\nor the selected source signal of the background profiles'))

        self.pidSVbuttonsFlag = QCheckBox(QApplication.translate('Label','Buttons'))
        self.pidSVbuttonsFlag.setChecked(self.aw.pidcontrol.svButtons)
        self.pidSVbuttonsFlag.stateChanged.connect(self.activateONOFFeasySVslot)
        self.pidSVbuttonsFlag.setToolTip(QApplication.translate('Tooltip', 'Show the set value (SV) buttons for manual input of the PID target'))
        self.pidSVsliderFlag = QCheckBox(QApplication.translate('Label','Slider'))
        self.pidSVsliderFlag.setChecked(self.aw.pidcontrol.svSlider)
        self.pidSVsliderFlag.stateChanged.connect(self.activateSVSlider)
        self.pidSVsliderFlag.setToolTip(QApplication.translate('Tooltip', 'Show the set value (SV) slider for manual input of the PID target'))

        self.pidSVSliderMin = QSpinBox()
        self.pidSVSliderMin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidSVSliderMin.setRange(0,999)
        self.pidSVSliderMin.setSingleStep(10)
        self.pidSVSliderMin.setValue(max(0, min(999, int(self.aw.pidcontrol.svSliderMin))))
        self.pidSVSliderMin.setToolTip(QApplication.translate('Tooltip', 'Lower limit of the set value (SV) slider'))
        pidSVSliderMinLabel = QLabel(QApplication.translate('Label','Min'))
        self.pidSVSliderMin.valueChanged.connect(self.sliderMinValueChangedSlot)

        self.pidSVSliderMax = QSpinBox()
        self.pidSVSliderMax.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pidSVSliderMax.setRange(0,999)
        self.pidSVSliderMax.setSingleStep(10)
        self.pidSVSliderMax.setValue(max(0, min(999, int(self.aw.pidcontrol.svSliderMax))))
        self.pidSVSliderMax.setToolTip(QApplication.translate('Tooltip', 'Upper limit of the set value (SV) slider'))
        pidSVSliderMaxLabel = QLabel(QApplication.translate('Label','Max'))
        self.pidSVSliderMax.valueChanged.connect(self.sliderMaxValueChangedSlot)

        if self.aw.qmc.mode == 'F':
            self.pidSVSliderMin.setSuffix(' F')
            self.pidSVSliderMax.setSuffix(' F')
            self.pidSV.setSuffix(' F')
            self.pidSchedule0.setSuffix(' F')
            self.pidSchedule1.setSuffix(' F')
            self.pidSchedule2.setSuffix(' F')
        elif self.aw.qmc.mode == 'C':
            self.pidSVSliderMin.setSuffix(' C')
            self.pidSVSliderMax.setSuffix(' C')
            self.pidSV.setSuffix(' C')
            self.pidSchedule0.setSuffix(' C')
            self.pidSchedule1.setSuffix(' C')
            self.pidSchedule2.setSuffix(' C')

        modeBox = QHBoxLayout()
        modeBox.addWidget(pidSVModeLabel)
        modeBox.addWidget(self.pidMode)
        modeBox.addStretch()
        modeBox.addWidget(pidSVLookaheadLabel)
        modeBox.addWidget(self.pidSVLookahead)

        sliderBox = QHBoxLayout()
        sliderBox.addWidget(self.pidSVsliderFlag)
        sliderBox.addStretch()
        sliderBox.addWidget(pidSVSliderMinLabel)
        sliderBox.addWidget(self.pidSVSliderMin)
        sliderBox.addSpacing(10)
        sliderBox.addWidget(pidSVSliderMaxLabel)
        sliderBox.addWidget(self.pidSVSliderMax)

        svInputBox = QHBoxLayout()
        svInputBox.addWidget(self.pidSVbuttonsFlag)
        svInputBox.addStretch()
        svInputBox.addWidget(pidSVLabel)
        svInputBox.addWidget(self.pidSV)
        svInputBox.addWidget(pidSetSV)

        self.dutyMin = QSpinBox()
        self.dutyMin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.dutyMin.setRange(-100,100)
        self.dutyMin.setSingleStep(10)
        self.dutyMin.setValue(int(self.aw.pidcontrol.dutyMin))
        self.dutyMin.setSuffix(' %')
        dutyMinLabel = QLabel(QApplication.translate('Label','Min'))

        self.dutyMax = QSpinBox()
        self.dutyMax.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.dutyMax.setRange(-100,100)
        self.dutyMax.setSingleStep(10)
        self.dutyMax.setValue(int(self.aw.pidcontrol.dutyMax))
        self.dutyMax.setSuffix(' %')
        dutyMaxLabel = QLabel(QApplication.translate('Label','Max'))

        svGrpBox = QVBoxLayout()
        svGrpBox.addLayout(modeBox)
        svGrpBox.addLayout(sliderBox)
        svGrpBox.addLayout(svInputBox)
        if pid_controller == 0:
            # only for the internal PID we support a SV filter setting
            self.svFilterFlag = QCheckBox(QApplication.translate('Label','SV Filter'))
            self.svFilterFlag.setChecked(bool(self.aw.pidcontrol.sv_filter))
            self.svFilterFlag.setToolTip(QApplication.translate('Tooltip', 'Filter on SV in background follow mode'))
            svFilterBox = QHBoxLayout()
            svFilterBox.addStretch()
            svFilterBox.addWidget(self.svFilterFlag)
            svGrpBox.addLayout(svFilterBox)
        svGrpBox.addStretch()
        svGrpBox.setSpacing(5)
        svGrpBox.setContentsMargins(5,5,5,5) # left, top, right, bottom
        svGrp = QGroupBox(QApplication.translate('GroupBox','Set Value'))
        svGrp.setLayout(svGrpBox)
        svGrp.setContentsMargins(0,10,0,0) # left, top, right, bottom

        pidBox = QHBoxLayout()
        pidBox.addWidget(pidGrp)
        pidBox.setSpacing(4)

        svBox = QHBoxLayout()
        svBox.addWidget(svGrp)
        if pid_controller == 0: # only the internal PID allows for duty control

            # only for the internal PID we support a duty filter setting
            self.dutyFilterFlag = QCheckBox(QApplication.translate('Label','Duty Filter'))
            self.dutyFilterFlag.setToolTip(QApplication.translate('Tooltip', 'Smooth the final output signal and suppress abrupt changes in the P/I term'))
            self.dutyFilterFlag.setChecked(bool(self.aw.pidcontrol.duty_filter))

            dutyFilterBox = QHBoxLayout()
            dutyFilterBox.addWidget(self.dutyFilterFlag)
            dutyFilterBox.addStretch()
            dutyFilterBox.setContentsMargins(0,0,0,0)

            self.pidDutySteps = QSpinBox()
            self.pidDutySteps.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.pidDutySteps.setRange(1,10)
            self.pidDutySteps.setSingleStep(1)
            self.pidDutySteps.setValue(int(self.aw.pidcontrol.dutySteps))
            self.pidDutySteps.setSuffix(' %')
            self.pidDutySteps.setToolTip(QApplication.translate('Tooltip', 'Duty signal step size'))
            pidDutyStepsLabel = QLabel(QApplication.translate('Label','Steps'))

            dutyClampGrpBox = QGridLayout()
            dutyClampGrpBox.addWidget(dutyMaxLabel,1,0)
            dutyClampGrpBox.addWidget(self.dutyMax,1,1)
            dutyClampGrpBox.addWidget(dutyMinLabel,2,0)
            dutyClampGrpBox.addWidget(self.dutyMin,2,1)

            dutyClampGrp = QGroupBox(QApplication.translate('GroupBox','Clamp'))
            dutyClampGrp.setLayout(dutyClampGrpBox)
            dutyClampGrp.setToolTip(QApplication.translate('Tooltip', 'With just a positive output active, the PID duty ranges from 0% to 100%.\nWith just a negative output it ranges from -100% to 0%.\nWith both outputs active the range is -100% to 100%.\nThis range can be clamped by setting tighter minimum and maximum  limits.'))

            dutyGrid = QGridLayout()
            dutyGrid.addWidget(pidDutyStepsLabel,0,0)
            dutyGrid.addWidget(self.pidDutySteps,0,1)

            dutyGrpBox = QVBoxLayout()
            dutyGrpBox.addLayout(dutyFilterBox)
            dutyGrpBox.addLayout(dutyGrid)
            dutyGrpBox.addSpacing(15)
            dutyGrpBox.addWidget(dutyClampGrp)
            dutyGrpBox.addStretch()
            dutyGrpBox.setContentsMargins(5,5,5,5)
            dutyGrp = QGroupBox(QApplication.translate('GroupBox','Duty'))
            dutyGrp.setLayout(dutyGrpBox)
            dutyGrp.setContentsMargins(0,15,0,0)

            pTermSPweightLabel = QLabel(QApplication.translate('Label','\u03B2'))
            self.pTermSPweightSpinBox = MyQDoubleSpinBox()
            self.pTermSPweightSpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.pTermSPweightSpinBox.setRange(0.0, self.aw.pidcontrol.pidPsetpointWeightMax)
            self.pTermSPweightSpinBox.setSingleStep(.1)
            self.pTermSPweightSpinBox.setDecimals(2)
            self.pTermSPweightSpinBox.setValue(self.aw.pidcontrol.pidPsetpointWeight)
            self.pTermSPweightSpinBox.setToolTip(QApplication.translate('Tooltip', 'Proportional setvalue weight'))
            self.pTermSPweightSpinBox.valueChanged.connect(self.pTermSPweightChanged)

            dTermSPweightLabel = QLabel(QApplication.translate('Label','\u03B3'))
            self.dTermSPweightSpinBox = MyQDoubleSpinBox()
            self.dTermSPweightSpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.dTermSPweightSpinBox.setRange(0.0, self.aw.pidcontrol.pidDsetpointWeightMax)
            self.dTermSPweightSpinBox.setSingleStep(.1)
            self.dTermSPweightSpinBox.setDecimals(2)
            self.dTermSPweightSpinBox.setValue(self.aw.pidcontrol.pidDsetpointWeight)
            self.dTermSPweightSpinBox.setToolTip(QApplication.translate('Tooltip', 'Derivative setvalue weight'))
            self.dTermSPweightSpinBox.valueChanged.connect(self.dTermSPweightChanged)

            # only for the internal PID we support a derative filter setting
            self.derivativeFilterFlag = QCheckBox(QApplication.translate('Label','Derivative Filter'))
            self.derivativeFilterFlag.setChecked(bool(self.aw.pidcontrol.derivative_filter))

            DFilterBox = QHBoxLayout()
            DFilterBox.addWidget(self.derivativeFilterFlag)
            DFilterBox.addStretch()
            DFilterBox.setContentsMargins(0,0,0,0)

            self.PoERadioButton = QRadioButton(QApplication.translate('Label','PoE'))
            self.PoERadioButton.setToolTip(QApplication.translate('Tooltip', 'Proportional on Error'))
            self.PoMRadioButton = QRadioButton(QApplication.translate('Label','PoM'))
            self.PoMRadioButton.setToolTip(QApplication.translate('Tooltip', 'Proportional on Measurement'))

            self.DoERadioButton = QRadioButton(QApplication.translate('Label','DoE'))
            self.DoERadioButton.setToolTip(QApplication.translate('Tooltip', 'Derivative on Error'))
            self.DoMRadioButton = QRadioButton(QApplication.translate('Label','DoM'))
            self.DoMRadioButton.setToolTip(QApplication.translate('Tooltip', 'Derivative on Measurement (preventing the derivative kick)'))

            self.PoX = QButtonGroup(self)
            self.PoX.addButton(self.PoERadioButton)
            self.PoX.addButton(self.PoMRadioButton)
            pTypeBox = QHBoxLayout()
            pTypeBox.addWidget(self.PoERadioButton)
            pTypeBox.addWidget(self.PoMRadioButton)
            pTypeBox.addStretch()
            pTypeBox.addSpacing(5)
            pTypeBox.addWidget(pTermSPweightLabel)
            pTypeBox.addWidget(self.pTermSPweightSpinBox)

            self.updatePtypeRadioButtons()
            self.PoERadioButton.toggled.connect(self.PoERadioButtonToggled)
            self.PoMRadioButton.toggled.connect(self.PoMRadioButtonToggled)

            self.DoX = QButtonGroup(self)
            self.DoX.addButton(self.DoERadioButton)
            self.DoX.addButton(self.DoMRadioButton)
            dTypeBox = QHBoxLayout()
            dTypeBox.addWidget(self.DoERadioButton)
            dTypeBox.addWidget(self.DoMRadioButton)
            dTypeBox.addStretch()
            dTypeBox.addSpacing(5)
            dTypeBox.addWidget(dTermSPweightLabel)
            dTypeBox.addWidget(self.dTermSPweightSpinBox)

            self.updateDtypeRadioButtons()
            self.DoERadioButton.toggled.connect(self.DoERadioButtonToggled)
            self.DoMRadioButton.toggled.connect(self.DoMRadioButtonToggled)

            iLimitLabel = QLabel(QApplication.translate('Label','ILF'))
            self.iLimitSpinBox = MyQDoubleSpinBox()
            self.iLimitSpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.iLimitSpinBox.setRange(0.0,1.0)
            self.iLimitSpinBox.setSingleStep(.1)
            self.iLimitSpinBox.setDecimals(2)
            self.iLimitSpinBox.setValue(self.aw.pidcontrol.pidIlimitFactor)
            self.iLimitSpinBox.setToolTip(QApplication.translate('Tooltip', 'Integral limit factor'))

            dLimitLabel = QLabel(QApplication.translate('Label','Dlimit'))
            self.dLimitSpinBox = QSpinBox()
            self.dLimitSpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.dLimitSpinBox.setRange(0,999)
            self.dLimitSpinBox.setSingleStep(1)
            self.dLimitSpinBox.setValue(int(self.aw.pidcontrol.pidDlimit))
            self.dLimitSpinBox.setToolTip(QApplication.translate('Tooltip', 'Derivative limit'))

            LimitBox = QHBoxLayout()
            LimitBox.addWidget(iLimitLabel)
            LimitBox.addWidget(self.iLimitSpinBox)
            LimitBox.addSpacing(5)
            LimitBox.addStretch()
            LimitBox.addWidget(dLimitLabel)
            LimitBox.addWidget(self.dLimitSpinBox)
            LimitBox.setSpacing(3)

            self.SPthresholdSpinBox = QSpinBox()
            self.SPthresholdSpinBox.setToolTip(QApplication.translate('Tooltip', 'Integral reset on target (SP) changes exceeding the limit'))
            self.SPthresholdSpinBox.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.SPthresholdSpinBox.setRange(0,100)
            self.SPthresholdSpinBox.setSingleStep(1)
            self.SPthresholdSpinBox.setValue(int(self.aw.pidcontrol.pidIRoCthreshold))
            self.SPthresholdSpinBox.setEnabled(self.aw.pidcontrol.pidIRoC)
            self.IWPFlag = QCheckBox(QApplication.translate('Label','IWP'))
            self.IWPFlag.setToolTip(QApplication.translate('Tooltip', 'Integral Windup Prevention'))
            self.IWPFlag.setChecked(self.aw.pidcontrol.pidIWP)
            self.IRoCFlag = QCheckBox(QApplication.translate('Label','IRoC'))
            self.IRoCFlag.setToolTip(QApplication.translate('Tooltip', 'Integral reset on target (SP) changes exceeding the limit'))
            self.IRoCFlag.stateChanged.connect(self.IRoCFlag_changedSlot)
            self.IRoCFlag.setChecked(self.aw.pidcontrol.pidIRoC)

            IBox = QHBoxLayout()
            IBox.addWidget(self.IWPFlag)
            IBox.addSpacing(10)
            IBox.addStretch()
            IBox.addWidget(self.IRoCFlag)
            IBox.addWidget(self.SPthresholdSpinBox)
            IBox.setContentsMargins(0,0,0,0)

            filterGrpBox = QVBoxLayout()
            filterGrpBox.addLayout(pTypeBox)
            filterGrpBox.addLayout(dTypeBox)
            filterGrpBox.addLayout(DFilterBox)
            filterGrpBox.addLayout(LimitBox)
            filterGrpBox.addLayout(IBox)
            filterGrpBox.addStretch()
            filterGrpBox.setSpacing(10)
            filterGrp = QGroupBox(QApplication.translate('Menu','Config'))
            filterGrp.setLayout(filterGrpBox)
#            filterGrp.setContentsMargins(0,0,0,0) # left, top, right, bottom

            svBox.addWidget(dutyGrp)
            svBox.addWidget(filterGrp)
        svBox.addStretch()

        self.startPIDonCHARGE = QCheckBox(QApplication.translate('CheckBox', 'Start PID on CHARGE'))
        self.startPIDonCHARGE.setToolTip(QApplication.translate('Tooltip', 'Automatically turn the PID ON on CHARGE'))
        self.startPIDonCHARGE.setChecked(self.aw.pidcontrol.pidOnCHARGE)

        self.stopPIDonDROP = QCheckBox(QApplication.translate('CheckBox', 'Stop PID on DROP'))
        self.stopPIDonDROP.setToolTip(QApplication.translate('Tooltip', 'Automatically turn the PID OFF on DROP'))
        self.stopPIDonDROP.setChecked(self.aw.pidcontrol.pidOffDROP)

        self.createEvents = QCheckBox(QApplication.translate('CheckBox', 'Create Events'))
        self.createEvents.setChecked(self.aw.pidcontrol.createEvents)
        self.createEvents.setToolTip(QApplication.translate('Tooltip', 'Generated an event mark on each output slider change\ninitiated by the PID'))
        if pid_controller != 0:
            self.createEvents.setEnabled(False)

        self.loadPIDfromBackground = QCheckBox(QApplication.translate('CheckBox', 'Load p-i-d from background'))
        self.loadPIDfromBackground.setToolTip(QApplication.translate('Tooltip', 'Load kp, ki, kd, PID Input, P on Error/Input and Lookahead settings from background profile'))
        self.loadPIDfromBackground.setChecked(self.aw.pidcontrol.loadpidfrombackground)
        if pid_controller == 4:
            self.loadPIDfromBackground.setEnabled(False)

        flagsLayout = QHBoxLayout()
        flagsLayout.addWidget(self.startPIDonCHARGE)
        flagsLayout.addSpacing(10)
        flagsLayout.addWidget(self.stopPIDonDROP)
        flagsLayout.addSpacing(10)
        flagsLayout.addWidget(self.createEvents)
        flagsLayout.addSpacing(10)
        flagsLayout.addWidget(self.loadPIDfromBackground)
        flagsLayout.addSpacing(10) # to avoid cutting the last flag label (layout bug!)
        flagsLayout.addStretch()

        tab1Layout.addLayout(pidBox)
        tab1Layout.addLayout(svBox)
        tab1Layout.addStretch()
        tab1Layout.addLayout(flagsLayout)

        labelLabel = QLabel(QApplication.translate('Label', 'Label'))
        self.labelEdit = QLineEdit()

        labelRow = QHBoxLayout()
        labelRow.addStretch()
        labelRow.addWidget(labelLabel)
        labelRow.addWidget(self.labelEdit)
        labelRow.addStretch()

        # Ramp/Soak tab
        tab2InnerLayout = QHBoxLayout()
        tab2Layout = QVBoxLayout()
        tab2Layout.addSpacing(10)
        tab2Layout.addLayout(labelRow)
        tab2Layout.addSpacing(15)
        tab2Layout.addLayout(tab2InnerLayout)
        rsGrid = QGridLayout()
        self.SVWidgets:list[QSpinBox] = []
        self.RampWidgets:list[QTimeEdit] = []
        self.SoakWidgets:list[QTimeEdit] = []
        self.ActionWidgets:list[MyQComboBox] = []
        self.BeepWidgets:list[QWidget] = []
        self.DescriptionWidgets:list[QLineEdit] = []
        rsGrid.addWidget(QLabel(QApplication.translate('Table','SV')),0,1)
        rsGrid.addWidget(QLabel(QApplication.translate('Table','Ramp')),0,2)
        rsGrid.addWidget(QLabel(QApplication.translate('Table','Soak')),0,3)
        rsGrid.addWidget(QLabel(QApplication.translate('Table','Action')),0,4)
        rsGrid.addWidget(QLabel(QApplication.translate('Table','Beep')),0,5)
        rsGrid.addWidget(QLabel(QApplication.translate('Table','Description')),0,6)
        actions = ['',
            QApplication.translate('ComboBox','Pop Up'),
            QApplication.translate('ComboBox','Call Program'),
            QApplication.translate('ComboBox','Event Button'),
            QApplication.translate('ComboBox','Slider') + ' ' + self.aw.qmc.etypesf(0),
            QApplication.translate('ComboBox','Slider') + ' ' + self.aw.qmc.etypesf(1),
            QApplication.translate('ComboBox','Slider') + ' ' + self.aw.qmc.etypesf(2),
            QApplication.translate('ComboBox','Slider') + ' ' + self.aw.qmc.etypesf(3),
            QApplication.translate('ComboBox','START'),
            QApplication.translate('Label','DRY END'),
            QApplication.translate('Label','FC START'),
            QApplication.translate('Label','FC END'),
            QApplication.translate('Label','SC START'),
            QApplication.translate('Label','SC END'),
            QApplication.translate('Label','DROP'),
            QApplication.translate('ComboBox','COOL END'),
            QApplication.translate('ComboBox','OFF'),
            QApplication.translate('Label','CHARGE'),
            QApplication.translate('ComboBox','RampSoak ON'),
            QApplication.translate('ComboBox','RampSoak OFF'),
            QApplication.translate('ComboBox','PID ON'),
            QApplication.translate('ComboBox','PID OFF'),
            QApplication.translate('ComboBox','SV'),
            QApplication.translate('ComboBox','Playback ON'),
            QApplication.translate('ComboBox','Playback OFF'),
            QApplication.translate('ComboBox','Set Canvas Color'),
            QApplication.translate('ComboBox','Reset Canvas Color')]
        for i in range(self.aw.pidcontrol.svLen):
            n = i+1
            svwidget = QSpinBox()
            svwidget.setAlignment(Qt.AlignmentFlag.AlignRight)
            svwidget.setRange(0,999)
            svwidget.setSingleStep(10)
            if self.aw.qmc.mode == 'F':
                svwidget.setSuffix(' F')
            elif self.aw.qmc.mode == 'C':
                svwidget.setSuffix(' C')
            self.SVWidgets.append(svwidget)
            rampwidget = QTimeEdit()
            rampwidget.setDisplayFormat('mm:ss')
            rampwidget.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.RampWidgets.append(rampwidget)
            soakwidget = QTimeEdit()
            soakwidget.setDisplayFormat('mm:ss')
            soakwidget.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.SoakWidgets.append(soakwidget)
            actionwidget = MyQComboBox()
            actionwidget.addItems(actions)
            self.ActionWidgets.append(actionwidget)
            #beep
            beepwidget = QWidget()
            beepCheckBox = QCheckBox()
            beepCheckBox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            beepLayout = QHBoxLayout()
            beepLayout.addStretch()
            beepLayout.addWidget(beepCheckBox)
            beepLayout.addSpacing(6)
            beepLayout.addStretch()
            beepLayout.setContentsMargins(0,0,0,0)
            beepLayout.setSpacing(0)
            beepwidget.setLayout(beepLayout)
            self.BeepWidgets.append(beepwidget)
            # description
            descriptionwidget = QLineEdit()
            descriptionwidget.setCursorPosition(0)
            self.DescriptionWidgets.append(descriptionwidget)
            rsGrid.addWidget(QLabel(str(n)),n,0)
            rsGrid.addWidget(svwidget,n,1)
            rsGrid.addWidget(self.RampWidgets[i],n,2)
            rsGrid.addWidget(self.SoakWidgets[i],n,3)
            rsGrid.addWidget(self.ActionWidgets[i],n,4)
            rsGrid.addWidget(self.BeepWidgets[i],n,5)
            rsGrid.addWidget(self.DescriptionWidgets[i],n,6)

        ############################
        importButton = QPushButton(QApplication.translate('Button','Load'))
        importButton.setMinimumWidth(80)
        importButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        importButton.clicked.connect(self.importrampsoaks)
        exportButton = QPushButton(QApplication.translate('Button','Save'))
        exportButton.setMinimumWidth(80)
        exportButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        exportButton.clicked.connect(self.exportrampsoaks)
        self.loadRampSoakFromProfile = QCheckBox(QApplication.translate('CheckBox', 'Load from profile'))
        self.loadRampSoakFromProfile.setChecked(self.aw.pidcontrol.loadRampSoakFromProfile)
        self.loadRampSoakFromProfile.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.loadRampSoakFromBackground = QCheckBox(QApplication.translate('CheckBox', 'Load from background'))
        self.loadRampSoakFromBackground.setChecked(self.aw.pidcontrol.loadRampSoakFromBackground)
        self.loadRampSoakFromBackground.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.rsfile = QLabel(self.aw.qmc.rsfile)
        self.rsfile.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.rsfile.setMinimumWidth(300)
        self.rsfile.setSizePolicy(QSizePolicy.Policy.MinimumExpanding,QSizePolicy.Policy.Preferred)

        tab2InnerLayout.addStretch()
        tab2InnerLayout.addLayout(rsGrid)
        tab2InnerLayout.addStretch()

        okButton = QPushButton(QApplication.translate('Button','OK'))
        okButton.clicked.connect(self.okAction)
        onButton = QPushButton(QApplication.translate('Button','On'))
        onButton.setToolTip(QApplication.translate('Tooltip', 'Turn PID ON'))
        onButton.clicked.connect(self.pidONAction)
        onButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        offButton = QPushButton(QApplication.translate('Button','Off'))
        offButton.clicked.connect(self.pidOFFAction)
        offButton.setToolTip(QApplication.translate('Tooltip', 'Turn PID OFF'))
        offButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        okButtonLayout = QHBoxLayout()
        okButtonLayout.addWidget(onButton)
        okButtonLayout.addWidget(offButton)
        okButtonLayout.addStretch()
        okButtonLayout.addWidget(self.rsfile)
        okButtonLayout.addStretch()
        okButtonLayout.addWidget(okButton)
        okButtonLayout.setContentsMargins(0,0,0,0)
        tab1Layout.setContentsMargins(0,0,0,0) # left, top, right, bottom
        tab1Layout.setSpacing(5)
        tab2Layout.setContentsMargins(10,10,10,10)
        tab2Layout.setSpacing(5)
        self.tabWidget = QTabWidget()
        C1Widget = QWidget()
        C1Widget.setLayout(tab1Layout)
        self.tabWidget.addTab(C1Widget,QApplication.translate('Tab','PID'))
        C2Widget = QWidget()
        C2Widget.setLayout(tab2Layout)
        self.tabWidget.addTab(C2Widget,QApplication.translate('Tab','Ramp/Soak'))
        self.tabWidget.setContentsMargins(0,0,0,0)
        ############################

        # RSn tabs
        self.RSnTab_LabelWidgets:list[QLineEdit] = []
        self.RSnTab_SVWidgets:list[list[QSpinBox]] = []
        self.RSnTab_RampWidgets:list[list[QTimeEdit]] = []
        self.RSnTab_SoakWidgets:list[list[QTimeEdit]] = []
        self.RSnTab_ActionWidgets:list[list[MyQComboBox]] = []
        self.RSnTab_BeepWidgets:list[list[QWidget]] = []
        self.RSnTab_DescriptionWidgets:list[list[QLineEdit]] = []

        self.RSnButtons = []

        RSbuttonLayout = QHBoxLayout()
        RSbuttonLayout.addStretch()

        for j in range(self.aw.pidcontrol.RSLen):
            # create tab per RSn set
            RSnGrid = QGridLayout()
            RSnGrid.addWidget(QLabel(QApplication.translate('Table','SV')),0,1)
            RSnGrid.addWidget(QLabel(QApplication.translate('Table','Ramp')),0,2)
            RSnGrid.addWidget(QLabel(QApplication.translate('Table','Soak')),0,3)
            RSnGrid.addWidget(QLabel(QApplication.translate('Table','Action')),0,4)
            RSnGrid.addWidget(QLabel(QApplication.translate('Table','Beep')),0,5)
            RSnGrid.addWidget(QLabel(QApplication.translate('Table','Description')),0,6)
            SVWidgets:list[QSpinBox] = []
            RampWidgets:list[QTimeEdit] = []
            SoakWidgets:list[QTimeEdit] = []
            ActionWidgets:list[MyQComboBox] = []
            BeepWidgets:list[QWidget] = []
            DescriptionWidgets:list[QLineEdit] = []
            labelLabel = QLabel(QApplication.translate('Label', 'Label'))
            labelEdit = QLineEdit()
            for i in range(self.aw.pidcontrol.svLen):
                n = i+1
                svwidget = QSpinBox()
                svwidget.setAlignment(Qt.AlignmentFlag.AlignRight)
                svwidget.setRange(0,999)
                svwidget.setSingleStep(10)
                if self.aw.qmc.mode == 'F':
                    svwidget.setSuffix(' F')
                elif self.aw.qmc.mode == 'C':
                    svwidget.setSuffix(' C')
                SVWidgets.append(svwidget)
                rampwidget = QTimeEdit()
                rampwidget.setDisplayFormat('mm:ss')
                rampwidget.setAlignment(Qt.AlignmentFlag.AlignRight)
                RampWidgets.append(rampwidget)
                soakwidget = QTimeEdit()
                soakwidget.setDisplayFormat('mm:ss')
                soakwidget.setAlignment(Qt.AlignmentFlag.AlignRight)
                SoakWidgets.append(soakwidget)
                actionwidget = MyQComboBox()
                actionwidget.addItems(actions)
                ActionWidgets.append(actionwidget)
                #beep
                beepwidget = QWidget()
                beepCheckBox = QCheckBox()
                beepCheckBox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                beepLayout = QHBoxLayout()
                beepLayout.addStretch()
                beepLayout.addWidget(beepCheckBox)
                beepLayout.addSpacing(6)
                beepLayout.addStretch()
                beepLayout.setContentsMargins(0,0,0,0)
                beepLayout.setSpacing(0)
                beepwidget.setLayout(beepLayout)
                BeepWidgets.append(beepwidget)
                # description
                descwidget = QLineEdit()
                descwidget.setCursorPosition(0)
                DescriptionWidgets.append(descwidget)
                #
                RSnGrid.addWidget(QLabel(str(n)),n,0)
                RSnGrid.addWidget(svwidget,n,1)
                RSnGrid.addWidget(RampWidgets[i],n,2)
                RSnGrid.addWidget(SoakWidgets[i],n,3)
                RSnGrid.addWidget(ActionWidgets[i],n,4)
                RSnGrid.addWidget(BeepWidgets[i],n,5)
                RSnGrid.addWidget(DescriptionWidgets[i],n,6)
            self.RSnTab_LabelWidgets.append(labelEdit)
            self.RSnTab_SVWidgets.append(SVWidgets)
            self.RSnTab_RampWidgets.append(RampWidgets)
            self.RSnTab_SoakWidgets.append(SoakWidgets)
            self.RSnTab_ActionWidgets.append(ActionWidgets)
            self.RSnTab_BeepWidgets.append(BeepWidgets)
            self.RSnTab_DescriptionWidgets.append(DescriptionWidgets)
            # create tab
            RSnTabLayout = QVBoxLayout()
            RSnLabelLayout = QHBoxLayout()
            RSnLabelLayout.addStretch()
            RSnLabelLayout.addWidget(labelLabel)
            RSnLabelLayout.addWidget(labelEdit)
            RSnLabelLayout.addStretch()
            RSnTabInnerLayout = QHBoxLayout()
            RSnTabInnerLayout.addStretch()
            RSnTabInnerLayout.addLayout(RSnGrid)
            RSnTabInnerLayout.addStretch()
            RSnTabLayout.addSpacing(10)
            RSnTabLayout.addLayout(RSnLabelLayout)
            RSnTabLayout.addSpacing(15)
            RSnTabLayout.addLayout(RSnTabInnerLayout)
            RSnTabLayout.addStretch()
            RSnTabLayout.setContentsMargins(10,10,10,10)
            RSnTabLayout.setSpacing(5)

            RSnTabWidget = QWidget()
            RSnTabWidget.setLayout(RSnTabLayout)
            self.tabWidget.addTab(RSnTabWidget,QApplication.translate('Tab','RS')+str(j+1))

            setRSnButton = QPushButton(QApplication.translate('Button','RS')+str(j+1))
            setRSnButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            setRSnButton.clicked.connect(self.setRS)
            self.RSnButtons.append(setRSnButton)
            RSbuttonLayout.addWidget(setRSnButton)
        RSbuttonLayout.addStretch()

        flagsLayout = QHBoxLayout()
        flagsLayout.addStretch()
        flagsLayout.addWidget(self.loadRampSoakFromProfile)
        flagsLayout.addSpacing(15)
        flagsLayout.addWidget(self.loadRampSoakFromBackground)
        flagsLayout.addStretch()

#        time_label = QLabel(QApplication.translate('Label', 'Time starts at'))
#        self.radioTimeAfterCHARGE = QRadioButton(QApplication.translate('Label','CHARGE'))
#        self.radioTimeAfterPIDON = QRadioButton(QApplication.translate('Button','PID ON'))
#        if self.aw.pidcontrol.RStimeAfterCHARGE:
#            self.radioTimeAfterCHARGE.setChecked(True)
#        else:
#            self.radioTimeAfterPIDON.setChecked(True)
#        radioButtonsLayout = QHBoxLayout()
#        radioButtonsLayout.addStretch()
#        radioButtonsLayout.addWidget(time_label)
#        radioButtonsLayout.addWidget(self.radioTimeAfterCHARGE)
#        radioButtonsLayout.addWidget(self.radioTimeAfterPIDON)
#        radioButtonsLayout.addStretch()

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(importButton)
        buttonLayout.addWidget(exportButton)
        if self.aw.pidcontrol.RSLen > 0:
            buttonLayout.addSpacing(25)
            buttonLayout.addLayout(RSbuttonLayout)
        buttonLayout.addStretch()

        tab2Layout.addLayout(buttonLayout)
        tab2Layout.addStretch()
#        tab2Layout.addLayout(radioButtonsLayout)
        tab2Layout.addLayout(flagsLayout)


        okButton.setFocus()

        ############################
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tabWidget)
        mainLayout.addLayout(okButtonLayout)
        mainLayout.setContentsMargins(5,10,5,5)
        mainLayout.setSpacing(5)
        self.setLayout(mainLayout)

        self.setrampsoaks()
        self.setRSs()

        settings = QSettings()
        if settings.contains('PIDPosition'):
            self.move(settings.value('PIDPosition'))

        mainLayout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        # we set the active tab with a QTimer after the tabbar has been rendered once, as otherwise
        # some tabs are not rendered at all on Windows using Qt v6.5.1 (https://bugreports.qt.io/projects/QTBUG/issues/QTBUG-114204?filter=allissues)
        QTimer.singleShot(10, self.setActiveTab)

    @pyqtSlot(int)
    def scheduling_state_changed(self, _:int) -> None:
        self.updateSchedulingWidgetsEnableStatus()

    @pyqtSlot(bool)
    def scheduling_input_changed(self, _:bool = False) -> None:
        self.updateSchedulingInput()

    @pyqtSlot(bool)
    def scheduling_method_changed(self, _:bool = False) -> None:
        self.updateSchedulingWidgetsEnableStatus()

    def updateSchedulingInput(self) -> None:
        if self.pidSchedulingPV.isChecked():
            self.pidScheduleModeLabel.setText('PV')
        else:
            self.pidScheduleModeLabel.setText('SV')


    def updateSchedulingWidgetsEnableStatus(self) -> None:
        scheduling_enabled:bool = self.pidSchedulingFlag.isChecked()
        scheduling_quadratic:bool = self.pidSchedulingQuadratic.isChecked()
        self.pidScheduleModeLabel.setEnabled(scheduling_enabled)
        self.pidSchedulingPV.setEnabled(scheduling_enabled)
        self.pidSchedulingSV.setEnabled(scheduling_enabled)
        self.pidSchedulingLinear.setEnabled(scheduling_enabled)
        self.pidSchedulingQuadratic.setEnabled(scheduling_enabled)
        self.pidSchedule0.setEnabled(scheduling_enabled)
        self.pidSchedule1.setEnabled(scheduling_enabled)
        self.pidSchedule2.setEnabled(scheduling_enabled and scheduling_quadratic)
        self.pidKp1.setEnabled(scheduling_enabled)
        self.pidKp2.setEnabled(scheduling_enabled and scheduling_quadratic)
        self.pidKi1.setEnabled(scheduling_enabled)
        self.pidKi2.setEnabled(scheduling_enabled and scheduling_quadratic)
        self.pidKd1.setEnabled(scheduling_enabled)
        self.pidKd2.setEnabled(scheduling_enabled and scheduling_quadratic)


    def updatePTermSPweightSpinBox(self) -> None:
        self.pTermSPweightSpinBox.blockSignals(True)
        self.pTermSPweightSpinBox.setValue(self.aw.pidcontrol.pidPsetpointWeight)
        self.pTermSPweightSpinBox.blockSignals(False)

    def updateDTermSPweightSpinBox(self) -> None:
        self.dTermSPweightSpinBox.blockSignals(True)
        self.dTermSPweightSpinBox.setValue(self.aw.pidcontrol.pidDsetpointWeight)
        self.dTermSPweightSpinBox.blockSignals(False)


    @pyqtSlot(bool)
    def PoERadioButtonToggled(self, checked:bool) -> None:
        if checked:
            self.aw.pidcontrol.pidPsetpointWeight = 1
            self.updatePTermSPweightSpinBox()
            self.PoX.setExclusive(True)

    @pyqtSlot(bool)
    def PoMRadioButtonToggled(self, checked:bool) -> None:
        if checked:
            self.aw.pidcontrol.pidPsetpointWeight = 0
            self.updatePTermSPweightSpinBox()
            self.PoX.setExclusive(True)

    @pyqtSlot(float)
    def pTermSPweightChanged(self, value:float) -> None:
        self.aw.pidcontrol.pidPsetpointWeight = min(self.aw.pidcontrol.pidPsetpointWeightMax, max(0., float2float(value,2)))
        self.updatePtypeRadioButtons()


    @pyqtSlot(bool)
    def DoERadioButtonToggled(self, checked:bool) -> None:
        if checked:
            self.aw.pidcontrol.pidDsetpointWeight = 1
            self.updateDTermSPweightSpinBox()
            self.DoX.setExclusive(True)

    @pyqtSlot(bool)
    def DoMRadioButtonToggled(self, checked:bool) -> None:
        if checked:
            self.aw.pidcontrol.pidDsetpointWeight = 0
            self.updateDTermSPweightSpinBox()
            self.DoX.setExclusive(True)

    @pyqtSlot(float)
    def dTermSPweightChanged(self, value:float) -> None:
        self.aw.pidcontrol.pidDsetpointWeight = min(self.aw.pidcontrol.pidDsetpointWeightMax, max(0., float2float(value,2)))
        self.updateDtypeRadioButtons()

    def updatePtypeRadioButtons(self) -> None:
        if self.aw.pidcontrol.pidPsetpointWeight == 1:
            self.PoERadioButton.setChecked(True)
            self.PoX.setExclusive(True)
        elif self.aw.pidcontrol.pidPsetpointWeight == 0:
            self.PoMRadioButton.setChecked(True)
            self.PoX.setExclusive(True)
        else:
            self.PoX.setExclusive(False)
            self.PoERadioButton.setChecked(False)
            self.PoMRadioButton.setChecked(False)

    def updateDtypeRadioButtons(self) -> None:
        if self.aw.pidcontrol.pidDsetpointWeight == 1:
            self.DoERadioButton.setChecked(True)
            self.DoX.setExclusive(True)
        elif self.aw.pidcontrol.pidDsetpointWeight == 0:
            self.DoMRadioButton.setChecked(True)
            self.DoX.setExclusive(True)
        else:
            self.DoX.setExclusive(False)
            self.DoERadioButton.setChecked(False)
            self.DoMRadioButton.setChecked(False)

    # NOTE: ET/BT inverted as pidSource=1 => BT and pidSource=2 => ET !!
    def getCurveNames(self) -> list[str]:
        curveNames = []
        curveNames.append(self.aw.qmc.device_name_subst(self.aw.ETname))
        curveNames.append(self.aw.qmc.device_name_subst(self.aw.BTname))
        for i in range(len(self.aw.qmc.extradevices)):
            curveNames.append(self.aw.qmc.device_name_subst(self.aw.qmc.extraname1[i]))
            curveNames.append(self.aw.qmc.device_name_subst(self.aw.qmc.extraname2[i]))
        return curveNames

    @pyqtSlot(int)
    def IRoCFlag_changedSlot(self, flag:int) -> None:
        self.SPthresholdSpinBox.setEnabled(bool(flag))

    @pyqtSlot()
    def setActiveTab(self) -> None:
        self.tabWidget.setCurrentIndex(self.activeTab)

    @pyqtSlot(int)
    def updatePidMode(self, i:int) -> None:
        self.aw.pidcontrol.svMode = i
        if self.aw.pidcontrol.pidActive and i == 1:
            self.aw.pidcontrol.pidModeInit()
        else:
            self.aw.setTimerColor('timer')
            if self.aw.qmc.flagon and not self.aw.qmc.flagstart:
                self.aw.qmc.setLCDtime(0)

    @pyqtSlot(int)
    def activateSVSlider(self, i:int) -> None:
        self.aw.pidcontrol.activateSVSlider(bool(i))

    @pyqtSlot(bool)
    def pidONAction(self, _:bool = False) -> None:
        self.aw.pidcontrol.pidOn()

    @pyqtSlot(bool)
    def pidOFFAction(self, _:bool = False) -> None:
        self.aw.pidcontrol.pidOff()

    @pyqtSlot(bool)
    def okAction(self, _:bool = False) -> None:
        self.close()

    @pyqtSlot(int)
    def activateONOFFeasySVslot(self, i:int) -> None:
        self.aw.pidcontrol.activateONOFFeasySV(bool(i))

    @pyqtSlot(int)
    def positiveTargetRangeLimitSlot(self, i:int) -> None:
        self.aw.pidcontrol.positiveTargetRangeLimit = bool(i)
        self.positiveTargetMin.setEnabled(self.aw.pidcontrol.positiveTargetRangeLimit)
        self.positiveTargetMax.setEnabled(self.aw.pidcontrol.positiveTargetRangeLimit)

    # ensure that the target limits are within the selected target sliders limits
    @pyqtSlot(int)
    def updatePositiveTargetLimits(self, i:int) -> None:
        self.aw.pidcontrol.pidPositiveTarget = i
        if self.aw.pidcontrol.pidPositiveTarget == 0:
            # default to a range within [0,100]
            slider_min = 0
            slider_max = 100
            self.positiveTargetRangeLimitFlag.setEnabled(False)
            self.positiveTargetMin.setEnabled(False)
            self.positiveTargetMax.setEnabled(False)
        else:
            slidernr = self.aw.pidcontrol.pidPositiveTarget - 1
            slider_min = self.aw.eventslidermin[slidernr]
            slider_max = self.aw.eventslidermax[slidernr]
            self.positiveTargetRangeLimitFlag.setEnabled(True)
            self.positiveTargetMin.setEnabled(self.aw.pidcontrol.positiveTargetRangeLimit)
            self.positiveTargetMax.setEnabled(self.aw.pidcontrol.positiveTargetRangeLimit)
        self.positiveTargetMin.setRange(slider_min, slider_max)
        self.positiveTargetMax.setRange(slider_min, slider_max)


    # ensure that the target limits are within the selected target sliders limits
    @pyqtSlot(int)
    def updateNegativeTargetLimits(self, i:int) -> None:
        self.aw.pidcontrol.pidNegativeTarget = i
        if self.aw.pidcontrol.pidNegativeTarget == 0:
            # default to a range within [0,100]
            slider_min = 0
            slider_max = 100
            self.negativeTargetRangeLimitFlag.setEnabled(False)
            self.negativeTargetMin.setEnabled(False)
            self.negativeTargetMax.setEnabled(False)
        else:
            slidernr = self.aw.pidcontrol.pidNegativeTarget - 1
            slider_min = self.aw.eventslidermin[slidernr]
            slider_max = self.aw.eventslidermax[slidernr]
            self.negativeTargetRangeLimitFlag.setEnabled(True)
            self.negativeTargetMin.setEnabled(self.aw.pidcontrol.negativeTargetRangeLimit)
            self.negativeTargetMax.setEnabled(self.aw.pidcontrol.negativeTargetRangeLimit)
        self.negativeTargetMin.setRange(slider_min, slider_max)
        self.negativeTargetMax.setRange(slider_min, slider_max)


    @pyqtSlot(int)
    def negativeTargetRangeLimitSlot(self, i:int) -> None:
        self.aw.pidcontrol.negativeTargetRangeLimit = bool(i)
        self.negativeTargetMin.setEnabled(self.aw.pidcontrol.negativeTargetRangeLimit)
        self.negativeTargetMax.setEnabled(self.aw.pidcontrol.negativeTargetRangeLimit)

    @pyqtSlot(int)
    def sliderMinValueChangedSlot(self, i:int) -> None:
        self.aw.pidcontrol.sliderMinValueChanged(i)

    @pyqtSlot(int)
    def sliderMaxValueChangedSlot(self, i:int) -> None:
        self.aw.pidcontrol.sliderMaxValueChanged(i)

    @pyqtSlot(bool)
    def importrampsoaks(self, _:bool = False) -> None:
        self.aw.fileImport(QApplication.translate('Message', 'Load Ramp/Soak Table'),self.importrampsoaksJSON)

    @pyqtSlot(bool)
    def setRS(self, _:bool = False) -> None:
        try:
            sender = self.sender()
            assert isinstance(sender, QPushButton)
            n = self.RSnButtons.index(sender)
            self.aw.pidcontrol.svLabel = self.getRSnSVLabel(n)
            self.aw.pidcontrol.svValues = self.getRSnSVvalues(n)
            self.aw.pidcontrol.svRamps = self.getRSnSVramps(n)
            self.aw.pidcontrol.svSoaks = self.getRSnSVsoaks(n)
            self.aw.pidcontrol.svActions = self.getRSnSVactions(n)
            self.aw.pidcontrol.svBeeps = self.getRSnSVbeeps(n)
            self.aw.pidcontrol.svDescriptions = self.getRSnSVdescriptions(n)
            self.setrampsoaks()
            self.aw.qmc.rsfile = ''
            self.rsfile.setText(self.aw.qmc.rsfile)
        except Exception as e: # pylint: disable=broad-exception-caught
            _log.exception(e)

    def getRSnSVLabel(self, n:int) -> str:
        return self.RSnTab_LabelWidgets[n].text()
    def getRSnSVvalues(self, n:int) -> list[float]:
        return [w.value() for w in self.RSnTab_SVWidgets[n]]
    def getRSnSVramps(self, n:int) -> list[int]:
        return [int(round(self.aw.QTime2time(w.time()))) for w in self.RSnTab_RampWidgets[n]]
    def getRSnSVsoaks(self, n:int) -> list[int]:
        return [int(round(self.aw.QTime2time(w.time()))) for w in self.RSnTab_SoakWidgets[n]]
    def getRSnSVactions(self, n:int) -> list[int]:
        return [int(w.currentIndex()) - 1 for w in self.RSnTab_ActionWidgets[n]]
    def getRSnSVbeeps(self, n:int) -> list[bool]:
        res:list[bool] = []
        for w in self.RSnTab_BeepWidgets[n]:
            b:bool = False
            l = w.layout()
            if l is not None:
                item = l.itemAt(1)
                if item is not None:
                    wid = item.widget()
                    if wid is not None:
                        b = cast(QCheckBox, wid).isChecked()
            res.append(b)
        return res
    def getRSnSVdescriptions(self, n:int) -> list[str]:
        return [w.text() for w in self.RSnTab_DescriptionWidgets[n]]

    def setRSnSVLabel(self, n:int) -> None:
        self.RSnTab_LabelWidgets[n].setText(self.aw.pidcontrol.RS_svLabels[n])
    def setRSnSVvalues(self, n:int) -> None:
        for i in range(self.aw.pidcontrol.svLen):
            self.RSnTab_SVWidgets[n][i].setValue(int(round(self.aw.pidcontrol.RS_svValues[n][i])))
    def setRSnSVramps(self, n:int) -> None:
        for i in range(self.aw.pidcontrol.svLen):
            self.RSnTab_RampWidgets[n][i].setTime(self.aw.time2QTime(self.aw.pidcontrol.RS_svRamps[n][i]))
    def setRSnSVsoaks(self, n:int) -> None:
        for i in range(self.aw.pidcontrol.svLen):
            self.RSnTab_SoakWidgets[n][i].setTime(self.aw.time2QTime(self.aw.pidcontrol.RS_svSoaks[n][i]))
    def setRSnSVactions(self, n:int) -> None:
        for i in range(self.aw.pidcontrol.svLen):
            self.RSnTab_ActionWidgets[n][i].setCurrentIndex(self.aw.pidcontrol.RS_svActions[n][i] + 1)
    def setRSnSVbeeps(self, n:int) -> None:
        for i in range(self.aw.pidcontrol.svLen):
            beep:QCheckBox|None = None
            l = self.RSnTab_BeepWidgets[n][i].layout()
            if l is not None:
                item = l.itemAt(1)
                if item is not None:
                    wid = item.widget()
                    if wid is not None:
                        beep = cast(QCheckBox, wid)
            if beep is not None:
                if self.aw.pidcontrol.RS_svBeeps[n][i]:
                    beep.setCheckState(Qt.CheckState.Checked)
                else:
                    beep.setCheckState(Qt.CheckState.Unchecked)
    def setRSnSVdescriptions(self, n:int) -> None:
        for i in range(self.aw.pidcontrol.svLen):
            self.RSnTab_DescriptionWidgets[n][i].setText(self.aw.pidcontrol.RS_svDescriptions[n][i])

    def importrampsoaksJSON(self, filename:str) -> None:
        try:
            self.aw.qmc.rampSoakSemaphore.acquire(1)
            from json import load as json_load
            with open(filename, encoding='utf-8') as infile:
                rampsoaks = json_load(infile)
            self.aw.pidcontrol.svLabel = rampsoaks.get('svLabel', '')
            self.aw.pidcontrol.svValues = rampsoaks['svValues']
            self.aw.pidcontrol.svRamps = rampsoaks['svRamps']
            self.aw.pidcontrol.svSoaks = rampsoaks['svSoaks']
            self.aw.pidcontrol.svActions = rampsoaks['svActions']
            self.aw.pidcontrol.svBeeps = rampsoaks['svBeeps']
            self.aw.pidcontrol.svDescriptions = rampsoaks['svDescriptions']
            self.aw.qmc.rsfile = filename
            self.rsfile.setText(self.aw.qmc.rsfile)
        except Exception as ex: # pylint: disable=broad-exception-caught
            _log.exception(ex)
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message','Exception:') + ' importrampsoaksJSON() {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
        finally:
            if self.aw.qmc.rampSoakSemaphore.available() < 1:
                self.aw.qmc.rampSoakSemaphore.release(1)
            self.setrampsoaks()

    @pyqtSlot(bool)
    def exportrampsoaks(self, _:bool = False) -> None:
        self.aw.fileExport(QApplication.translate('Message', 'Save Ramp/Soak Table'),'*.aprs',self.exportrampsoaksJSON)

    def exportrampsoaksJSON(self, filename:str) -> bool:
        try:
            self.saverampsoaks()
            rampsoaks:dict[str,str|list[float]|list[int]|list[bool]|list[str]] = {}
            rampsoaks['svLabel'] = self.aw.pidcontrol.svLabel
            rampsoaks['svValues'] = self.aw.pidcontrol.svValues
            rampsoaks['svRamps'] = self.aw.pidcontrol.svRamps
            rampsoaks['svSoaks'] = self.aw.pidcontrol.svSoaks
            rampsoaks['svActions'] = self.aw.pidcontrol.svActions
            rampsoaks['svBeeps'] = self.aw.pidcontrol.svBeeps
            rampsoaks['svDescriptions'] = self.aw.pidcontrol.svDescriptions
            rampsoaks['mode'] = self.aw.qmc.mode
            from json import dump as json_dump
            with open(filename, 'w', encoding='utf-8') as outfile:
                json_dump(rampsoaks, outfile, indent=None, separators=(',', ':'), ensure_ascii=False)
                outfile.write('\n')
            self.aw.qmc.rsfile = filename
            self.rsfile.setText(self.aw.qmc.rsfile)
            return True
        except Exception as ex: # pylint: disable=broad-except
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' exportrampsoaksJSON(): {0}').format(str(ex)),getattr(exc_tb, 'tb_lineno', '?'))
            return False

    def saverampsoaks(self) -> None:
        try:
            self.aw.qmc.rampSoakSemaphore.acquire(1)
            self.aw.pidcontrol.svLabel = self.labelEdit.text()
            for i in range(self.aw.pidcontrol.svLen):
                self.aw.pidcontrol.svValues[i] = self.SVWidgets[i].value()
                self.aw.pidcontrol.svRamps[i] = int(round(self.aw.QTime2time(self.RampWidgets[i].time())))
                self.aw.pidcontrol.svSoaks[i] = int(round(self.aw.QTime2time(self.SoakWidgets[i].time())))
                self.aw.pidcontrol.svActions[i] = int(self.ActionWidgets[i].currentIndex()) - 1
                layout = self.BeepWidgets[i].layout()
                if layout is not None:
                    layoutItem = layout.itemAt(1)
                    if layoutItem is not None:
                        beep = cast(QCheckBox, layoutItem.widget())
                        self.aw.pidcontrol.svBeeps[i] = bool(beep.isChecked())
                self.aw.pidcontrol.svDescriptions[i] = self.DescriptionWidgets[i].text()
        finally:
            if self.aw.qmc.rampSoakSemaphore.available() < 1:
                self.aw.qmc.rampSoakSemaphore.release(1)

    def setrampsoaks(self) -> None:
        try:
            self.aw.qmc.rampSoakSemaphore.acquire(1)
            self.labelEdit.setText(self.aw.pidcontrol.svLabel)
            for i in range(self.aw.pidcontrol.svLen):
                self.SVWidgets[i].setValue(int(round(self.aw.pidcontrol.svValues[i])))
                self.RampWidgets[i].setTime(self.aw.time2QTime(self.aw.pidcontrol.svRamps[i]))
                self.SoakWidgets[i].setTime(self.aw.time2QTime(self.aw.pidcontrol.svSoaks[i]))
                self.ActionWidgets[i].setCurrentIndex(self.aw.pidcontrol.svActions[i] + 1)
                layout = self.BeepWidgets[i].layout()
                if layout is not None:
                    layoutItem = layout.itemAt(1)
                    if layoutItem is not None:
                        beep = cast(QCheckBox, layoutItem.widget())
                        if self.aw.pidcontrol.svBeeps[i]:
                            beep.setCheckState(Qt.CheckState.Checked)
                        else:
                            beep.setCheckState(Qt.CheckState.Unchecked)
                self.DescriptionWidgets[i].setText(self.aw.pidcontrol.svDescriptions[i])
        finally:
            if self.aw.qmc.rampSoakSemaphore.available() < 1:
                self.aw.qmc.rampSoakSemaphore.release(1)

    def saveRSs(self) -> None:
        try:
            self.aw.qmc.rampSoakSemaphore.acquire(1)
            self.aw.pidcontrol.RS_svLabels = []
            self.aw.pidcontrol.RS_svValues = []
            self.aw.pidcontrol.RS_svRamps = []
            self.aw.pidcontrol.RS_svSoaks = []
            self.aw.pidcontrol.RS_svActions = []
            self.aw.pidcontrol.RS_svBeeps = []
            self.aw.pidcontrol.RS_svDescriptions = []
            for n in range(self.aw.pidcontrol.RSLen):
                self.aw.pidcontrol.RS_svLabels.append(self.getRSnSVLabel(n))
                self.aw.pidcontrol.RS_svValues.append(self.getRSnSVvalues(n))
                self.aw.pidcontrol.RS_svRamps.append(self.getRSnSVramps(n))
                self.aw.pidcontrol.RS_svSoaks.append(self.getRSnSVsoaks(n))
                self.aw.pidcontrol.RS_svActions.append(self.getRSnSVactions(n))
                self.aw.pidcontrol.RS_svBeeps.append(self.getRSnSVbeeps(n))
                self.aw.pidcontrol.RS_svDescriptions.append(self.getRSnSVdescriptions(n))
        finally:
            if self.aw.qmc.rampSoakSemaphore.available() < 1:
                self.aw.qmc.rampSoakSemaphore.release(1)

    def setRSs(self) -> None:
        for n in range(self.aw.pidcontrol.RSLen):
            self.setRSnSVLabel(n)
            self.setRSnSVvalues(n)
            self.setRSnSVramps(n)
            self.setRSnSVsoaks(n)
            self.setRSnSVactions(n)
            self.setRSnSVbeeps(n)
            self.setRSnSVdescriptions(n)

    @pyqtSlot(bool)
    def pidConf(self, _:bool = False) -> None:
        kp = self.pidKp.value() # 5.00
        ki = self.pidKi.value() # 0.15
        kd = self.pidKd.value() # 0.00
        source:int|None = None
        cycle:int|None = None
        pid_controller = self.aw.pidcontrol.externalPIDControl()
        if pid_controller in {0, 4}: # Internal PID and Kaleido
            pidSourceIdx = self.pidSource.currentIndex()
            if pidSourceIdx == 0:
                source = 2 # ET
            elif pidSourceIdx == 1:
                source = 1 # BT
            else:
                source = self.pidSource.currentIndex() + 1 # 3, 4, ... (extra device curves)
            if pid_controller == 4: # Kaleido
                cycle = self.pidCycle.value() # def 1000 in ms
            if pid_controller == 0:
                self.aw.pidcontrol.pidPositiveTarget = self.positiveControlCombo.currentIndex()
                self.aw.pidcontrol.pidNegativeTarget = self.negativeControlCombo.currentIndex()
                self.aw.pidcontrol.invertControl = self.invertControlFlag.isChecked()
                # we configure all parameters of the software pid from current pidcontrol settings
                self.aw.pidcontrol.confSoftwarePID()
            else:
                self.aw.pidcontrol.confPID(kp,ki,kd,source,cycle)

    @pyqtSlot(bool)
    def setSV(self, _:bool = False) -> None: # and DutySteps
        self.aw.pidcontrol.setSV(self.pidSV.value())
        if self.aw.pidcontrol.externalPIDControl() == 0: # only the internal PID allows for duty control
            self.aw.pidcontrol.setDutySteps(self.pidDutySteps.value())

    @override
    def close(self) -> bool:
        #
        self.aw.pidcontrol.pidOnCHARGE = self.startPIDonCHARGE.isChecked()
        self.aw.pidcontrol.pidOffDROP = self.stopPIDonDROP.isChecked()
#        self.aw.pidcontrol.RStimeAfterCHARGE = self.radioTimeAfterCHARGE.isChecked()
        self.aw.pidcontrol.loadpidfrombackground = self.loadPIDfromBackground.isChecked()
        self.aw.pidcontrol.createEvents = self.createEvents.isChecked()
        self.aw.pidcontrol.loadRampSoakFromProfile = self.loadRampSoakFromProfile.isChecked()
        self.aw.pidcontrol.loadRampSoakFromBackground = self.loadRampSoakFromBackground.isChecked()
        self.aw.pidcontrol.svSliderMin = max(0, min(999, self.pidSVSliderMin.value(), self.pidSVSliderMax.value()))
        self.aw.pidcontrol.svSliderMax = min(999, max(0, self.pidSVSliderMin.value(), self.pidSVSliderMax.value()))
        self.aw.pidcontrol.svValue = self.pidSV.value()
        self.aw.pidcontrol.svSlider = self.pidSVsliderFlag.isChecked()
        self.aw.pidcontrol.activateSVSlider(self.aw.pidcontrol.svSlider)
        self.aw.pidcontrol.svButtons = self.pidSVbuttonsFlag.isChecked()
        self.aw.pidcontrol.activateONOFFeasySV(self.aw.pidcontrol.svButtons)
        self.aw.pidcontrol.svMode = self.pidMode.currentIndex()
        #-
        if self.aw.pidcontrol.externalPIDControl() == 0:
            self.aw.pidcontrol.positiveTargetMin = min(self.positiveTargetMin.value(),self.positiveTargetMax.value())
            self.aw.pidcontrol.positiveTargetMax = max(self.positiveTargetMin.value(),self.positiveTargetMax.value())
            self.aw.pidcontrol.negativeTargetMin = min(self.negativeTargetMin.value(),self.negativeTargetMax.value())
            self.aw.pidcontrol.negativeTargetMax = max(self.negativeTargetMin.value(),self.negativeTargetMax.value())
            # only for internal PID there is a configuration derivative filter and configurable duty
            self.aw.pidcontrol.dutyMin = min(self.dutyMin.value(),self.dutyMax.value())
            self.aw.pidcontrol.dutyMax = max(self.dutyMin.value(),self.dutyMax.value())
            self.aw.pidcontrol.dutySteps = self.pidDutySteps.value()
            self.aw.pidcontrol.derivative_filter = int(self.derivativeFilterFlag.isChecked())
            self.aw.pidcontrol.duty_filter = int(self.dutyFilterFlag.isChecked())
            self.aw.pidcontrol.sv_filter = int(self.svFilterFlag.isChecked())
            self.aw.pidcontrol.pidDlimit = int(self.dLimitSpinBox.value())
            self.aw.pidcontrol.pidIlimitFactor = self.iLimitSpinBox.value()
            self.aw.pidcontrol.pidIRoCthreshold = int(self.SPthresholdSpinBox.value())
            self.aw.pidcontrol.pidIWP = self.IWPFlag.isChecked()
            self.aw.pidcontrol.pidIRoC = self.IRoCFlag.isChecked()
            #- Gain Scheduling
            self.aw.pidcontrol.pidGainScheduling = self.pidSchedulingFlag.isChecked()
            self.aw.pidcontrol.pidGainSchedulingSV = self.pidSchedulingSV.isChecked()
            self.aw.pidcontrol.pidGainSchedulingQuadratic = self.pidSchedulingQuadratic.isChecked()
            self.aw.pidcontrol.pidKp1 = self.pidKp1.value()
            self.aw.pidcontrol.pidKp2 = self.pidKp2.value()
            self.aw.pidcontrol.pidKi1 = self.pidKi1.value()
            self.aw.pidcontrol.pidKi2 = self.pidKi2.value()
            self.aw.pidcontrol.pidKd1 = self.pidKd1.value()
            self.aw.pidcontrol.pidKd2 = self.pidKd2.value()
            self.aw.pidcontrol.pidSchedule0 = self.pidSchedule0.value()
            self.aw.pidcontrol.pidSchedule1 = self.pidSchedule1.value()
            self.aw.pidcontrol.pidSchedule2 = self.pidSchedule2.value()

        self.aw.pidcontrol.svLookahead = self.pidSVLookahead.value()
        kp = self.pidKp.value() # 5.00
        ki = self.pidKi.value() # 0.15
        kd = self.pidKd.value() # 0.00
        source:int|None = None
        cycle:int|None = None
        pid_controller = self.aw.pidcontrol.externalPIDControl()
        if pid_controller in {0, 4}: # Internal PID and Kaleido
            pidSourceIdx = self.pidSource.currentIndex()
            if pidSourceIdx == 0:
                source = 2 # ET
            elif pidSourceIdx == 1:
                source = 1 # BT
            else:
                source = pidSourceIdx + 1 # 3, 4, ... (extra device curves)
            if pid_controller == 4: # Kaleido
                cycle = self.pidCycle.value() # def 1000 in ms
            if pid_controller == 0: # internal software PID
                self.aw.pidcontrol.pidPositiveTarget = self.positiveControlCombo.currentIndex()
                self.aw.pidcontrol.pidNegativeTarget = self.negativeControlCombo.currentIndex()
                self.aw.pidcontrol.invertControl = self.invertControlFlag.isChecked()
                # we configure all parameters of the software pid from current pidcontrol settings
                self.aw.pidcontrol.confSoftwarePID()
        self.aw.pidcontrol.setPID(kp,ki,kd,source,cycle)
        #
        self.aw.PID_DlgControl_activeTab = self.tabWidget.currentIndex()
        #
        self.saverampsoaks()
        self.saveRSs()
        #
        self.closeEvent(None)
        return True

    @pyqtSlot('QCloseEvent')
    @override
    def closeEvent(self, a0:'QCloseEvent|None' = None) -> None:
        del a0
        #save window position (only; not size!)
        settings = QSettings()
        settings.setValue('PIDPosition',self.frameGeometry().topLeft())
        self.aw.PID_DlgControl_activeTab = self.tabWidget.currentIndex()
        self.accept()
