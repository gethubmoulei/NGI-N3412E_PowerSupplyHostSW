import os
import logging
from logging import handlers
import time
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from PyQt5 import QtWidgets

import binascii

#日志输出
formater = '%(asctime)s - %(levelname)s: %(message)s'
#路径管理
def log_path_check(filename):
    log_path = os.getcwd() + '/Logs/'
    if not os.path.exists(log_path):
        os.mkdir(log_path)
    day = time.strftime('%Y-%m-%d', time.localtime())
    log_name = log_path + filename + day+'.log'
    return log_name

#日志过滤器
class allLogFilter(logging.Filter):
    def __init__(self, name, level=logging.DEBUG):
        super().__init__(name=name)
        self.level = level
    def filter(self, record):
        if record.levelno >= self.level:
            return True
        return False
#日志处理器
class QLogHandler(logging.Handler, QObject):
    update_text = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.update_text.emit(msg)
        
class Logger(object):
    def __init__(self, filename='', level='debug', when='D',backCount=10,fmt=formater):
        self.level_relations = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'crit': logging.CRITICAL
        }  # 日志级别关系映射
        self.logger = logging.getLogger()
        format_str = logging.Formatter(fmt)#设置日志格式
        self.logger.setLevel(self.level_relations.get(level))#设置日志级别
        #日志器配置
        testh = handlers.TimedRotatingFileHandler(filename=log_path_check(filename),when='midnight',interval=1,backupCount=backCount,encoding='utf-8')#往文件里写入
        testh.setFormatter(format_str)#设置文件里写入的格式
        testh.addFilter(allLogFilter('',level=logging.INFO))
        self.logger.addHandler(testh)
Log = Logger(level='info')         #日志类实例化