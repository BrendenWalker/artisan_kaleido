#
# ABOUT
# Artisan PID Controller (software, Kaleido, Hybrid)

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

import numpy
import logging
from typing import Final, TYPE_CHECKING

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow # pylint: disable=unused-import

from artisanlib.util import fromCtoFstrict, fromFtoCstrict, stringfromseconds

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QApplication

_log: Final[logging.Logger] = logging.getLogger(__name__)

###################################################################################
##########################  PID CONTROL CLASS DEFINITION  #########################
###################################################################################

class PIDcontrol:
    __slots__ = [ 'aw', 'pidActive', 'sv', 'pidOnCHARGE', 'pidOffDROP', 'RStimeAfterCHARGE', 'loadpidfrombackground', 'createEvents', 'loadRampSoakFromProfile', 'loadRampSoakFromBackground', 'svLen', 'svLabel',
            'svValues', 'svSync', 'svRamps', 'svSoaks', 'svActions', 'svBeeps', 'svDescriptions','svTriggeredAlarms',
            'RSLen', 'RS_svLabels', 'RS_svValues', 'RS_svRamps', 'RS_svSoaks',
            'RS_svActions', 'RS_svBeeps', 'RS_svDescriptions', 'svSlider', 'svButtons', 'svMode', 'svLookahead', 'dutySteps', 'svSliderMin', 'svSliderMax', 'svValue',
            'dutyMin', 'dutyMax', 'pidKp', 'pidKi', 'pidKd', 'pidPsetpointWeight', 'pidDsetpointWeight', 'pidSource', 'pidCycle', 'pidPositiveTarget', 'pidNegativeTarget', 'invertControl',
            'pidPsetpointWeightMax', 'pidDsetpointWeightMax', 'sv_filter',
            'sv_smoothing_factor_default', 'sv_smoothing_factor', 'sv_decay_weights', 'previous_svs', 'time_pidON', 'source_reading_pidON', 'current_ramp_segment',  'current_soak_segment', 'ramp_soak_engaged',
            'RS_total_time', 'slider_force_move', 'positiveTargetRangeLimit', 'positiveTargetMin', 'positiveTargetMax', 'negativeTargetRangeLimit',
            'negativeTargetMin', 'negativeTargetMax', 'derivative_filter', 'duty_filter', 'pidDlimit', 'pidIlimitFactor', 'pidIWP', 'pidIRoC', 'pidIRoCthreshold',
            'pidKp1', 'pidKd1', 'pidKi1', 'pidKp2', 'pidKi2', 'pidKd2', 'pidGainScheduling', 'pidGainSchedulingSV', 'pidGainSchedulingQuadratic',
            'pidSchedule0', 'pidSchedule1', 'pidSchedule2' ]

    def __init__(self, aw:'ApplicationWindow') -> None:
        self.aw:ApplicationWindow = aw
        self.pidActive:bool = False
        self.sv:float|None = None # the last sv send to the Arduino
        #
        self.pidOnCHARGE:bool = False
        self.pidOffDROP:bool = False
        self.RStimeAfterCHARGE = False # if True RS time is taken from CHARGE if FALSE it is the time after the PID was last started
        self.loadpidfrombackground = False # if True, p-i-d parameters pidKp, pidKi, pidKd, pidSource, and svLookahead are set from the background profile
        self.createEvents:bool = False
        self.loadRampSoakFromProfile:bool = False
        self.loadRampSoakFromBackground:bool = False
        self.svLen:Final[int] = 8 # should stay at 8 for compatibility reasons!
        self.svLabel:str = ''
        self.svValues: list[float]     = [0.0]*self.svLen      # sv temp as int per 8 channels
        self.svRamps: list[int]        = [0]*self.svLen      # seconds as int per 8 channels
        self.svSoaks: list[int]        = [0]*self.svLen      # seconds as int per 8 channels
        self.svActions: list[int]      = [-1]*self.svLen     # alarm action as int per 8 channels
        self.svBeeps: list[bool]       = [False]*self.svLen  # alarm beep as bool per 8 channels
        self.svDescriptions: list[str] = ['']*self.svLen     # alarm descriptions as string per 8 channels
        #
        self.svTriggeredAlarms = [False]*self.svLen # set to true once the corresponding alarm was triggered
        # extra RS sets:
        self.RSLen:Final[int] = 3 # can be changed to have less or more RSn sets
        self.RS_svLabels: list[str]       = ['']*self.RSLen                  # label of the RS set
        self.RS_svValues: list[list[float]] = [[0.0]*self.svLen]*self.RSLen      # sv temp as int per 8 channels
        self.RS_svRamps: list[list[int]]  = [[0]*self.svLen]*self.RSLen      # seconds as int per 8 channels
        self.RS_svSoaks: list[list[int]]  = [[0]*self.svLen]*self.RSLen      # seconds as int per 8 channels
        self.RS_svActions: list[list[int]]= [[-1]*self.svLen]*self.RSLen     # alarm action as int per 8 channels
        self.RS_svBeeps: list[list[bool]] = [[False]*self.svLen]*self.RSLen  # alarm beep as bool per 8 channels
        self.RS_svDescriptions: list[list[str]] = [['']*self.svLen]*self.RSLen     # alarm descriptions as string per 8 channels
        #
        self.svSlider:bool = True # Kaleido preheat SV (Machine PID TS); PID dialog can still hide it
        self.svButtons:bool = False
        self.svMode:int = 0 # 0: manual, 1: Ramp/Soak, 2: Follow (background profile)
        self.svLookahead:int = 0
        self.svSliderMin:int = 0
        self.svSliderMax:int = (230 if self.aw.qmc.mode == 'C' else 446) # 446F / 230C
        self.svValue:float = (180 if self.aw.qmc.mode == 'C' else 356) # 356F / 180C # the value in the setSV textinput box of the PID dialog
        self.svSync:int = 0 # 0: off, 1:BT, 2:ET, >2: extra devices index of temperature curve to be used to move SV slider in manual mode
        self.dutySteps:int = 1
        self.dutyMin:int = -100
        self.dutyMax:int = 100
        self.positiveTargetRangeLimit:bool = False # if True the duty is mapped to the target slider subrange [positiveTargetMin, positiveTargetMax]
        self.positiveTargetMin:int = 0
        self.positiveTargetMax:int = 100
        self.negativeTargetRangeLimit:bool = False # if True the duty is mapped to the target slider subrange [negativeTargetMin, negativeTargetMax]
        self.negativeTargetMin:int = 0
        self.negativeTargetMax:int = 100
        # derivative filter
        self.derivative_filter:int = 0 # 0: off, 1: on
        # duty filter
        self.duty_filter:int = 0 # 0: off, 1: on
        # sv smoothing
        self.sv_filter:int = 0 # 0: off, 1: on
        self.sv_smoothing_factor_default: Final[int] = 5 # if sv filter is active this indicates the number of values decay smoothing is applied to
        self.sv_smoothing_factor:int = 0 # off if 0
        self.sv_decay_weights:list[float]|None = None
        self.previous_svs:list[float] = []
        # p-i-d parameterss
        self.pidKp:float = (15.0 if self.aw.qmc.mode == 'C' else 8.3334) # 15.0 in C
        self.pidKi:float = (0.01 if self.aw.qmc.mode == 'C' else 0.00556) # 0.01 in C
        self.pidKd:float = (20.0 if self.aw.qmc.mode == 'C' else 11.1111) # 20.0 in C
        #-
        self.pidKp1:float = (15.0 if self.aw.qmc.mode == 'C' else 8.3334) # 15.0 in C
        self.pidKi1:float = (0.01 if self.aw.qmc.mode == 'C' else 0.00556) # 0.01 in C
        self.pidKd1:float = (20.0 if self.aw.qmc.mode == 'C' else 11.1111) # 20.0 in C
        #-
        self.pidKp2:float = (15.0 if self.aw.qmc.mode == 'C' else 8.3334) # 15.0 in C
        self.pidKi2:float = (0.01 if self.aw.qmc.mode == 'C' else 0.00556) # 0.01 in C
        self.pidKd2:float = (20.0 if self.aw.qmc.mode == 'C' else 11.1111) # 20.0 in C
        #-
        self.pidSchedule0:float = 0
        self.pidSchedule1:float = 0
        self.pidSchedule2:float = 0
        #-
        self.pidGainScheduling:bool = False
        self.pidGainSchedulingSV:bool = True # variable observed by Gain Scheduling defaults to SV; setting this to False observes PV
        self.pidGainSchedulingQuadratic:bool = False # Gain Scheduling defaults to linear mapping between p-i-d set 0 and 1; if True p-i-d set 2 is involved too with a quadratic mapping
        #-
        self.pidPsetpointWeight:float = 1. # [0, pidPsetpointWeightMax] defaults to 1: PoE (0: PoM)
        self.pidPsetpointWeightMax:Final[float] = 2.
        self.pidDsetpointWeight:float = 1. # [0, pidDsetpointWeightMax] defaults to 1: DoE (0: DoM)
        self.pidDsetpointWeightMax:Final[float] = 2.
        # Proposional on Measurement (PoM) mode see: http://brettbeauregard.com/blog/2017/06/introducing-proportional-on-measurement/
        # => PoM removed in v3.1.2
        ## further pid configurations (only supported by the software pid currently)
#        self.pidDoE:bool = False          # classical Derivative on Error (DoE) if True, otherwise Derivative on Measurement (DoM) to reduce derivative kick
        self.pidDlimit:float = 500.0      # derivative limit [0-999] (used for both, DoM and DoE)
        self.pidIlimitFactor:float = 1    # integral limit factor [0-1]
        self.pidIWP:bool = True           # Advanced Integral Windup Prevention
        self.pidIRoC:bool = False         # Reset integral on large setpoint changes
        self.pidIRoCthreshold:float = 30  # SP threshold beyond which the integral will be reset if pidRIoC is set
        # pidSource
        #   1 is interpreted as BT and 2 as ET, 3 as 0xT1, 4 as 0xT2, 5 as 1xT1, ...
        self.pidSource:int = 1
        self.pidCycle:int = 1000
        # the positive target should increase with positive PID duty
        self.pidPositiveTarget:int = 0 # one of [0,1,..,4] with 0: None, 1,..,4: for slider event 1-4
        # the negative target should decrease with negative PID duty
        self.pidNegativeTarget:int = 0 # one of [0,1,..,4] with 0: None, 1,..,4: for slider event 1-4
        # if invertControl is True, a PID duty of 100% delivers 0% positive duty and a 0% PID duty delivers 100% positive duty
        self.invertControl:bool = False
        # time @ PID ON
        self.time_pidON:float = 0 # in monitoring mode, ramp-soak times are interpreted w.r.t. the time after the PID was turned on and not the time after CHARGE as during recording
        self.source_reading_pidON:float = 0 # the reading of the selected source on PID ON (to be used as start point for the first RAMP/SOAK pattern)
        self.current_ramp_segment:int = 0 # the RS segment currently active. Note that this is 1 based, 0 indicates that no segment has started yet
        self.current_soak_segment:int = 0 # the RS segment currently active. Note that this is 1 based, 0 indicates that no segment has started yet
        self.ramp_soak_engaged:int = 1 # set to 0, disengaged, after the RS pattern was processed fully
        self.RS_total_time:float = 0 # holds the total time of the current Ramp/Soak pattern

        self.slider_force_move:bool = True # if True move the slider independent of the slider position to fire slider action!

    @staticmethod
    def RStotalTime(ramps:list[int], soaks:list[int]) -> int:
        return sum(ramps) + sum(soaks)

    # the returned value indicates the type of PID control:
    #  0: internal software PID
    #  4: Kaleido
    #  5: Kaleido Hybrid
    def externalPIDControl(self) -> int:
        if (self.aw.qmc.device == 138 and self.aw.kaleidoHybridControl):
            return 5
        if (self.aw.qmc.device == 138 and self.aw.kaleidoPID):
            return 4
        return 0

    # Hybrid mode uses Machine PID (AH/TS) for warmup until CHARGE is marked
    def kaleidoInWarmupPhase(self) -> bool:
        return self.externalPIDControl() == 5 and self.aw.qmc.timeindex[0] == -1

    # After CHARGE with a background loaded: leave Machine PID and activate Hybrid
    def kaleidoEnterHybridOnCharge(self) -> None:
        if self.aw.kaleido is None or not self.aw.qmc.Controlbuttonflag:
            return
        self.aw.kaleido.pidOFF()
        # Hybrid will command HP; ensure heaters are enabled regardless of Start Heating UI state
        self.aw.kaleido.ensureHeating(True)
        self.aw.qmc.pid.off()
        self.aw.hybrid_controller.activate()
        self.pidActive = True
        self.aw.buttonCONTROL.setStyleSheet(self.aw.pushbuttonstyles['PIDactive'])
        backend = getattr(self.aw.hybrid_controller, 'backend_name', self.aw.hybridControlBackend)
        self.aw.sendmessage(
            QApplication.translate('Message','Hybrid Controller ON ({})').format(backend))

    # v is from [-min,max]
    def setEnergy(self, v:float) -> None:
        try:
            # if invertControl we invert min/max to max/min
            vx = float(numpy.interp(v,[self.dutyMin,self.dutyMax],[self.dutyMax,self.dutyMin]) if self.invertControl else v)
            if self.pidPositiveTarget:
                slidernr = self.pidPositiveTarget - 1
                # we need to map the duty [0%,100%] to the [slidermin,slidermax] range
                # NOTE: numpy.interp(v, [min_in,max_in], [min_out, max_out]) never results in values outside of [min_out, max_out]
                slider_min = self.aw.eventslidermin[slidernr]
                slider_max = self.aw.eventslidermax[slidernr]
                # assumption: if self.positiveTargetRangeLimit then slider_min < self.positiveTargetMin < self.positiveTargetMax < slider_max
                heat_min = (max(self.positiveTargetMin, slider_min) if self.positiveTargetRangeLimit else slider_min)
                heat_max = (min(self.positiveTargetMax, slider_max) if self.positiveTargetRangeLimit else slider_max)
                raw_heat:float = numpy.interp(vx,[0,100],[heat_min,heat_max])
                heat = int(round(float(raw_heat)))
                heat = self.aw.applySliderStepSize(slidernr, heat) # quantify by slider step size
                self.aw.addRawEventSignal.emit(heat,raw_heat,slidernr,self.createEvents,True,self.slider_force_move)
                self.slider_force_move = False
            if self.pidNegativeTarget:
                slidernr = self.pidNegativeTarget - 1
                # we need to map the duty [0%,-100%] to the [slidermin,slidermax] range
                # NOTE: numpy.interp(v, [min_in,max_in], [min_out, max_out]) never results in values outside of [min_out, max_out]
                slider_min = self.aw.eventslidermin[slidernr]
                slider_max = self.aw.eventslidermax[slidernr]
                # assumption: if self.positiveTargetRangeLimit then slider_min < self.positiveTargetMin < self.positiveTargetMax < slider_max
                cool_min = (max(self.negativeTargetMin, slider_min) if self.negativeTargetRangeLimit else slider_min)
                cool_max = (min(self.negativeTargetMax, slider_max) if self.negativeTargetRangeLimit else slider_max)
                raw_cool:float = numpy.interp(vx,[-100,0],[cool_max,cool_min])
                cool = int(round(float(raw_cool)))
                cool = self.aw.applySliderStepSize(slidernr, cool) # quantify by slider step size
                self.aw.addRawEventSignal.emit(cool,raw_cool,slidernr,self.createEvents,True,self.slider_force_move)
                self.slider_force_move = False
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)

    def conv2celsius(self) -> None:
        try:
            self.aw.qmc.rampSoakSemaphore.acquire(1)
            self.svValue = (0 if self.svValue == 0 else max(0, int(round(fromFtoCstrict(self.svValue)))))
            self.svSliderMin = (0 if self.svSliderMin == 0 else max(0, min(999, int(round(fromFtoCstrict(self.svSliderMin))))))
            self.svSliderMax = (0 if self.svSliderMax == 0 else max(0, min(999, int(round(fromFtoCstrict(self.svSliderMax))))))
            # establish ne limits on sliders
            self.aw.sliderSV.setMinimum(self.svSliderMin)
            self.aw.sliderSV.setMaximum(self.svSliderMax)
            self.aw.moveSVslider(self.svValue,setValue=False)
            self.pidKp = self.pidKp * (9/5.)
            self.pidKi = self.pidKi * (9/5.)
            self.pidKd = self.pidKd * (9/5.)
            #
            self.pidKp1 = self.pidKp1 * (9/5.)
            self.pidKi1 = self.pidKi1 * (9/5.)
            self.pidKd1 = self.pidKd1 * (9/5.)
            #
            self.pidKp2 = self.pidKp2 * (9/5.)
            self.pidKi2 = self.pidKi2 * (9/5.)
            self.pidKd2 = self.pidKd2 * (9/5.)
            #
            self.pidSchedule0 = max(0, min(999, int(round(fromFtoCstrict(self.pidSchedule0)))))
            self.pidSchedule1 = max(0, min(999, int(round(fromFtoCstrict(self.pidSchedule1)))))
            self.pidSchedule2 = max(0, min(999, int(round(fromFtoCstrict(self.pidSchedule2)))))
            #
            for i in range(len(self.svValues)): # pylint: disable=consider-using-enumerate
                if self.svValues[i] != 0:
                    self.svValues[i] = fromFtoCstrict(self.svValues[i])
            for n in range(len(self.RS_svValues)): # pylint: disable=consider-using-enumerate
                for j in range(len(self.RS_svValues[n])):
                    if self.RS_svValues[n][j] != 0:
                        self.RS_svValues[n][j] = fromFtoCstrict(self.RS_svValues[n][j])
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
        finally:
            if self.aw.qmc.rampSoakSemaphore.available() < 1:
                self.aw.qmc.rampSoakSemaphore.release(1)

    def conv2fahrenheit(self) -> None:
        try:
            self.aw.qmc.rampSoakSemaphore.acquire(1)
            self.svValue = (0 if self.svValue == 0 else max(0.0, fromCtoFstrict(self.svValue)))
            self.svSliderMin = (0 if self.svSliderMin == 0 else max(0, min(999, int(round(fromCtoFstrict(self.svSliderMin))))))
            self.svSliderMax = (0 if self.svSliderMax == 0 else max(0, min(999, int(round(fromCtoFstrict(self.svSliderMax))))))
            # establish ne limits on sliders
            self.aw.sliderSV.setMinimum(int(round(self.svSliderMin)))
            self.aw.sliderSV.setMaximum(int(round(self.svSliderMax)))
            self.aw.moveSVslider(self.svValue,setValue=False)
            self.pidKp = self.pidKp / (9/5.)
            self.pidKi = self.pidKi / (9/5.)
            self.pidKd = self.pidKd / (9/5.)
            #
            self.pidKp1 = self.pidKp1 / (9/5.)
            self.pidKi1 = self.pidKi1 / (9/5.)
            self.pidKd1 = self.pidKd1 / (9/5.)
            #
            self.pidKp2 = self.pidKp2 / (9/5.)
            self.pidKi2 = self.pidKi2 / (9/5.)
            self.pidKd2 = self.pidKd2 / (9/5.)
            #
            self.pidSchedule0 = max(0, min(999, int(round(fromCtoFstrict(self.pidSchedule0)))))
            self.pidSchedule1 = max(0, min(999, int(round(fromCtoFstrict(self.pidSchedule1)))))
            self.pidSchedule2 = max(0, min(999, int(round(fromCtoFstrict(self.pidSchedule2)))))
            #
            for i in range(len(self.svValues)): # pylint: disable=consider-using-enumerate
                if self.svValues[i] != 0:
                    self.svValues[i] = fromCtoFstrict(self.svValues[i])
            for n in range(len(self.RS_svValues)): # pylint: disable=consider-using-enumerate
                for j in range(len(self.RS_svValues[n])): # pylint: disable=consider-using-enumerate
                    if self.RS_svValues[n][j] != 0:
                        self.RS_svValues[n][j] = fromCtoFstrict(self.RS_svValues[n][j])
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
        finally:
            if self.aw.qmc.rampSoakSemaphore.available() < 1:
                self.aw.qmc.rampSoakSemaphore.release(1)

    def togglePID(self) -> None:
        if self.pidActive:
            self.pidOff()
        else:
            self.pidOn()

    # initializes the PID mode on PID ON and switch of mode
    def pidModeInit(self) -> None:
        if self.aw.qmc.flagon:
            self.current_ramp_segment = 0
            self.current_soak_segment = 0
            self.ramp_soak_engaged = 1
            self.RS_total_time = self.RStotalTime(self.svRamps,self.svSoaks)
            self.svTriggeredAlarms = [False]*self.svLen

            if self.aw.qmc.flagstart:
                self.time_pidON = (self.aw.qmc.timex[-1] if len(self.aw.qmc.timex)>0 else 0)
            elif len(self.aw.qmc.on_timex)<1:
                self.time_pidON = 0
            else:
                self.time_pidON = (self.aw.qmc.on_timex[-1] if len(self.aw.qmc.on_timex)>0 else 0)
                if self.svMode == 1:
                    # turn the timer LCD color blue if in RS mode and not recording
                    self.aw.setTimerColor('rstimer')

            # remember current pidSource reading
            self.source_reading_pidON = 0
            if self.pidSource == 1: # we observe the BT
                self.source_reading_pidON = (self.aw.qmc.temp2[-1] if len(self.aw.qmc.temp2)>0 else 0)
            elif self.pidSource == 2: # we observe the ET
                self.source_reading_pidON = (self.aw.qmc.temp1[-1] if len(self.aw.qmc.temp1)>0 else 0)
            elif self.pidSource>2: # we observe an extra curve
                n = self.pidSource-3
                c = n // 2
                if n % 2 == 0:
                    tempX = self.aw.qmc.extratemp1 if self.aw.qmc.flagstart else self.aw.qmc.on_extratemp1
                else:
                    tempX = self.aw.qmc.extratemp2 if self.aw.qmc.flagstart else self.aw.qmc.on_extratemp2
                if len(tempX)>c:
                    self.source_reading_pidON = (tempX[c][-1] if len(tempX[c])>0 else 0)


    # the internal software PID should be configured on ON, but not be activated yet to warm it up
    def confSoftwarePID(self) -> None:
        # software PID
        self.aw.qmc.pid.setSamplingRate(self.aw.qmc.delay/1000)
        self.aw.qmc.pid.setPID(self.pidKp,self.pidKi,self.pidKd)
        self.aw.qmc.pid.setWeights(self.pidPsetpointWeight,self.pidDsetpointWeight)
        self.aw.qmc.pid.setLimits((-100 if self.pidNegativeTarget else 0),(100 if self.pidPositiveTarget else 0))
        self.aw.qmc.pid.setDutySteps(self.dutySteps)
        self.aw.qmc.pid.setDutyMin(self.dutyMin)
        self.aw.qmc.pid.setDutyMax(self.dutyMax)
        self.aw.qmc.pid.setControl(self.setEnergy)
        self.sv_smoothing_factor = (self.sv_smoothing_factor_default if self.sv_filter else 0)
        self.aw.qmc.pid.setOutputFilterLevel(self.duty_filter, reset=not self.pidActive)
        self.aw.qmc.pid.setDerivativeFilterLevel(self.derivative_filter, reset=not self.pidActive)
        self.aw.qmc.pid.setDerivativeLimit(self.pidDlimit)
        self.aw.qmc.pid.setIntegralWindupPrevention(self.pidIWP)
        self.aw.qmc.pid.setIntegralResetOnSP(self.pidIRoC)
        self.aw.qmc.pid.setSetpointChangeThreshold(self.pidIRoCthreshold)
        self.aw.qmc.pid.setIntegralLimitFactor(self.pidIlimitFactor)
        self.aw.qmc.pid.setGainScheduleState(self.pidGainScheduling)
        self.aw.qmc.pid.setGainScheduleOnSV(self.pidGainSchedulingSV)
        self.aw.qmc.pid.setGainSCheduleQuadratic(self.pidGainSchedulingQuadratic)
        self.aw.qmc.pid.setGainSchedule(self.pidKp1,self.pidKi1,self.pidKd1,self.pidKp2,self.pidKi2,self.pidKd2,
            self.pidSchedule0,self.pidSchedule1,self.pidSchedule2)


    # if send_command is False, the pidOn command is not forwarded to the external PID (Kaleido, ..)
    def pidOn(self, send_command:bool = True) -> None:
        if not self.pidActive:
            self.aw.sendmessage(QApplication.translate('StatusBar','PID ON'))
        self.pidModeInit()

        self.slider_force_move = True
        if self.aw.qmc.Controlbuttonflag and self.externalPIDControl() == 4 and self.aw.kaleido is not None:
            # Kaleido PID
            if send_command:
                self.aw.kaleido.pidON()
            self.pidActive = True
            self.aw.qmc.pid.on()
            self.aw.buttonCONTROL.setStyleSheet(self.aw.pushbuttonstyles['PIDactive'])
        elif self.aw.qmc.Controlbuttonflag and self.externalPIDControl() == 5 and self.aw.kaleido is not None:
            # Kaleido Hybrid Controller: Machine PID warmup until CHARGE, then Hybrid
            if self.kaleidoInWarmupPhase():
                if send_command:
                    self.aw.hybrid_controller.reset()
                    self.aw.kaleido.pidON()
                self.pidActive = True
                self.aw.qmc.pid.on()
                self.aw.buttonCONTROL.setStyleSheet(self.aw.pushbuttonstyles['PIDactive'])
                self.aw.sendmessage(QApplication.translate('Message','Machine PID warmup ON'))
            else:
                if send_command:
                    self.aw.kaleido.pidOFF()
                    self.aw.qmc.pid.off()
                    self.aw.hybrid_controller.activate()
                self.pidActive = True
                self.aw.buttonCONTROL.setStyleSheet(self.aw.pushbuttonstyles['PIDactive'])
                backend = getattr(self.aw.hybrid_controller, 'backend_name', self.aw.hybridControlBackend)
                self.aw.sendmessage(
                    QApplication.translate('Message','Hybrid Controller ON ({})').format(backend))
        elif self.aw.qmc.Controlbuttonflag:
            # software PID
            if not self.pidActive: # only if not yet active!
                self.confSoftwarePID()
                self.pidActive = True
                self.aw.qmc.pid.on()
                self.aw.buttonCONTROL.setStyleSheet(self.aw.pushbuttonstyles['PIDactive'])
                self.aw.qmc.pid.setTarget(self.svValue,init=False)
        if self.sv is None and self.svMode == 0: # only in manual SV mode we initialize the SV on PID ON
            self.setSV(self.svValue)

    # if send_command is False, the pidOff command is not forwarded to the external PID (Kaleido, ..)
    def pidOff(self, send_command:bool = True) -> None:
        if self.pidActive:
            self.aw.sendmessage(QApplication.translate('Message','PID OFF'))
        self.aw.setTimerColor('timer')
        if self.aw.qmc.flagon and not self.aw.qmc.flagstart:
            self.aw.qmc.setLCDtime(0)
        if self.aw.qmc.Controlbuttonflag and self.externalPIDControl() == 4 and self.aw.kaleido is not None:
            # Kaleido PID
            if send_command:
                self.aw.kaleido.pidOFF()
            self.pidActive = False
            self.aw.qmc.pid.off()
            self.aw.buttonCONTROL.setStyleSheet(self.aw.pushbuttonstyles['PID'])
        elif self.aw.qmc.Controlbuttonflag and self.aw.kaleidoHybridControl and self.aw.kaleido is not None:
            # Kaleido Hybrid Controller (warmup uses Machine PID; post-CHARGE uses Hybrid)
            if send_command:
                self.aw.kaleido.pidOFF()
            self.aw.hybrid_controller.reset()
            self.pidActive = False
            self.aw.qmc.pid.off()
            self.aw.buttonCONTROL.setStyleSheet(self.aw.pushbuttonstyles['PID'])
        elif self.aw.qmc.Controlbuttonflag:
            # software PID
            self.aw.qmc.pid.setControl(lambda _: None)
            self.pidActive = False
            self.aw.qmc.pid.off()
            self.aw.buttonCONTROL.setStyleSheet(self.aw.pushbuttonstyles['PID'])

    @pyqtSlot(int)
    def sliderMinValueChanged(self, i:int) -> None:
        self.svSliderMin = i
        self.aw.sliderSV.setMinimum(self.svSliderMin)

    @pyqtSlot(int)
    def sliderMaxValueChanged(self, i:int) -> None:
        self.svSliderMax = i
        self.aw.sliderSV.setMaximum(self.svSliderMax)

    # returns SV (or None) wrt. to the ramp-soak table and the given time t
    # (used only internally)
    def svRampSoak(self, t:float) -> float|None:
        try:
            self.aw.qmc.rampSoakSemaphore.acquire(1)
            if self.ramp_soak_engaged == 0:
                return None
            if self.aw.qmc.flagon and not self.aw.qmc.flagstart:
                self.aw.qmc.setLCDtime(self.RS_total_time-t)
            segment_end_time = 0 # the (end) time of the segments
            prev_segment_end_time = 0 # the (end) time of the previous segment
            segment_start_sv = 0. # the (target) sv of the segment
            prev_segment_start_sv = self.source_reading_pidON # the (target) sv of the previous segment; initialized to the reading of the pid source on PID ON
            for i, v in enumerate(self.svValues):
                # Ramp
                if self.svRamps[i] != 0:
                    segment_end_time = segment_end_time + self.svRamps[i]
                    segment_start_sv = v
                    if segment_end_time > t:
                        # t is within the current segment
                        k = float(segment_start_sv - prev_segment_start_sv) / float(segment_end_time - prev_segment_end_time)
                        if self.current_ramp_segment != i+1:
                            self.aw.sendmessage(QApplication.translate('Message',f'Ramp {i+1}: in {stringfromseconds(self.svRamps[i])} to SV {int(round(v))}'))
                            self.current_ramp_segment = i+1
                        return prev_segment_start_sv + k*(t - prev_segment_end_time)
                prev_segment_end_time = segment_end_time
                prev_segment_start_sv = segment_start_sv
                # Soak
                if self.svSoaks[i] != 0:
                    segment_end_time = segment_end_time + self.svSoaks[i]
                    segment_start_sv = v
                    if segment_end_time > t:
                        prev_segment_start_sv = segment_start_sv # ensure that the segment sv is set even then the segments ramp is 00:00
                        # t is within the current segment
                        if self.current_soak_segment != i+1:
                            self.current_soak_segment = i+1
                            self.aw.sendmessage(QApplication.translate('Message',f'Soak {i+1}: for {stringfromseconds(self.svSoaks[i])} at SV {int(round(v))}'))
                        return prev_segment_start_sv
                prev_segment_end_time = segment_end_time
                prev_segment_start_sv = segment_start_sv
                if (self.current_ramp_segment > i or self.current_soak_segment > 1) and not self.svTriggeredAlarms[i]:
                    self.svTriggeredAlarms[i] = True
                    if self.svActions[i] > -1:
                        self.aw.qmc.processAlarmSignal.emit(0,self.svBeeps[i],self.svActions[i],self.svDescriptions[i])
            self.aw.sendmessage(QApplication.translate('Message','Ramp/Soak pattern finished'))
            self.aw.qmc.setLCDtime(0)
            self.ramp_soak_engaged = 0 # stop the ramp/soak process
            return None
        finally:
            if self.aw.qmc.rampSoakSemaphore.available() < 1:
                self.aw.qmc.rampSoakSemaphore.release(1)

    def smooth_sv(self, sv:float) -> float:
        if self.sv_smoothing_factor:
            # create or update smoothing decay weights
            if self.sv_decay_weights is None or len(self.sv_decay_weights) != self.sv_smoothing_factor: # recompute only on changes
                self.sv_decay_weights = [float(w) for w in numpy.arange(1,self.sv_smoothing_factor+1)]
            # add new value
            self.previous_svs.append(sv)
            # throw away superfluous values
            self.previous_svs = self.previous_svs[-self.sv_smoothing_factor:]
            # compute smoothed output
            if len(self.previous_svs) >= self.sv_smoothing_factor:
                return float(numpy.average(self.previous_svs,weights=self.sv_decay_weights))
        return sv # no smoothing yet

    # returns None if in manual mode or no other sv (via ramp/soak or follow mode) defined
    def calcSV(self, tx:float) -> float|None:
        # tx is the timestamp recorded, NOT the time displayed to the user after CHARGE
        if self.svMode == 1:
            # Ramp/Soak mode
            # actual time (after CHARGE) on recording (if CHARGE and RStimeAfterCHARGE) and time after PID ON (on monitoring or if RStimeAfterCHARGE):
            time = tx
            if not self.aw.qmc.flagstart or not self.RStimeAfterCHARGE:
                time = time - self.time_pidON
            elif self.aw.qmc.timeindex[0] > -1:
                # after CHARGE
                time = time - self.aw.qmc.timex[self.aw.qmc.timeindex[0]]
            return self.svRampSoak(time)
        if self.svMode == 2 and self.aw.qmc.background:
            # Follow Background mode
            followCurveNr = self.pidSource
            # followCurveNr indicates which curve the PID should follow (take the SV from)
            #  1: BT, 2: ET, 3: as 0xT1, 4: as 0xT2, 5: as 1xT1, ...

            if self.aw.qmc.timeindex[6] > 0: # after DROP, the SV configured in the dialog is returned (min/maxed)
                return max(float(self.svSliderMin), min(float(self.svSliderMax), self.svValue))
            if self.aw.qmc.timeindex[0] < 0: # before CHARGE, the CHARGE temp of the background profile is returned
                if self.aw.qmc.timeindexB[0] < 0:
                    # no CHARGE in background, return manual SV
                    return max(float(self.svSliderMin),(min(float(self.svSliderMax),self.svValue)))
                # if background contains a CHARGE event
                if followCurveNr == 1: # we observe the BT
                    res = self.aw.qmc.backgroundBTat(self.aw.qmc.timeB[self.aw.qmc.timeindexB[0]]) # approximated background
                elif followCurveNr == 2: # we observe the ET
                    res = self.aw.qmc.backgroundETat(self.aw.qmc.timeB[self.aw.qmc.timeindexB[0]]) # approximated background
                elif followCurveNr>2: # we observe an extra curve
                    res = self.aw.qmc.backgroundXTat(followCurveNr-3, self.aw.qmc.timeB[self.aw.qmc.timeindexB[0]])
                else:
                    return None
                if res == -1:
                    return None # no background value for that time point
                return self.smooth_sv(res)
            if ((not self.aw.qmc.timeB or tx+self.svLookahead > self.aw.qmc.timeB[-1]) or (self.aw.qmc.timeindexB[6] > 0 and tx+self.svLookahead > self.aw.qmc.timeB[self.aw.qmc.timeindexB[6]])):
                # if tx+self.svLookahead > last background data or background has a DROP and tx+self.svLookahead index is beyond that DROP index
                return None # "deactivate" background follow mode
            if followCurveNr == 1: # we observe the BT
                res = self.aw.qmc.backgroundSmoothedBTat(tx + self.svLookahead) # smoothed and approximated background
            elif followCurveNr == 2: # we observe the ET
                res = self.aw.qmc.backgroundSmoothedETat(tx + self.svLookahead) # smoothed and approximated background
            elif followCurveNr>2: # we observe an extra curve
                res = self.aw.qmc.backgroundXTat(followCurveNr-3, tx + self.svLookahead, smoothed=True)
            else:
                return None
            if res == -1:
                return None
            return self.smooth_sv(res)
        # return None in manual mode
        return None

    def setDutySteps(self, dutySteps:int) -> None:
        if self.aw.qmc.Controlbuttonflag and not self.externalPIDControl():
            self.aw.qmc.pid.setDutySteps(dutySteps)


    def setSV(self, sv:float, move:bool = True, init:bool = False) -> None:
        if self.externalPIDControl() == 4 and self.aw.kaleido is not None:
            # Kaleido PID
            if move and self.svSlider:
                self.aw.moveSVslider(sv,setValue=True)
            self.aw.kaleido.setSV(sv)
            self.sv = sv # remember last sv
        elif self.externalPIDControl() == 5 and self.aw.kaleido is not None and self.kaleidoInWarmupPhase():
            # Hybrid warmup: SV drives Machine PID target (TS)
            if move and self.svSlider:
                self.aw.moveSVslider(sv,setValue=True)
            self.aw.kaleido.setSV(sv)
            self.sv = sv # remember last sv
            self.svValue = sv
        elif self.aw.qmc.Controlbuttonflag:
            # in all other cases if the "Control" flag is ticked: software PID
            if move and self.svSlider:
                self.aw.moveSVslider(sv,setValue=True)
            self.aw.qmc.pid.setTarget(sv,init=init)
            self.sv = sv # remember last sv
            self.svValue = sv

    # set RS patterns from one of the RS sets
    def setRSpattern(self, n:int) -> None:
        try:
            self.aw.qmc.rampSoakSemaphore.acquire(1)
            if n < self.RSLen:
                self.svLabel = self.RS_svLabels[n]
                self.svValues = self.RS_svValues[n]
                self.svRamps = self.RS_svRamps[n]
                self.svSoaks = self.RS_svSoaks[n]
                self.svActions = self.RS_svActions[n]
                self.svBeeps = self.RS_svBeeps[n]
                self.svDescriptions = self.RS_svDescriptions[n]
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
        finally:
            if self.aw.qmc.rampSoakSemaphore.available() < 1:
                self.aw.qmc.rampSoakSemaphore.release(1)

    # returns the first RS patterrn idx with label or None
    def findRSset(self, label:str) -> int|None:
        try:
            self.aw.qmc.rampSoakSemaphore.acquire(1)
            return self.RS_svLabels.index(label)
        except Exception as e: # pylint: disable=broad-except
            _log.exception(e)
            return None
        finally:
            if self.aw.qmc.rampSoakSemaphore.available() < 1:
                self.aw.qmc.rampSoakSemaphore.release(1)

    def adjustsv(self, diff:float) -> None:
        if self.sv is None or self.sv<0:
            self.sv = 0
        self.setSV(self.sv + diff,move=True)

    def activateSVSlider(self, flag:bool) -> None:
        if flag:
            self.aw.sliderGrpBoxSV.setVisible(True)
            self.aw.sliderSV.blockSignals(True)
            self.aw.sliderSV.setMinimum(self.svSliderMin)
            self.aw.sliderSV.setMaximum(self.svSliderMax)
            # we set the SV slider/lcd to the last SV issues or the minimum
            if self.sv is not None:
                sv = self.sv
            else:
                sv = min(float(self.svSliderMax), max(float(self.svSliderMin), self.svValue))
            sv = int(round(sv))
            self.aw.updateSVSliderLCD(sv)
            self.aw.sliderSV.setValue(sv)
            self.aw.sliderSV.blockSignals(False)
            self.svSlider = True
            self.aw.slidersAction.setEnabled(True)
        else:
            self.aw.sliderGrpBoxSV.setVisible(False)
            self.svSlider = False
            self.aw.slidersAction.setEnabled(any(self.aw.eventslidervisibilities))

    def showSVButtons(self) -> None:
        if self.aw.qmc.flagon and self.aw.qmc.Controlbuttonflag:
            self.aw.buttonSVp5.setVisible(True)
            self.aw.buttonSVp10.setVisible(True)
            self.aw.buttonSVp20.setVisible(True)
            self.aw.buttonSVm20.setVisible(True)
            self.aw.buttonSVm10.setVisible(True)
            self.aw.buttonSVm5.setVisible(True)

    def hideSVButtons(self) -> None:
        self.aw.buttonSVp5.setVisible(False)
        self.aw.buttonSVp10.setVisible(False)
        self.aw.buttonSVp20.setVisible(False)
        self.aw.buttonSVm20.setVisible(False)
        self.aw.buttonSVm10.setVisible(False)
        self.aw.buttonSVm5.setVisible(False)

    def activateONOFFeasySV(self, flag:bool) -> None:
        if flag:
            self.showSVButtons()
        else:
            self.hideSVButtons()

    # just store the p-i-d configuration
    def setPID(self, kp:float, ki:float, kd:float, source:int|None = None, cycle:int|None = None) -> None:
        self.pidKp = kp
        self.pidKi = ki
        self.pidKd = kd
        if source is not None:
            self.pidSource = source
        if cycle is not None:
            self.pidCycle = cycle


    # set PID beta/gamma weights of software PID
    def confPIDweights(self, beta:float|None, gamma:float|None) -> None:
        if self.externalPIDControl() == 0:
            if beta is not None:
                self.pidPsetpointWeight = beta
            if gamma is not None:
                self.pidDsetpointWeight = gamma
            self.aw.qmc.pid.setWeights(beta, gamma)

    # send p-i-d conf to connected PID
    def confPID(self, kp:float, ki:float, kd:float, source:int|None = None, cycle:int|None = None) -> None:
        if self.aw.qmc.Controlbuttonflag: # software / Kaleido PID
            self.aw.qmc.pid.setPID(kp,ki,kd)
            self.pidKp = kp
            self.pidKi = ki
            self.pidKd = kd
            self.aw.qmc.pid.setLimits((-100 if self.pidNegativeTarget else 0),(100 if self.pidPositiveTarget else 0))
            if source is not None and source>0:
                self.pidSource = source
            self.aw.sendmessage(QApplication.translate('Message','p-i-d values updated'))
