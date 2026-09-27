#
# ABOUT
# Artisan Communication Ports Dialog

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
import platform
from typing import override, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from artisanlib.main import ApplicationWindow # noqa: F401 # pylint: disable=unused-import
    from PyQt6.QtWidgets import QWidget # pylint: disable=unused-import
    from PyQt6.QtGui import QCloseEvent # pylint: disable=unused-import

from artisanlib.util import comma2dot, toInt
from artisanlib.dialogs import ArtisanResizeablDialog, PortComboBox
from artisanlib.comm import serialport


from PyQt6.QtCore import (Qt, pyqtSlot, QSettings)
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTabWidget, QComboBox, QDialogButtonBox, QGridLayout,QSizePolicy,
                             QTableWidget, QTableWidgetItem, QDialog, QHeaderView)


class comportDlg(ArtisanResizeablDialog):

    __slots__ = [ 'comportEdit', 'baudrateComboBox', 'bauds', 'bytesizeComboBox', 'bytesizes', 'parityComboBox', 'parity', 'stopbitsComboBox', 'stopbits',
        'timeoutEdit', 'serialtable', 'TabWidget'
    ]

    def __init__(self, parent:'QWidget', aw:'ApplicationWindow') -> None:
        super().__init__(parent, aw)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False) # overwrite the ArtisanDialog class default here!!
        self.setWindowTitle(QApplication.translate('Form Caption','Ports Configuration'))
        self.setModal(True)
        ##########################    TAB 1 WIDGETS
        comportlabel =QLabel(QApplication.translate('Label', 'Comm Port'))
        self.comportEdit = PortComboBox(selection = self.aw.ser.comport)
        self.comportEdit.activated.connect(self.portComboBoxIndexChanged)
#        comportlabel.setBuddy(self.comportEdit)
        baudratelabel = QLabel(QApplication.translate('Label', 'Baud Rate'))
        self.baudrateComboBox = QComboBox()
#        baudratelabel.setBuddy(self.baudrateComboBox)
        self.bauds = ['1200', '2400','4800','9600','19200','38400','57600','57800','115200']
        self.baudrateComboBox.addItems(self.bauds)
        self.baudrateComboBox.setCurrentIndex(self.bauds.index(str(self.aw.ser.baudrate)))
        bytesizelabel = QLabel(QApplication.translate('Label', 'Byte Size'))
        self.bytesizeComboBox = QComboBox()
#        bytesizelabel.setBuddy(self.bytesizeComboBox)
        self.bytesizes = ['7','8']
        self.bytesizeComboBox.addItems(self.bytesizes)
        self.bytesizeComboBox.setCurrentIndex(self.bytesizes.index(str(self.aw.ser.bytesize)))
        paritylabel = QLabel(QApplication.translate('Label', 'Parity'))
        self.parityComboBox = QComboBox()
#        paritylabel.setBuddy(self.parityComboBox)
        #0 = Odd, E = Even, N = None. NOTE: These strings cannot be translated as they are arguments to the lib pyserial.
        self.parity = ['O','E','N']
        self.parityComboBox.addItems(self.parity)
        self.parityComboBox.setCurrentIndex(self.parity.index(self.aw.ser.parity))
        stopbitslabel = QLabel(QApplication.translate('Label', 'Stopbits'))
        self.stopbitsComboBox = QComboBox()
#        stopbitslabel.setBuddy(self.stopbitsComboBox)
        self.stopbits = ['1','2']
        self.stopbitsComboBox.addItems(self.stopbits)
        self.stopbitsComboBox.setCurrentIndex(self.aw.ser.stopbits-1)
        timeoutlabel = QLabel(QApplication.translate('Label', 'Timeout'))
        self.timeoutEdit:QLineEdit = QLineEdit(str(self.aw.ser.timeout))
        self.timeoutEdit.setValidator(self.aw.createCLocaleDoubleValidator(0,5,1,self.timeoutEdit))
        etbt_help_label = QLabel(QApplication.translate('Label', 'Settings for serial devices') + '<br>')
        ##########################    TAB 2  WIDGETS   EXTRA DEVICES
        self.serialtable = QTableWidget()
        self.serialtable.setTabKeyNavigation(True)
        self.serialtable.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        hheader: QHeaderView|None = self.serialtable.horizontalHeader()
        if hheader is not None:
            hheader.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            hheader.setStretchLastSection(True)
        self.createserialTable()
        #### dialog buttons
        # connect the ArtisanDialog standard OK/Cancel buttons
        self.dialogbuttons.accepted.connect(self.accept)
        self.dialogbuttons.rejected.connect(self.reject)

        #button layout
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.dialogbuttons)
        #LAYOUT TAB 1
        tab1Layout = QVBoxLayout()
        tab1Layout.addWidget(etbt_help_label)
        devid = self.aw.qmc.device
        if ((devid not in self.aw.qmc.nonSerialDevices) or (devid == 138 and self.aw.kaleidoSerial)):
            grid = QGridLayout()
            grid.addWidget(comportlabel,0,0,Qt.AlignmentFlag.AlignRight)
            grid.addWidget(self.comportEdit,0,1)
            grid.addWidget(baudratelabel,1,0,Qt.AlignmentFlag.AlignRight)
            grid.addWidget(self.baudrateComboBox,1,1)
            grid.addWidget(bytesizelabel,2,0,Qt.AlignmentFlag.AlignRight)
            grid.addWidget(self.bytesizeComboBox,2,1)
            grid.addWidget(paritylabel,3,0,Qt.AlignmentFlag.AlignRight)
            grid.addWidget(self.parityComboBox,3,1)
            grid.addWidget(stopbitslabel,4,0,Qt.AlignmentFlag.AlignRight)
            grid.addWidget(self.stopbitsComboBox,4,1)
            grid.addWidget(timeoutlabel,5,0,Qt.AlignmentFlag.AlignRight)
            grid.addWidget(self.timeoutEdit,5,1)
            gridBoxLayout = QHBoxLayout()
            gridBoxLayout.addLayout(grid)
            gridBoxLayout.addStretch()
            tab1Layout.addLayout(gridBoxLayout)
        tab1Layout.addStretch()
        #LAYOUT TAB 2
        tab2Layout = QVBoxLayout()
        tab2Layout.addWidget(self.serialtable)
        #tab widget
        self.TabWidget = QTabWidget()
        C1Widget = QWidget()
        C1Widget.setLayout(tab1Layout)
        self.TabWidget.addTab(C1Widget,QApplication.translate('Tab','ET/BT'))
        C2Widget = QWidget()
        C2Widget.setLayout(tab2Layout)
        self.TabWidget.addTab(C2Widget,QApplication.translate('Tab','Extra'))
        #incorporate layouts
        Mlayout = QVBoxLayout()
        Mlayout.addWidget(self.TabWidget)
        Mlayout.addLayout(buttonLayout)
        Mlayout.setContentsMargins(10,15,10,10) # left, top, right, bottom
        Mlayout.setSpacing(5)
        self.setLayout(Mlayout)
        if platform.system() != 'Windows':
            ok_button: QPushButton|None = self.dialogbuttons.button(QDialogButtonBox.StandardButton.Ok)
            if ok_button is not None:
                ok_button.setFocus()
        else:
            self.TabWidget.setFocus()
        settings = QSettings()
        if settings.contains('PortsGeometry'):
            self.restoreGeometry(settings.value('PortsGeometry'))


    @pyqtSlot(int)
    def portComboBoxIndexChanged(self, i:int) -> None:
        sender = cast(PortComboBox, self.sender())
        sender.setSelection(i)

    def createserialTable(self) -> None:
        try:
            self.serialtable.clear()
            nssdevices = min(len(self.aw.extracomport),len(self.aw.qmc.extradevices))
            if nssdevices:
                self.serialtable.setRowCount(nssdevices)
                self.serialtable.setColumnCount(7)
                self.serialtable.setHorizontalHeaderLabels([QApplication.translate('Table','Device'),
                                                            QApplication.translate('Table','Comm Port'),
                                                            QApplication.translate('Table','Baud Rate'),
                                                            QApplication.translate('Table','Byte Size'),
                                                            QApplication.translate('Table','Parity'),
                                                            QApplication.translate('Table','Stopbits'),
                                                            QApplication.translate('Table','Timeout')])
                self.serialtable.setAlternatingRowColors(True)
                self.serialtable.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                self.serialtable.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
                self.serialtable.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
                self.serialtable.setShowGrid(True)
                vheader: QHeaderView|None = self.serialtable.verticalHeader()
                if vheader is not None:
                    vheader.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
                for i in range(nssdevices):
                    if len(self.aw.qmc.extradevices) > i:
                        devid = self.aw.qmc.extradevices[i]
                        devicename = self.aw.qmc.devices[max(0,devid-1)]
                        if devicename[0] == '+':
                            devname = devicename[1:]
                        else:
                            devname = devicename
                        device = QTableWidgetItem(devname)    #type identification of the device. Non editable
                        self.serialtable.setItem(i,0,device)
                        if (devid not in self.aw.qmc.nonSerialDevices) and devicename[0] != '+': # hide serial confs for non-serial and "+X" extra devices
                            comportComboBox = PortComboBox(selection = self.aw.extracomport[i])
                            comportComboBox.activated.connect(self.portComboBoxIndexChanged)
                            comportComboBox.setMinimumContentsLength(15)
                            baudComboBox =  QComboBox()
                            baudComboBox.addItems(self.bauds)
                            if str(self.aw.extrabaudrate[i]) in self.bauds:
                                baudComboBox.setCurrentIndex(self.bauds.index(str(self.aw.extrabaudrate[i])))
                            byteComboBox =  QComboBox()
                            byteComboBox.addItems(self.bytesizes)
                            if str(self.aw.extrabytesize[i]) in self.bytesizes:
                                byteComboBox.setCurrentIndex(self.bytesizes.index(str(self.aw.extrabytesize[i])))
                            parityComboBox =  QComboBox()
                            parityComboBox.addItems(self.parity)
                            if self.aw.extraparity[i] in self.parity:
                                parityComboBox.setCurrentIndex(self.parity.index(self.aw.extraparity[i]))
                            stopbitsComboBox = QComboBox()
                            stopbitsComboBox.addItems(self.stopbits)
                            if str(self.aw.extrastopbits[i]) in self.stopbits:
                                stopbitsComboBox.setCurrentIndex(self.stopbits.index(str(self.aw.extrastopbits[i])))
                            timeoutEdit = QLineEdit(str(self.aw.extratimeout[i]))
                            timeoutEdit.setValidator(self.aw.createCLocaleDoubleValidator(0,5,1,timeoutEdit))
#                            timeoutEdit.setFixedWidth(65)
                            timeoutEdit.setMinimumWidth(65)
                            timeoutEdit.setAlignment(Qt.AlignmentFlag.AlignRight)
                            #add widgets to the table
                            self.serialtable.setCellWidget(i,1,comportComboBox)
                            self.serialtable.setCellWidget(i,2,baudComboBox)
                            self.serialtable.setCellWidget(i,3,byteComboBox)
                            self.serialtable.setCellWidget(i,4,parityComboBox)
                            self.serialtable.setCellWidget(i,5,stopbitsComboBox)
                            self.serialtable.setCellWidget(i,6,timeoutEdit)
                self.serialtable.resizeColumnsToContents()
        except Exception as e: # pylint: disable=broad-except
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' createserialTable(): {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))

    def saveserialtable(self) -> None:
        try:
            ser_ports = min(len(self.aw.extracomport),len(self.aw.qmc.extradevices))
            self.closeserialports()
            for i in range(ser_ports):
                if len(self.aw.qmc.extradevices) > i:
                    devid = self.aw.qmc.extradevices[i]
                    devicename = self.aw.qmc.devices[devid-1]    #type identification of the device. Non editable
                    if (devid not in self.aw.qmc.nonSerialDevices) and devicename[0] != '+': # hide serial confs for non-serial and "+XX" extra devices
                        comportComboBox = cast(PortComboBox, self.serialtable.cellWidget(i,1))
                        self.aw.extracomport[i] = str(comportComboBox.getSelection())
                        baudComboBox = cast(QComboBox, self.serialtable.cellWidget(i,2))
                        self.aw.extrabaudrate[i] = toInt(str(baudComboBox.currentText()))
                        byteComboBox = cast(QComboBox, self.serialtable.cellWidget(i,3))
                        self.aw.extrabytesize[i] = toInt(str(byteComboBox.currentText()))
                        parityComboBox = cast(QComboBox, self.serialtable.cellWidget(i,4))
                        self.aw.extraparity[i] = str(parityComboBox.currentText())
                        stopbitsComboBox = cast(QComboBox, self.serialtable.cellWidget(i,5))
                        self.aw.extrastopbits[i] = toInt(str(stopbitsComboBox.currentText()))
                        timeoutEdit = cast(QLineEdit, self.serialtable.cellWidget(i,6))
                        self.aw.extratimeout[i] = float(str(timeoutEdit.text()))
            #create serial ports for each extra device
            self.aw.extraser = []
            #load the settings for the extra serial ports found
            for i in range(ser_ports):
                xser = serialport(self.aw)
                if len(self.aw.extracomport)>i:
                    xser.comport = str(self.aw.extracomport[i])
                if len(self.aw.extrabaudrate)>i:
                    xser.baudrate = self.aw.extrabaudrate[i]
                if len(self.aw.extrabytesize)>i:
                    xser.bytesize = self.aw.extrabytesize[i]
                if len(self.aw.extraparity)>i:
                    xser.parity = str(self.aw.extraparity[i])
                if len(self.aw.extrastopbits)>i:
                    xser.stopbits = self.aw.extrastopbits[i]
                if len(self.aw.extratimeout)>i:
                    xser.timeout = self.aw.extratimeout[i]
                self.aw.extraser.append(xser)
        except Exception as e: # pylint: disable=broad-except
            _, _, exc_tb = sys.exc_info()
            self.aw.qmc.adderror((QApplication.translate('Error Message', 'Exception:') + ' saveserialtable(): {0}').format(str(e)),getattr(exc_tb, 'tb_lineno', '?'))

    @pyqtSlot('QCloseEvent')
    @override
    def closeEvent(self, a0:'QCloseEvent|None' = None) -> None:
        del a0
        settings = QSettings()
        #save window geometry
        settings.setValue('PortsGeometry',self.saveGeometry())

    @pyqtSlot()
    @override
    def accept(self) -> None:
        #validate serial parameter against input errors
        class comportError(Exception):
            pass
        class timeoutError(Exception):
            pass
        comport = str(self.comportEdit.getSelection())
        baudrate = str(self.baudrateComboBox.currentText())
        bytesize = str(self.bytesizeComboBox.currentText())
        parity = str(self.parityComboBox.currentText())
        stopbits = str(self.stopbitsComboBox.currentText())
        timeout = comma2dot(str(self.timeoutEdit.text()))
        #save extra serial ports by reading the serial extra table
        self.saveserialtable()
        if self.aw.qmc.device not in self.aw.qmc.nonSerialDevices: # only if serial conf is not hidden
            try:
                #check here comport errors
                if not comport:
                    raise comportError
                if not timeout:
                    raise timeoutError
                #add more checks here
                self.aw.sendmessage(QApplication.translate('Message','Serial Port Settings: {0}, {1}, {2}, {3}, {4}, {5}').format(comport,baudrate,bytesize,parity,stopbits,timeout))
            except comportError:
                self.aw.qmc.adderror(QApplication.translate('Error Message','Serial Exception: invalid comm port'))
                self.comportEdit.setFocus()
                return
            except timeoutError:
                self.aw.qmc.adderror(QApplication.translate('Error Message','Serial Exception: timeout'))
                self.timeoutEdit.selectAll()
                self.timeoutEdit.setFocus()
                return
        self.closeEvent(None)
        QDialog.accept(self)

    def closeserialports(self) -> None:
        self.aw.closeserialports()
