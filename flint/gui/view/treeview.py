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

from PyQt5.QtCore import Qt, QRectF, pyqtSlot
from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene)
from PyQt5.QtGui import QPainter
from PyQt5.QtOpenGL import (QGL, QGLFormat, QGLWidget)
from flint.gui.style import FlPalette
from flint.glob import (FlGlob, log)
from flint.gui.view.nodeitems import (TalkNodeItem, ResponseNodeItem, 
	BankNodeItem, RootNodeItem, TriggerNodeItem)
from flint.gui.view.frameitem import FrameItem
from flint.gui.view.edgeitem import EdgeItem
from flint.tree_editor import TreeEditor
import os
import gc
from collections import deque


class TreeView (TreeEditor, QGraphicsView):
    __types = {'talk': TalkNodeItem, 'response': ResponseNodeItem, 
        'bank': BankNodeItem, 'root': RootNodeItem, 'trigger': TriggerNodeItem}
    
    def __init__ (self, nodecontainer, parent=None):
        TreeEditor.__init__(self, nodecontainer)
        QGraphicsView.__init__(self, parent)
        self.zoomscale = 1
        self.activenode = None
        self.selectednode = None
        self.playmode = False
        self.itemtable = dict()
        self.itemindex = dict()
        
        self.setOptimizationFlags(QGraphicsView.DontAdjustForAntialiasing | QGraphicsView.DontSavePainterState)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        """OPTIONS: OpenGL rendering; FullViewportUpdate; MinimalViewportUpdate"""
        self.setViewport(QGLWidget(QGLFormat(QGL.SampleBuffers)))
        #self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        #self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        
        scene = QGraphicsScene(self)
        scene.setBackgroundBrush(FlPalette.bg)
        self.viewframe = FrameItem(view=self)
        scene.addItem(self.viewframe)
        self.setScene(scene)
        
        self.style = FlGlob.mainwindow.style
        
        self.updateview(refresh=True)
        self.setselectednode(self.treeroot())
    
    def updateview (self, refresh=False):
        if refresh:
            for ID in self.nodeorder:
                self.nodeorder[ID] = None
        self.constructed = False
        self.updatedocs()
        self.traverse()
        self.constructed = self.applychanges()
        for child in self.treeroot().childlist():
            child().setrank(self.treeroot())
        self.updatelayout()
        FlGlob.mainwindow.viewUpdated.emit()
        
        self.setactivenode(self.activenode)
        self.setselectednode(self.selectednode)
    
    def applychanges (self):
        funcs = {"newitem": self.newitem, "reparent": self.reparent, 
            "removeitem": self.removeitem, "setstate": self.setstate}
        while self.changes:
            change = self.changes.popleft()
            funcs[change[0]](*change[1])
        return True
    
    def newitem (self, fullID, state):
        log("verbose", "%s.newitem(%s, %s)" % (self, fullID, state))
        fromID, toID = fullID
        parent = self.itembyID(fromID)
        nodeobj = self.nodecontainer.nodes[toID]
        scene = self.scene()
        nodeitem = self.__types[nodeobj.typename](nodeobj, parent=parent, view=self, state=state)
        scene.addItem(nodeitem)
        if not nodeitem.issubnode():
            edgeitem = EdgeItem(nodeitem)
            scene.addItem(edgeitem)
        
        if toID in self.itemindex:
            if state == 1:
                self.itemindex[toID].insert(0, nodeitem)
            else:
                self.itemindex[toID].append(nodeitem)
        else:
            self.itemindex[toID] = [nodeitem]
        
        if self.itembyfullID(fullID):
            self.removeitem(fullID)
        self.tableitem(fullID, nodeitem)
    
    def reparent (self, oldID, newID):
        log("verbose", "%s.reparent(%s, %s)" % (self, oldID, newID))
        fromID, toID = newID
        oldref = oldID[0]
        newparent = self.itembyID(fromID)
        nodeitem = self.itemtable[oldref].pop(toID)
        self.tableitem(newID, nodeitem)
        nodeitem.refID = fromID
        nodeitem.setrank(newparent)
    
    def removeitem (self, fullID):
        log("verbose", "%s.removeitem(%s)" % (self, fullID))
        fromID, toID = fullID
        nodeitem = self.itemtable[fromID].pop(toID)
        edgeitem = nodeitem.edge
        self.itemindex[toID].remove(nodeitem)
        if not self.itemindex[toID]:
            self.itemindex.pop(toID)
        scene = self.scene()
        scene.removeItem(nodeitem)
        if edgeitem is not None:
            scene.removeItem(edgeitem)
            edgeitem.source = None
            nodeitem.edge = None
        if self.activenode is nodeitem:
            self.activenode = None
        if self.selectednode is nodeitem:
            self.selectednode = None
        nodeitem = None
        edgeitem = None
        gc.collect()
    
    def setstate (self, fullID, state):
        log("verbose", "%s.stestate(%s, %s)" % (self, fullID, state))
        fromID, toID = fullID
        nodeitem = self.itemtable[fromID][toID]
        if state == 1:
            index = self.itemindex[toID]
            i = self.itemindex[toID].index(nodeitem)
            index[0], index[i] = index[i], index[0]
        nodeitem.setstate(state)
    
    def tableitem (self, fullID, nodeitem):
        fromID, toID = fullID
        table = self.itemtable
        if fromID not in table:
            table[fromID] = dict()
        table[fromID][toID] = nodeitem
    
    def itembyID (self, nodeID):
        if nodeID in self.itemindex:
            return self.itemindex[nodeID][0]
        else:
            return None #EXCEPTION
    
    def itembyfullID (self, fullID):
        fromID, toID = fullID
        if fromID in self.itemtable and toID in self.itemtable[fromID]:
            return self.itemtable[fromID][toID]
        else:
            return None
    
    def treeroot (self):
        return self.itembyID("0")
    
    def updatelayout (self):
        if not self.constructed:
            return
        root = self.treeroot()
        root.treeposition()
        self.updatescenerect(root)
    
    def updatescenerect (self, root):
        top, bottom, depth = root.subtreesize(-1)
        height = abs(bottom - top)
        rank = self.style.rankwidth
        row = self.style.rowgap
        self.setSceneRect(QRectF(-rank/2, top-row/2, depth*(rank+0.5), height+row))
    
    def zoomstep (self, step):
        self.zoomview(1.1 ** step)
    
    def zoomfixed (self, scale):
        ratio = scale / self.zoomscale
        self.zoomview(ratio)
        
    def zoomview (self, ratio):
        totalzoom = min(2, max(0.05, self.zoomscale*ratio)) # OPTION: zoom limits
        ratio = totalzoom / self.zoomscale
        self.scale(ratio, ratio)
        self.zoomscale = totalzoom
    
    def shownode (self, nodeitem):
        if nodeitem is None:
            return
        self.ensureVisible(nodeitem, self.style.rankgap/2, self.style.rowgap/2)
    
    def setselectednode (self, nodeitem):
        log("verbose", "%s.setselectednode(%s)" % (self, nodeitem))
        if nodeitem is not None:
            if self.selectednode:
                self.selectednode.setselected(False)
            self.selectednode = nodeitem
            self.selectednode.setselected(True)
            nodeID = nodeitem.realid()
        else:
            nodeID = "-1"
        FlGlob.mainwindow.setselectednode(self, nodeID)
    
    @pyqtSlot(str)
    def selectbyID (self, nodeID):
        if FlGlob.mainwindow.activeview is not self:
            return
        log("verbose", "%s.selectbyID(%s)" % (self, nodeID))
        if self.playmode:
            return
        if self.selectednode is not None and self.selectednode.realid() == nodeID:
            self.shownode(self.selectednode)
            return
        
        if nodeID in self.itemindex:
            nodeitem = self.itembyID(nodeID)
            if self.selectednode:
                self.selectednode.setselected(False)
            self.selectednode = nodeitem
            self.selectednode.setselected(True)
            self.shownode(self.selectednode)
        else:
            if self.selectednode is not None:
                self.selectednode.setselected(False)
                self.selectednode = None
    
    def setactivenode (self, nodeitem):
        log("verbose", "%s.setactivenode(%s)" % (self, nodeitem))
        if nodeitem is not None:
            nodeID = nodeitem.realid()
        else:
            nodeID = "-1"
        FlGlob.mainwindow.setactivenode(self, nodeID)
    
    @pyqtSlot(str)
    def activatebyID (self, nodeID):
        if FlGlob.mainwindow.activeview is not self:
            return
        log("verbose", "%s.activatebyID(%s)" % (self, nodeID))
        if self.playmode:
            return
        if nodeID in self.itemindex:
            nodeitem = self.itembyID(nodeID)
            if self.activenode:
                self.activenode.setactive(False)
            self.activenode = nodeitem
            self.activenode.setactive(True)
        else:
            if self.activenode is not None:
                self.activenode.setactive(False)
                self.activenode = None
    
    def callupdates (self, nodeID, funcname):
        if nodeID in self.itemindex:
            for nodeitem in self.itemindex[nodeID]:
                func = getattr(nodeitem, funcname, None)
                if func is not None:
                    func()
    
    def setplaymode (self, playmode):
        self.playmode = playmode
        for item in (i for items in self.itemindex.values() for i in items):
            item.setplaymode(playmode)
            item.setactive(False)
    
    @pyqtSlot(str)
    def playshowID (self, nodeID):
        if nodeID in self.itemindex:
            for nodeitem in self.itemindex[nodeID]:
                nodeitem.setplaymode(False)
    
    @pyqtSlot(str)
    def playvisitID (self, nodeID):
        if nodeID in self.itemindex:
            for nodeitem in self.itemindex[nodeID]:
                nodeitem.setactive(True)
                self.shownode(nodeitem)
    
    def linknode (self, nodeID, refID, pos=None, undo=False):
        super().linknode(nodeID, refID, pos, undo)
        if not undo:
            self.updateview()
    
    def addnode (self, nodeID, typename="", ndict=None, undo=False):
        newid = super().addnode(nodeID, typename, ndict, undo)
        if not undo:
            self.updateview()
            self.shownode(self.itembyID(newid))
    
    def addsubnode (self, nodeID, typename="", ndict=None, undo=False):
        newid = super().addsubnode(nodeID, typename, ndict, undo)
        if not undo:
            self.updateview()
            self.shownode(self.itembyID(newid))
    
    def changebanktype (self, bankID, banktype):
        super().changebanktype(bankID, banktype)
        self.callupdates(bankID, "updatebanktype")
    
    def unlink (self, nodeID, refID, undo=False):
        super().unlink(nodeID, refID, undo)
        if not undo:
            self.updateview()
    
    def unlinksubnode (self, subID, bankID, undo=False):
        super().unlinksubnode(subID, bankID, undo)
        if not undo:
            self.updateview()
    
    def unlink_inherit (self, nodeID, refID, undo=False):
        super().unlink_inherit(nodeID, refID, undo)
        if not undo:
            self.updateview()
    
    def move (self, nodeID, refID, up, undo=False):
        super().move(nodeID, refID, up, undo)
        if not undo:
            self.updateview()
    
    def parentswap (self, gpID, parID, nodeID, pos=None, undo=False):
        super().parentswap(gpID, parID, nodeID, pos, undo)
        if not undo:
            self.updateview()
    
    def nodetobank (self, nodeID, subID=None, undo=False):
        if nodeID in self.itemindex:
            for item in self.itemindex[nodeID]:
                fullID = item.id()
                self.nodeorder[fullID] = None
                for ref in self.itemindex[item.refID]:
                    ref.linkIDs = None
        super().nodetobank(nodeID, subID, undo)
        if not undo:
            self.updateview()
    
    def banktonode (self, nodeID, undo=False):
        if nodeID in self.itemindex:
            for item in self.itemindex[nodeID]:
                fullID = item.id()
                self.nodeorder[fullID] = None
                for ref in self.itemindex[item.refID]:
                    ref.linkIDs = None
        subID = self.nodecontainer.nodes[nodeID].subnodes[0]
        subitem = self.itembyID(subID)
        subitems = deque()
        subitems.append(subitem)
        while subitems:
            subitem = subitems.popleft()
            if subitem is None:
                continue
            self.nodeorder[subitem.id()] = None
            for subID in subitem.nodeobj.subnodes:
                subitems.append(self.itembyID(subID))
        super().banktonode(nodeID, undo)
        if not undo:
            self.updateview()
    
    def splitnode (self, nodeID, splitID=None, undo=False):
        super().splitnode(nodeID, splitID, undo)
        if not undo:
            self.updateview()
    
    def collapse (self, fullID, collapse=None):
        super().collapse(fullID, collapse)
        self.updateview()
    
    def removenodes (self, nodeIDs):
        copied = FlGlob.mainwindow.copiednode
        copied.ID = None
        copied.view = copied.blank
        super().removenodes(nodeIDs)
        self.updateview()
    
    def removetrash (self):
        copied = FlGlob.mainwindow.copiednode
        copied.ID = None
        copied.view = copied.blank
        super().removetrash()
        self.updateview()
    
    def wheelEvent (self, event):
        mod = event.modifiers()
        if mod == Qt.ControlModifier:
            delta = event.angleDelta().y()
            step = delta/120
            self.zoomstep(step) 
        else:
            super().wheelEvent(event)
    
    def keyPressEvent (self, event):
        key = event.key()
        mod = event.modifiers()
        node = self.selectednode
        if node is None:
            return
        if key == Qt.Key_Left:
            if node.refID:
                self.setselectednode(self.itembyID(node.refID))
        elif key == Qt.Key_Up:
            sib = node.siblingabove()
            if sib:
                self.setselectednode(sib)
        elif key == Qt.Key_Down:
            sib = node.siblingbelow()
            if sib:
                self.setselectednode(sib)
        elif key == Qt.Key_Right:
            if mod & Qt.ControlModifier and node.nodeobj.typename == "bank":
                sublist = node.sublist()
                if sublist:
                    subnode = sublist[0]
                    self.setselectednode(subnode)
            else:
                children = node.childlist()
                count = len(children)-1
                if children:
                    self.setselectednode(children[count//2]())
        elif key == Qt.Key_Enter or key == Qt.Key_Return:
            if self.selectednode:
                self.setactivenode(self.selectednode)
        else:
            super().keyPressEvent(event)
    
    def __repr__ (self):
        return "<%s %s>" % (type(self).__name__, 
            os.path.basename(self.nodecontainer.filename) or
            self.nodecontainer.name)
