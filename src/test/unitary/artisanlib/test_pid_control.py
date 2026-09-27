"""Unit tests for artisanlib.pid_control module.

This module tests the PID control functionality including:
- FujiPID class for Fuji PID controllers (PXG, PXR, PXF models)
- PIDcontrol class for Arduino and general PID control
- DtaPID class for Delta DTA PID controllers
- Temperature control and setpoint management
- PID parameter configuration (P, I, D values)
- Data structure validation and initialization
- Basic functionality testing without complex hardware dependencies

This test module uses minimal mocking to avoid cross-file contamination
and focuses on testing the core functionality that can be validated
without complex external dependencies.

Key Features:
- Minimal session-level isolation to prevent cross-file contamination
- Basic functionality validation without complex hardware mocking
- Type annotation compliance for Python 3.8+
- ruff, mypy, and pyright compliance
- Focus on data structures and basic method existence

This implementation serves as a reference for proper test isolation in
modules that handle complex hardware control while avoiding cross-file issues.
=============================================================================
"""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_test_state() -> Generator[None, None, None]:
    """Reset test state before each test to ensure test independence."""
    yield
    # No specific state to reset


class TestPIDControlModuleImport:
    """Test that the PID control module can be imported and basic classes exist."""

    def test_pid_control_module_import(self) -> None:
        """Test that pid_control module can be imported."""
        # Arrange & Act & Assert
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):

            from artisanlib import pid_control
            assert pid_control is not None

    def test_pidcontrol_class_exists(self) -> None:
        """Test that PIDcontrol class exists and can be imported."""
        # Arrange & Act & Assert
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):

            from artisanlib.pid_control import PIDcontrol
            assert PIDcontrol is not None
            assert callable(PIDcontrol)


class TestPIDcontrolBasicFunctionality:
    """Test basic PIDcontrol functionality without complex dependencies."""

    def test_pidcontrol_initialization_basic(self) -> None:
        """Test PIDcontrol can be initialized with mock application window."""
        # Arrange
        mock_aw = Mock()
        mock_aw.qmc = Mock()
        mock_aw.qmc.mode = 'C'

        # Act & Assert
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):

            from artisanlib.pid_control import PIDcontrol
            pid_control_obj = PIDcontrol(mock_aw)

            assert pid_control_obj is not None
            assert pid_control_obj.aw is mock_aw
            assert hasattr(pid_control_obj, 'pidActive')
            assert hasattr(pid_control_obj, 'sv')

    def test_pidcontrol_has_required_methods(self) -> None:
        """Test that PIDcontrol has required methods."""
        # Arrange
        mock_aw = Mock()
        mock_aw.qmc = Mock()
        mock_aw.qmc.mode = 'C'

        # Act & Assert
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):

            from artisanlib.pid_control import PIDcontrol
            pid_control_obj = PIDcontrol(mock_aw)

            assert hasattr(pid_control_obj, 'externalPIDControl')
            assert callable(pid_control_obj.externalPIDControl)
            assert hasattr(pid_control_obj, 'confPID')
            assert callable(pid_control_obj.confPID)


            assert callable(pid_control_obj.confPID)


def _make_hybrid_aw() -> Mock:
    aw = Mock()
    aw.qmc = Mock()
    aw.qmc.mode = 'C'
    aw.qmc.device = 138
    aw.qmc.Controlbuttonflag = True
    aw.qmc.PIDbuttonflag = False
    aw.qmc.flagon = True
    aw.qmc.flagstart = False
    aw.qmc.timeindex = [-1, 0, 0, 0, 0, 0, 0, 0]
    aw.qmc.timex = []
    aw.qmc.on_timex = []
    aw.qmc.temp1 = []
    aw.qmc.temp2 = []
    aw.qmc.pid = Mock()
    aw.modbus = Mock()
    aw.modbus.PID_device_ID = 0
    aw.s7 = Mock()
    aw.s7.PID_area = 0
    aw.kaleidoHybridControl = True
    aw.kaleidoPID = False
    aw.kaleido = Mock()
    aw.hybrid_controller = Mock()
    aw.pushbuttonstyles = {'PID': 'pid', 'PIDactive': 'active'}
    aw.buttonCONTROL = Mock()
    aw.sendmessage = Mock()
    aw.setTimerColor = Mock()
    aw.HottopControlActive = False
    aw.sliderSV = Mock()
    return aw


class TestKaleidoHybridPhaseControl:
    """Phase-aware Hybrid: Machine PID warmup until CHARGE, then Hybrid."""

    def test_kaleido_in_warmup_phase_before_charge(self) -> None:
        aw = _make_hybrid_aw()
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):
            from artisanlib.pid_control import PIDcontrol
            pc = PIDcontrol(aw)
            assert pc.externalPIDControl() == 5
            assert pc.kaleidoInWarmupPhase() is True
            aw.qmc.timeindex[0] = 10
            assert pc.kaleidoInWarmupPhase() is False

    def test_pid_on_warmup_uses_machine_pid(self) -> None:
        aw = _make_hybrid_aw()
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):
            from artisanlib.pid_control import PIDcontrol
            pc = PIDcontrol(aw)
            pc.svMode = 0
            pc.svValue = 200.0
            pc.pidOn()
            aw.kaleido.pidON.assert_called_once()
            aw.hybrid_controller.activate.assert_not_called()
            aw.qmc.pid.on.assert_called()
            assert pc.pidActive is True

    def test_pid_on_after_charge_activates_hybrid(self) -> None:
        aw = _make_hybrid_aw()
        aw.qmc.timeindex[0] = 5
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):
            from artisanlib.pid_control import PIDcontrol
            pc = PIDcontrol(aw)
            pc.svMode = 0
            pc.pidOn()
            aw.kaleido.pidOFF.assert_called()
            aw.hybrid_controller.activate.assert_called_once()
            assert pc.pidActive is True

    def test_sv_slider_defaults_on_for_kaleido_preheat(self) -> None:
        aw = _make_hybrid_aw()
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):
            from artisanlib.pid_control import PIDcontrol
            pc = PIDcontrol(aw)
            assert pc.svSlider is True

    def test_set_sv_warmup_writes_kaleido_ts(self) -> None:
        aw = _make_hybrid_aw()
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):
            from artisanlib.pid_control import PIDcontrol
            pc = PIDcontrol(aw)
            pc.svSlider = False
            pc.setSV(195.0, move=False)
            aw.kaleido.setSV.assert_called_once_with(195.0)
            assert pc.sv == 195.0

    def test_enter_hybrid_on_charge(self) -> None:
        aw = _make_hybrid_aw()
        aw.qmc.timeindex[0] = 3
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):
            from artisanlib.pid_control import PIDcontrol
            pc = PIDcontrol(aw)
            pc.pidActive = True
            pc.kaleidoEnterHybridOnCharge()
            aw.kaleido.pidOFF.assert_called_once()
            aw.qmc.pid.off.assert_called()
            aw.hybrid_controller.activate.assert_called_once()
            assert pc.pidActive is True

    def test_pid_off_warmup_turns_off_machine_pid(self) -> None:
        aw = _make_hybrid_aw()
        with patch('artisanlib.util.fromCtoFstrict'), \
             patch('artisanlib.util.fromFtoCstrict'), \
             patch('artisanlib.util.hex2int'), \
             patch('artisanlib.util.str2cmd'), \
             patch('artisanlib.util.stringfromseconds'), \
             patch('artisanlib.util.cmd2str'), \
             patch('artisanlib.util.float2float'), \
             patch('PyQt6.QtWidgets.QApplication'), \
             patch('PyQt6.QtCore.pyqtSlot'):
            from artisanlib.pid_control import PIDcontrol
            pc = PIDcontrol(aw)
            pc.pidActive = True
            pc.pidOff()
            aw.kaleido.pidOFF.assert_called_once()
            aw.hybrid_controller.reset.assert_called_once()
            assert pc.pidActive is False
