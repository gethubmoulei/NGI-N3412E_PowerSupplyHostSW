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
        self.setDefaultDropAction(Qt.MoveAction)
        self._dragRows = []
        self._dragRowData = []

    def startDrag(self, supportedActions):
        self._dragRows = sorted({index.row() for index in self.selectedIndexes()})
        self._dragRowData = self.clone_rows(self._dragRows)
        if not self._dragRows:
            return
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData('application/x-power-supply-table-row', b'move')
        drag.setMimeData(mime_data)
        if drag.exec_(Qt.MoveAction) != Qt.MoveAction:
            self._dragRows = []
            self._dragRowData = []

    def dragEnterEvent(self, event):
        if event.source() == self and event.mimeData().hasFormat('application/x-power-supply-table-row'):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.source() == self and event.mimeData().hasFormat('application/x-power-supply-table-row'):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.source() != self:
            super().dropEvent(event)
            return

        rows = list(self._dragRows) if self._dragRows else sorted({index.row() for index in self.selectedIndexes()})
        if not rows:
            event.ignore()
            return

        target_row = self.drop_target_row(event)
        if rows[0] <= target_row <= rows[-1] + 1:
            event.accept()
            return

        row_items = self._dragRowData if self._dragRowData else self.clone_rows(rows)

        for row in reversed(rows):
            self.removeRow(row)
            if row < target_row:
                target_row -= 1

        target_row = max(0, min(target_row, self.rowCount()))
        for offset, items in enumerate(row_items):
            insert_row = target_row + offset
            self.insertRow(insert_row)
            for column, item in enumerate(items):
                if item is not None:
                    self.setItem(insert_row, column, item)

        self.clearSelection()
        for row in range(target_row, target_row + len(row_items)):
            self.selectRow(row)
        self.setCurrentCell(target_row, 0)
        self._dragRows = []
        self._dragRowData = []
        event.setDropAction(Qt.IgnoreAction)
        event.accept()

    def drop_target_row(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return self.rowCount()
        target_row = index.row()
        if self.dropIndicatorPosition() == QAbstractItemView.BelowItem:
            target_row += 1
        elif self.dropIndicatorPosition() == QAbstractItemView.OnViewport:
            target_row = self.rowCount()
        return max(0, min(target_row, self.rowCount()))

    def clone_rows(self, rows):
        row_items = []
        for row in rows:
            row_items.append([
                QTableWidgetItem(self.item(row, column)) if self.item(row, column) is not None else None
                for column in range(self.columnCount())
            ])
        return row_items

    def drop_on(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return self.rowCount()

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
        if self.currentRow() < 0:
            return
        self.copied_row = []
        row = self.currentRow()
        for column in range(self.columnCount()):
            item = self.item(row, column)
            if item is not None:
                self.copied_row.append(item.text())
            else:
                self.copied_row.append("")

    def paste_row(self):
        if not hasattr(self, 'copied_row'):
            return
        row = self.currentRow()
        if row < 0:
            row = self.rowCount()
        self.insertRow(row)  # Insert a row at the current position
        for column, text in enumerate(self.copied_row):
            item = QTableWidgetItem(text)
            self.setItem(row, column, item)  # Set the item in the new row
    
    def cut_row(self):
        if self.currentRow() < 0:
            return
        self.copy_row()
        row = self.currentRow()
        self.removeRow(row)
        
    def delete_row(self):
        row = self.currentRow()
        if row < 0:
            return
        self.removeRow(row)
        
    def delete_row_all(self):
        self.tableDeleteAllEmitted = True  
        self._tableDeleteAll.emit('警告！','是否删除所有数据？')
        
    def insert_row(self):
        row = self.currentRow()
        if row < 0:
            row = self.rowCount()
        self.insertRow(row)  # Insert a row at the current position
    
    def delete_row_all_handel(self,reply):
        if self.tableDeleteAllEmitted:
            self.tableDeleteAllEmitted = False
            if reply == QMessageBox.Ok:
                while self.rowCount() > 0:
                    self.removeRow(0)
        
