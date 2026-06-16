import pyvisa
import time
import copy
from collections import deque
from queue import Empty, Queue
import threading
from PyqtPowerSupply_log import Log
from Ui_powerMainWindow import Ui_MainWindow

import json
import numpy as np
import pyqtgraph as pg
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5 import QtCore

def busy_wait_nanos(nanoseconds):
    start_time = time.perf_counter_ns()
    end_time = start_time + nanoseconds
    while time.perf_counter_ns() < end_time:
        pass

class Window(QMainWindow, Ui_MainWindow):
    _startRunList = pyqtSignal(str)  # 信号

    def __init__(self, app):
        super(QMainWindow, self).__init__()
        self.app = app
        self.qmut = QMutex()
        self.myDialog = MyDialog()
        self.dialog = self.myDialog.dialog
        self.followWindowSeconds = 50
        self.autoFollowX = True
        self._updatingXRange = False
        self.setup_ui()
        self.runStep = RunListThread()
        self.mode = 0
        self.stepList = []
        self.maxPlotPoints = 6000
        self.plotRefreshMs = 100
        self.channelStatus = {}
        self.plotData = {
            'time': deque(maxlen=self.maxPlotPoints),
            'Current1': deque(maxlen=self.maxPlotPoints),
            'Voltage1': deque(maxlen=self.maxPlotPoints),
            'Current2': deque(maxlen=self.maxPlotPoints),
            'Voltage2': deque(maxlen=self.maxPlotPoints),
            'Current3': deque(maxlen=self.maxPlotPoints),
            'Voltage3': deque(maxlen=self.maxPlotPoints),
        }
        self.powerSupply = PowerSupply()
        self.powerSupply.powerInit()
        self.runStep.powerSupply = self.powerSupply
        self.connect_signals()  # 绑定触发事件
        self.flush_spinBox()
        self.flush_mode()
        self.pgtimer = QtCore.QTimer()
        self.pgtimer.timeout.connect(self.plot_show)
        self.pgtimer.start(self.plotRefreshMs)
        

    def setup_ui(self):
        self.setupUi(self)
        self.set_graph_ui()
        self.polish_ui()  # 设置绘图窗口

    def polish_ui(self):
        self.setWindowTitle('Power Supply Console')
        self.resize(1280, 760)
        self.setMinimumSize(1180, 720)
        self.setMaximumSize(16777215, 16777215)

        self.setFont(QFont('Microsoft YaHei UI', 10))
        self.reparent_legacy_widgets()

        main_layout = QGridLayout(self.centralwidget)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setHorizontalSpacing(16)
        main_layout.setVerticalSpacing(16)
        main_layout.setColumnStretch(0, 7)
        main_layout.setColumnStretch(1, 4)
        main_layout.setRowStretch(0, 5)
        main_layout.setRowStretch(1, 3)

        chart_card, chart_layout = self.create_card('chartCard')
        chart_header = QHBoxLayout()
        title = QLabel('实时曲线')
        title.setObjectName('sectionTitle')
        chart_header.addWidget(title)
        chart_header.addStretch()
        self.label_13.setText('刷新(ms)')
        chart_header.addWidget(self.label_13)
        chart_header.addWidget(self.spinBox_flushTime)
        chart_header.addWidget(self.pushButton_pauseGraph)
        chart_layout.addLayout(chart_header)
        chart_layout.addWidget(self.verticalLayoutWidget, 1)
        series_bar = QHBoxLayout()
        self.seriesToggleBar = QFrame()
        self.seriesToggleBar.setObjectName('seriesToggleBar')
        series_toggle_layout = QHBoxLayout(self.seriesToggleBar)
        series_toggle_layout.setContentsMargins(0, 0, 0, 0)
        series_toggle_layout.setSpacing(14)
        for checkbox in (self.checkBox_U1, self.checkBox_I1, self.checkBox_U2,
                         self.checkBox_I2, self.checkBox_U3, self.checkBox_I3):
            checkbox.setParent(self.seriesToggleBar)
            series_toggle_layout.addWidget(checkbox)
        self.splitter.hide()
        series_bar.addWidget(self.seriesToggleBar)
        series_bar.addStretch()
        chart_layout.addLayout(series_bar)
        main_layout.addWidget(chart_card, 0, 0)

        channel_card, channel_layout = self.create_card('channelCard')
        channel_header = QHBoxLayout()
        channel_title = QLabel('通道控制')
        channel_title.setObjectName('sectionTitle')
        channel_header.addWidget(channel_title)
        channel_header.addStretch()
        channel_header.addWidget(self.comboBox_mode)
        channel_layout.addLayout(channel_header)

        self.channelArea = QFrame()
        self.channelArea.setObjectName('channelArea')
        channel_area_layout = QGridLayout(self.channelArea)
        channel_area_layout.setContentsMargins(0, 0, 0, 0)
        channel_area_layout.setSpacing(0)

        channel_grid = QGridLayout()
        channel_grid.setHorizontalSpacing(12)
        channel_grid.setVerticalSpacing(12)
        channel_grid.addWidget(self.layoutWidget2, 0, 0)
        channel_grid.addWidget(self.layoutWidget3, 0, 1)
        channel_grid.addWidget(self.layoutWidget4, 0, 2)
        for column in range(3):
            channel_grid.setColumnStretch(column, 1)
        channel_area_layout.addLayout(channel_grid, 0, 0)

        self.modeOverlay = QFrame(self.channelArea)
        self.modeOverlay.setObjectName('modeOverlay')
        mode_layout = QVBoxLayout(self.modeOverlay)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setAlignment(Qt.AlignCenter)
        for mode_label in (self.label_mult, self.label_chuan, self.label_trace):
            mode_label.setMinimumSize(0, 0)
            mode_label.setMaximumSize(16777215, 16777215)
            mode_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            mode_label.setAlignment(Qt.AlignCenter)
            mode_layout.addWidget(mode_label)
        self.modeOverlay.hide()
        self.channelArea.installEventFilter(self)
        channel_layout.addWidget(self.channelArea, 1)
        main_layout.addWidget(channel_card, 1, 0)

        flow_card, flow_layout = self.create_card('flowCard')
        flow_header = QHBoxLayout()
        flow_title = QLabel('执行流程')
        flow_title.setObjectName('sectionTitle')
        flow_header.addWidget(flow_title)
        flow_header.addStretch()
        flow_header.addWidget(self.checkBox_repeat)
        flow_layout.addLayout(flow_header)
        flow_layout.addWidget(self.tableWidget_flow, 1)
        command_title = QLabel('步骤编辑')
        command_title.setObjectName('subTitle')
        flow_layout.addWidget(command_title)
        flow_layout.addWidget(self.layoutWidget)
        flow_layout.addWidget(self.layoutWidget1)
        main_layout.addWidget(flow_card, 0, 1, 2, 1)

        self.configure_widgets()
        self.apply_theme()

    def reparent_legacy_widgets(self):
        for widget in (
            self.verticalLayoutWidget, self.tableWidget_flow, self.pushButton_pauseGraph,
            self.label_13, self.spinBox_flushTime, self.splitter, self.layoutWidget,
            self.layoutWidget1, self.layoutWidget2, self.layoutWidget3, self.layoutWidget4,
            self.comboBox_mode, self.label_mult, self.label_chuan, self.label_trace
        ):
            widget.setParent(None)

    def create_card(self, object_name):
        card = QFrame(self.centralwidget)
        card.setObjectName(object_name)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        return card, layout

    def eventFilter(self, watched, event):
        if watched is getattr(self, 'channelArea', None) and event.type() == QEvent.Resize:
            self.update_mode_overlay_geometry()
        return super().eventFilter(watched, event)

    def update_mode_overlay_geometry(self):
        if not hasattr(self, 'modeOverlay'):
            return
        channel_rect = self.layoutWidget3.geometry()
        if self.mode == 3:
            channel_rect.setTop(channel_rect.top() + channel_rect.height() // 2)
        self.modeOverlay.setGeometry(channel_rect)
        self.modeOverlay.raise_()

    def update_mode_overlay(self):
        if not hasattr(self, 'modeOverlay'):
            return
        self.label_mult.setVisible(False)
        self.label_chuan.setVisible(False)
        self.label_trace.setVisible(False)
        overlay_label = None
        if self.mode == 1:
            overlay_label = self.label_mult
        elif self.mode == 2:
            overlay_label = self.label_chuan
        elif self.mode == 3:
            overlay_label = self.label_trace
        self.modeOverlay.setVisible(overlay_label is not None)
        if overlay_label is not None:
            overlay_label.setVisible(True)
            self.update_mode_overlay_geometry()

    def configure_widgets(self):
        self.tableWidget_flow.verticalHeader().setVisible(False)
        self.tableWidget_flow.horizontalHeader().setStretchLastSection(True)
        self.tableWidget_flow.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tableWidget_flow.horizontalHeader().setMinimumSectionSize(70)
        self.tableWidget_flow.horizontalHeader().setStyleSheet(
            'QHeaderView::section { background: #1e293b; color: #bfdbfe; '
            'border: 0; border-bottom: 1px solid #334155; padding: 8px; font-weight: 700; }'
        )
        self.tableWidget_flow.setAlternatingRowColors(True)
        self.tableWidget_flow.setShowGrid(False)
        self.tableWidget_flow.setMinimumHeight(260)
        self.tableWidget_flow.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.tableWidget_flow.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tableWidget_flow.setWordWrap(False)

        for widget in (self.layoutWidget2, self.layoutWidget3, self.layoutWidget4,
                       self.layoutWidget, self.layoutWidget1, self.verticalLayoutWidget):
            widget.setMinimumSize(0, 0)
            widget.setMaximumSize(16777215, 16777215)
        for label in (self.label_CH1, self.label_CH2, self.label_CH3):
            label.setObjectName('channelTitle')
        for label in (self.label_CH1_ONOFF, self.label_CH2_ONOFF, self.label_CH3_ONOFF):
            label.setObjectName('statusBadge')
            label.setMinimumHeight(24)
            label.setStyleSheet('')
        for checkbox in (self.checkBox_U1, self.checkBox_I1, self.checkBox_U2,
                         self.checkBox_I2, self.checkBox_U3, self.checkBox_I3):
            checkbox.setAutoFillBackground(False)
        self.checkBox_U1.setStyleSheet(self.series_checkbox_style('#34d399'))
        self.checkBox_I1.setStyleSheet(self.series_checkbox_style('#fb7185'))
        self.checkBox_U2.setStyleSheet(self.series_checkbox_style('#facc15'))
        self.checkBox_I2.setStyleSheet(self.series_checkbox_style('#e2e8f0'))
        self.checkBox_U3.setStyleSheet(self.series_checkbox_style('#c084fc'))
        self.checkBox_I3.setStyleSheet(self.series_checkbox_style('#38bdf8'))
        for lcd in (self.lcdNumber_CH1_V, self.lcdNumber_CH1_I, self.lcdNumber_CH2_V,
                    self.lcdNumber_CH2_I, self.lcdNumber_CH3_V, self.lcdNumber_CH3_I):
            lcd.setDigitCount(7)
            lcd.setMinimumHeight(34)
            lcd.setFrameShape(QFrame.NoFrame)
            lcd.setStyleSheet('QLCDNumber { color: #60a5fa; background: transparent; }')
        for button in (self.pushButton_start, self.pushButton_pause, self.pushButton_stop,
                       self.pushButton_pauseGraph, self.pushButton_channel, self.pushButton_output,
                       self.pushButton_setV, self.pushButton_setI, self.pushButton_setT,
                       self.pushButton_CH1_ON, self.pushButton_CH2_ON, self.pushButton_CH3_ON,
                       self.pushButton_CH1_OFF, self.pushButton_CH2_OFF, self.pushButton_CH3_OFF):
            button.setCursor(Qt.PointingHandCursor)
            button.setMinimumHeight(32)
        for button in (self.pushButton_CH1_ON, self.pushButton_CH2_ON, self.pushButton_CH3_ON):
            button.setProperty('role', 'success')
        for button in (self.pushButton_CH1_OFF, self.pushButton_CH2_OFF, self.pushButton_CH3_OFF,
                       self.pushButton_stop):
            button.setProperty('role', 'danger')
        self.pushButton_start.setProperty('role', 'primary')
        self.pushButton_pause.setProperty('role', 'warning')
        self.pushButton_pauseGraph.setProperty('role', 'ghost')

    def series_checkbox_style(self, color):
        return f"""
            QCheckBox {{
                background: transparent;
                color: {color};
                font-weight: 700;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 4px;
                border: 1px solid {color};
                background: #0f172a;
            }}
            QCheckBox::indicator:checked {{
                background: {color};
                border-color: {color};
            }}
        """

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget#centralwidget {
                background: #0f172a;
                color: #dbeafe;
            }
            QFrame#chartCard, QFrame#channelCard, QFrame#flowCard {
                background: #172033;
                border: 1px solid #2b3b55;
                border-radius: 8px;
            }
            QFrame#modeOverlay {
                background: transparent;
                border: 0;
            }
            QFrame#seriesToggleBar {
                background: transparent;
                border: 0;
            }
            QLabel {
                color: #cbd5e1;
                background: transparent;
            }
            QLabel#sectionTitle {
                color: #f8fafc;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#subTitle {
                color: #93c5fd;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#channelTitle {
                color: #f8fafc;
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#statusBadge {
                background: #475569;
                border-radius: 12px;
                color: #e2e8f0;
                font-weight: 700;
                padding: 2px 12px;
            }
            QLabel#statusBadge[state="on"] {
                background: #0f766e;
                color: #ccfbf1;
            }
            QLabel#statusBadge[state="off"] {
                background: #334155;
                color: #cbd5e1;
            }
            QPushButton {
                background: #243449;
                border: 1px solid #38506f;
                border-radius: 6px;
                color: #e5edf8;
                font-weight: 700;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #2e4260;
                border-color: #5b7fb0;
            }
            QPushButton:pressed {
                background: #1d2a3d;
            }
            QPushButton[role="primary"] {
                background: #2563eb;
                border-color: #3b82f6;
                color: white;
            }
            QPushButton[role="success"] {
                background: #047857;
                border-color: #10b981;
                color: white;
            }
            QPushButton[role="danger"] {
                background: #b91c1c;
                border-color: #ef4444;
                color: white;
            }
            QPushButton[role="warning"] {
                background: #b45309;
                border-color: #f59e0b;
                color: white;
            }
            QPushButton[role="ghost"] {
                background: #1e293b;
                border-color: #475569;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #e2e8f0;
                min-height: 28px;
                padding: 3px 8px;
                selection-background-color: #2563eb;
            }
            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #60a5fa;
            }
            QCheckBox {
                color: #dbeafe;
                spacing: 6px;
                font-weight: 700;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 4px;
                border: 1px solid #64748b;
                background: #0f172a;
            }
            QCheckBox::indicator:checked {
                background: #38bdf8;
                border-color: #7dd3fc;
            }
            QCheckBox#checkBox_U1 {
                color: #34d399;
            }
            QCheckBox#checkBox_I1 {
                color: #fb7185;
            }
            QCheckBox#checkBox_U2 {
                color: #facc15;
            }
            QCheckBox#checkBox_I2 {
                color: #e2e8f0;
            }
            QCheckBox#checkBox_U3 {
                color: #c084fc;
            }
            QCheckBox#checkBox_I3 {
                color: #38bdf8;
            }
            QTableWidget {
                background: #0f172a;
                alternate-background-color: #142136;
                border: 1px solid #26364f;
                border-radius: 6px;
                color: #dbeafe;
                gridline-color: #26364f;
                selection-background-color: #1d4ed8;
                selection-color: #ffffff;
            }
            QTableWidget QHeaderView::section {
                background: #1e293b;
                color: #bfdbfe;
                border: 0;
                border-bottom: 1px solid #334155;
                padding: 8px;
                font-weight: 700;
            }
            QHeaderView::section {
                background: #1e293b;
                color: #bfdbfe;
                border: 0;
                border-bottom: 1px solid #334155;
                padding: 8px;
                font-weight: 700;
            }
            QScrollBar:vertical {
                background: #111827;
                width: 10px;
                margin: 0;
            }
            QScrollBar:horizontal {
                background: #111827;
                height: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 5px;
                min-height: 28px;
            }
            QScrollBar::handle:horizontal {
                background: #475569;
                border-radius: 5px;
                min-width: 28px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)
        
    def set_graph_ui(self):
        pg.setConfigOptions(antialias=True, background='#0b1220', foreground='#cbd5e1')

        axisItems = pg.DateAxisItem()
        self.w = pg.PlotWidget(axisItems={'bottom': axisItems})
        self.w.setBackground('#0b1220')
        self.w.showGrid(x=True, y=True, alpha=0.22)
        self.w.setLabel('left', text='电压', color='#bfdbfe')
        self.w.setLabel('right', text='电流', color='#bfdbfe')
        self.w.setLogMode(x=False, y=False)
        self.w.setMenuEnabled(False)
        self.w.getPlotItem().layout.setContentsMargins(8, 8, 8, 8)
        self.w.getPlotItem().getAxis('left').setPen(pg.mkPen('#334155'))
        self.w.getPlotItem().getAxis('bottom').setPen(pg.mkPen('#334155'))
        self.w.getPlotItem().getAxis('left').setTextPen(pg.mkPen('#94a3b8'))
        self.w.getPlotItem().getAxis('bottom').setTextPen(pg.mkPen('#94a3b8'))

        self.vLine = pg.InfiniteLine(
            movable=True,
            angle=90,
            pen=pg.mkPen('#f59e0b', width=1),
            hoverPen=pg.mkPen('#fbbf24', width=2),
            pos=time.time(),
        )
        self.w.addItem(self.vLine)

        tooltip_fill = (15, 23, 42, 215)
        self.textItem_c1 = pg.TextItem(anchor=(1, 1), border='#fb7185', fill=tooltip_fill)
        self.textItem_v1 = pg.TextItem(anchor=(1, 1), border='#34d399', fill=tooltip_fill)
        self.textItem_c2 = pg.TextItem(anchor=(1, 1), border='#e2e8f0', fill=tooltip_fill)
        self.textItem_v2 = pg.TextItem(anchor=(1, 1), border='#facc15', fill=tooltip_fill)
        self.textItem_c3 = pg.TextItem(anchor=(1, 1), border='#38bdf8', fill=tooltip_fill)
        self.textItem_v3 = pg.TextItem(anchor=(1, 1), border='#c084fc', fill=tooltip_fill)
        for item in (self.textItem_c1, self.textItem_v1, self.textItem_c2,
                     self.textItem_v2, self.textItem_c3, self.textItem_v3):
            self.w.addItem(item)

        self.vLine.sigPositionChanged.connect(self.updateCursor)

        self.plotCur1 = self.w.plot(pen=pg.mkPen('#fb7185', width=2), name='Current1')
        self.plotVol1 = self.w.plot(pen=pg.mkPen('#34d399', width=2), name='Voltage1')
        self.plotCur2 = self.w.plot(pen=pg.mkPen('#e2e8f0', width=2), name='Current2')
        self.plotVol2 = self.w.plot(pen=pg.mkPen('#facc15', width=2), name='Voltage2')
        self.plotCur3 = self.w.plot(pen=pg.mkPen('#38bdf8', width=2), name='Current3')
        self.plotVol3 = self.w.plot(pen=pg.mkPen('#c084fc', width=2), name='Voltage3')
        self.w.getViewBox().sigXRangeChanged.connect(self.on_x_range_changed)
        self.set_initial_x_range()

        self.plot_view.addWidget(self.w)

    def set_initial_x_range(self):
        now = time.time()
        self._updatingXRange = True
        self.w.setXRange(now - self.followWindowSeconds, now, padding=0)
        self._updatingXRange = False

    def on_x_range_changed(self):
        if not self._updatingXRange:
            self.autoFollowX = False
        
    def updateCursor(self):
        if not hasattr(self, 'data') or len(self.data['time']) == 0:
            return
        # Get the x position of the cursor
        cursor_x = self.vLine.value()
        
        # Find the nearest x index
        index = np.searchsorted(self.data['time'], cursor_x)
        if index >= len(self.data['time']):
            index = len(self.data['time']) - 1

        # Get the corresponding y value
        cursor_Current1 = self.data['Current1'][index]
        cursor_Voltage1 = self.data['Voltage1'][index]
        cursor_Current2 = self.data['Current2'][index]
        cursor_Voltage2 = self.data['Voltage2'][index]
        cursor_Current3 = self.data['Current3'][index]
        cursor_Voltage3 = self.data['Voltage3'][index]

        self.textItem_c1.setPos(cursor_x, cursor_Current1)
        self.textItem_v1.setPos(cursor_x, cursor_Voltage1)
        self.textItem_c2.setPos(cursor_x, cursor_Current2)
        self.textItem_v2.setPos(cursor_x, cursor_Voltage2)
        self.textItem_c3.setPos(cursor_x, cursor_Current3)
        self.textItem_v3.setPos(cursor_x, cursor_Voltage3)
        
        self.textItem_c1.setText(f"c1 = {cursor_Current1:.3f}")
        self.textItem_v1.setText(f"v1 = {cursor_Voltage1:.3f}")
        self.textItem_c2.setText(f"c2 = {cursor_Current2:.3f}")
        self.textItem_v2.setText(f"v2 = {cursor_Voltage2:.3f}")
        self.textItem_c3.setText(f"c3 = {cursor_Current3:.3f}")
        self.textItem_v3.setText(f"v3 = {cursor_Voltage3:.3f}")

        if self.checkBox_I1.isChecked():
            self.textItem_c1.setVisible(True)
        else:
            self.textItem_c1.setVisible(False)
        if self.checkBox_U1.isChecked():
            self.textItem_v1.setVisible(True)
        else:
            self.textItem_v1.setVisible(False)
        if self.checkBox_I2.isChecked():
            self.textItem_c2.setVisible(True)
        else:
            self.textItem_c2.setVisible(False)
        if self.checkBox_U2.isChecked():
            self.textItem_v2.setVisible(True)
        else:
            self.textItem_v2.setVisible(False)
        if self.checkBox_I3.isChecked():
            self.textItem_c3.setVisible(True)
        else:
            self.textItem_c3.setVisible(False)
        if self.checkBox_U3.isChecked():
            self.textItem_v3.setVisible(True)
        else:
            self.textItem_v3.setVisible(False)
        
    def plot_show(self):
        # 显示波形
        dataDict = self.powerSupply.snapshot()
        required_keys = ('time', 'Current1', 'Voltage1', 'Current2', 'Voltage2', 'Current3', 'Voltage3')
        if not all(key in dataDict for key in required_keys):
            return
        for key in required_keys:
            self.plotData[key].append(dataDict[key])
        self.data = {key: np.asarray(values, dtype=float) for key, values in self.plotData.items()}
        if len(self.data['time']) == 0:
            return

        npTime = self.data['time']
        if self.autoFollowX:
            self._updatingXRange = True
            self.w.setXRange(npTime[-1]-self.followWindowSeconds, npTime[-1], padding=0)
            self._updatingXRange = False
        if self.checkBox_I1.isChecked():
            self.plotCur1.setData(npTime,self.data['Current1'])
        else:
            self.plotCur1.clear()
        if self.checkBox_U1.isChecked():
            self.plotVol1.setData(npTime,self.data['Voltage1'])
        else:
            self.plotVol1.clear()
        if self.checkBox_I2.isChecked():
            self.plotCur2.setData(npTime,self.data['Current2'])
        else:
            self.plotCur2.clear()
        if self.checkBox_U2.isChecked():
            self.plotVol2.setData(npTime,self.data['Voltage2'])
        else:
            self.plotVol2.clear()
        if self.checkBox_I3.isChecked():
            self.plotCur3.setData(npTime,self.data['Current3'])
        else:   
            self.plotCur3.clear()
        if self.checkBox_U3.isChecked():
            self.plotVol3.setData(npTime,self.data['Voltage3'])
        else:
            self.plotVol3.clear()

    def connect_signals(self):
        # 绑定触发事件
        self.pushButton_start.clicked.connect(self.btn_start_clicked)
        self.pushButton_pause.clicked.connect(self.btn_pause_clicked)
        self.pushButton_stop.clicked.connect(self.btn_stop_clicked)
        self.checkBox_repeat.stateChanged.connect(self.runStep.set_repeat)
        self.pushButton_pauseGraph.clicked.connect(self.btn_pause_graph_clicked)
        
        self.pushButton_CH1_ON.clicked.connect(self.pushButton_CH_ONOFF)
        self.pushButton_CH1_OFF.clicked.connect(self.pushButton_CH_ONOFF)
        self.pushButton_CH2_ON.clicked.connect(self.pushButton_CH_ONOFF)
        self.pushButton_CH2_OFF.clicked.connect(self.pushButton_CH_ONOFF)
        self.pushButton_CH3_ON.clicked.connect(self.pushButton_CH_ONOFF)
        self.pushButton_CH3_OFF.clicked.connect(self.pushButton_CH_ONOFF)
        
        self.doubleSpinBox_CH1_setV.editingFinished.connect(self.pushButton_CH_VC)
        self.doubleSpinBox_CH1_setI.editingFinished.connect(self.pushButton_CH_VC)
        self.doubleSpinBox_CH2_setV.editingFinished.connect(self.pushButton_CH_VC)
        self.doubleSpinBox_CH2_setI.editingFinished.connect(self.pushButton_CH_VC)
        self.doubleSpinBox_CH3_setV.editingFinished.connect(self.pushButton_CH_VC)
        self.doubleSpinBox_CH3_setI.editingFinished.connect(self.pushButton_CH_VC)
        
        self.spinBox_flushTime.editingFinished.connect(self.set_flush_time)
        
        self.pushButton_channel.clicked.connect(self.add_step_to_table)
        self.pushButton_output.clicked.connect(self.add_step_to_table)
        self.pushButton_setV.clicked.connect(self.add_step_to_table)
        self.pushButton_setI.clicked.connect(self.add_step_to_table)
        self.pushButton_setT.clicked.connect(self.add_step_to_table)
        
        self._startRunList.connect(self.runStep.rec_data_and_run)
        self.runStep._runListError.connect(self.dialog)
        self.tableWidget_flow._tableDeleteAll.connect(self.dialog)
        self.powerSupply.dialog_signal.connect(self.dialog)
        self.myDialog._dialog_result_signal.connect(self.tableWidget_flow.delete_row_all_handel)
        self.w.scene().sigMouseClicked.connect(self.onMouseClick)
        
        self.powerSupply.displayQthread_signal.connect(self.displayQthread)
    
    def onMouseClick(self, event):
        if event.double():
            self.autoFollowX = True
            return
        if not hasattr(self, 'data') or len(self.data['time']) == 0:
            return
        pos = self.w.mapToScene(self.w.mapFromGlobal(QCursor.pos()))
        start_time, end_time = self.w.viewRange()[0]
        time = self.pixel_to_time(pos.x(), start_time, end_time)
        self.vLine.setX(time)
        
    def pixel_to_time(self, pixel, start_time, end_time):
        total_time = end_time - start_time
        width = self.w.width()
        return start_time + (pixel / width) * total_time
    
    def add_step_to_table(self):
        btn = self.sender()
        row = self.tableWidget_flow.rowCount()
        self.tableWidget_flow.insertRow(row)
        self.tableWidget_flow.setItem(row, 0, QTableWidgetItem(btn.text()))
        if 'channel' in btn.objectName():
            value = self.spinBox_channel.value()
        elif 'output' in btn.objectName():
            value = self.spinBox_output.value()
        elif 'setV' in btn.objectName():
            value = self.doubleSpinBox_setV.value()
        elif 'setI' in btn.objectName():
            value = self.doubleSpinBox_setI.value()
        elif 'setT' in btn.objectName():
            value = self.doubleSpinBox_setT.value()
        else:
            self.tableWidget_flow.removeRow(row)
            return
        self.tableWidget_flow.setItem(row, 1, QTableWidgetItem(str(value)))
    
    def start_flow(self):
        if self.tableWidget_flow.rowCount() == 0:
            return
        self.stepList = []
        for i in range(self.tableWidget_flow.rowCount()):
            step_item = self.tableWidget_flow.item(i, 0)
            value_item = self.tableWidget_flow.item(i, 1)
            if step_item is None or value_item is None:
                continue
            step = step_item.text()
            value = value_item.text()
            self.stepList.append({step:value})
        if not self.stepList:
            return
        self.runStep.step_pause_event.set()
        self._startRunList.emit(json.dumps({'stepList': self.stepList}))  # 发送信号给槽函数
        
    def pushButton_CH_ONOFF(self):
        btn = self.sender()
        channel = int(btn.objectName().split('CH')[1][0])
        if 'ON' in btn.objectName(): 
            self.powerSupply.powerAddQueen({'ONOFF'+str(channel):{self.powerSupply.powerSwitch:[channel,True]}})
        elif 'OFF' in btn.objectName():
            self.powerSupply.powerAddQueen({'ONOFF'+str(channel):{self.powerSupply.powerSwitch:[channel,False]}})
    
    def pushButton_CH_VC(self):
        spinBox = self.sender()
        channel = int(spinBox.objectName().split('CH')[1][0])
        if 'V' in spinBox.objectName():
            self.powerSupply.powerAddQueen({'setVoltage'+str(channel):{self.powerSupply.powerVoltage:[channel,spinBox.value()]}})
        elif 'I' in spinBox.objectName():
            self.powerSupply.powerAddQueen({'setCurrent'+str(channel):{self.powerSupply.powerCurrent:[channel,spinBox.value()]}})
    

    def btn_start_clicked(self):
        #如果runList线程没有运行
        if self.runStep.isRunning() == False:
            self.start_flow()
        #如果线程处于等待状态
        elif self.runStep.step_pause_event.is_set() == False:
            self.runStep.step_pause_event.set()
    def btn_pause_clicked(self):
        self.runStep.step_pause_event.clear()
    def btn_stop_clicked(self):
        self.runStep.set_stop()
        self.runStep.step_pause_event.set()
    def btn_pause_graph_clicked(self):
        if self.pushButton_pauseGraph.text() == '暂停':
            self.pushButton_pauseGraph.setText('继续')
            self.pgtimer.stop()
        elif self.pushButton_pauseGraph.text() == '继续':
            self.pushButton_pauseGraph.setText('暂停')
            self.pgtimer.start(self.plotRefreshMs)

    def flush_spinBox(self):
        self.doubleSpinBox_CH1_setI.setValue(self.powerSupply.powerGetCurrent(1))
        self.doubleSpinBox_CH1_setV.setValue(self.powerSupply.powerGetVoltage(1))
        self.doubleSpinBox_CH2_setI.setValue(self.powerSupply.powerGetCurrent(2))
        self.doubleSpinBox_CH2_setV.setValue(self.powerSupply.powerGetVoltage(2))
        self.doubleSpinBox_CH3_setI.setValue(self.powerSupply.powerGetCurrent(3))
        self.doubleSpinBox_CH3_setV.setValue(self.powerSupply.powerGetVoltage(3))
    def flush_mode(self):
        self.mode = int(self.powerSupply.snapshot().get('Mode', 0))
        self.comboBox_mode.setCurrentIndex(self.mode)
        self.update_mode_overlay()
        self.comboBox_mode.currentIndexChanged.connect(self.set_mode)
        
    def set_flush_time(self):
        self.powerSupply.flushTime = self.spinBox_flushTime.value()/1000
        self.plotRefreshMs = max(100, int(self.spinBox_flushTime.value()))
        if self.pgtimer.isActive():
            self.pgtimer.start(self.plotRefreshMs)
        
    def set_mode(self):
        power_data = self.powerSupply.snapshot()
        powerStatus = power_data.get('Status1', 0) or power_data.get('Status2', 0) or power_data.get('Status3', 0)
        if powerStatus != 0:
            self.dialog('警告', '请先关闭输出')
            Log.logger.warning('请先关闭输出')
            self.comboBox_mode.setCurrentIndex(self.mode)
            return
        comboBox = self.sender()
        mode_old = self.mode
        self.mode = comboBox.currentIndex()
        try:
            self.powerSupply.powerAddQueen({'Mode': {self.powerSupply.powerSetMode: [self.mode]}})
        except Exception:
            self.mode = mode_old
            self.comboBox_mode.currentIndexChanged.disconnect(self.set_mode)
            comboBox.setCurrentIndex(mode_old)
            self.comboBox_mode.currentIndexChanged.connect(self.set_mode)
            self.dialog('错误', '设置模式失败')
            Log.logger.error('设置模式失败')
            return
        self.update_mode_overlay()
        self.comboBox_mode.currentIndexChanged.disconnect(self.set_mode)
        self.comboBox_mode.setCurrentIndex(self.mode)
        self.comboBox_mode.currentIndexChanged.connect(self.set_mode)
    
    def displayQthread(self,disDataDict):
        required_keys = ('Current1', 'Voltage1', 'Current2', 'Voltage2', 'Current3', 'Voltage3',
                         'setCurrent1', 'setVoltage1', 'setCurrent2', 'setVoltage2', 'setCurrent3', 'setVoltage3',
                         'Status1', 'Status2', 'Status3')
        if not all(key in disDataDict for key in required_keys):
            return
        self.lcdNumber_CH1_I.display(disDataDict['Current1'])
        self.lcdNumber_CH1_V.display(disDataDict['Voltage1'])
        self.lcdNumber_CH2_I.display(disDataDict['Current2'])
        self.lcdNumber_CH2_V.display(disDataDict['Voltage2'])
        self.lcdNumber_CH3_I.display(disDataDict['Current3'])
        self.lcdNumber_CH3_V.display(disDataDict['Voltage3'])

        spin_pairs = (
            (self.doubleSpinBox_CH1_setI, disDataDict.get('setCurrent1')),
            (self.doubleSpinBox_CH1_setV, disDataDict.get('setVoltage1')),
            (self.doubleSpinBox_CH2_setI, disDataDict.get('setCurrent2')),
            (self.doubleSpinBox_CH2_setV, disDataDict.get('setVoltage2')),
            (self.doubleSpinBox_CH3_setI, disDataDict.get('setCurrent3')),
            (self.doubleSpinBox_CH3_setV, disDataDict.get('setVoltage3')),
        )
        for spin_box, value in spin_pairs:
            if value is None:
                continue
            if not spin_box.hasFocus() and spin_box.value() != value:
                spin_box.setValue(float(value))

        status_labels = (
            (1, self.label_CH1_ONOFF, disDataDict.get('Status1', 0)),
            (2, self.label_CH2_ONOFF, disDataDict.get('Status2', 0)),
            (3, self.label_CH3_ONOFF, disDataDict.get('Status3', 0)),
        )
        for channel, label, status in status_labels:
            status = 1 if float(status or 0) != 0 else 0
            self.channelStatus[channel] = status
            label.setText('ON' if status == 1 else 'OFF')
            label.setProperty('state', 'on' if status == 1 else 'off')
            label.style().unpolish(label)
            label.style().polish(label)
        

class RunListThread(QThread):
    _runListError = pyqtSignal(str,str)  # 信号

    def __init__(self):
        super().__init__()
        self.qmut = QMutex()
        self.step_pause_event = threading.Event()
        self.repeat = False
        self.pause = False
        self.stop = False
        self.data = []
        self.powerSupply = None

    def run(self):
        self.pause = False
        self.stop = False
        if self.powerSupply is None:
            self._runListError.emit('错误','电源控制对象未初始化')
            return
        while True:
            for dic in self.data:
                self.qmut.lock()
                should_stop = self.stop
                self.qmut.unlock()
                if should_stop:
                    break
                for key,value in dic.items():
                    self.step_pause_event.wait()
                    self.qmut.lock()
                    should_stop = self.stop
                    self.qmut.unlock()
                    if should_stop:
                        break
                    if '延时' in key:
                        time.sleep(float(value))
                    elif '通道' in key:
                        self.channel = int(value)
                    elif '开关' in key:
                        if not hasattr(self,'channel'):
                            self.set_stop()
                            self._runListError.emit('错误','请先设置通道号')
                            break
                        self.powerSupply.powerAddQueen({key:{self.powerSupply.powerSwitch:[self.channel,self.str_to_bool(value)]}})
                    elif '电压' in key:
                        if not hasattr(self,'channel'):
                            self.set_stop()
                            self._runListError.emit('错误','请先设置通道号')
                            break
                        self.powerSupply.powerAddQueen({key:{self.powerSupply.powerVoltage:[self.channel,float(value)]}})
                    elif '限流' in key:
                        if not hasattr(self,'channel'):
                            self.set_stop()
                            self._runListError.emit('错误','请先设置通道号')
                            break
                        self.powerSupply.powerAddQueen({key:{self.powerSupply.powerCurrent:[self.channel,float(value)]}})
            self.qmut.lock()
            should_repeat = self.repeat and not self.stop
            self.qmut.unlock()
            if not should_repeat:
                break
    def set_repeat(self):
        checBox = self.sender()
        self.qmut.lock()
        self.repeat = checBox.isChecked()
        self.qmut.unlock()
    def set_stop(self):
        self.qmut.lock()
        self.stop = True
        self.qmut.unlock()
    def rec_data_and_run(self, data):
        self.qmut.lock()
        self.data = []
        self.data = copy.deepcopy(json.loads(data)['stepList'])
        self.qmut.unlock()
        self.start()
    def str_to_bool(self,s):
        return s == '1'
    
class PowerSupply(QThread):
    displayQthread_signal = pyqtSignal(dict)
    dialog_signal = pyqtSignal(str,str)
    def __init__(self):
        super().__init__()
        self.qmut = QMutex()
        self.rm = pyvisa.ResourceManager()
        self.myLoopQueen = Queue(1000)
        self.flushTime = 0.05
        self.maxCommandsPerCycle = 10
        self.myLoopDict = {'Current1':{self.powerGetMeasCurrent:1},
                           'Voltage1':{self.powerGetMeasVoltage:1},
                           'Current2':{self.powerGetMeasCurrent:2},
                           'Voltage2':{self.powerGetMeasVoltage:2},
                           'Current3':{self.powerGetMeasCurrent:3},
                           'Voltage3':{self.powerGetMeasVoltage:3},
                           'Status1':{self.powerGetStatus:1},
                           'Status2':{self.powerGetStatus:2},
                           'Status3':{self.powerGetStatus:3}}
        self.dataDict = {}
        self._setpointRefreshCount = 0
        
    def powerInit(self):
        try:
            self.Power = self.rm.open_resource('TCPIP0::172.16.40.214::7000::SOCKET',read_termination = '\r\n',timeout = 200)
        except:
            self.dialog_signal.emit('错误','设备连接失败，请检查连接')
            Log.logger.error('设备连接失败，请检查连接')
            sys.exit()
        self.dataDict['Mode'] = self.powerGetMode()
        self.dataDict['time'] = time.time()
        self.dataDict['setVoltage1'] = self.powerGetVoltage(1)
        self.dataDict['setCurrent1'] = self.powerGetCurrent(1)
        self.dataDict['setVoltage2'] = self.powerGetVoltage(2)
        self.dataDict['setCurrent2'] = self.powerGetCurrent(2)
        self.dataDict['setVoltage3'] = self.powerGetVoltage(3)
        self.dataDict['setCurrent3'] = self.powerGetCurrent(3)
        self.dataDict['Status1'] = self.powerGetStatus(1)
        self.dataDict['Status2'] = self.powerGetStatus(2)
        self.dataDict['Status3'] = self.powerGetStatus(3)
        self.start() 
        self.displayTimer = QtCore.QTimer()
        self.displayTimer.timeout.connect(self.displaySender)
        self.displayTimer.start(500)
        
    def displaySender(self):
        self.displayQthread_signal.emit(self.snapshot())

    def snapshot(self):
        self.qmut.lock()
        data = dict(self.dataDict)
        self.qmut.unlock()
        return data
        
    def run(self):
        next_tick = time.monotonic()
        while True:
            self._drain_commands(self.maxCommandsPerCycle)
            now_monotonic = time.monotonic()
            sleep_time = next_tick - now_monotonic
            if sleep_time > 0:
                time.sleep(min(sleep_time, 0.01))
                continue

            next_tick = now_monotonic + self.flushTime
            now = time.time()
            self.qmut.lock()
            self.dataDict['time'] = now
            self.qmut.unlock()

            for key,fun_val in self.myLoopDict.items():
                self._drain_commands(self.maxCommandsPerCycle)
                function, value = next(iter(fun_val.items()))
                result = function(value)
                self.qmut.lock()
                self.dataDict[key] = result
                self.qmut.unlock()

            self._refresh_setpoints_periodically()
            self._drain_commands(self.maxCommandsPerCycle)

    def _refresh_setpoints_periodically(self):
        self._setpointRefreshCount += 1
        if self._setpointRefreshCount < 10:
            return
        self._setpointRefreshCount = 0
        setpoint_getters = (
            ('setVoltage1', self.powerGetVoltage, 1),
            ('setCurrent1', self.powerGetCurrent, 1),
            ('setVoltage2', self.powerGetVoltage, 2),
            ('setCurrent2', self.powerGetCurrent, 2),
            ('setVoltage3', self.powerGetVoltage, 3),
            ('setCurrent3', self.powerGetCurrent, 3),
        )
        for key, function, channel in setpoint_getters:
            value = function(channel)
            self.qmut.lock()
            self.dataDict[key] = value
            self.qmut.unlock()

    def _drain_commands(self, limit=None):
        processed = 0
        while limit is None or processed < limit:
            try:
                command = self.myLoopQueen.get_nowait()
            except Empty:
                break
            Qkey = list(command.keys())[0]
            Func = list(command[Qkey].keys())[0]
            value = command[Qkey][Func]
            result = Func(*value)
            if result is not None:
                self.qmut.lock()
                self.dataDict[Qkey] = result
                self.qmut.unlock()
            processed += 1
        return processed
                # Log.logger.info(self.dataDict)
            # time.sleep(self.flushTime)
            
    def powerAddQueen(self, command):
        self.myLoopQueen.put(command)
    def powerChannel(self,channel):
        self.Power.write('INST:NSEL '+str(channel))
    def powerGetStatus(self,channel,retries=5):
        self.powerChannel(channel)
        self.Power.write('OUTP?')
        try:
            return self.parse_power_status(self.Power.read())
        except Exception:
            if retries > 0:
                return self.powerGetStatus(channel,retries-1)
            Log.logger.warning('获取通道'+str(channel)+'电源状态失败,使用上一次数据。')
            return self.dataDict.get('Status'+str(channel), 0)

    def parse_power_status(self, value):
        text = str(value).strip().upper()
        if text in ('ON', 'TRUE'):
            return 1
        if text in ('OFF', 'FALSE'):
            return 0
        return 1 if float(text or 0) != 0 else 0
    
    def powerSwitch(self,channel,state):
        self.Power.write('INST:NSEL '+str(channel))
        if state == True:
            self.Power.write('OUTP 1')
            return 1
        else:
            self.Power.write('OUTP 0')
            return 0
    def powerVoltage(self,channel,voltage):
        self.Power.write('INST:NSEL '+str(channel))
        self.Power.write('VOLT '+str(voltage))
        return float(voltage)
    def powerCurrent(self,channel,current):
        self.Power.write('INST:NSEL '+str(channel))
        self.Power.write('CURR '+str(current))
        return float(current)
    def powerSetVoltageCurrent(self,voltage,current):
        self.Power.write('VOLT '+str(voltage))
        self.Power.write('CURR '+str(current))
    def powerGetVoltage(self,channel,retries=5):
        self.powerChannel(channel)
        self.Power.write('VOLT?')
        try:
            return float(self.Power.read())
        except Exception:
            if retries > 0:
                return self.powerGetVoltage(channel,retries-1)
            Log.logger.warning('获取通道'+str(channel)+'电压设置数据失败,使用上一次数据。')
            return self.dataDict.get('setVoltage'+str(channel), 0)
    def powerGetCurrent(self,channel,retries=5):
        self.powerChannel(channel)
        self.Power.write('CURR?')
        try:
            return float(self.Power.read())
        except Exception:
            if retries > 0:
                return self.powerGetCurrent(channel,retries-1)
            Log.logger.warning('获取通道'+str(channel)+'限流设置数据失败,使用上一次数据。')
            return self.dataDict.get('setCurrent'+str(channel), 0)
    
    def powerGetMeasVoltage(self,channel,retries=5):
        self.Power.write('INST:NSEL '+str(channel))
        self.Power.write('MEAS:VOLT?')
        try:
            return float(self.Power.read())
        except Exception:
            if retries > 0:
                return self.powerGetMeasVoltage(channel,retries-1)
            Log.logger.warning('获取通道'+str(channel)+'电压数据失败,使用上一次数据。')
            return self.dataDict.get('Voltage'+str(channel), 0)
    def powerGetMeasCurrent(self,channel,retries=5):
        self.Power.write('INST:NSEL '+str(channel))
        self.Power.write('MEAS:CURR?')
        try:
            return float(self.Power.read())
        except Exception:
            if retries > 0:
                return self.powerGetMeasCurrent(channel,retries-1)
            Log.logger.warning('获取通道'+str(channel)+'电流数据失败,使用上一次数据。')
            return self.dataDict.get('Current'+str(channel), 0)
    
    def powerGetMode(self,retries=5):
        try:
            self.Power.write('OUTP:PARA?')
            if float(self.Power.read() or 0):
                return 1
            self.Power.write('OUTP:SERI?')
            if float(self.Power.read() or 0):
                return 2
            self.Power.write('OUTP:TRAC?')
            if float(self.Power.read() or 0):
                return 3
            return 0
        except Exception:
            if retries > 0:
                return self.powerGetMode(retries-1)
            Log.logger.warning('获取模式失败,使用上一次数据。')
            return self.dataDict.get('Mode', 0)
        
    def powerSetMode(self,mode):
        if mode == 0:
            self.Power.write('OUTP:PARA 0')
            self.Power.write('OUTP:SERI 0')
            self.Power.write('OUTP:TRAC 0')
        elif mode == 1:
            self.Power.write('OUTP:SERI 0')
            self.Power.write('OUTP:TRAC 0')
            self.Power.write('OUTP:PARA 1')
        elif mode == 2:
            self.Power.write('OUTP:PARA 0')
            self.Power.write('OUTP:TRAC 0')
            self.Power.write('OUTP:SERI 1')
        elif mode == 3:
            self.Power.write('OUTP:PARA 0')
            self.Power.write('OUTP:SERI 0')
            self.Power.write('OUTP:TRAC 1')
        Log.logger.info('设置模式为：'+str(mode))
        
        
#提示弹窗   
class MyDialog(QTableWidget):
    _dialog_result_signal = pyqtSignal(int)
    def dialog(self,Level,Text):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText(Text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(Level)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.buttonClicked.connect(msg.close)
        result = msg.exec_()
        self._dialog_result_signal.emit(result)  # 发出信号，传递用户点击的按钮

if __name__ == "__main__":
    # import pyqtgraph.examples
    # pyqtgraph.examples.run()
    app = QApplication(sys.argv)
    mywindow = Window(app)
    mywindow.show()
    sys.exit(app.exec_())


