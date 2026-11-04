"""Wrap action buttons onto additional rows without shrinking their height."""
from PySide6.QtCore import QRect,QSize,Qt
from PySide6.QtWidgets import QLayout,QWidgetItem

class ActionLayout(QLayout):
    def __init__(self):super().__init__();self.items=[];self.setContentsMargins(0,0,0,0);self.setSpacing(10)
    def addItem(self,item):self.items.append(item)
    def insertWidget(self,index,widget):self.addChildWidget(widget);self.items.insert(index,QWidgetItem(widget));self.invalidate()
    def count(self):return len(self.items)
    def itemAt(self,index):return self.items[index] if 0<=index<len(self.items) else None
    def takeAt(self,index):return self.items.pop(index) if 0<=index<len(self.items) else None
    def expandingDirections(self):return Qt.Orientations(Qt.Horizontal)
    def hasHeightForWidth(self):return True
    def heightForWidth(self,width):return self.arrange(QRect(0,0,width,0),True)
    def setGeometry(self,rect):super().setGeometry(rect);self.arrange(rect,False)
    def sizeHint(self):return self.minimumSize()
    def minimumSize(self):
        size=QSize()
        for item in self.items:size=size.expandedTo(item.minimumSize())
        return size
    def arrange(self,rect,measure):
        x=rect.x();y=rect.y();height=0;gap=self.spacing()
        for item in self.items:
            size=item.sizeHint().expandedTo(item.minimumSize());width=min(size.width(),max(1,rect.width()))
            if x>rect.x() and x+width>rect.right()+1:x=rect.x();y+=height+gap;height=0
            if not measure:item.setGeometry(QRect(x,y,width,size.height()))
            x+=width+gap;height=max(height,size.height())
        return y+height-rect.y()
