from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
class MyTableWidget(QTableWidget):
    _tableDeleteAll = pyqtSignal(str,str)
    def __init__(self, parent=None):
        super(MyTableWidget, self).__init__(parent)
        self.tableDeleteAllEmitted = False
        #允许右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.generateMenu)
        #使能编辑
        self.cellDoubleClicked.connect(self.check_column)
        #使能拖拽
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setDragDropMode(QAbstractItemView.InternalMove)

    def dropEvent(self, event):
        if event.source() == self:
            rows = set([mi.row() for mi in self.selectedIndexes()])
            targetRow = self.indexAt(event.pos()).row()
            rows.discard(targetRow)
            rows = sorted(rows)
            if not rows:
                return
            if targetRow == -1:
                targetRow = self.rowCount()
            for _ in range(len(rows)):
                self.insertRow(targetRow)
            rowMapping = dict() # Src row to target row.
            for idx, row in enumerate(rows):
                if row < targetRow:
                    rowMapping[row] = targetRow + idx
                else:
                    rowMapping[row + len(rows)] = targetRow + idx
            colCount = self.columnCount()
            for srcRow, tgtRow in sorted(rowMapping.items()):
                for col in range(0, colCount):
                    self.setItem(tgtRow, col, self.takeItem(srcRow, col))
            for row in reversed(sorted(rowMapping.keys())):
                self.removeRow(row)
            event.accept()
            return

    def drop_on(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return self.rowCount()
            print("drop_on_return:",self.rowCount())

        return index.row() + 1 if self.is_below(event.pos(), index) else index.row()


    def is_below(self, pos, index):
        rect = self.visualRect(index)
        margin = 2
        if pos.y() - rect.top() < margin:
            return False
        elif rect.bottom() - pos.y() < margin:
            return True
        # noinspection PyTypeChecker
        return rect.contains(pos, True) and not (
                    int(self.model().flags(index)) & Qt.ItemIsDropEnabled) and pos.y() >= rect.center().y()
        
    def generateMenu(self,pos):
        # 获取点击行号
        menu = QMenu()
        item1 = menu.addAction("复制")
        item2 = menu.addAction("剪切")
        item3 = menu.addAction("粘贴")
        item4 = menu.addAction("删除")
        item5 = menu.addAction("插入")
        item6 = menu.addAction("全部删除")
            
        # 转换坐标系
        screenPos = self.mapToGlobal(pos)
 
        # 被阻塞
        action = menu.exec(screenPos)
        if action == item1:
            self.copy_row()
        elif action == item2:
            self.cut_row()
        elif action == item3:
            self.paste_row()
        elif action == item4:
            self.delete_row()
        elif action == item5:
            self.insert_row()
        elif action == item6:
            self.delete_row_all()
        else:
            return
          
    def check_column(self, row, column):
        # Check if the column is one of the editable ones
        if column in [1,2]:  # Replace with your column numbers
            item = self.item(row, column)
            if item is not None:
                item.setFlags(item.flags() | Qt.ItemIsEditable)
        else:
            item = self.item(row, column)
            if item is not None:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                
    def copy_row(self):
        self.copied_row = []
        row = self.currentRow()
        for column in range(self.columnCount()):
            item = self.item(row, column)
            if item is not None:
                self.copied_row.append(item.text())
            else:
                self.copied_row.append("")

    def paste_row(self):
        row = self.currentRow()
        self.insertRow(row)  # Insert a row at the current position
        for column, text in enumerate(self.copied_row):
            item = QTableWidgetItem(text)
            self.setItem(row, column, item)  # Set the item in the new row
    
    def cut_row(self):
        self.copy_row()
        row = self.currentRow()
        self.removeRow(row)
        
    def delete_row(self):
        row = self.currentRow()
        self.removeRow(row)
        
    def delete_row_all(self):
        self.tableDeleteAllEmitted = True  
        self._tableDeleteAll.emit('警告！','是否删除所有数据？')
        
    def insert_row(self):
        row = self.currentRow()
        self.insertRow(row)  # Insert a row at the current position
    
    def delete_row_all_handel(self,reply):
        if self.tableDeleteAllEmitted:
            self.tableDeleteAllEmitted = False
            if reply == QMessageBox.Ok:
                while self.rowCount() > 0:
                    self.removeRow(0)
        