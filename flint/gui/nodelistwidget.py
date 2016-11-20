#!/usr/bin/env python3
#
# Copyright (C) 2015, 2016 Justas Lavišius
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from PyQt5.QtCore import Qt, QSize, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import (QAbstractItemView, QAction, QCheckBox, 
    QGroupBox, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, 
    QMessageBox, QPushButton, QToolBar, QVBoxLayout, QWidget)
from PyQt5.QtGui import QIcon, QPalette
from flint.glob import FlGlob, elidestring
from flint.gui.style import FlPalette
from collections import OrderedDict

class SearchWidget (QWidget):
    searched = pyqtSignal()
    
    def __init__ (self, parent):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self.inputline = QLineEdit(self)
        self.inputline.editingFinished.connect(self.search)
        self.inputline.setPlaceholderText("Search")
        searchbutton = QPushButton(self)
        searchbutton.setIcon(QIcon.fromTheme("edit-find"))
        searchbutton.setToolTip("Search")
        searchbutton.clicked.connect(self.search)
        advbutton = QPushButton(self)
        advbutton.setIcon(QIcon.fromTheme("preferences-other"))
        advbutton.setToolTip("Search Fields")
        advbutton.clicked.connect(self.advancedpopup)
        
        self.popup = None
        self.fields = {"text": True}
        
        checks = OrderedDict()
        checks["Text"] = (("Text", "text"), ("Speaker", "speaker"), ("Listener", "listener"))
        checks["Enter Scripts"] = (("Function name", "entername"), ("Arguments", "enterarg"))
        checks["Exit Scripts"] = (("Function name", "exitname"), ("Arguments", "exitarg"))
        checks["Condition"] = (("Function name", "condname"), ("Arguments", "condarg"))
        checks["Properties"] = (("Persistence", "persistence"), ("Bank mode", "bankmode"), ("Question hub", "questionhub"), ("Random weight", "randweight"), ("Comment", "comment"))
        
        popup = QWidget(FlGlob.mainwindow, Qt.Dialog)
        popup.setWindowTitle("Fields")
        poplayout = QVBoxLayout(popup)
        for group in checks.keys():
            box = QGroupBox(group, popup)
            boxlayout = QVBoxLayout(box)
            for label, field in checks[group]:
                check = QCheckBox(label, box)
                check.stateChanged.connect(self.adv_factory(field))
                if field in self.fields:
                    check.setChecked(self.fields[field])
                boxlayout.addWidget(check)
            boxlayout.addStretch()
            poplayout.addWidget(box)
        self.popup = popup
        
        layout.addWidget(self.inputline)
        layout.addWidget(searchbutton)
        layout.addWidget(advbutton)
    
    def search (self):
        palette = QPalette()
        defbase = palette.color(QPalette.Base)
        deftext = palette.color(QPalette.Text)
        query = self.inputline.text().casefold()
        view = self.parent().view
        if view is not None:
            view.search(query, self.fields)
            self.searched.emit()
            
            if view.hits is None:
                palette.setColor(QPalette.Base, defbase)
                palette.setColor(QPalette.Text, deftext)
            elif view.hits:
                palette.setColor(QPalette.Base, FlPalette.hit)
                palette.setColor(QPalette.Text, FlPalette.dark)
            else:
                palette.setColor(QPalette.Base, FlPalette.miss)
                palette.setColor(QPalette.Text, FlPalette.dark)
            self.inputline.setPalette(palette)
    
    def adv_factory (self, field):
        def adv (state):
            self.fields[field] = bool(state)
        return adv
    
    @pyqtSlot()
    def advancedpopup (self):
        self.popup.setVisible(not self.popup.isVisible())

class NodeListItem (QListWidgetItem):
    IDRole = Qt.UserRole + 1
    TrashRole = Qt.UserRole + 2
    
    def __lt__ (self, other):
        return self.data(self.IDRole) < other.data(self.IDRole)

class NodeListWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.search = SearchWidget(self)
        self.search.searched.connect(self.populatelist)
        
        self.nodelist = QListWidget(self)
        self.nodelist.setSortingEnabled(True)
        self.nodelist.setIconSize(QSize(*(FlGlob.mainwindow.style.boldheight,)*2))
        self.nodelist.currentItemChanged.connect(self.selectnode)
        self.nodelist.itemSelectionChanged.connect(self.onselectionchange)
        self.nodelist.itemActivated.connect(self.activatenode)
        self.nodelist.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        remwidget = QToolBar(self)
        remselected = QAction("Remove Selected", self)
        remselected.setIcon(QIcon.fromTheme("edit-delete"))
        remselected.setToolTip("Remove selected")
        remselected.triggered.connect(self.remselected)
        self.remselaction = remselected
        remtrash = QAction("Remove Trash", self)
        remtrash.setIcon(QIcon.fromTheme("edit-clear"))
        remtrash.setToolTip("Clear all trash")
        remtrash.triggered.connect(self.remtrash)
        self.remtrashaction = remtrash
        remwidget.addAction(remselected)
        remwidget.addAction(remtrash)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.nodelist)
        layout.addWidget(remwidget)
        self.view = None
        self.active = False
        self.setEnabled(False)
    
    @pyqtSlot()
    def setview (self):
        self.view = FlGlob.mainwindow.activeview
        if self.view is None:
            self.setEnabled(False)
            self.active = False
        else:
            self.setEnabled(True)
            self.active = True
        self.populatelist()
    
    @pyqtSlot()
    def populatelist (self):
        self.index = dict()
        self.nodelist.clear()
        if not self.active:
            return
        nodecont = self.view.nodecontainer.nodes
        for nodeID, nodeobj in nodecont.items():
            if self.view.hits is not None and nodeID not in self.view.hits:
                continue
            listitem = self.listitem(self.view, nodeobj, nodeID)
            self.nodelist.addItem(listitem)
            self.index[nodeID] = listitem
        self.remtrashaction.setEnabled(bool(self.view.trash))
    
    @pyqtSlot(str)
    def selectbyID (self, nodeID):
        if not self.active:
            return
        if nodeID in self.index:
            self.nodelist.setCurrentItem(self.index[nodeID])
    
    def listitem (self, view, nodeobj, nodeID):
        typename = nodeobj.typename
        if   typename == "root":
            descr = ""
        elif typename == "bank":
            descr = "(%s) %s" % (nodeobj.bankmode, ", ".join(nodeobj.subnodes))
        elif typename == "talk":
            descr = "[%s]" % elidestring(nodeobj.text, 30)
        elif typename == "response":
            descr = "[%s]" % elidestring(nodeobj.text, 30)
        else:
            descr = ""
        
        label = "%s: %s %s" % (nodeID, typename, descr) 
        if nodeID in view.trash:
            trash = True
            icon = QIcon.fromTheme("user-trash")
        else:
            trash = False
            icon = QIcon.fromTheme("text-x-generic")
        item = NodeListItem(icon, label)
        item.setData(item.IDRole, int(nodeID))
        item.setData(item.TrashRole, trash)
        return item
    
    @pyqtSlot(QListWidgetItem, QListWidgetItem)
    def selectnode (self, listitem, olditem):
        if listitem is None:
            return
        window = FlGlob.mainwindow
        view = window.activeview
        nodeID = str(listitem.data(listitem.IDRole))
        window.setselectednode(view, nodeID)
    
    @pyqtSlot()
    def onselectionchange (self):
        selected = self.nodelist.selectedItems()
        seltrash = [item for item in selected if item.data(item.TrashRole)]
        self.remselaction.setEnabled(bool(seltrash))
    
    @pyqtSlot(QListWidgetItem)
    def activatenode (self, listitem):
        window = FlGlob.mainwindow
        view = window.activeview
        nodeID = str(listitem.data(listitem.IDRole))
        window.setactivenode(view, nodeID)
    
    @pyqtSlot()
    def remselected (self):
        selected = self.nodelist.selectedItems()
        seltrash = [item for item in selected if item.data(item.TrashRole)]
        answer = QMessageBox.question(self, "Node removal", 
            "Permanently remove selected trash nodes (%s)?\n\nThis will also clear the undo action list." % len(seltrash))
        if answer == QMessageBox.No:
            return
        self.view.removenodes([str(item.data(item.IDRole)) for item in selected])
        self.remselaction.setEnabled(False)
    
    @pyqtSlot()
    def remtrash (self):
        count = len(self.view.trash)
        answer = QMessageBox.question(self, "Node removal", 
            "Permanently remove all (%s) trash nodes?\n\nThis will also clear the undo action list." % count)
        if answer == QMessageBox.No:
            return
        self.remtrashaction.setEnabled(False)
        self.view.removetrash()
