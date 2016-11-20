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

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import (QAbstractItemView, QToolBar, QTreeWidget, 
	QTreeWidgetItem, QVBoxLayout, QWidget)
from PyQt5.QtGui import QIcon
from flint.glob import FlGlob, log
import os

class ProjectWidget (QWidget):
    ProjType = QTreeWidgetItem.UserType + 1
    ConvType = QTreeWidgetItem.UserType + 2
    
    def __init__ (self, parent):
        super().__init__(parent)
        self.tree = QTreeWidget(self)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setColumnCount(2)
        self.tree.setColumnHidden(1, True)
        self.tree.setHeaderLabels(("Name", "Path"))
        self.tree.itemActivated.connect(self.onactivate)
        
        window = FlGlob.mainwindow
        actions = QToolBar(self)
        actions.addAction(window.globactions["newconv"])
        actions.addAction(window.globactions["reloadscripts"])
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        layout.addWidget(actions)
    
    def currentproj (self):
        sel = self.tree.selectedItems()
        if not sel:
            return None
        else:
            return self.getitemroot(sel[0]).data(1, 0)
    
    @pyqtSlot(str)
    def addproject (self, path, pos=None):
        window = FlGlob.mainwindow
        proj = window.projects[path]
        if proj.name:
            projname = proj.name
        else:
            projname = os.path.basename(os.path.splitext(path)[0])
        root = QTreeWidgetItem((projname, path), self.ProjType)
        root.setIcon(0, QIcon.fromTheme("package-generic"))
        root.setToolTip(0, path)
        if pos is None:
            self.tree.addTopLevelItem(root)
        else:
            self.tree.insertTopLevelItem(pos, root)
        root.setExpanded(True)
        
        for relpath in proj.convs + proj.tempconvs:
            abspath = proj.checkpath(relpath)
            if relpath in window.convs: # temp
                cont = window.convs[relpath]().nodecontainer
                name = cont.name
                loaded = cont.proj is proj
            elif abspath in window.convs: # saved
                cont = window.convs[abspath]().nodecontainer
                name = cont.name
                loaded = cont.proj is proj
            else: # not loaded
                if relpath in proj.tempconvs: # closed temp
                    proj.tempconvs.remove(relpath)
                    continue
                name = os.path.basename(relpath)
                loaded = False
            conv = QTreeWidgetItem((name, relpath), self.ConvType)
            if loaded:
                conv.setIcon(0, QIcon.fromTheme("folder-open"))
            else:
                conv.setIcon(0, QIcon.fromTheme("folder"))
                conv.setFont(0, window.style.italicfont)
            conv.setToolTip(0, relpath)
            root.addChild(conv)
    
    @pyqtSlot(str)
    def updateproject (self, path):
        log("debug", "updateproject %s" % path)
        count = self.tree.topLevelItemCount()
        item = None
        for i in range(count):
            item = self.tree.topLevelItem(i)
            if item.data(1, 0) == path:
                self.tree.takeTopLevelItem(i)
                self.addproject(path, i)
                break
    
    @pyqtSlot(QTreeWidgetItem, int)
    def onactivate (self, item, column):
        window = FlGlob.mainwindow
        if item.type() == self.ConvType:
            projfile = item.parent().data(1, 0)
            window.openconv(projfile, item.data(1, 0))
    
    def getitemroot (self, item):
        while item.type() != self.ProjType:
            item = item.parent()
        return item
    
    @pyqtSlot()
    def newconv (self):
        window = FlGlob.mainwindow
        item = self.getitemroot(self.tree.currentItem())
        path = item.data(1, 0)
        proj = window.projects[path]
        tempID = window.newtempID()
        proj.tempconvs.append(tempID)
        window.newconv(proj, tempID)
