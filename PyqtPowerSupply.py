import pyvisa
import time
import copy
from queue import Queue
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
        self.setup_ui()  # 渲染画布
        self.runStep = RunListThread()
        self.displayThread = DisplayThread(self)
        self.displayThread.start()
        self.connect_signals()  # 绑定触发事件
        self.mode = 0
        self.stepList = []
        self.npTime = np.array([])
        self.npC1 = np.array([])
        self.npV1 = np.array([])
        self.npC2 = np.array([])
        self.npV2 = np.array([])
        self.npC3 = np.array([])
        self.npV3 = np.array([])
        
        self.pgtimer = QtCore.QTimer()
        self.pgtimer.timeout.connect(self.plot_show)
        self.pgtimer.start(int(powerSupply.flushTime*1000))
        

    def setup_ui(self):
        self.setupUi(self)
        self.set_graph_ui()  # 设置绘图窗口
        
    def set_graph_ui(self):
        pg.setConfigOptions(antialias=True, background='k')  # pyqtgraph全局变量设置函数，antialias=True开启曲线抗锯齿

        axisItems = pg.DateAxisItem()
        self.w = pg.PlotWidget(axisItems = {'bottom': axisItems})
        self.w.showGrid(x=True, y=True)
        
        self.w.setLabel('left',text='电压', color='white')  
        self.w.setLabel('right',text='电流', color='white')
        
        self.w.setLogMode(x=False, y=False)  # False代表线性坐标轴，True代表对数坐标轴
        
        self.vLine = pg.InfiniteLine(movable=True, angle=90, hoverPen={'color': 'yellow', 'width': 2},
                                    pos = time.time())
        
        # Add a vertical cursor
        # self.vLine = pg.InfiniteLine(angle=90, movable=True)
        self.w.addItem(self.vLine)

        # Add text item to display the cursor data
        self.textItem_c1  = pg.TextItem(anchor=(1, 1), border='red', fill=(0, 0, 0, 100))
        self.textItem_v1  = pg.TextItem(anchor=(1, 1), border='lightgreen', fill=(0, 0, 0, 100))
        self.textItem_c2  = pg.TextItem(anchor=(1, 1), border='white', fill=(0, 0, 0, 100))
        self.textItem_v2  = pg.TextItem(anchor=(1, 1), border='yellow', fill=(0, 0, 0, 100))
        self.textItem_c3  = pg.TextItem(anchor=(1, 1), border='lightblue', fill=(0, 0, 0, 100))
        self.textItem_v3  = pg.TextItem(anchor=(1, 1), border='pink', fill=(0, 0, 0, 100))
        self.w.addItem(self.textItem_c1)
        self.w.addItem(self.textItem_v1)
        self.w.addItem(self.textItem_c2)
        self.w.addItem(self.textItem_v2)
        self.w.addItem(self.textItem_c3)
        self.w.addItem(self.textItem_v3)

        # Connect the signal for cursor movement
        self.vLine.sigPositionChanged.connect(self.updateCursor)
        
        self.plotCur1 = self.w.plot(pen=pg.mkPen('red',width=2), name='Current1')
        self.plotVol1 = self.w.plot(pen=pg.mkPen('lightgreen',width=2), name='Voltage1')
        self.plotCur2 = self.w.plot(pen=pg.mkPen('white',width=2), name='Current2')
        self.plotVol2 = self.w.plot(pen=pg.mkPen('yellow',width=2), name='Voltage2')
        self.plotCur3 = self.w.plot(pen=pg.mkPen('lightblue',width=2), name='Current2')
        self.plotVol3 = self.w.plot(pen=pg.mkPen('pink',width=2), name='Voltage2')
        
        self.plot_view.addWidget(self.w)
        
    def updateCursor(self):
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
        self.qmut.lock()
        self.deepcpyDataDict = copy.deepcopy(powerSupply.dataDict)
        self.qmut.unlock()
        self.npTime = np.append(self.npTime, self.deepcpyDataDict['time'])
        self.npC1 = np.append(self.npC1, self.deepcpyDataDict['Current1'])
        self.npV1 = np.append(self.npV1, self.deepcpyDataDict['Voltage1'])
        self.npC2 = np.append(self.npC2, self.deepcpyDataDict['Current2'])
        self.npV2 = np.append(self.npV2, self.deepcpyDataDict['Voltage2'])
        self.npC3 = np.append(self.npC3, self.deepcpyDataDict['Current3'])
        self.npV3 = np.append(self.npV3, self.deepcpyDataDict['Voltage3'])
        
        if len(self.npTime) > 6000:
            self.npTime = np.delete(self.npTime, 0)
            self.npC1 = np.delete(self.npC1, 0)
            self.npV1 = np.delete(self.npV1, 0)
            self.npC2 = np.delete(self.npC2, 0)
            self.npV2 = np.delete(self.npV2, 0)
            self.npC3 = np.delete(self.npC3, 0)
            self.npV3 = np.delete(self.npV3, 0)
        
                
        self.w.setXRange(self.npTime[-1]-50, self.npTime[-1], padding=0)
        if self.checkBox_I1.isChecked():
            self.plotCur1.setData(self.npTime,self.npC1)
        else:
            self.plotCur1.clear()
        if self.checkBox_U1.isChecked():
            self.plotVol1.setData(self.npTime,self.npV1)
        else:
            self.plotVol1.clear()
        if self.checkBox_I2.isChecked():
            self.plotCur2.setData(self.npTime,self.npC2)
        else:
            self.plotCur2.clear()
        if self.checkBox_U2.isChecked():
            self.plotVol2.setData(self.npTime,self.npV2)
        else:
            self.plotVol2.clear()
        if self.checkBox_I3.isChecked():
            self.plotCur3.setData(self.npTime,self.npC3)
        else:   
            self.plotCur3.clear()
        if self.checkBox_U3.isChecked():
            self.plotVol3.setData(self.npTime,self.npV3)
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
        self.tableWidget_flow._tableDeleteAll.connect(self.myDialog.dialog)
        self.myDialog._dialog_result_signal.connect(self.tableWidget_flow.delete_row_all_handel)
        self.w.scene().sigMouseClicked.connect(self.onMouseClick)
    
    def onMouseClick(self):
        pos = self.w.mapToScene(self.w.mapFromGlobal(QCursor.pos()))
        start_time = self.data['time'][-1]-50
        end_time = self.data['time'][-1]
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
        self.tableWidget_flow.setItem(row, 1, QTableWidgetItem(str(value)))
    
    def start_flow(self):
        if self.tableWidget_flow.rowCount() == 0:
            return
        for i in range(self.tableWidget_flow.rowCount()):
            step = self.tableWidget_flow.item(i, 0).text()
            value = self.tableWidget_flow.item(i, 1).text()
            self.stepList.append({step:value})
        self.runStep.step_pause_event.set()
        self._startRunList.emit(json.dumps({'stepList': self.stepList}))  # 发送信号给槽函数
        
    def pushButton_CH_ONOFF(self):
        btn = self.sender()
        channel = int(btn.objectName().split('CH')[1][0])
        if 'ON' in btn.objectName(): 
            powerSupply.powerAddQueen({'ONOFF'+str(channel):{powerSupply.powerSwitch:[channel,True]}})
        elif 'OFF' in btn.objectName():
            powerSupply.powerAddQueen({'ONOFF'+str(channel):{powerSupply.powerSwitch:[channel,False]}})
    
    def pushButton_CH_VC(self):
        spinBox = self.sender()
        channel = int(spinBox.objectName().split('CH')[1][0])
        if 'V' in spinBox.objectName():
            powerSupply.powerAddQueen({'setVoltage'+str(channel):{powerSupply.powerVoltage:[channel,spinBox.value()]}})
        elif 'I' in spinBox.objectName():
            powerSupply.powerAddQueen({'setVoltage'+str(channel):{powerSupply.powerCurrent:[channel,spinBox.value()]}})
    

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
            self.pgtimer.start(int(powerSupply.flushTime*1000))

    def flush_spinBox(self):
        self.doubleSpinBox_CH1_setI.setValue(powerSupply.powerGetCurrent(1))
        self.doubleSpinBox_CH1_setV.setValue(powerSupply.powerGetVoltage(1))
        self.doubleSpinBox_CH2_setI.setValue(powerSupply.powerGetCurrent(2))
        self.doubleSpinBox_CH2_setV.setValue(powerSupply.powerGetVoltage(2))
        self.doubleSpinBox_CH3_setI.setValue(powerSupply.powerGetCurrent(3))
        self.doubleSpinBox_CH3_setV.setValue(powerSupply.powerGetVoltage(3))
    def flush_mode(self):
        self.qmut.lock()
        self.mode = powerSupply.dataDict['Mode']
        self.qmut.unlock()
        self.label_chuan.setVisible(False)
        self.label_mult.setVisible(False)
        self.label_trace.setVisible(False)
        if self.mode == 0:
            return
        elif self.mode == 1:
            self.label_mult.setVisible(True)
        elif self.mode == 2:
            self.label_chuan.setVisible(True)
        elif self.mode == 3:
            self.label_trace.setVisible(True)
        self.comboBox_mode.setCurrentIndex(self.mode)
        self.comboBox_mode.currentIndexChanged.connect(self.set_mode)
        
    def set_flush_time(self):
        self.pgtimer.stop()
        powerSupply.flushTime = self.spinBox_flushTime.value()/1000
        self.pgtimer.start(int(self.spinBox_flushTime.value()))
        
    def set_mode(self):
        self.qmut.lock()
        powerStatus = powerSupply.dataDict['Status1'] or powerSupply.dataDict['Status2'] or powerSupply.dataDict['Status3']
        self.qmut.unlock()
        if powerStatus!=0:
            self.dialog('警告','请先关闭输出')
            Log.logger.warning('请先关闭输出')
            self.comboBox_mode.setCurrentIndex(self.mode)
            return
        comboBox = self.sender()
        mode_old = self.mode
        if comboBox.currentText() == '普通模式':
            self.mode = 0
        if comboBox.currentText() == '并联模式':
            self.mode = 1
        if comboBox.currentText() == '串联模式':
            self.mode = 2
        if comboBox.currentText() == '跟踪模式':
            self.mode = 3
        try:
            self.qmut.lock()
            powerSupply.powerAddQueen({'Mode':{powerSupply.powerSetMode:[self.mode]}})
            self.qmut.unlock()
        except:
            self.mode = mode_old
            self.comboBox_mode.currentIndexChanged.disconnect(self.set_mode)
            comboBox.setCurrentIndex(mode_old)
            self.comboBox_mode.currentIndexChanged.connect(self.set_mode)
            self.dialog('错误','设置模式失败')
            Log.logger.error('设置模式失败')
        self.label_chuan.setVisible(False)
        self.label_mult.setVisible(False)
        self.label_trace.setVisible(False)
        if self.mode == 0:
            return
        elif self.mode == 1:
            self.label_mult.setVisible(True)
        elif self.mode == 2:
            self.label_chuan.setVisible(True)
        elif self.mode == 3:
            self.label_trace.setVisible(True)
        self.comboBox_mode.currentIndexChanged.disconnect(self.set_mode)
        self.comboBox_mode.setCurrentIndex(self.mode)
        self.comboBox_mode.currentIndexChanged.connect(self.set_mode)
        

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

    def run(self):
        self.pause = False
        self.stop = False
        while True:
            for dic in self.data:
                self.qmut.lock()
                if self.stop:
                    self.qmut.unlock()
                    break
                self.qmut.unlock()
                for key,value in dic.items():
                    self.step_pause_event.wait()
                    if '延时' in key:
                        time.sleep(float(value))
                    elif '通道' in key:
                        self.channel = int(value)
                    elif '开关' in key:
                        #如果不存在通道号
                        if not hasattr(self,'channel'):
                            self.set_stop()
                            self._runListError.emit('错误','请先设置通道号')
                            break
                        powerSupply.powerAddQueen({key:{powerSupply.powerSwitch:[self.channel,self.str_to_bool(value)]}})
                    elif '电压' in key:
                        if not hasattr(self,'channel'):
                            self.set_stop()
                            self._runListError.emit('错误','请先设置通道号')
                            break
                        powerSupply.powerAddQueen({key:{powerSupply.powerVoltage:[self.channel,float(value)]}})
                    elif '限流' in key:
                        if not hasattr(self,'channel'):
                            self.set_stop()
                            self._runListError.emit('错误','请先设置通道号')
                            break
                        powerSupply.powerAddQueen({key:{powerSupply.powerCurrent:[self.channel,float(value)]}})
                        
            self.qmut.lock()
            if self.repeat == False:
                self.qmut.unlock()
                break
            self.qmut.unlock()
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

    
class DisplayThread(QThread):
    def __init__(self,windowDisplay):
        super().__init__()
        self.qmut = QMutex()
        self.windowDisplay = windowDisplay
        self.disDataDict = {}
    def run(self):
        while True:
            self.qmut.lock()
            self.disDataDict = copy.deepcopy(powerSupply.dataDict)
            self.qmut.unlock()
            self.LcdNumberDisplay()
            self.SpinBoxDisplay()
            self.OnOffDispaly()
            time.sleep(0.5)   
            
    def LcdNumberDisplay(self):
        self.windowDisplay.lcdNumber_CH1_I.display(self.disDataDict['Current1'])
        self.windowDisplay.lcdNumber_CH1_V.display(self.disDataDict['Voltage1'])
        self.windowDisplay.lcdNumber_CH2_I.display(self.disDataDict['Current2'])
        self.windowDisplay.lcdNumber_CH2_V.display(self.disDataDict['Voltage2'])
        self.windowDisplay.lcdNumber_CH3_I.display(self.disDataDict['Current3'])
        self.windowDisplay.lcdNumber_CH3_V.display(self.disDataDict['Voltage3'])
    def SpinBoxDisplay(self):
        if not self.windowDisplay.doubleSpinBox_CH1_setI.hasFocus():
            self.windowDisplay.doubleSpinBox_CH1_setI.setValue(self.disDataDict['setCurrent1'])
        if not self.windowDisplay.doubleSpinBox_CH1_setV.hasFocus():
            self.windowDisplay.doubleSpinBox_CH1_setV.setValue(self.disDataDict['setVoltage1'])
        if not self.windowDisplay.doubleSpinBox_CH2_setI.hasFocus():
            self.windowDisplay.doubleSpinBox_CH2_setI.setValue(self.disDataDict['setCurrent2'])
        if not self.windowDisplay.doubleSpinBox_CH2_setV.hasFocus():
            self.windowDisplay.doubleSpinBox_CH2_setV.setValue(self.disDataDict['setVoltage2'])
        if not self.windowDisplay.doubleSpinBox_CH3_setI.hasFocus():
            self.windowDisplay.doubleSpinBox_CH3_setI.setValue(self.disDataDict['setCurrent3'])
        if not self.windowDisplay.doubleSpinBox_CH3_setV.hasFocus(): 
            self.windowDisplay.doubleSpinBox_CH3_setV.setValue(self.disDataDict['setVoltage3'])  
    def OnOffDispaly(self):
        if self.disDataDict['Status1'] == 1:
            self.windowDisplay.label_CH1_ONOFF.setText('ON')
            self.windowDisplay.label_CH1_ONOFF.setStyleSheet('background:lightgreen')
        else:
            self.windowDisplay.label_CH1_ONOFF.setText('OFF')
            self.windowDisplay.label_CH1_ONOFF.setStyleSheet('background:gray')
        if self.disDataDict['Status2'] == 1:
            self.windowDisplay.label_CH2_ONOFF.setText('ON')
            self.windowDisplay.label_CH2_ONOFF.setStyleSheet('background:lightgreen')
        else:
            self.windowDisplay.label_CH2_ONOFF.setText('OFF')
            self.windowDisplay.label_CH2_ONOFF.setStyleSheet('background:gray')
        if self.disDataDict['Status3'] == 1:
            self.windowDisplay.label_CH3_ONOFF.setText('ON')
            self.windowDisplay.label_CH3_ONOFF.setStyleSheet('background:lightgreen')
        else:
            self.windowDisplay.label_CH3_ONOFF.setText('OFF')
            self.windowDisplay.label_CH3_ONOFF.setStyleSheet('background:gray')
    
class PowerSupply(QThread):
    def __init__(self):
        super().__init__()
        self.qmut = QMutex()
        self.rm = pyvisa.ResourceManager()
        self.myLoopQueen = Queue(1000)
        self.flushTime = 0.05
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
        
    def powerInit(self):
        try:
            self.Power = self.rm.open_resource('TCPIP0::172.16.40.214::7000::SOCKET',read_termination = '\r\n',timeout = 200)
        except:
            self.dialog('错误','设备连接失败，请检查连接')
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
        self.start() 
        
    def run(self):
        now = time.time()
        while True:
            if time.time()-now > self.flushTime:
                now = time.time()
                self.qmut.lock()
                self.dataDict['time'] = now
                self.qmut.unlock()
                for key,fun_val in self.myLoopDict.items():
                    function = list(fun_val.keys())[0]
                    value = fun_val[function]
                    self.qmut.lock()
                    self.dataDict[key] = function(value)
                    # Log.logger.info(key+str(function)+str(value)+str(self.dataDict[key]))  
                    self.qmut.unlock()
                    
                if not self.myLoopQueen.empty():
                    self.qmut.lock()
                    dict = self.myLoopQueen.get()
                    self.qmut.unlock()
                    Qkey = list(dict.keys())[0]
                    Func = list(dict[Qkey].keys())[0]
                    value = dict[Qkey][Func]
                    self.qmut.lock()
                    # if  value == None:
                    #     self.dataDict[Qkey] = Func()
                    # else:
                    self.dataDict[Qkey] = Func(*value)
                    self.qmut.unlock()
                # Log.logger.info(self.dataDict)
            # time.sleep(self.flushTime)
            
    def powerAddQueen(self,dict):
        self.qmut.lock()
        self.myLoopQueen.put(dict)
        self.qmut.unlock()
    def powerChannel(self,channel):
        self.Power.write('INST:NSEL '+str(channel))
    def powerGetStatus(self,channel,retries=5):
        self.powerChannel(channel)
        self.Power.write('OUTP?')
        try:
            return float(self.Power.read())
        except:
            if retries > 0:
                self.powerGetStatus(channel,retries-1)
                print("再次执行Status"+str(channel))
            else:
                Log.logger.warning('获取通道'+str(channel)+'电源状态失败,使用上一次数据。')
                if 'Status'+str(channel) in self.dataDict:
                    return self.dataDict['Status'+str(channel)]
                else:
                    return 0
    
    def powerSwitch(self,channel,state):
        self.Power.write('INST:NSEL '+str(channel))
        if state == True:
            self.Power.write('OUTP 1')
        else:
            self.Power.write('OUTP 0')
    def powerVoltage(self,channel,voltage):
        self.Power.write('INST:NSEL '+str(channel))
        self.Power.write('VOLT '+str(voltage)) 
    def powerCurrent(self,channel,current):
        self.Power.write('INST:NSEL '+str(channel))
        self.Power.write('CURR '+str(current))
    def powerSetVoltageCurrent(self,voltage,current):
        self.Power.write('VOLT '+str(voltage))
        self.Power.write('CURR '+str(current))
    def powerGetVoltage(self,channel,retries=5):
        self.powerChannel(channel)
        self.Power.write('VOLT?')
        try:
            return float(self.Power.read())
        except:
            if retries > 0:
                self.powerGetVoltage(channel,retries-1)
            else:
                Log.logger.warning('获取通道'+str(channel)+'电压设置数据失败,使用上一次数据。')
                if 'getVoltage'+str(channel) in self.dataDict:
                    return self.dataDict['getVoltage'+str(channel)]
                else:
                    return 0
    def powerGetCurrent(self,channel,retries=5):
        self.powerChannel(channel)
        self.Power.write('CURR?')
        try:
            return float(self.Power.read())
        except:
            if retries > 0:
                self.powerGetCurrent(channel,retries-1)
            else:
                Log.logger.warning('获取通道'+str(channel)+'限流设置数据失败,使用上一次数据。')
                if 'getCurrent'+str(channel) in self.dataDict:
                    return self.dataDict['getCurrent'+str(channel)]
                else:
                    return 0
    
    def powerGetMeasVoltage(self,channel,retries=5):
        self.Power.write('INST:NSEL '+str(channel))
        self.Power.write('MEAS:VOLT?')
        try:
            return float(self.Power.read())
        except:
            if retries > 0:
                self.powerGetMeasVoltage(channel,retries-1)
                print("再次执行Voltage"+str(channel))
            else:
                Log.logger.warning('获取通道'+str(channel)+'电压数据失败,使用上一次数据。')
                return self.dataDict['Voltage'+str(channel)]
    def powerGetMeasCurrent(self,channel,retries=5):
        self.Power.write('INST:NSEL '+str(channel))
        self.Power.write('MEAS:CURR?')
        try:
            return float(self.Power.read())
        except:
            if retries > 0:
                self.powerGetMeasCurrent(channel,retries-1)
                print("再次执行Current"+str(channel))
            else:
                Log.logger.warning('获取通道'+str(channel)+'电流数据失败,使用上一次数据。')
                return self.dataDict['Current'+str(channel)]
    
    def powerGetMode(self,retries=5):
        mode = 0
        try:
            self.Power.write('OUTP:PARA?')
            if self.Power.read():
                mode = 1
                return mode
            self.Power.write('OUTP:SERI?')
            if self.Power.read():
                mode = 2
                return mode
            self.Power.write('OUTP:TRAC?')
            if self.Power.read():
                mode = 3  
            return mode
        except:
            if retries > 0:
                self.powerGetMode(retries-1)
            else:
                Log.logger.warning('获取模式失败,使用上一次数据。')
                if 'Mode' in self.dataDict:
                    return self.dataDict['Mode']
                return 0
        
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
    
def main():
    app = QApplication(sys.argv)
    
    powerSupply.powerInit()
    mywindow = Window(app)
    mywindow.flush_spinBox()
    mywindow.flush_mode()
    
    mywindow.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    # import pyqtgraph.examples
    # pyqtgraph.examples.run()
    
    powerSupply = PowerSupply()
    
    main()
    powerSupply.close()


