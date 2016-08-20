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

import sys
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtOpenGL import *
import conv_parser as cp
import proj_parser as pp
import conv_player as play
import os
import weakref
import inspect as insp
from collections import deque, OrderedDict
import gc

def log (level, text):
    if level not in FlGlob.loglevels:
        print("[warn] Unknown loglevel: %s" % level)
        level = "warn"
    if FlGlob.loglevels[level] <= FlGlob.loglevel:
        print("[%s] %s" % (level, text))
        if level == "warn":
            QMessageBox.warning(FlGlob.mainwindow, "Warning", text)
        elif level == "error":
            QMessageBox.critical(FlGlob.mainwindow, "Error", text)

class FlGlob:
    loglevels = {"quiet": 0, "error": 1, "warn": 2, "info": 3, "debug": 4, "verbose": 5}
    loglevel = 3
    mainwindow = None

class FlPalette (object):
    """Palette of custom colors for quick reference."""
    dark    = QColor( 38,  39,  41) # shadows, node text
    light   = QColor(250, 250, 250) # highlights, node labels
    hl1var  = QColor(255, 121,  13) # talk active
    hl1     = QColor(224, 111,  19) # talk normal
    hl2var  = QColor(102, 183, 204) # response active
    hl2     = QColor(108, 158, 171) # response normal
    bankvar = QColor(134, 179, 156) # bank active
    bank    = QColor(130, 150, 140) # bank normal
    rootvar = QColor(153, 153, 153) # root active
    root    = QColor(128, 128, 128) # root normal
    trigvar = QColor(181, 219,  29) # trigger active
    trig    = QColor(172, 204,  42) # trigger normal
    bg      = QColor( 90,  94,  98) # scene, bank background
    hit     = QColor(120, 255, 180) # search input BG on hit
    miss    = QColor(255, 150, 150) # search input BG on miss

class FlNodeStyle (object):    
    def __init__ (self, font):
        basefont = font
        boldfont = QFont(basefont)
        boldfont.setBold(True)
        italicfont = QFont(basefont)
        italicfont.setItalic(True)
        self.basefont = basefont
        self.boldfont = boldfont
        self.italicfont = italicfont
        
        basemetrics = QFontMetrics(basefont)
        self.basemetrics = basemetrics
        baseem = basemetrics.height()
        baseen = baseem // 2
        
        boldmetrics = QFontMetrics(boldfont)
        self.boldheight = boldmetrics.height()
        
        nodemargin = baseen*3//5
        itemmargin = baseen//2
        activemargin = baseen*3//4
        selectmargin = activemargin//2
        self.nodemargin = nodemargin
        self.itemmargin = itemmargin
        self.activemargin = activemargin
        self.selectmargin = selectmargin
        self.shadowoffset = selectmargin
        
        self.nodemargins = QMarginsF(*(nodemargin,)*4)
        self.banknodemargins = QMarginsF(*(nodemargin//2,)*4)
        self.itemmargins = QMarginsF(*(itemmargin,)*4)
        self.activemargins = QMarginsF(*(selectmargin//2,)*4)
        self.selectmargins = QMarginsF(*(selectmargin//2,)*4)
        
        self.nodetextwidth = basemetrics.averageCharWidth()*40
        
        nodewidth = self.nodetextwidth + 2*(activemargin+nodemargin+itemmargin)
        self.nodewidth = nodewidth
        
        rankgap = 7*activemargin
        self.rankgap = rankgap
        self.rankwidth = rankgap + nodewidth
        
        rowgap = 3*activemargin
        self.rowgap = rowgap
        
        # Edge style
        self.pensize = self.shadowoffset
        self.arrowsize = self.pensize * 3.5

class QGraphicsRectItemCond (QGraphicsRectItem):
    def __init__ (self, parent=0, cond=None):
        super().__init__(parent)
        self.cond = cond
    
    def paint (self, painter, style, widget):
        if widget is self.cond:
            super().paint(painter, style, widget)

class QGraphicsSimpleTextItemCond (QGraphicsSimpleTextItem):
    def __init__ (self, parent=0, cond=None):
        super().__init__(parent)
        self.cond = cond
    
    def paint (self, painter, style, widget):
        if widget is self.cond:
            super().paint(painter, style, widget)

class QGraphicsTextItemCond (QGraphicsTextItem):
    def __init__ (self, parent=0, cond=None):
        super().__init__(parent)
        self.cond = cond
    
    def paint (self, painter, style, widget):
        if widget is self.cond:
            super().paint(painter, style, widget)

class QGraphicsPixmapItemCond (QGraphicsPixmapItem):
    def __init__ (self, pixmap, parent, cond=None):
        super().__init__(pixmap, parent)
        self.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)
        self.cond = cond
    
    def paint (self, painter, style, widget):
        if widget is self.cond:
            super().paint(painter, style, widget)

class NodeItem(QGraphicsItem):
    def __init__ (self, nodeobj, parent=None, view=None, state=1):
        super().__init__()
        self.edge = None
        self.linkIDs = None
        self.children = None
        self.childpos = None
        self.nodeobj = nodeobj
        self.style = FlGlob.mainwindow.style
        self.view = weakref.proxy(view)
        self.refID = parent.realid() if parent is not None else None
        self.state = state
        self.setrank(parent)
        self.setCursor(Qt.ArrowCursor)
        self.yoffset = 0
        self.graphicsetup()
        self.setstate(state)
    
    def id (self):
        return (self.refID, self.nodeobj.ID)
    
    def realid (self):
        return self.nodeobj.ID
    
    def childlist (self, generate=False):
        ID = self.nodeobj.ID
        itemtable = self.view.itemtable
        if self.state == 1 and ID in itemtable and not self.iscollapsed():
            if self.children and self.nodeobj.linkIDs == self.linkIDs and None not in [c() for c in self.children]:
                ret = self.children
            else:
                children = []
                for child in self.nodeobj.linkIDs:
                    if child in itemtable[ID]:
                        item = itemtable[ID][child]
                    else:
                        continue
                    children.append(weakref.ref(item))
                self.linkIDs = self.nodeobj.linkIDs.copy()
                self.children = children
                ret = children
        else:
            ret = []
        if generate:
            x = self.x()
            y = self.y()
            self.childpos = []
            for target in ret:
                t = target()
                self.childpos.append((t.x()+t.boundingRect().left()-self.style.activemargin-x, t.y()-y))
            if self.edge:
                if self.childpos != self.edge.childpos:
                    self.edge.prepareGeometryChange()
                    self.edge.sourceright = self.boundingRect().right()
                    self.edge.update(self.edge.boundingRect())
        return ret
    
    def setedge (self, edge):
        self.edge = edge
        edge.setX(self.x())
    
    def setactive (self, active):
        if active:
            self.activebox.show()
            self.mainbox.setBrush(QBrush(self.altcolor))
        else:
            self.activebox.hide()
            self.mainbox.setBrush(QBrush(self.maincolor))
    
    def setselected (self, selected):
        if selected:
            self.selectbox.show()
        else:
            self.selectbox.hide()
    
    def setstate (self, state):
        self.state = state
        if state == 1: # normal
            self.show()
            self.graphgroup.setOpacity(1)
            self.shadowbox.show()
        elif state == 0: # ghost
            self.show()
            self.graphgroup.setOpacity(0.7)
            self.shadowbox.hide()
        elif state == -1: # hidden
            self.hide()
    
    def setplaymode (self, playmode):
        if playmode:
            self.setOpacity(0.5)
        else:
            self.setOpacity(1)
    
    def setY (self, y):
        parent = self.view.itembyID(self.refID)
        y += self.getyoffset()
        if self.edge is not None:
            self.edge.setY(y)
        super().setY(y)
    
    def setrank (self, parent):
        if parent is None:
            return
        if self.issubnode():
            x = parent.x()
            self.setX(x)
        else:
            x = parent.x()+self.style.rankwidth
            self.setX(x)
            self.nudgechildren()
        if self.edge is not None:
            self.edge.setX(x)
    
    def nudgechildren (self):
        for child in self.childlist():
            child().setrank(self)
    
    def getyoffset (self):
        if self.nodeobj.nodebank == -1:
            return self.yoffset
        else:
            return self.view.itembyID(self.refID).getyoffset() + self.yoffset
    
    def hide (self):
        super().hide()
        if self.edge:
            self.edge.hide()
    
    def show (self):
        super().show()
        if self.edge:
            self.edge.show()
    
    def issubnode (self):
        return self.nodeobj.nodebank is not -1
    
    def isghost (self):
        return not self.state
    
    def realnode (self):
        return self.view.itembyID(self.nodeobj.ID)
    
    def isactive (self):
        return self.view.activenode is self
    
    def isselected (self):
        return self.view.selectednode is self
    
    def iscollapsed (self):
        return self.id() in self.view.collapsednodes
    
    def y_top (self):
        return self.y() - self.boundingRect().height()//2
    
    def y_bottom (self):
        return self.y() + self.boundingRect().height()//2
    
    def bulkshift (self, children, diff):
        self.setY(self.y() + diff)
        if children is None:
            children = [c() for c in self.childlist()]
        for child in children:
            child.bulkshift(None, diff)
    
    def treeposition (self, ranks=None):
        if ranks is None:
            ranks = dict()
        localranks = dict()
        children = [c() for c in self.childlist()]
        for child in children:
            localranks = child.treeposition(localranks)
        rank = self.x() // self.style.rankwidth
        if children:
            top = children[0].y_top()
            bottom = children[-1].y_bottom()
            self.setY((top+bottom)//2)
        localranks[rank] = [self.y_top, self.y_bottom]
        streeshift = None
        for r in localranks:
            if r in ranks:
                rankshift = ranks[r][1]() + self.style.rowgap - localranks[r][0]()
                if streeshift is None or rankshift > streeshift:
                    streeshift = rankshift
                ranks[r][1] = localranks[r][1]
            else:
                ranks[r] = localranks[r]
        if streeshift:
            self.bulkshift(children, streeshift)
        return ranks
    
    def siblings (self):
        if self.refID is None:
            return None
        parent = self.view.nodecontainer.nodes[self.refID]
        if self.issubnode():
            return parent.subnodes
        else:
            return parent.linkIDs
    
    def siblingabove (self):
        sibs = self.siblings()
        if sibs is None or self.nodeobj.ID not in sibs:
            return None
        myindex = sibs.index(self.nodeobj.ID)
        if myindex:
            sibID = (self.refID, sibs[myindex-1])
            return self.view.itembyfullID(sibID)
        else:
            return None
    
    def siblingbelow (self):
        sibs = self.siblings()
        if sibs is None or self.nodeobj.ID not in sibs:
            return None
        myindex = sibs.index(self.nodeobj.ID)
        if len(sibs) > myindex+1:
            sibID = (self.refID, sibs[myindex+1])
            return self.view.itembyfullID(sibID)
        else:
            return None
    
    def subtreesize (self, depth=-1):
        """Find vertical extents of a subtree.
        
        Returns min/max y coordinates up to given depth (negative depth means
        whole subtree)."""

        # calculate child positions for EgdeItem only once when calculating scenerect
        if depth<0:
            generate = True
        else:
            generate = False
        
        children = [c() for c in self.childlist(generate=generate)]
        maxdepth = abs(depth)
        if children and depth:
            nextdepth = depth-1
            ymin = self.y_top()
            ymax = self.y_bottom()
            for child in children:
                top, bottom, depth = child.subtreesize(nextdepth)
                ymin = min(ymin, top)
                ymax = max(ymax, bottom)
                maxdepth = max(maxdepth, depth)
        else:
            ymin = self.y_top()
            ymax = self.y_bottom()
        return ymin, ymax, maxdepth
        
    def boundingRect (self):
        return self.rect
    
    def paint (self, painter, style, widget):
        pass
    
    def pixmap (self, path):
        return QPixmap(path).scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
    
    def graphicsetup (self):
        lightbrush = QBrush(FlPalette.light)
        mainbrush = QBrush(self.maincolor)
        altbrush = QBrush(self.altcolor)
        nopen = QPen(0)
        viewport = self.view.viewport()
        
        self.graphgroup = QGraphicsItemGroup(self)
        self.fggroup = QGraphicsItemGroup(self)
        
        self.shadowbox = QGraphicsRectItem(self)
        self.shadowbox.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.shadowbox.setBrush(FlPalette.dark)
        self.shadowbox.setPen(nopen)
        self.shadowbox.setPos(*(self.style.shadowoffset,)*2)
        self.graphgroup.addToGroup(self.shadowbox)
        
        self.activebox = QGraphicsRectItem(self)
        self.activebox.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        activepen = QPen(self.maincolor, self.style.selectmargin, join=Qt.MiterJoin)
        self.activebox.setPen(activepen)
        self.activebox.hide()
        self.graphgroup.addToGroup(self.activebox)
        
        self.selectbox = QGraphicsRectItem(self)
        self.selectbox.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        selectpen = QPen(FlPalette.light, self.style.selectmargin, join=Qt.MiterJoin)
        self.selectbox.setPen(selectpen)
        self.selectbox.hide()
        self.graphgroup.addToGroup(self.selectbox)
        
        self.mainbox = QGraphicsRectItem(self)
        self.mainbox.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.mainbox.setBrush(mainbrush)
        self.mainbox.setPen(nopen)
        self.graphgroup.addToGroup(self.mainbox)
        
        self.nodelabel = QGraphicsSimpleTextItemCond(self, viewport)
        self.nodelabel.setBrush(lightbrush)
        self.nodelabel.setFont(self.style.boldfont)
        self.nodelabel.setText(self.label % self.realid())
        self.nodelabel.setPos(self.style.itemmargin, self.style.itemmargin)
        self.fggroup.addToGroup(self.nodelabel)
        
        self.icon = self.pixmap("images/blank.png")
        self.iwidth = self.icon.width()
        self.iconx = self.style.nodetextwidth
        
        self.condicon = QGraphicsPixmapItemCond(self.icon, self, viewport)
        self.condicon.setPos(self.iconx-self.iwidth, self.style.itemmargin)
        self.iconx = self.condicon.x()
        self.fggroup.addToGroup(self.condicon)
        
        self.randicon = QGraphicsPixmapItemCond(self.icon, self, viewport)
        self.randicon.setPos(self.iconx-self.style.itemmargin-self.iwidth, self.style.itemmargin)
        self.iconx = self.randicon.x()
        self.fggroup.addToGroup(self.randicon)
        
        self.exiticon = QGraphicsPixmapItemCond(self.icon, self, viewport)
        self.exiticon.setPos(self.iconx-self.style.itemmargin-self.iwidth, self.style.itemmargin)
        self.iconx = self.exiticon.x()
        self.fggroup.addToGroup(self.exiticon)
        
        self.entericon = QGraphicsPixmapItemCond(self.icon, self, viewport)
        self.entericon.setPos(self.iconx-self.style.itemmargin-self.iwidth, self.style.itemmargin)
        self.iconx = self.entericon.x()
        self.fggroup.addToGroup(self.entericon)
        
        self.persisticon = QGraphicsPixmapItemCond(self.icon, self, viewport)
        self.persisticon.setPos(self.iconx-self.style.itemmargin-self.iwidth, self.style.itemmargin)
        self.iconx = self.persisticon.x()
        self.fggroup.addToGroup(self.persisticon)
        
        self.comment = QGraphicsTextItemCond(self, viewport)
        self.comment.setTextWidth(self.style.nodetextwidth)
        self.comment.setDefaultTextColor(FlPalette.light)
        self.comment.setPos(0, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin)
        self.fggroup.addToGroup(self.comment)
        
        self.graphgroup.addToGroup(self.fggroup)
        
        self.view.nodedocs[self.realid()]["comment"].contentsChanged.connect(self.updatecomment)
        self.updatecondition()
        self.updateenterscripts()
        self.updateexitscripts()
        self.updaterandweight()
        self.updatepersistence()
        
        # Never call updatelayout() from here (or any inheritable reimplementation)!
    
    def collapse (self, collapse):
        for item in self.fggroup.childItems():
            if item is not self.nodelabel:
                if collapse:
                    item.hide()
                else:
                    item.show()
        self.updatelayout()
    
    def updatecondition (self):
        icons = {True: "key", False: "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.hascond()])
        self.condicon.setPixmap(pixmap)
        if self.nodeobj.hascond():
            self.condicon.setToolTip("Condition")
        else:
            self.condicon.setToolTip("")
    
    def updateenterscripts (self):
        icons = {True: "script-enter", False: "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.hasenterscripts()])
        self.entericon.setPixmap(pixmap)
        if self.nodeobj.hasenterscripts():
            self.entericon.setToolTip("Enter Scripts")
        else:
            self.entericon.setToolTip("")
    
    def updateexitscripts (self):
        icons = {True: "script-exit", False: "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.hasexitscripts()])
        self.exiticon.setPixmap(pixmap)
        if self.nodeobj.hasexitscripts():
            self.exiticon.setToolTip("Exit Scripts")
        else:
            self.exiticon.setToolTip("")
    
    def updaterandweight (self):
        icons = {True: "dice", False: "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[bool(self.nodeobj.randweight)])
        self.randicon.setPixmap(pixmap)
        if self.nodeobj.randweight:
            self.randicon.setToolTip("Random Weight: %s" % self.nodeobj.randweight)
        else:
            self.randicon.setToolTip("")
    
    def updatepersistence (self):
        icons = {"Mark": "mark", "OncePerConv": "once", "OnceEver": "onceever", "": "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.persistence])
        self.persisticon.setPixmap(pixmap)
        if self.nodeobj.persistence:
            self.persisticon.setToolTip("Persistence: %s" % self.nodeobj.persistence)
        else:
            self.persisticon.setToolTip("")
    
    def updatecomment (self):
        self.fggroup.removeFromGroup(self.comment)
        contents = self.view.nodedocs[self.realid()]["comment"].toPlainText()
        if not contents:
            self.comment.hide()
        else:
            self.comment.show()
            self.comment.setPlainText(contents)
            self.fggroup.addToGroup(self.comment)
        self.updatelayout()
    
    def updatelayout (self):
        if self.iscollapsed():
            rect = self.nodelabel.mapRectToParent(self.nodelabel.boundingRect())
        else:
            rect = self.fggroup.childrenBoundingRect()
        mainrect = rect.marginsAdded(self.style.nodemargins)
        self.mainbox.setRect(mainrect)
        self.shadowbox.setRect(mainrect)
        self.selectbox.setRect(mainrect.marginsAdded(self.style.selectmargins))
        activerect = mainrect.marginsAdded(self.style.activemargins)
        self.activebox.setRect(activerect)
        self.graphgroup.setPos(-activerect.width()//2-activerect.x(), -activerect.height()//2-activerect.y())
        self.prepareGeometryChange()
        self.rect = self.graphgroup.mapRectToParent(mainrect)
        self.view.updatelayout()
    
    def mouseDoubleClickEvent (self, event):
        super().mouseDoubleClickEvent(event)
        event.accept()
        if event.button() == Qt.LeftButton:
            self.view.setactivenode(self)
    
    def mousePressEvent (self, event):
        super().mousePressEvent(event)
        if event.button() & (Qt.LeftButton | Qt.RightButton) :
            self.view.setselectednode(self)
            event.accept()
    
    def __repr__ (self):
        return "<%s %s>" % (type(self).__name__, self.id())


class RootNodeItem (NodeItem):
    maincolor = FlPalette.root
    altcolor = FlPalette.rootvar
    label = "%s Root"
    
    def graphicsetup (self):
        super().graphicsetup()
        self.updatecomment()
    
    def contextMenuEvent (self, event):
        menu = QMenu()
        if self.isselected():
            window = FlGlob.mainwindow
            menu.addAction(window.actions["collapse"])
            menu.addMenu(window.addmenu)
        if not menu.isEmpty():
            menu.exec_(event.screenPos())


class TextNodeItem (NodeItem):
    def __init__ (self, nodeobj, parent=None, view=None, state=1):
        self.textheight = 0
        self.collapselayout = False
        super().__init__(nodeobj, parent, view, state)
    
    def graphicsetup (self):
        super().graphicsetup()
        
        lightbrush = QBrush(FlPalette.light)
        nopen = QPen(0)
        viewport = self.view.viewport()
        
        self.textbox = QGraphicsRectItemCond(self, viewport)
        self.textbox.setBrush(lightbrush)
        self.textbox.setPen(nopen)
        self.fggroup.addToGroup(self.textbox)
        
        self.nodespeaker = QGraphicsSimpleTextItemCond(self, viewport)
        self.nodespeaker.setBrush(lightbrush)
        self.nodespeaker.setText(" ")
        self.nodespeaker.setPos(self.style.itemmargin, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin*2)
        self.fggroup.addToGroup(self.nodespeaker)
        
        self.nodetext = QGraphicsTextItemCond(self, viewport)
        self.nodetext.setTextWidth(self.style.nodetextwidth)
        self.nodetext.setDefaultTextColor(FlPalette.dark)
        self.nodetext.setPos(0, self.nodespeaker.y()+self.nodespeaker.boundingRect().height()+self.style.itemmargin)
        self.fggroup.addToGroup(self.nodetext)
        
        self.view.nodedocs[self.realid()]["text"].contentsChanged.connect(self.updatetext)
    
    def updatespeaker (self):
        speaker = self.nodeobj.speaker
        listener = self.nodeobj.listener
        label = "%s -> %s" % (elidestring(speaker, 15), elidestring(listener, 15))
        fixedwidth = self.style.basemetrics.elidedText(label, Qt.ElideRight, self.style.nodetextwidth)
        self.nodespeaker.setText(fixedwidth)
    
    def updatetext (self):
        ndtxt = self.nodetext
        ndtxt.setPlainText(self.view.nodedocs[self.realid()]["text"].toPlainText())
        textrect = ndtxt.mapRectToParent(ndtxt.boundingRect())
        self.textbox.setRect(textrect)
        self.comment.setY(textrect.bottom()+self.style.itemmargin)
        
        textheight = textrect.height()
        if textheight == self.textheight:
            return
        self.textheight = textheight
        self.updatelayout()
    
    def contextMenuEvent (self, event):
        menu = QMenu()
        if self.isselected():
            window = FlGlob.mainwindow
            menu.addAction(window.actions["collapse"])
            if self.isghost():
                menu.addAction(window.actions["selectreal"])
            menu.addAction(window.actions["copynode"])
            menu.addMenu(window.addmenu)
            menu.addAction(window.actions["moveup"])
            menu.addAction(window.actions["movedown"])
            menu.addAction(window.actions["parentswap"])
            menu.addAction(window.actions["unlinknode"])
            menu.addAction(window.actions["unlinkstree"])
            menu.addAction(window.actions["settemplate"])
            menu.addMenu(window.transformmenu)
        if not menu.isEmpty():
            menu.exec_(event.screenPos())

class TalkNodeItem (TextNodeItem):
    maincolor = FlPalette.hl1
    altcolor = FlPalette.hl1var
    label = "%s Talk"
    
    def graphicsetup (self):
        super().graphicsetup()
        viewport = self.view.viewport()
        
        self.qhubicon = QGraphicsPixmapItemCond(self.icon, self, viewport)
        self.qhubicon.setPos(self.iconx-self.style.itemmargin-self.iwidth, self.style.itemmargin)
        self.iconx = self.qhubicon.x()
        self.fggroup.addToGroup(self.qhubicon)
        
        self.updatespeaker()
        self.updatecomment()
        self.updatetext()
        self.updatequestionhub()
    
    def updatequestionhub (self):
        icons = {"ShowOnce": "question-once", "ShowNever": "question-never", "": "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.questionhub])
        self.qhubicon.setPixmap(pixmap)
        if self.nodeobj.questionhub:
            self.qhubicon.setToolTip("Question hub: %s" % self.nodeobj.questionhub)
        else:
            self.qhubicon.setToolTip("")

class ResponseNodeItem (TextNodeItem):
    maincolor = FlPalette.hl2
    altcolor = FlPalette.hl2var
    label = "%s Response"
    
    def graphicsetup (self):
        super().graphicsetup()
        self.updatespeaker()
        self.updatecomment()
        self.updatetext()

class BankNodeItem (NodeItem):
    maincolor = FlPalette.bank
    altcolor = FlPalette.bankvar
    label = "%s Bank"
    
    def __init__ (self, nodeobj, parent=None, view=None, state=1):
        super().__init__(nodeobj, parent, view, state)
        self.rect = QRectF()
        self.setZValue(-1)
        self.updatecomment()
        self.updatebanktype()
        self.updatebankmode()
    
    def nudgechildren(self):
        super().nudgechildren()
        for sub in self.sublist():
            sub.setrank(self)
    
    def sublist (self):
        ID = self.nodeobj.ID
        itemtable = self.view.itemtable
        if self.state == 1 and ID in itemtable and not self.iscollapsed():
            children = []
            for child in self.nodeobj.subnodes:
                if child in itemtable[ID]:
                    item = itemtable[ID][child]
                else:
                    continue
                if item.state > -1:
                    children.append(item)
            return children
        else:
            return []
    
    def treeposition (self, ranks=None):
        self.updatelayout(external=True)
        return super().treeposition(ranks)
    
    def graphicsetup (self):
        super().graphicsetup()
        darkbrush = QBrush(FlPalette.bg)
        nopen = QPen(0)
        viewport = self.view.viewport()
        
        self.btypeicon = QGraphicsPixmapItemCond(self.icon, self, viewport)
        self.btypeicon.setPos(self.iconx-self.style.itemmargin-self.iwidth, self.style.itemmargin)
        self.iconx = self.btypeicon.x()
        self.fggroup.addToGroup(self.btypeicon)
        
        self.centerbox = QGraphicsRectItem(self)
        self.centerbox.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.centerbox.setRect(QRectF())
        self.centerbox.setBrush(darkbrush)
        self.centerbox.setPen(nopen)
        self.centerbox.setPos(0, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin*2)
        self.fggroup.addToGroup(self.centerbox)
    
    def updatebanktype (self):
        types = {"talk": "(T)", "response": "(R)", "": ""}
        self.nodelabel.setText("%s Bank %s" % (self.realid(), types[self.nodeobj.banktype]))
    
    def updatebankmode (self):
        icons = {"First": "bank-first", "All": "bank-all", "Append": "bank-append", "": "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.bankmode])
        self.btypeicon.setPixmap(pixmap)
        if self.nodeobj.bankmode:
            self.btypeicon.setToolTip("Bank mode: %s" % self.nodeobj.bankmode)
        else:
            self.btypeicon.setToolTip("")
    
    def updatecenterbox (self):
        verticalpos = self.centerbox.y()
        maxwidth = self.style.nodetextwidth
        subnodes = self.sublist()
        for subnode in subnodes:
            if subnode.nodeobj.typename == "bank":
                subnode.updatelayout(external=True)
            noderect = subnode.boundingRect()
            nodeheight = noderect.height()
            nodewidth = noderect.width()
            subnode.show()
            subnode.yoffset = self.mapToScene(0,verticalpos + nodeheight/2+self.style.activemargin).y()-self.y_bottom()
            verticalpos += nodeheight+self.style.activemargin*2
            maxwidth = max(maxwidth, nodewidth)
        centerrect = self.centerbox.rect()
        centerrect.setWidth(maxwidth+self.style.selectmargin*2)
        centerrect.setHeight(verticalpos-self.centerbox.y())
        self.centerbox.setRect(centerrect)
        centerrect = self.centerbox.mapRectToParent(centerrect)
        
        self.comment.setY(centerrect.bottom()+self.style.itemmargin)
    
    def updatelayout (self, external=False):
        subnodes = self.sublist()
        if self.iscollapsed():
            rect = self.nodelabel.mapRectToParent(self.nodelabel.boundingRect())
        else:
            self.updatecenterbox()
            rect = self.fggroup.childrenBoundingRect()
        mainrect = rect.marginsAdded(self.style.banknodemargins)
        self.mainbox.setRect(mainrect)
        self.shadowbox.setRect(mainrect)
        self.selectbox.setRect(mainrect.marginsAdded(self.style.selectmargins))
        activerect = mainrect.marginsAdded(self.style.activemargins)
        self.activebox.setRect(activerect)
        oldypos = self.centerbox.mapToScene(self.centerbox.pos()).y()
        self.graphgroup.setPos(-activerect.width()//2-activerect.x(), -activerect.height()//2-activerect.y())
        newypos = self.centerbox.mapToScene(self.centerbox.pos()).y()
        for subnode in subnodes:
            subnode.yoffset += newypos - oldypos
            subnode.setY(self.y())
        self.prepareGeometryChange()
        self.rect = self.graphgroup.mapRectToParent(mainrect)
        if not external:
            self.view.updatelayout()
    
    def setY (self, y):
        super().setY(y)
        for subnode in self.sublist():
            subnode.setY(y)
    
    def contextMenuEvent (self, event):
        menu = QMenu()
        if self.isselected():
            window = FlGlob.mainwindow
            menu.addAction(window.actions["collapse"])
            if self.isghost():
                menu.addAction(window.actions["selectreal"])
            menu.addAction(window.actions["copynode"])
            menu.addMenu(window.subnodemenu)
            menu.addMenu(window.addmenu)
            menu.addAction(window.actions["moveup"])
            menu.addAction(window.actions["movedown"])
            menu.addAction(window.actions["parentswap"])
            menu.addAction(window.actions["unlinknode"])
            menu.addAction(window.actions["unlinkstree"])
            menu.addAction(window.actions["settemplate"])
            menu.addMenu(window.transformmenu)
        if not menu.isEmpty():
            menu.exec_(event.screenPos())

class TriggerNodeItem (NodeItem):
    maincolor = FlPalette.trig
    altcolor = FlPalette.trigvar
    label = "%s Trigger"
    
    def graphicsetup (self):
        super().graphicsetup()
        
        lightbrush = QBrush(FlPalette.light)
        nopen = QPen(0)
        viewport = self.view.viewport()
        
        self.triggerbox = QGraphicsRectItemCond(self, viewport)
        self.triggerbox.setBrush(lightbrush)
        self.triggerbox.setPen(nopen)
        self.fggroup.addToGroup(self.triggerbox)
        
        self.triggerlabel = QGraphicsTextItemCond(self, viewport)
        self.triggerlabel.setTextWidth(self.style.nodetextwidth)
        self.triggerlabel.setDefaultTextColor(FlPalette.dark)
        self.triggerlabel.setPos(0, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin)
        self.fggroup.addToGroup(self.triggerlabel)
        
        self.updatetrigger()
        self.updatecomment()
    
    def updatetrigger (self):
        self.triggerlabel.setPlainText(self.nodeobj.triggerconv)
        textrect = self.triggerlabel.mapRectToParent(self.triggerlabel.boundingRect())
        self.triggerbox.setRect(textrect)
        self.comment.setY(textrect.bottom()+self.style.itemmargin)
        self.updatelayout()
    
    def contextMenuEvent (self, event):
        menu = QMenu()
        if self.isselected():
            window = FlGlob.mainwindow
            menu.addAction(window.actions["collapse"])
            if self.isghost():
                menu.addAction(window.actions["selectreal"])
            menu.addAction(window.actions["copynode"])
            menu.addAction(window.actions["moveup"])
            menu.addAction(window.actions["movedown"])
            menu.addAction(window.actions["unlinknode"])
            menu.addAction(window.actions["unlinkstree"])
            menu.addAction(window.actions["settemplate"])
            menu.addMenu(window.transformmenu)
        if not menu.isEmpty():
            menu.exec_(event.screenPos())

class EdgeItem (QGraphicsItem):
    def __init__ (self, source):
        super().__init__()
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.childpos = []
        self.source = source
        self.sourceright = 0
        source.setedge(self)
        self.style = FlGlob.mainwindow.style
        self.arrowsize = self.style.arrowsize
        self.pensize = self.style.pensize
        
        pen = QPen(FlPalette.light, self.pensize, cap = Qt.FlatCap, join=Qt.MiterJoin)
        pen.setCosmetic(False)
        brush = QBrush(FlPalette.light)
        
        pen2 = QPen(pen)
        pen2.setColor(FlPalette.dark)
        brush2 = QBrush(FlPalette.dark)
        
        visuals = dict()
        visuals[True] = (pen, brush)
        visuals[False] = (pen2, brush2)
        self.visuals = visuals
    
    def boundingRect (self):
        self.childpos = self.source.childpos
        if self.childpos:
            halfarrow = (self.arrowsize + + self.pensize*1.5)/2
            xmax = max([c[0] for c in self.childpos]) + self.style.shadowoffset + self.pensize*1.5
            ymin = self.childpos[0][1] - halfarrow
            ymax = self.childpos[-1][1] + halfarrow + self.style.shadowoffset
            rect = QRectF(0, ymin, xmax, abs(ymax-ymin))
        else:
            rect = QRectF(0, 0, 0, 0)
        return rect
    
    def paint (self, painter, style, widget, off=0, main=True):
        if not self.source:
            return
        children = self.childpos
        if not children:
            return
        
        if main:
            self.paint(painter, style, widget, off=self.style.shadowoffset, main=False)
        
        pen, brush = self.visuals[main]
        painter.setPen(pen)
        painter.setBrush(brush)
        
        x0 = self.sourceright + off
        y0 = off
        vert_x = self.style.rankwidth/2 + off
        painter.drawLine(x0, y0, vert_x, y0)
        
        arrow = self.arrowsize
        corr = self.pensize/2
        for tx, ty in children:
            tx += off
            ty += off
            painter.drawLine(vert_x-corr, ty, tx-arrow+1, ty)
            arrowtip = [QPointF(tx, ty),
                        QPointF(tx-arrow, ty-(arrow/2)),
                        QPointF(tx-arrow, ty+(arrow/2))]
            painter.drawPolygon(*arrowtip)
        
        if len(children) > 1:
            vert_top = children[0][1] + off
            vert_bottom = children[-1][1] + off
            painter.drawLine(vert_x, vert_top, vert_x, vert_bottom)

class FrameItem (QGraphicsItem):
    def __init__ (self, view):
        super().__init__()
        self.treeview = weakref.proxy(view)
        self.setZValue(1)
    
    def boundingRect (self):
        viewport = self.treeview.viewport()
        viewportrect = QRect(0, 0, viewport.width(), viewport.height())
        visiblerect = self.treeview.mapToScene(viewportrect).boundingRect()
        return visiblerect
    
    def paint (self, painter, style, widget):
        if widget is not self.treeview.viewport():
            pen = QPen(FlPalette.light)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QBrush())
            painter.drawRect(self.boundingRect())

class ParagraphEdit (QPlainTextEdit):
    def keyPressEvent (self, event):
        key = event.key()
        mod = event.modifiers()
        if not (mod & Qt.ShiftModifier) and (key == Qt.Key_Enter or key == Qt.Key_Return):
            FlGlob.mainwindow.activeview.setFocus()
        else:
            super().keyPressEvent(event)

class TextEditWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setEnabled(False)
        layout = QFormLayout(self)
        l_speaker = QLabel("&Speaker")
        self.speaker = QLineEdit(self)
        l_speaker.setBuddy(self.speaker)
        
        l_listener = QLabel("&Listener")
        self.listener = QLineEdit(self)
        l_listener.setBuddy(self.listener)
        
        l_nodetext = QLabel("&Text")
        self.nodetext = ParagraphEdit(self)
        self.nodetext.setTabChangesFocus(True)
        l_nodetext.setBuddy(self.nodetext)
        
        layout.addRow(l_speaker, self.speaker)
        layout.addRow(l_listener, self.listener)
        layout.addRow(l_nodetext, self.nodetext)
        
        self.nodeobj = None
        textdoc = QTextDocument(self)
        textdoc.setDocumentLayout(QPlainTextDocumentLayout(textdoc))
        self.blankdoc = textdoc
        self.speaker.textChanged.connect(self.setnodespeaker)
        self.listener.textChanged.connect(self.setnodelistener)
        self.nodetext.textChanged.connect(self.setnodetext)
        
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        self.nodeobj = nodeobj
        
        if nodeobj is not None and nodeobj.typename in ("talk", "response"):
            self.setEnabled(True)
            nodetextdoc = view.nodedocs[nodeID]["text"]
            self.speaker.setText(nodeobj.speaker)
            self.listener.setText(nodeobj.listener)
            self.nodetext.setDocument(nodetextdoc)
            self.nodetext.moveCursor(QTextCursor.End)
        else:
            self.setEnabled(False)
            self.nodeobj = None
            self.speaker.setText("")
            self.listener.setText("")
            self.nodetext.setDocument(self.blankdoc)
    
    @pyqtSlot()
    def setnodespeaker (self):
        if self.nodeobj is None:
            return
        self.nodeobj.speaker = self.speaker.text()
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatespeaker")
    
    @pyqtSlot()
    def setnodelistener (self):
        if self.nodeobj is None:
            return
        self.nodeobj.listener = self.listener.text()
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatespeaker")
    
    @pyqtSlot()
    def setnodetext (self):
        if self.nodeobj is None:
            return
        self.nodeobj.text = self.nodetext.toPlainText()

"""
class ScriptParamWidget (QWidget):
    def __init__ (self, parent, name, annot, default):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(name)
        if annot is bool:
            editor = QCheckBox("True", self)
            signal = editor.stateChanged
            value = lambda: bool(editor.checkState())
            editor.setChecked(bool(default))
        elif annot is int:
            editor = QSpinBox(self)
            signal = editor.valueChanged
            value = editor.value
            if not default:
                default = 0
            editor.setValue(int(default))
        else:
            editor = QLineEdit(self)
            signal = editor.textEdited
            value = editor.text
            if not default:
                default = ""
            editor.setText(str(default))
        
        layout.addWidget(label)
        layout.addWidget(editor)
        
        self.editor = editor
        self.signal = signal
        self.value = value

class CallWidget (QGroupBox):
    removed = pyqtSignal()
    changed = pyqtSignal()
    
    def __init__ (self, parent, callobj, name):
        super().__init__ (name, parent)
        self.callobj = callobj
        self.setStyleSheet('''
            QGroupBox::indicator:unchecked {
                image: url(images/plus.png);
            }
            QGroupBox::indicator:!unchecked {
                image: url(images/minus.png);
            }
            QGroupBox {
                font-weight: bold;
                border: solid gray;
                border-width: 0px 0px 0px 2px;
                margin-top: 1ex;
                margin-left: 0.5ex;
                padding-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin:margin;
            }
            ''')
        self.setCheckable(True)
        
        actremove = QAction("&Remove", self)
        actremove.triggered.connect(self.remove)
        self.actremove = actremove
    
    @pyqtSlot()
    def remove (self):
        self.removed.emit(self.callobj)
        self.changed.emit()
    
    def contextMenuEvent (self, event):
        menu = QMenu(self)
        menu.addAction(self.actremove)
        menu.exec_(event.globalPos())

class ScriptCallWidget (CallWidget):
    removed = pyqtSignal(cp.ScriptCall)
    
    def __init__ (self, parent, callobj, nodeID, cond=False):
        name = callobj.funcname
        super().__init__(parent, callobj, name)
        self.nodeID = nodeID
        params = callobj.funcparams
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 4, 9, 4)
        
        if cond:
            notcheck = QCheckBox("Not", self)
            notcheck.setChecked(callobj._not)
            notcheck.stateChanged.connect(self.notchanged)
            layout.addWidget(notcheck)
            self.toggled.connect(notcheck.setVisible)
        
        paramswidget = QWidget(self)
        paramslayout = QVBoxLayout(paramswidget)
        paramslayout.setContentsMargins(0, 0, 0, 0)
        paramslist = []
        if callobj.funccall is not None:
            signature = insp.signature(callobj.funccall)
            for param in signature.parameters.values():
                pname = param.name
                annot = param.annotation if param.annotation is not insp._empty else ""
                default = params.pop(0) if params else None
                parwidget = ScriptParamWidget(paramswidget, pname, annot, default)
                paramslayout.addWidget(parwidget)
                paramslist.append(parwidget)
                parwidget.signal.connect(self.paramchanged)
            layout.addWidget(paramswidget)
        
        self.paramslist = paramslist
        
        self.toggled.connect(paramswidget.setVisible)
    
    @pyqtSlot(int)
    def notchanged (self, newnot):
        self.callobj._not = bool(newnot)
        self.changed.emit()
    
    @pyqtSlot()
    def paramchanged (self):
        newparams = []
        for param in self.paramslist:
            newparams.append(param.value())
        self.callobj.funcparams = newparams

class CallCreateWidget (QWidget):
    newCallObj = pyqtSignal(cp.MetaCall)
    
    def __init__ (self, parent, cond=False):
        super().__init__(parent)
        self.cond = cond
        
        self.combobox = QComboBox(self)
        addbutton = QPushButton("Add", self)
        addbutton.clicked.connect(self.newscriptcall)
        
        layout = QHBoxLayout(self)
        layout.addWidget(self.combobox)
        layout.addWidget(addbutton)
        
        self.reload()
    
    def getscripts (self, strict=False):
        view = FlGlob.mainwindow.activeview
        if view is not None and view.nodecontainer.proj is not None:
            return view.nodecontainer.proj.scripts
        elif strict:
            return None
        else:
            return dict()
    
    def reload (self):
        scripts = self.getscripts()
        if self.cond:
            names = ["( )"]
            condcalls = [n for n, sc in scripts.items() if "return" in sc.__annotations__]
            names.extend(sorted(condcalls))
        else:
            names = sorted(scripts.keys())
        self.scriptcalls = names
        
        self.combobox.clear()
        self.combobox.insertItems(len(self.scriptcalls), self.scriptcalls)
    
    @pyqtSlot()
    def newscriptcall (self):
        name = self.combobox.currentText()
        if not name:
            return
        elif name == "( )":
            callobj = cp.MetaCall({"type":"cond","operator":"and","calls":[]})
        else:
            scripts = self.getscripts()
            signature = insp.signature(scripts[name])
            defaults = {int: 0, bool: False}
            params = []
            for param in signature.parameters.values():
                if param.name == "self":
                    continue
                if param.annotation in defaults:
                    params.append(defaults[param.annotation])
                else:
                    params.append("")
            callobj = cp.MetaCall({"type":"script", "command":name, "params":params},
                scripts=self.getscripts(strict=True))
        self.newCallObj.emit(callobj)

class ConditionCallWidget (CallWidget):
    removed = pyqtSignal(cp.ConditionCall)
    
    def __init__ (self, parent, callobj, nodeID, cond=True):
        name = "()"
        super().__init__ (parent, callobj, name)
        self.nodeID = nodeID
        operatorwidget = QWidget(self)
        operatorlabel = QLabel("Operator", operatorwidget)
        operatorcombo = QComboBox(operatorwidget)
        operatorcombo.insertItems(2, ["and", "or"])
        operatorcombo.setCurrentText(callobj.operatorname)
        operatorcombo.currentTextChanged.connect(self.setoperator)
        operatorlayout = QHBoxLayout(operatorwidget)
        operatorlayout.addWidget(operatorlabel)
        operatorlayout.addWidget(operatorcombo)
        
        self.widgets = dict()
        callswidget = QWidget(self)
        self.callswidget = callswidget
        callslayout = QVBoxLayout(callswidget)
        callslayout.setContentsMargins(0, 0, 0, 0)
        self.types = {"cond": ConditionCallWidget, "script": ScriptCallWidget}
        for call in callobj.calls:
            self.addcallwidget(call)
        
        newwidget = CallCreateWidget(self, cond=True)
        newwidget.layout().addStretch()
        newwidget.newCallObj.connect(self.addcall)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(operatorwidget)
        layout.addWidget(callswidget)
        layout.addWidget(newwidget)
        
        self.toggled.connect(callswidget.setVisible)
        self.toggled.connect(operatorwidget.setVisible)
        self.toggled.connect(newwidget.setVisible)
    
    @pyqtSlot(cp.MetaCall)
    def addcall (self, metacall):
        callobj = metacall.callobj
        self.callobj.calls.append(callobj)
        self.addcallwidget(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeID, "updatecondition")
    
    def addcallwidget (self, callobj):
        widget = self.types[callobj.typename](self, callobj, self.nodeID, cond=True)
        widget.removed.connect(self.removecall)
        widget.changed.connect(self.newtitle)
        self.widgets[callobj] = widget
        self.callswidget.layout().addWidget(widget)
        self.newtitle()
    
    def fullname (self, callobj, recursive=False):
        fullname = ""
        for call in callobj.calls:
            if callobj.calls.index(call):
                fullname += " %s " % callobj.operatorname
            if call.typename == "cond":
                if recursive:
                    fullname += self.fullname(call)
                elif not call.calls:
                    fullname += "()"
                else:
                    fullname += "(…)"
            elif call.typename == "script":
                if call._not:
                    fullname += "!"
                fullname += call.funcname
        
        if not fullname:
            return "()"
        else:
            return "(%s)" % fullname
        
    @pyqtSlot()
    def newtitle (self):
        fullname = self.fullname(self.callobj, recursive=True)
        shortname = self.fullname(self.callobj)
        self.setTitle(elidestring(shortname,30))
        self.setToolTip(fullname)
        self.changed.emit()
    
    @pyqtSlot(str)
    def setoperator (self, operatorname):
        self.callobj.setoperator(operatorname)
        self.newtitle()
    
    @pyqtSlot(cp.ScriptCall)
    @pyqtSlot(cp.ConditionCall)
    def removecall (self, callobj):
        prompt = QMessageBox.question(self, "Prompt", "Remove call?", defaultButton=QMessageBox.Yes)
        if prompt == QMessageBox.No:
            return
        widget = self.widgets.pop(callobj)
        self.callswidget.layout().removeWidget(widget)
        widget.deleteLater()
        self.callobj.calls.remove(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeID, "updatecondition")
        widget = None
        gc.collect()

class CallEditWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setEnabled(False)
        callsarea = QScrollArea(self)
        callsarea.setWidgetResizable(True)
        self.callsarea = callsarea
        self.resetwidget()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
    
    def resetwidget (self):
        callswidget = self.callsarea.widget()
        if callswidget is not None:
            callswidget.setParent(None)
            callswidget.deleteLater()
            callswidget = None
            gc.collect()
        callswidget = QWidget(self.callsarea)
        callslayout = QVBoxLayout(callswidget)
        callslayout.setAlignment(Qt.AlignTop)
        self.callsarea.setWidget(callswidget)
        return callswidget

class ConditionEditWidget (CallEditWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.layout().addWidget(self.callsarea)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        self.nodeobj = nodeobj
 
        if nodeobj is not None:
            callobj = nodeobj.condition
            callswidget = self.resetwidget()
            scwidget = ConditionCallWidget(callswidget, callobj, nodeID)
            scwidget.actremove.setEnabled(False)
            callswidget.layout().addWidget(scwidget)
            if view.nodecontainer.proj is not None:
                self.setEnabled(True)
            else:
                self.setEnabled(False)
        else:
            self.setEnabled(False)
            self.resetwidget()

class ScriptEditWidget (CallEditWidget):
    def __init__ (self, parent, slot="enter"):
        super().__init__(parent)
        if slot in ("enter", "exit"):
            self.slot = slot
        else:
            return
        
        newwidget = CallCreateWidget(self)
        newwidget.newCallObj.connect(self.addscriptcall)
        self.newwidget = newwidget
        
        self.widgets = dict()
        
        layout = self.layout()
        layout.addWidget(newwidget)
        layout.addWidget(self.callsarea)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        self.nodeobj = nodeobj
        
        if nodeobj is not None:
            self.resetwidget()
            self.newwidget.reload()
            if self.slot == "enter":
                self.scripts = nodeobj.enterscripts
            elif self.slot == "exit":
                self.scripts = nodeobj.exitscripts
            for callobj in self.scripts:
                self.addscriptcallwidget(callobj)
            if view.nodecontainer.proj is not None:
                self.setEnabled(True)
            else:
                self.setEnabled(False)
        else:
            self.setEnabled(False)
            self.resetwidget()
    
    @pyqtSlot(cp.MetaCall)
    def addscriptcall (self, metacall):
        callobj = metacall.callobj
        self.scripts.append(callobj)
        self.addscriptcallwidget(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "update%sscripts" % self.slot)
    
    def addscriptcallwidget (self, callobj):
        callswidget = self.callsarea.widget()
        scwidget = ScriptCallWidget(callswidget, callobj, self.nodeobj.ID)
        scwidget.removed.connect(self.removescriptcall)
        self.widgets[callobj] = scwidget
        callswidget.layout().addWidget(scwidget)
    
    @pyqtSlot(cp.ScriptCall)
    def removescriptcall (self, callobj):
        prompt = QMessageBox.question(self, "Prompt", "Remove call?", defaultButton=QMessageBox.Yes)
        if prompt == QMessageBox.No:
            return
        callswidget = self.callsarea.widget()
        scwidget = self.widgets.pop(callobj)
        callswidget.layout().removeWidget(scwidget)
        scwidget.deleteLater()
        self.scripts.remove(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "update%sscripts" % self.slot)
        scwidget = None
        gc.collect()
"""

class ScriptHighlighter (QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        styles = {
            'keyword': self.textformat('blue', 'bold'),
            'bool': self.textformat('green', 'bold'),
            'string': self.textformat('yellowgreen'),
            'numbers': self.textformat('green'),
        }
        
        rules = []
        
        rules += [(r'\b%s\b' % w, styles['keyword']) for w in ('and', 'or', 'not')]
        rules += [(r'\b%s\b' % w, styles['bool']) for w in ('true', 'false')]
        rules += [(r'\s!' , styles['keyword'])]
        
        rules += [
            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', styles['string']),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", styles['string']),

            # Numeric literals
            (r'\b[+-]?[0-9]+\b', styles['numbers']),
            (r'\b[+-]?0[bB][01]+\b', styles['numbers']),
            (r'\b[+-]?0[oO][0-7]+\b', styles['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+\b', styles['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', styles['numbers']),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QRegExp(pat, cs=Qt.CaseInsensitive), fmt) for (pat, fmt) in rules]

    def textformat (self, color, style=''):
        tformat = QTextCharFormat()
        tformat.setForeground(QColor(color))
        if 'bold' in style:
            tformat.setFontWeight(QFont.Bold)
        if 'italic' in style:
            tformat.setFontItalic(True)
    
        return tformat

    
    def highlightBlock(self, text):
        for exp, fmt in self.rules:
            index = exp.indexIn(text, 0)

            while index >= 0:
                length = len(exp.cap())
                self.setFormat(index, length, fmt)
                index = exp.indexIn(text, index + length)

        self.setCurrentBlockState(0)

class ScriptTextEdit (QPlainTextEdit):
    def __init__ (self, parent):
        super().__init__(parent)
        self.completer = None
        self.highlighter = ScriptHighlighter(self)
    
    def setcompleter (self, completer):
        completer.setWidget(self)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.activated.connect(self.insertcompletion)
        self.completer = completer
    
    def setDocument (self, document):
        super().setDocument(document)
        self.highlighter.setDocument(document)
    
    @pyqtSlot(str)
    def insertcompletion (self, completion):
        c = self.completer
        tc = self.textCursor();
        extra = len(c.completionPrefix())
        print(completion, c.completionPrefix(), extra)
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[extra:])
        self.setTextCursor(tc)
    
    def textundercursor (self):
        cur = self.textCursor()
        cur.select(QTextCursor.WordUnderCursor)
        return cur.selectedText()
    
    def keyPressEvent (self, event):
        c = self.completer
        if c and c.popup().isVisible():
            if event.key() in (Qt.Key_Enter,Qt.Key_Return,Qt.Key_Escape,Qt.Key_Tab,Qt.Key_Backtab):
                event.ignore()
                return
        super().keyPressEvent(event)
        if not c:
            return
        p = c.popup()
        t = event.text()
        prefix = self.textundercursor()
        if not t or len(prefix) < 3 or t[-1] in "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-=":
            c.popup().hide()
            return
        #print(prefix)
        if prefix != c.completionPrefix():
            c.setCompletionPrefix(prefix)
            p.setCurrentIndex(c.completionModel().index(0, 0))
        cr = self.cursorRect()
        cr.setWidth(p.sizeHintForColumn(0) + p.verticalScrollBar().sizeHint().width())
        c.complete(cr)

class ScriptWidget (QWidget):
    def __init__ (self, parent, slot):
        super().__init__(parent)
        
        self.setEnabled(False)
        self.slot = slot
        
        layout = QVBoxLayout(self)
        
        textedit = ScriptTextEdit(self)
        #textedit = QPlainTextEdit(self)
        #completer = QCompleter(self.getscripts().keys(), self)
        #textedit.setcompleter(completer)
        #self.highlight = ScriptHighlighter(textedit.document())
        #textedit.setPlainText("QWE('rty') and not asd(false)")
        self.textedit = textedit
        
        layout.addWidget(textedit)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        
        if nodeobj is not None:
            #scriptdoc = view.nodedocs[nodeID].get("script", None)
            #if self.slot not in view.nodedocs[nodeID]:
            #    view.nodedocs[nodeID][self.slot] = self.scripttodoc(nodeID)
                
            scriptdoc = view.nodedocs[nodeID][self.slot]
            completer = QCompleter(self.getscripts().keys(), self)
            self.textedit.setcompleter(completer)
            self.textedit.setDocument(scriptdoc)
            self.setEnabled(True)
        else:
            self.setEnabled(False)
        
    
    def getscripts (self, strict=False):
        view = FlGlob.mainwindow.activeview
        if view is not None and view.nodecontainer.proj is not None:
            return view.nodecontainer.proj.scripts
        elif strict:
            return None
        else:
            return dict()

class PropertiesEditWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setEnabled(False)
        layout = QFormLayout(self)
        
        l_persistence = QLabel("&Persistence", self)
        persistence = QComboBox(self)
        persvals = ("", "Mark", "OnceEver", "OncePerConv")
        persistence.insertItems(len(persvals), persvals)
        persistence.currentTextChanged.connect(self.persistencechanged)
        l_persistence.setBuddy(persistence)
        self.persistence = persistence
        
        l_bankmode = QLabel("&Bank play mode", self)
        bankmode = QComboBox(self)
        bankmodes = ("First", "All", "Append")
        bankmode.insertItems(len(bankmodes), bankmodes)
        bankmode.currentTextChanged.connect(self.bankmodechanged)
        l_bankmode.setBuddy(bankmode)
        self.bankmode = bankmode
        
        l_questionhub = QLabel("&Question hub", self)
        questionhub = QComboBox(self)
        qhubtypes = ("", "ShowOnce", "ShowNever")
        questionhub.insertItems(len(qhubtypes), qhubtypes)
        questionhub.currentTextChanged.connect(self.questionhubchanged)
        l_questionhub.setBuddy(questionhub)
        self.questionhub = questionhub
        
        l_trigger = QLabel("&Trigger conversation", self)
        trigger = QComboBox(self)
        trigger.currentTextChanged.connect(self.triggerchanged)
        l_trigger.setBuddy(trigger)
        self.trigger = trigger
        
        l_randweight = QLabel("&Random weight", self)
        randweight = QLineEdit(self)
        rwvalidator = QDoubleValidator(self)
        rwvalidator.setBottom(0)
        rwvalidator.setDecimals(3)
        randweight.setValidator(rwvalidator)
        randweight.editingFinished.connect(self.randweightchanged)
        l_randweight.setBuddy(randweight)
        self.randweight = randweight
        
        l_comment = QLabel("&Comment", self)
        comment = ParagraphEdit(self)
        comment.textChanged.connect(self.commentchanged)
        self.comment = comment
        l_comment.setBuddy(comment)
        
        layout.addRow(l_persistence, persistence)
        layout.addRow(l_bankmode, bankmode)
        layout.addRow(l_questionhub, questionhub)
        layout.addRow(l_trigger, trigger)
        layout.addRow(l_randweight, randweight)
        layout.addRow(l_comment, comment)
        
        textdoc = QTextDocument(self)
        textdoc.setDocumentLayout(QPlainTextDocumentLayout(textdoc))
        self.blankdoc = textdoc
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        self.nodeobj = nodeobj
        
        if nodeobj is not None:
            self.setEnabled(True)
            self.persistence.setCurrentText(nodeobj.persistence)
            
            if nodeobj.typename == "bank":
                self.bankmode.setCurrentText(nodeobj.bankmode)
                self.bankmode.setEnabled(True)
            else:
                self.bankmode.setEnabled(False)
            
            if nodeobj.typename == "talk":
                self.questionhub.setCurrentText(nodeobj.questionhub)
                self.questionhub.setEnabled(True)
            else:
                self.questionhub.setEnabled(False)
            
            if nodeobj.typename == "trigger" and view.nodecontainer.proj is not None:
                proj = view.nodecontainer.proj
                convs = [""] + proj.convs
                # nodeobj.triggerconv will be reset with clear(), so we save it
                triggerconv = nodeobj.triggerconv
                self.trigger.clear()
                self.trigger.insertItems(len(convs), convs)
                self.trigger.setCurrentText(triggerconv)
                self.trigger.setEnabled(True)
            else:
                self.trigger.setEnabled(False)
            
            self.randweight.setText(str(nodeobj.randweight))
            
            commentdoc = view.nodedocs[nodeID]["comment"]
            self.comment.setDocument(commentdoc)
            self.comment.moveCursor(QTextCursor.End)
        else:
            self.setEnabled(False)
            self.persistence.setCurrentText("")
            self.bankmode.setCurrentText("")
            self.questionhub.setCurrentText("")
            self.randweight.setText("")
            self.comment.setDocument(self.blankdoc)
    
    @pyqtSlot()
    def persistencechanged (self):
        if self.nodeobj is None:
            return
        persistence = self.persistence.currentText()
        self.nodeobj.persistence = persistence
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatepersistence")
    
    @pyqtSlot()
    def bankmodechanged (self):
        if self.nodeobj is None:
            return
        bankmode = self.bankmode.currentText()
        self.nodeobj.bankmode = bankmode
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatebankmode")
    
    @pyqtSlot()
    def questionhubchanged (self):
        if self.nodeobj is None:
            return
        questionhub = self.questionhub.currentText()
        self.nodeobj.questionhub = questionhub
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatequestionhub")
    
    @pyqtSlot()
    def triggerchanged (self):
        if self.nodeobj is None:
            return
        trigger = self.trigger.currentText()
        self.nodeobj.triggerconv = trigger
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatetrigger")
    
    @pyqtSlot()
    def randweightchanged (self):
        if self.nodeobj is None:
            return
        randweight = float(self.randweight.text())
        self.nodeobj.randweight = randweight
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updaterandweight")
    
    @pyqtSlot()
    def commentchanged (self):
        if self.nodeobj is None:
            return
        comment = self.comment.toPlainText()
        self.nodeobj.comment = comment

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

class MapView (QGraphicsView):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setOptimizationFlags(QGraphicsView.DontAdjustForAntialiasing | QGraphicsView.DontSavePainterState)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.setViewport(QGLWidget(QGLFormat(QGL.SampleBuffers)))
        self.setViewportUpdateMode(QGraphicsView.NoViewportUpdate)
        self.treeview = None
        self.blankscene = QGraphicsScene(self)
        self.setScene(self.blankscene)
        self.scenerect = self.viewrect = QRectF()
    
    def mousePressEvent (self, event):
        if self.treeview is None:
            return
        pos = event.pos()
        adjpos = self.mapToScene(pos)
        self.treeview.centerOn(adjpos)
    
    def mouseMoveEvent (self, event):
        if event.buttons():
            self.mousePressEvent(event)
    
    def mouseDoubleClickEvent (self, event):
        pass
    
    @pyqtSlot()
    def update (self):
        change = False
        window = FlGlob.mainwindow
        activeview = window.activeview
        if activeview is None:
            self.treeview = None
            self.setScene(self.blankscene)
            return
        if activeview is not self.treeview:
            self.treeview = activeview
            self.setScene(activeview.scene())
            change = True
        scenerect = activeview.sceneRect()
        if scenerect != self.scenerect:
            self.scenerect = scenerect
            self.setSceneRect(scenerect)
            change = True
        viewrect = activeview.viewframe.boundingRect()
        if viewrect != self.viewrect:
            self.viewrect = viewrect
            change = True
        if change:
            self.fitInView(scenerect, Qt.KeepAspectRatio)

class HistoryAction (object):
    def __init__ (self, unfunc, unargs, refunc, reargs, descr):
        self.unfunc = unfunc
        self.unargs = unargs.copy()
        self.unargs["undo"] = True
        self.refunc = refunc
        self.reargs = reargs.copy()
        self.reargs["undo"] = True
        self.descr = descr
    
    def undo (self):
        log("debug", "UNDO %s(%s)" % (self.unfunc.__name__, self.unargs))
        self.unfunc(**self.unargs)
    
    def redo (self):
        log("debug", "REDO %s(%s)" % (self.refunc.__name__, self.reargs))
        self.refunc(**self.reargs)

class TreeEditor (object):
    def __init__ (self, nodecontainer):
        self.nodecontainer = nodecontainer
        self.nodeorder = OrderedDict()
        self.changes = deque()
        self.collapsednodes = []
        self.nodedocs = dict()
        self.hits = None
        
        historysize = 10 # OPTION
        self.undohistory = deque(maxlen=historysize)
        self.redohistory = deque(maxlen=historysize)
    
    def traverse (self):
        queue = deque()
        # queue element: (fromID, toID, state)
        # state:         None: auto, 1: normal, 0: ghost, -1: hidden
        queue.append((None, "0", None))
        nodes = self.nodecontainer.nodes
        visitlog = dict()
        neworder = OrderedDict()
        
        def follow (ID, state, sub=False):
            if sub:
                links = nodes[ID].subnodes
            else:
                links = nodes[ID].linkIDs
            
            for nextID in links:
                queue.append((ID, nextID, state))
        
        while queue:
            refID, curID, state = queue.popleft()
            fullID = (refID, curID)
            if fullID in neworder:
                continue
            visited = curID in visitlog
            skipped = visitlog.get(curID, False)
            collapsed = fullID in self.collapsednodes
            
            prefstate = 0
            if collapsed:
                if not visited:
                    visitlog[curID] = fullID # skip
            elif (visited and skipped) or not visited:
                visitlog[curID] = False # proceed
                prefstate = 1
            
            neworder[fullID] = prefstate if state is None else state
            
            if prefstate or state is not None:
                follow(curID, state, sub=True)
                follow(curID, state)
            
            if not queue: 
                for refID, fullID in visitlog.items():
                    if fullID:
                        # dead end: all instances of this node are collapsed
                        fromID, toID = fullID
                        if neworder[fullID] == 0:
                            neworder[fullID] = 1 # un-ghost last instance
                        follow(curID, -1, sub=True)
                        follow(toID, -1)
                        visitlog[refID] = False
        
        missingraw = [(ID, s) for ID, s in self.nodeorder.items() if ID not in neworder]
        missing = []
        misskeys = []
        toremove = []
        for ID, state in missingraw:
            if state is None: # marked for removal
                toremove.append(ID)
            else:
                missing.append(ID)
                misskeys.append(ID[1])
        changes = []
        for fullID, state in neworder.items():
            fromID, toID = fullID
            if fullID in self.nodeorder and self.nodeorder[fullID] is None:
                changes.append(("newitem", (fullID, state)))
            elif fullID not in self.nodeorder:
                if toID in misskeys:
                    index = misskeys.index(toID)
                    misskeys.pop(index)
                    oldID = missing.pop(index)
                    changes.append(("reparent", (oldID, fullID)))
                    if self.nodeorder[oldID] != neworder[fullID]:
                        changes.append(("setstate", (fullID, state)))
                else:
                    changes.append(("newitem", (fullID, state)))
            elif state != self.nodeorder[fullID]:
                changes.append(("setstate", (fullID, state)))
        toremove.extend(missing)
        for fullID in toremove:
            changes.append(("removeitem", (fullID,)))
        
        log("debug", "CHANGES %s" % changes)
        self.trash = nodes - visitlog.keys()
        self.changes.extend(changes)
        self.nodeorder = neworder
    
    def updatedocs (self):
        newnodedocs = dict()
        for nodeID, nodeobj in self.nodecontainer.nodes.items():
            if nodeID in self.nodedocs:
                newnodedocs[nodeID] = self.nodedocs[nodeID]
            else:
                newnodedocs[nodeID] = dict()
                if nodeobj.typename in ("talk", "response"):
                    textdoc = QTextDocument(self)
                    textdoc.setDocumentLayout(QPlainTextDocumentLayout(textdoc))
                    textdoc.setPlainText(nodeobj.text)
                    newnodedocs[nodeID]["text"] = textdoc
                commentdoc = QTextDocument(self)
                commentdoc.setDocumentLayout(QPlainTextDocumentLayout(commentdoc))
                commentdoc.setPlainText(nodeobj.comment)
                newnodedocs[nodeID]["comment"] = commentdoc
                
                for s in ("enterscripts", "exitscripts", "condition"):
                    scriptdoc = QTextDocument(self)
                    scriptdoc.setDocumentLayout(QPlainTextDocumentLayout(scriptdoc))
                    scriptdoc.setPlainText(self.scripttotext(nodeobj.__dict__[s]))
                    newnodedocs[nodeID][s] = scriptdoc
        self.nodedocs = newnodedocs
    
    def scripttotext (self, script):
        def calltotext (call):
            text = ""
            if call.typename == "script":
                text += call.funcname
                paramstr = []
                for p in call.funcparams:
                    if isinstance(p, str):
                        paramstr.append('"%s"' % p)
                    else:
                        paramstr.append('%s' % p)
                text += "(%s)" % ", ".join(paramstr)
            elif call.typename == "wrap":
                text += "["
                text += " {op} ".format(op=call.operatorname).join(calltotext(c) for c in call.calls)
                text += "]"
            return text
        
        if isinstance(script, list):
            return "; ".join(calltotext(c) for c in script)
        else:
            return calltotext(script)
    
    def addundoable (self, hist):
        self.undohistory.appendleft(hist)
        self.redohistory.clear()
    
    def linknode (self, nodeID, refID, pos=None, undo=False):
        self.nodecontainer.newlink(refID, nodeID, pos)
        
        if not undo:
            hist = HistoryAction(self.unlink,
                {"nodeID": nodeID, "refID": refID},
                self.linknode,
                {"nodeID": nodeID, "refID": refID, "pos": pos},
                "Link node %s to node %s" % (nodeID, refID))
            self.addundoable(hist)
    
    def linksubnode (self, subID, bankID, pos, undo=False):
        """Only called as Undo action, assume sane arguments."""
        self.nodecontainer.nodes[bankID].subnodes.insert(pos, subID)
    
    def addnode (self, nodeID, typename="", ndict=None, undo=False):
        if ndict is not None:
            nodedict = ndict
        elif typename and typename in self.nodecontainer.templates:
            nodedict = self.nodecontainer.templates[typename]
        else:
            return
        newobj = self.nodecontainer.newnode(nodedict, refID=nodeID)
        newid = newobj.ID
        
        if not undo:
            hist = HistoryAction(self.unlink,
                {"nodeID": newid, "refID": nodeID},
                self.linknode,
                {"nodeID": newid, "refID": nodeID},
                "Link new node %s to node %s" % (newid, nodeID))
            self.addundoable(hist)
        return newid
    
    def addsubnode (self, nodeID, typename="", ndict=None, undo=False):
        if ndict is not None:
            nodedict = ndict
        elif typename and typename in self.nodecontainer.templates:
            nodedict = self.nodecontainer.templates[typename]
        else:
            return
        nodedictmod = nodedict.copy()
        nodedictmod["nodebank"] = nodeID
        newobj = self.nodecontainer.newnode(nodedictmod, bankID=nodeID)
        newid = newobj.ID
        if newobj.typename in ("talk", "response"):
            self.changebanktype(nodeID, newobj.typename)
        elif newobj.typename == "trigger":
            self.changebanktype(nodeID, "talk")
        elif newobj.typename == "bank":
            newobj.banktype = self.nodecontainer.nodes[nodeID].banktype
        
        if not undo:
            pos = self.nodecontainer.nodes[nodeID].subnodes.index(newid)
            hist = HistoryAction(self.unlinksubnode,
                {"subID": newid, "bankID": nodeID},
                self.linksubnode,
                {"subID": newid, "bankID": nodeID, "pos": pos},
                "Add new subnode %s to node %s" % (newid, nodeID))
            self.addundoable(hist)
        return newid
    
    def changebanktype (self, bankID, banktype):
        nodes = self.nodecontainer.nodes
        bankobj = nodes[bankID]
        bankobj.banktype = banktype
        if bankobj.nodebank != -1:
            if nodes[bankobj.nodebank].banktype:
                return
            self.changebanktype(bankobj.nodebank, banktype)
        else:
            bankobj.banktype = banktype
            subbanks = [nodes[subID] for subID in bankobj.subnodes if nodes[subID].typename == "bank"]
            while subbanks:
                subbank = subbanks.pop(-1)
                if subbank.banktype != banktype:
                    self.changebanktype(subbank.ID, banktype)
                subbanks.extend([nodes[subID] for subID in subbank.subnodes if nodes[subID].typename == "bank"])
    
    def unlink (self, nodeID, refID, undo=False):
        nodeitem = self.itembyID(nodeID)
        cont = self.nodecontainer
        refnode = cont.nodes[refID]
        pos = refnode.linkIDs.index(nodeID)
        refnode.linkIDs.remove(nodeID)
        
        if not undo:
            hist = HistoryAction(self.linknode, {"nodeID": nodeID, "refID": refID, "pos": pos},
                self.unlink, {"nodeID": nodeID, "refID": refID},
                "Unlink node %s with subtree from %s" % (nodeID, refID))
            self.addundoable(hist)
    
    def unlinksubnode (self, subID, bankID, undo=False):
        cont = self.nodecontainer
        pos = cont.nodes[bankID].subnodes.index(subID)
        cont.nodes[bankID].subnodes.remove(subID)
        
        if not undo:
            hist = HistoryAction(
                self.linksubnode,   {"subID": subID, "bankID": bankID, "pos": pos},
                self.unlinksubnode, {"subID": subID, "bankID": bankID},
                "Unlink subnode %s from bank %s" % (subID, bankID))
            self.addundoable(hist)
    
    def unlink_inherit (self, nodeID, refID, undo=False):
        cont = self.nodecontainer
        nodeobj = cont.nodes[nodeID]
        refnode = cont.nodes[refID]
        pos = refnode.linkIDs.index(nodeID)
        refnode.linkIDs.remove(nodeID)
        inherited = []
        index = pos
        for orphan in nodeobj.linkIDs:
            if orphan not in refnode.linkIDs:
                inherited.append(orphan)
                refnode.linkIDs.insert(index, orphan)
                index += 1
        
        if not undo:
            hist = HistoryAction(self.undoinherit,
                {"nodeID": nodeID, "refID": refID, "pos": pos, "inherited": inherited},
                self.unlink_inherit, {"nodeID": nodeID, "refID": refID},
                "Unlink node %s from node %s" % (nodeID, refID))
            self.addundoable(hist)
    
    def undoinherit (self, nodeID, refID, pos, inherited, undo=False):
        """Only called as Undo action, assume sane arguments."""
        cont = self.nodecontainer
        ref = cont.nodes[refID]
        for childID in inherited:
            ref.linkIDs.remove(childID)
        cont.newlink(refID, nodeID, pos)
    
    def move (self, nodeID, refID, up, undo=False):
        cont = self.nodecontainer
        parent = cont.nodes[refID]
        if cont.nodes[nodeID].nodebank == -1:
            siblings = parent.linkIDs
        else:
            siblings = parent.subnodes
        
        nodeind = siblings.index(nodeID)
        if up:
            sibind = nodeind-1
            desc = "up"
        else:
            sibind = nodeind+1
            desc = "down"
        
        siblings[nodeind], siblings[sibind] = siblings[sibind], siblings[nodeind]
        
        if not undo:
            hist = HistoryAction(
                self.move, {"nodeID": nodeID, "refID": refID, "up": not up}, 
                self.move, {"nodeID": nodeID, "refID": refID, "up": up},
                "Move node %s %s" % (nodeID, desc))
            self.addundoable(hist)
    
    def parentswap (self, gpID, parID, nodeID, pos=None, undo=False):
        log("debug", "PARENSTSWAP %s" % str((gpID, parID, nodeID, pos, undo)))
        nodes = self.nodecontainer.nodes
        parlinks = nodes[parID].linkIDs
        childlinks = nodes[nodeID].linkIDs
        grandpalinks = nodes[gpID].linkIDs
        
        childindex = parlinks.index(nodeID)
        parlinks.remove(nodeID)
        parlinks.insert(childindex, parID)
        
        if pos is not None:
            log("debug", "- duplicate -> pos: %s; gplinks: %s" % (pos, grandpalinks))
            parindex = pos
            grandpalinks.insert(pos, parID)
        else:
            parindex = grandpalinks.index(parID)
        grandpalinks.pop(parindex)
        
        if nodeID not in grandpalinks:
            grandpalinks.insert(parindex, nodeID)
            dupepos = None
        else:
            dupepos = parindex
        
        nodes[parID].linkIDs = childlinks
        nodes[nodeID].linkIDs = parlinks
        
        if not undo:
            hist = HistoryAction(self.parentswap,
                {"gpID": gpID, "parID": nodeID, "nodeID": parID, "pos": dupepos},
                self.parentswap,
                {"gpID": gpID, "parID": parID, "nodeID": nodeID, "pos": None},
                "Swap node %s with parent %s" % (nodeID, parID))
            self.addundoable(hist)
    
    def nodetobank (self, nodeID, subID=None, undo=False):
        cont = self.nodecontainer
        selnode = cont.nodes[nodeID]
        nodedict = selnode.todict()
        
        bankdict = nodedict.copy()
        bankdict["type"] = "bank"
        bankdict["banktype"] = nodedict["type"] if nodedict["type"] in ("talk", "response") else "talk"
        clonedict = nodedict.copy()
        clonedict["links"] = []
        clonedict["nodebank"] = nodeID
        
        cont.newnode(bankdict, newID=nodeID, force=True)
        if subID is None:
            newobj = cont.newnode(clonedict, bankID=nodeID)
            subID = newobj.ID
        else:
            cont.nodes[nodeID].subnodes.insert(0, subID)
        
        self.nodedocs[subID] = self.nodedocs[nodeID]
        self.nodedocs.pop(nodeID)
        
        if not undo:
            hist = HistoryAction(self.banktonode, {"nodeID": nodeID},
                self.nodetobank, {"nodeID": nodeID, "subID": subID},
                "Transform node %s to Bank" % nodeID)
            self.addundoable(hist)
    
    def banktonode (self, nodeID, undo=False):
        cont = self.nodecontainer
        selnode = cont.nodes[nodeID]
        subID = selnode.subnodes[0]
        nodedict = cont.nodes[subID].todict()
        
        clonedict = nodedict.copy()
        clonedict["nodebank"] = selnode.nodebank
        clonedict["links"] = selnode.linkIDs
        
        cont.newnode(clonedict, newID=nodeID, force=True)
        
        self.nodedocs[nodeID] = self.nodedocs[subID]
        
        if not undo:
            hist = HistoryAction(self.nodetobank, {"nodeID": nodeID, "subID": subID}, 
                self.banktonode, {"nodeID": nodeID},
                "Transform node %s from Bank" % nodeID)
            self.addundoable(hist)
    
    def splitnode (self, nodeID, splitID=None, undo=False):
        cont = self.nodecontainer
        selnode = cont.nodes[nodeID]
        
        if splitID is None:
            nodedict = selnode.todict()
            nodedict["subnodes"] = []
            newnode = cont.newnode(nodedict)
            newID = newnode.ID
        else:
            newID = splitID
        selnode.linkIDs = [newID]
        
        if not undo:
            hist = HistoryAction(
                self.unlink_inherit, {"nodeID": newID, "refID": nodeID}, 
                self.splitnode, {"nodeID": nodeID, "splitID": newID},
                "Split node %s" % nodeID)
            self.addundoable(hist)
    
    def collapse (self, fullID, collapse=None):
        if fullID in self.collapsednodes:
            if collapse is None or not collapse:
                desc = "Uncollapse"
                self.collapsednodes.remove(fullID)
                col = False
        else:
            if collapse is None or collapse:
                desc = "Collapse"
                self.collapsednodes.append(fullID)
                col = True
        self.itembyfullID(fullID).collapse(col)
    
    def getfield (self, nodeobj, field):
        objdict = nodeobj.__dict__
        if field in objdict:
            return str(objdict[field])
        elif field == "entername":
            return "\n".join([s.funcname for s in nodeobj.enterscripts])
        elif field == "enterarg":
            return "\n".join(["\n".join([str(p) for p in s.funcparams]) for s in nodeobj.enterscripts])
        elif field == "exitname":
            return "\n".join([s.funcname for s in nodeobj.exitscripts])
        elif field == "exitarg":
            return "\n".join(["\n".join([str(p) for p in s.funcparams]) for s in nodeobj.exitscripts])
        elif field == "condname":
            retval = ""
            conds = [nodeobj.condition]
            while conds:
                cond = conds.pop(-1)
                for call in cond.calls:
                    if call.typename == "script":
                        retval += call.funcname+"\n"
                    elif call.typename == "wrap":
                        conds.append(call)
            return retval
        elif field == "condarg":
            retval = ""
            conds = [nodeobj.condition]
            while conds:
                cond = conds.pop(-1)
                for call in cond.calls:
                    if call.typename == "script":
                        retval += "\n".join([str(p) for p in call.funcparams])
                    elif call.typename == "wrap":
                        conds.append(call)
            return retval
    
    def search (self, query, fields):
        if not query or True not in fields.values():
            self.hits = None
        else:
            hits = []
            for nodeID, nodeobj in self.nodecontainer.nodes.items():
                for field in fields:
                    if field and query in self.getfield(nodeobj, field).casefold():
                        hits.append(nodeID)
            self.hits = hits
    
    def removenodes (self, nodeIDs):
        for nodeID in nodeIDs:
            self.nodecontainer.nodes.pop(nodeID)
            self.nodedocs.pop(nodeID)
        self.undohistory.clear()
        self.redohistory.clear()
    
    def removetrash (self):
        for nodeID in self.trash:
            self.nodecontainer.nodes.pop(nodeID)
            self.nodedocs.pop(nodeID)
        self.undohistory.clear()
        self.redohistory.clear()

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

class NodeCopy (object):
    def __init__ (self, ID=None, view=None, ndict=None):
        self.ID = ID
        if view is None:
            self.view = self.blank # self.view needs to be callable
        else:
            self.view = weakref.ref(view)
        self.ndict = ndict
    
    def blank (self):
        return None

class EditorWindow (QMainWindow):
    copiednode = NodeCopy()
    globactions = dict()
    actions = dict()
    editdocks = dict()
    projects = dict()
    convs = dict()
    activeview = None
    activenode = ""
    selectednode = ""
    newProject = pyqtSignal(str)
    projectUpdated = pyqtSignal(str)
    viewChanged = pyqtSignal()
    viewUpdated = pyqtSignal()
    activeChanged = pyqtSignal(str)
    selectedChanged = pyqtSignal(str)
    tempID = 0
    
    def __init__ (self):
        super().__init__()
        
        FlGlob.mainwindow = self
        self.activeChanged.connect(self.loadnode)
        self.selectedChanged.connect(self.filteractions)
        self.viewChanged.connect(self.filterglobactions)
        
        self.style = FlNodeStyle(QFont())
        self.initactions()
        self.initmenus()
        self.inittoolbars()
        
        tabs = QTabWidget(parent=self)
        tabs.setTabsClosable(True)
        tabs.setTabBarAutoHide(True)
        tabs.tabCloseRequested.connect(self.closetab)
        tabs.tabBarDoubleClicked.connect(self.nametab)
        tabs.currentChanged.connect(self.tabswitched)
        self.tabs = tabs
        
        self.setCentralWidget(tabs)
        self.initdocks()
        self.filterglobactions()
        self.filteractions()
    
    def initactions (self):
        self.globactions["openfile"] = self.createaction("&Open", self.selectopenfile,
            (QKeySequence.Open), "document-open", "Open Conversation file")
        self.globactions["save"] = self.createaction("&Save", self.save,
            (QKeySequence.Save), "document-save", "Save Conversation file")
        self.globactions["saveas"] = self.createaction("Save &As", self.saveas,
            (QKeySequence.SaveAs), "document-save-as", "Save Conversation file as")
        self.globactions["newproj"] = self.createaction("New &Project", self.newproj,
            None, "folder-new", "New Project")
        self.globactions["newconv"] = self.createaction("New &Conversation", self.newconv,
            (QKeySequence.New), "document-new", "New Conversation")
        self.globactions["close"] = self.createaction("Close", self.closefile,
            None, "window-close", "Close file")
        self.globactions["zoomin"] = self.createaction("Zoom &In", self.zoomin, 
            (QKeySequence.ZoomIn, QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_Plus)), 
            "zoom-in", "Zoom in")
        self.globactions["zoomout"] = self.createaction("Zoom &Out", self.zoomout, 
            (QKeySequence.ZoomOut, QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_Minus)), 
            "zoom-out", "Zoom out")
        self.globactions["zoomorig"] = self.createaction("Zoom O&riginal", self.zoomorig, 
            (QKeySequence(Qt.ControlModifier + Qt.Key_0), QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_0)), 
            "zoom-original", "Zoom to original size")
        self.globactions["refresh"] = self.createaction("Refresh", self.refresh,
            (QKeySequence(Qt.Key_F5)), "view-refresh", "Refresh view")
        self.globactions["reloadscripts"] = self.createaction("Reload Scripts", self.reloadscripts,
            None, "view-refresh", "Reload scripts from file")
        self.globactions["playconv"] = self.createaction("Play Conversation", self.playconv,
            None, "media-playback-start", "Play Conversation")
        
        self.actions["undo"] = self.createaction("&Undo", self.undofactory(1),
            (QKeySequence.Undo), "edit-undo", "Undo last action")
        self.actions["redo"] = self.createaction("&Redo", self.redofactory(1),
            (QKeySequence.Redo), "edit-redo", "Redo action")
        self.actions["gotoactive"] = self.createaction("Go To &Active", self.gotoactive, 
            None, "go-jump", "Center on active node")
        self.actions["selectreal"] = self.createaction("Select &Real", self.selectreal, 
            None, "go-jump", "Select real node")
        
        self.actions["newtalk"] = self.createaction("New &Talk Node", self.newtalk,
            (QKeySequence(Qt.ControlModifier+Qt.Key_T)), "insert-object", "Add new Talk node")
        self.actions["newresponse"] = self.createaction("New &Response Node", self.newresponse,
            (QKeySequence(Qt.ControlModifier+Qt.Key_R)), "insert-object", "Add new Response node")
        self.actions["newbank"] = self.createaction("New &Bank Node", self.newbank,
            (QKeySequence(Qt.ControlModifier+Qt.Key_B)), "insert-object", "Add new Bank node")
        self.actions["newtrigger"] = self.createaction("New Tri&gger Node", self.newtrigger,
            (QKeySequence(Qt.ControlModifier+Qt.Key_G)), "insert-object", "Add new Trigger node")
        self.actions["copynode"] = self.createaction("&Copy Node", self.copynode,
            (QKeySequence.Copy), "edit-copy", "Copy node")
        self.actions["pasteclone"] = self.createaction("Paste &Clone", self.pasteclone,
            (QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_V)), "edit-paste", "Paste cloned node")
        self.actions["pastelink"] = self.createaction("Paste &Link", self.pastelink,
            (QKeySequence.Paste), "insert-link", "Paste link to node")
        self.actions["unlinkstree"] = self.createaction("Unlink &Subtree", self.unlink,
            (QKeySequence.Delete), "edit-clear", "Unlink subtree from parent")
        self.actions["unlinknode"] = self.createaction("Unlink &Node", self.unlinkinherit,
            (QKeySequence(Qt.ControlModifier+Qt.Key_Delete)), "edit-delete", "Unlink node and let parent inherit its child nodes")
        self.actions["moveup"] = self.createaction("Move &Up", self.moveup,
            (QKeySequence(Qt.ShiftModifier+Qt.Key_Up)), "go-up", "Move node up")
        self.actions["movedown"] = self.createaction("Move &Down", self.movedown,
            (QKeySequence(Qt.ShiftModifier+Qt.Key_Down)), "go-down", "Move node down")
        self.actions["collapse"] = self.createaction("(Un)Colla&pse subtree", self.collapse,
            (QKeySequence(Qt.ControlModifier+Qt.Key_Space)), None, "(Un)Collapse subtree")
        self.actions["newtalksub"] = self.createaction("New &Talk Subnode", self.newtalksub,
            (QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_T)), "insert-object", "Add new Talk subnode")
        self.actions["newbanksub"] = self.createaction("New &Bank Subnode", self.newbanksub,
            (QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_B)), "insert-object", "Add new Bank subnode")
        self.actions["newresponsesub"] = self.createaction("New &Response Subnode", self.newresponsesub,
            (QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_R)), "insert-object", "Add new Response subnode")
        self.actions["newtriggersub"] = self.createaction("New Tri&gger Subnode", self.newtriggersub,
            (QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_G)), "insert-object", "Add new Trigger subnode")
        self.actions["pastesubnode"] = self.createaction("&Paste Subnode", self.pastesubnode,
            (QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_C)), "edit-paste", "Paste cloned node as subnode")
        self.actions["parentswap"] = self.createaction("S&wap with Parent", self.parentswap,
            (QKeySequence(Qt.ShiftModifier+Qt.Key_Left)), "go-left", "Swap places with parent node")
        self.actions["settemplate"] = self.createaction("Set as Te&mplate", self.settemplate,
            None, "text-x-generic-template", "Set node as the template for its type")
        
        self.actions["nodetobank"] = self.createaction("Regular -> Bank", self.nodetobank,
            None, None, "Transform node into a Bank node")
        self.actions["banktonode"] = self.createaction("Bank -> Regular", self.banktonode,
            None, None, "Transform Bank node into a regular node")
        self.actions["splitnode"] = self.createaction("Split Node", self.splitnode,
            None, None, "Split node in two")
    
    def createaction (self, text, slot=None, shortcuts=None, icon=None,
                     tip=None, checkable=False):
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(QIcon.fromTheme(icon))
        if shortcuts is not None:
            action.setShortcuts(shortcuts)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            action.triggered.connect(slot)
        if checkable:
            action.setCheckable(True)
        return action
    
    def initmenus (self):
        menubar = self.menuBar()
        
        filemenu = menubar.addMenu("&File")
        filemenu.addAction(self.globactions["openfile"])
        filemenu.addAction(self.globactions["newproj"])
        filemenu.addAction(self.globactions["newconv"])
        filemenu.addSeparator()
        filemenu.addAction(self.globactions["save"])
        filemenu.addAction(self.globactions["saveas"])
        filemenu.addSeparator()
        filemenu.addAction(self.globactions["playconv"])
        filemenu.addSeparator()
        filemenu.addAction(self.globactions["close"])
        
        addmenu = QMenu("Add &link...")
        addmenu.addAction(self.actions["pasteclone"])
        addmenu.addAction(self.actions["pastelink"])
        addmenu.addSeparator()
        addmenu.addAction(self.actions["newtalk"])
        addmenu.addAction(self.actions["newresponse"])
        addmenu.addAction(self.actions["newbank"])
        addmenu.addAction(self.actions["newtrigger"])
        addmenu.setIcon(QIcon.fromTheme("insert-object"))
        self.addmenu = addmenu
        
        subnodemenu = QMenu("Add &subnode...")
        subnodemenu.addAction(self.actions["pastesubnode"])
        subnodemenu.addSeparator()
        subnodemenu.addAction(self.actions["newtalksub"])
        subnodemenu.addAction(self.actions["newresponsesub"])
        subnodemenu.addAction(self.actions["newbanksub"])
        subnodemenu.addAction(self.actions["newtriggersub"])
        subnodemenu.setIcon(QIcon.fromTheme("insert-object"))
        self.subnodemenu = subnodemenu
        
        transformmenu = QMenu("Trans&form...")
        transformmenu.addAction(self.actions["nodetobank"])
        transformmenu.addAction(self.actions["banktonode"])
        transformmenu.addAction(self.actions["splitnode"])
        self.transformmenu = transformmenu
        
        undomenu = QMenu("Undo")
        undomenu.setIcon(QIcon.fromTheme("edit-undo"))
        def generateundo ():
            undomenu.clear()
            undo = self.activeview.undohistory
            for i in range(len(undo)):
                action = undo[i]
                item = QAction("%s: %s" % (i+1, action.descr), self)
                item.triggered.connect(self.undofactory(i+1))
                undomenu.addAction(item)
        undomenu.aboutToShow.connect(generateundo)
        self.actions["undo"].setMenu(undomenu)
        
        redomenu = QMenu("Redo")
        redomenu.setIcon(QIcon.fromTheme("edit-redo"))
        def generateredo ():
            redomenu.clear()
            redo = self.activeview.redohistory
            for i in range(len(redo)):
                action = redo[i]
                item = QAction("%s: %s" % (i+1, action.descr), self)
                item.triggered.connect(self.redofactory(i+1))
                redomenu.addAction(item)
        redomenu.aboutToShow.connect(generateredo)
        self.actions["redo"].setMenu(redomenu)
        
        editmenu = menubar.addMenu("&Edit")
        editmenu.addAction(self.actions["undo"])
        editmenu.addAction(self.actions["redo"])
        editmenu.addMenu(addmenu)
        editmenu.addMenu(subnodemenu)
        editmenu.addAction(self.actions["copynode"])
        editmenu.addAction(self.actions["moveup"])
        editmenu.addAction(self.actions["movedown"])
        editmenu.addAction(self.actions["parentswap"])
        editmenu.addAction(self.actions["settemplate"])
        editmenu.addMenu(transformmenu)
        editmenu.addSeparator()
        editmenu.addAction(self.actions["unlinknode"])
        editmenu.addAction(self.actions["unlinkstree"])
        self.editmenu = editmenu
        
        viewmenu = menubar.addMenu("&View")
        viewmenu.addAction(self.globactions["zoomin"])
        viewmenu.addAction(self.globactions["zoomout"])
        viewmenu.addAction(self.globactions["zoomorig"])
        viewmenu.addAction(self.actions["gotoactive"])
        viewmenu.addAction(self.actions["selectreal"])
        viewmenu.addAction(self.actions["collapse"])
        viewmenu.addAction(self.globactions["refresh"])
        
        windowmenu = menubar.addMenu("&Window")
        def generatemenu ():
            windowmenu.clear()
            menu = self.createPopupMenu()
            menu.setTitle("Tools")
            windowmenu.addMenu(menu)
        windowmenu.aboutToShow.connect(generatemenu)
    
    def inittoolbars (self):
        filetoolbar = QToolBar("File actions")
        filetoolbar.addAction(self.globactions["openfile"])
        filetoolbar.addAction(self.globactions["newproj"])
        filetoolbar.addAction(self.globactions["save"])
        filetoolbar.addAction(self.globactions["playconv"])
        self.addToolBar(filetoolbar)
        
        historytoolbar = QToolBar("History")
        historytoolbar.addAction(self.actions["undo"])
        historytoolbar.addAction(self.actions["redo"])
        self.addToolBar(historytoolbar)
        
        viewtoolbar = QToolBar("View control")
        viewtoolbar.addAction(self.globactions["zoomorig"])
        viewtoolbar.addAction(self.globactions["zoomin"])
        viewtoolbar.addAction(self.globactions["zoomout"])
        viewtoolbar.addAction(self.actions["gotoactive"])
        self.addToolBar(viewtoolbar)
        
        edittoolbar = QToolBar("Tree editing")
        edittoolbar.addAction(self.actions["copynode"])
        edittoolbar.addAction(self.actions["pasteclone"])
        edittoolbar.addAction(self.actions["pastelink"])
        edittoolbar.addAction(self.actions["unlinknode"])
        edittoolbar.addAction(self.actions["unlinkstree"])
        edittoolbar.addAction(self.actions["moveup"])
        edittoolbar.addAction(self.actions["movedown"])
        self.addToolBar(edittoolbar)
    
    def initdocks (self):
        mapview = MapView(self)
        maptimer = QTimer(self)
        maptimer.timeout.connect(mapview.update)
        maptimer.start(100) # OPTION: mapview frame rate
        mapdock = QDockWidget("Map view", self)
        mapdock.setWidget(mapview)
        
        textdock = QDockWidget("&Text", self)
        textdock.setWidget(TextEditWidget(self))
        self.editdocks["text"] = textdock
        
        conddock = QDockWidget("&Condition", self)
        conddock.setWidget(ScriptWidget(self, "condition"))
        self.editdocks["cond"] = conddock
        
        onenterdock = QDockWidget("On E&nter", self)
        onenterdock.setWidget(ScriptWidget(self, "enterscripts"))
        self.editdocks["enter"] = onenterdock
        
        onexitdock = QDockWidget("On E&xit", self)
        onexitdock.setWidget(ScriptWidget(self, "exitscripts"))
        self.editdocks["exit"] = onexitdock
        
        """scriptdock = QDockWidget("&Script", self)
        scriptdock.setWidget(ScriptWidget(self, "condition"))
        self.editdocks["script"] = scriptdock"""
        
        propdock = QDockWidget("&Properties", self)
        propdock.setWidget(PropertiesEditWidget(self))
        self.editdocks["prop"] = propdock
        
        projwidget = ProjectWidget(self)
        self.newProject.connect(projwidget.addproject)
        self.projectUpdated.connect(projwidget.updateproject)
        projwidget.tree.itemSelectionChanged.connect(self.filterglobactions)
        self.projwidget = projwidget
        projdock = QDockWidget("Projects", self)
        projdock.setWidget(projwidget)
        
        nodelist = NodeListWidget(self)
        self.viewChanged.connect(nodelist.setview)
        self.viewUpdated.connect(nodelist.populatelist)
        self.selectedChanged.connect(nodelist.selectbyID)
        listdock = QDockWidget("Node &List", self)
        listdock.setWidget(nodelist)
        self.listdock = listdock
        
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)
        self.addDockWidget(Qt.RightDockWidgetArea, mapdock)
        
        self.addDockWidget(Qt.RightDockWidgetArea, textdock)
        self.tabifyDockWidget(textdock, conddock)
        self.tabifyDockWidget(conddock, onenterdock)
        self.tabifyDockWidget(onenterdock, onexitdock)
        self.tabifyDockWidget(onexitdock, propdock)
        #self.tabifyDockWidget(textdock, propdock)
        #self.tabifyDockWidget(propdock, scriptdock)
        #textdock.raise_()
        
        self.addDockWidget(Qt.LeftDockWidgetArea, projdock)
        self.addDockWidget(Qt.LeftDockWidgetArea, listdock)
    
    @pyqtSlot()
    def filterglobactions (self):
        view = self.activeview
        if view is None:
            actions = ("openfile", "newproj")
        else:
            actions = ("zoomin", "zoomout", "zoomorig", "openfile", 
                "save", "saveas", "newproj", "close")
            if not view.playmode:
                actions += ("refresh", "playconv")
        if self.projwidget.currentproj() is not None:
            actions += ("newconv", "reloadscripts")
        for name, action in self.globactions.items():
            if name in actions:
                action.setEnabled(True)
            else:
                action.setEnabled(False)
    
    @pyqtSlot()
    def filteractions (self):
        view = self.activeview
        genericactions = ()
        actions = ()
        if view and not view.playmode:
            if view.undohistory:
                genericactions += ("undo",)
            if view.redohistory:
                genericactions += ("redo",)
            if view.activenode:
                genericactions += ("gotoactive",)
            if view.selectednode:
                genericactions += ("collapse", "selectreal")
            
            nodes = view.nodecontainer.nodes
            if self.selectednode and self.selectednode in nodes:
                nodeobj = nodes[self.selectednode]
                if self.selectednode not in view.itemindex:
                    if nodeobj.typename != "root":
                        actions = ("copynode", "settemplate")
                elif nodeobj.typename in ("talk", "response"):
                    actions = ("copynode", "moveup", "movedown", "unlinknode", 
                        "unlinkstree", "settemplate", "nodetobank")
                    if nodeobj.nodebank == -1:
                        actions += ("newtalk", "newresponse", "newbank", "newtrigger",
                            "pasteclone", "pastelink", "parentswap", "splitnode")
                elif nodeobj.typename == "bank":
                    actions = ("copynode", "moveup", "movedown", "unlinknode",
                        "unlinkstree", "pastesubnode", "newbanksub", "settemplate")
                    if not nodeobj.banktype or nodeobj.banktype == "talk":
                        actions += ("newtalksub", "newtriggersub")
                    if not nodeobj.banktype or nodeobj.banktype == "response":
                        actions += ("newresponsesub",)
                    if nodeobj.nodebank == -1:
                        actions += ("newtalk", "newresponse", "newbank", "newtrigger",
                            "pasteclone", "pastelink", "parentswap", "splitnode")
                    if len(nodeobj.subnodes) == 1:
                        actions += ("banktonode",)
                elif nodeobj.typename == "root":
                    actions = ("newtalk", "newresponse", "newbank", "pasteclone",
                        "pastelink")
                elif nodeobj.typename == "trigger":
                    actions = ("copynode", "settemplate", "moveup", "movedown",
                        "unlinknode", "unlinkstree", "nodetobank")
        
        actions += genericactions
        for name, action in self.actions.items():
            if name in actions:
                if name == "pasteclone" or name == "pastesubnode":
                    if self.copiednode.ndict is not None:
                        action.setEnabled(True)
                    else:
                        action.setEnabled(False)
                elif name == "pastelink":
                    if self.copiednode.view() is view and self.copiednode.ID in view.nodecontainer.nodes: 
                        action.setEnabled(True)
                    else:
                        action.setEnabled(False)
                else:
                    action.setEnabled(True)
            else:
                action.setEnabled(False)
    
    @pyqtSlot(int)
    def tabswitched (self, index):
        view = self.tabs.widget(index)
        self.setactiveview(view)
    
    def setactiveview (self, view):
        if view is self.activeview:
            return #nothing to do
        self.activeview = view
        if view is not None:
            if view.activenode is not None:
                self.setactivenode(view, view.activenode.realid())
            else:
                self.setactivenode(view, "-1")
            if view.selectednode is not None:
                self.setselectednode(view, view.selectednode.realid())
            else:
                self.setselectednode(view, "-1")
        else:
            self.setactivenode(view, "-1")
            self.setselectednode(view, "-1")
        self.viewChanged.emit()
    
    def setactivenode (self, view, nodeID):
        self.setactiveview(view)
        self.activenode = nodeID
        self.activeChanged.emit(nodeID)
    
    def setselectednode (self, view, nodeID):
        self.setactiveview(view)
        self.selectednode = nodeID
        self.selectedChanged.emit(nodeID)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        for dock in self.editdocks.values():
            dock.widget().loadnode(nodeID)
    
    @pyqtSlot()
    def selectopenfile (self):
        filters = OrderedDict()
        filters["Project files (*.proj)"] = self.openproj
        filters["Conversation files (*.conv)"] = self.openconvfile
        filename, selfilter = QFileDialog.getOpenFileName(self, "Open file", 
            os.getcwd(), ";;".join(filters.keys()))
        if filename == "":
            return
        filters[selfilter](filename)
    
    def openproj (self, filename):
        if filename in self.projects:
            return
        
        try:
            proj = pp.loadjson(filename)
            path = proj.filename
            if path in self.projects:
                return
            self.projects[path] = proj
            self.newProject.emit(path)
        except Exception as e:
            log("error", "Failed loading %s: %s" % (filename, repr(e)))
    
    @pyqtSlot()
    def newproj (self):
        filename = QFileDialog.getSaveFileName(self, "Create new Project", 
                os.path.join(os.getcwd(), "Untitled.proj"),
                "Project files (*.proj)")[0]
        if filename:
            try:
                proj = pp.newproject(filename)
                self.projects[proj.filename] = proj
                self.newProject.emit(proj.filename)
                proj.savetofile()
            except Exception as e:
                log("error", "Failed creating project: %s" % repr(e))
    
    @pyqtSlot()
    def reloadscripts (self):
        projfile = self.projwidget.currentproj()
        if projfile is None:
            return
        proj = self.projects[projfile]
        proj.reloadscripts()
        for conv in proj.convs:
            abspath = proj.checkpath(conv)
            if abspath and abspath in self.convs:
                view = self.convs[abspath]()
                view.nodecontainer.reinitscripts()
                if view is self.activeview:
                    view.updateview()
        for conv in proj.tempconvs:
            if conv in self.convs:
                view = self.convs[abspath]()
                view.nodecontainer.reinitscripts()
                if view is self.activeview:
                    view.updateview()
    
    def openconvfile (self, filename):
        try:
            cont = cp.loadjson(filename)
            if cont.projfile:
                projfile = os.path.join(os.path.dirname(filename), cont.projfile)
                self.openproj(projfile)
                if projfile not in self.projects:
                    return
                cont.proj = self.projects[projfile]
                cont.reinitscripts()
            treeview = TreeView(cont, parent=self)
            self.newtab(treeview)
        except Exception as e:
            log("error", "Failed opening %s: %s" % (filename, repr(e)))
    
    def openconv (self, projfile, relpath):
        proj = self.projects[projfile]
        abspath = proj.checkpath(relpath)
        if relpath.startswith("\0TEMP"):
            if relpath in self.convs:
                view = self.convs[relpath]()
                self.tabs.setCurrentWidget(view)
            else:
                log("error", "Temprorary ID invalid: %s" % relpath)
        elif abspath is None:
            log("error", "Not part of project or no such file: %s" % relpath)
        elif abspath in self.convs:
            view = self.convs[abspath]()
            if view is not None:
                if view.nodecontainer.proj is None:
                    cont = view.nodecontainer
                    cont.proj = proj
                    cont.reinitscripts()
                    view.updateview()
                    self.projectUpdated.emit(proj.filename)
                else:
                    self.tabs.setCurrentWidget(view)
            else:
                log("error", "Conversation no longer open: %s" % abspath)
        else:
            cont = cp.loadjson(abspath, proj)
            treeview = TreeView(cont, parent=self)
            self.newtab(treeview)
    
    @pyqtSlot()
    def newconv (self):
        projfile = self.projwidget.currentproj()
        if projfile is None:
            return
        proj = self.projects[projfile]
        nodecontainer = cp.newcontainer(proj)
        treeview = TreeView(nodecontainer, parent=self)
        self.newtab(treeview)
    
    def newtempID (self):
        viewid = "\0TEMP%s" % self.tempID
        self.tempID += 1
        return viewid
    
    def newtab (self, treeview):
        name = treeview.nodecontainer.name
        filename = treeview.nodecontainer.filename
        log("debug", "newtab %s" % filename)
        if filename:
            viewid = filename
        else:
            viewid = "\0TEMP%s" % self.tempID
            self.tempID += 1
            treeview.nodecontainer.filename = viewid
        self.convs[viewid] = weakref.ref(treeview)
        self.selectedChanged.connect(treeview.selectbyID)
        self.activeChanged.connect(treeview.activatebyID)
        tabindex = self.tabs.addTab(treeview, name)
        self.tabs.setCurrentIndex(tabindex)
        if treeview.nodecontainer.proj is None:
            log("warn", "This Conversation is not part of a Project. Script editing is disabled.")
        else:
            if viewid.startswith("\0TEMP"):
                treeview.nodecontainer.proj.tempconvs.append(viewid)
            self.projectUpdated.emit(treeview.nodecontainer.proj.filename)
    
    @pyqtSlot()
    def save (self, newfile=False):
        view = self.activeview
        convID = view.nodecontainer.filename
        self.saveconv(convID, newfile)
    
    def saveconv (self, convID, newfile=False):
        view = self.convs.get(convID)()
        if view is None:
            log("error", "Unknown conversation: %s" % convID)
        cont = view.nodecontainer
        if not cont.filename or convID.startswith("\0TEMP") or newfile:
            filename = QFileDialog.getSaveFileName(self, "Save as...", 
                os.path.join(os.getcwd(), (cont.name or "Untitled")+".conv"),
                "Conversation files (*.conv)")[0]
            if not filename:
                return None
            cont.filename = filename
            self.convs[filename] = self.convs[convID]
            self.convs.pop(convID)
        cont.savetofile()
        if cont.proj is not None:
            if convID in cont.proj.tempconvs:
                cont.proj.tempconvs.remove(convID)
            cont.proj.registerconv(cont.filename)
            self.projectUpdated.emit(cont.proj.filename)
            cont.proj.savetofile()
        return True
    
    @pyqtSlot()
    def saveas (self):
        self.save(newfile=True)
    
    @pyqtSlot()
    def closefile (self):
        view = self.activeview
        if view is None:
            return
        self.closeview(view)
    
    def closeview (self, view):
        index = self.tabs.indexOf(view)
        self.closetab(index)
    
    @pyqtSlot(int)
    def closetab (self, index):
        view = self.tabs.widget(index)
        proj = view.nodecontainer.proj
        filename = view.nodecontainer.filename
        answer = QMessageBox.question(self, "Close Conversation", "Save changes before closing?", 
            buttons=(QMessageBox.Cancel|QMessageBox.No|QMessageBox.Yes), defaultButton=QMessageBox.Yes)
        if answer == QMessageBox.Yes:
            ret = self.saveconv(view.nodecontainer.filename)
            if ret is None:
                return
        elif answer != QMessageBox.No:
            return
        if filename and filename in self.convs:
            self.convs.pop(filename)
        self.tabs.removeTab(index)
        view.deleteLater()
        view = None
        gc.collect()
        if proj is not None:
            self.projectUpdated.emit(proj.filename)
    
    @pyqtSlot(int)
    def nametab (self, index):
        if index == -1:
            return
        view = self.tabs.widget(index)
        name = view.nodecontainer.name
        newname = QInputDialog.getText(self, "Rename", "Conversation title:", text=name)
        if newname[1] and newname[0] != "":
            view.nodecontainer.name = newname[0]
            self.tabs.setTabText(index, newname[0])
    
    @pyqtSlot()
    def playconv (self):
        view = self.activeview
        proj = view.nodecontainer.proj
        projfile = proj.filename
        player = play.TextPlayer(self, projfile)
        player.setWindowFlags(Qt.Dialog)
        view.setplaymode(True)
        player.showedNode.connect(view.playshowID)
        player.visitedNode.connect(view.playvisitID)
        player.closed.connect(self.playquitfactory(view))
        player.startconv(view.nodecontainer)
        player.show()
        self.filterglobactions()
        self.filteractions()
    
    def playquitfactory (self, view):
        @pyqtSlot()
        def playquit ():
            view.setplaymode(False)
            self.filterglobactions()
            self.filteractions()
        return playquit
    
    @pyqtSlot()
    def zoomin (self):
        self.activeview.zoomstep(1)
    
    @pyqtSlot()
    def zoomout (self):
        self.activeview.zoomstep(-1)
    
    @pyqtSlot()
    def zoomorig (self):
        self.activeview.zoomfixed(1)
    
    @pyqtSlot()
    def gotoactive (self):
        view = self.activeview
        view.centerOn(view.activenode)
    
    @pyqtSlot()
    def selectreal (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.setselectednode(view.itembyID(nodeID))
    
    @pyqtSlot()
    def refresh (self):
        view = self.activeview
        view.updateview(refresh=True)
    
    @pyqtSlot()
    def newtalk (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addnode(nodeID, typename="talk")
    
    @pyqtSlot()
    def newresponse (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addnode(nodeID, typename="response")
    
    @pyqtSlot()
    def newbank (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addnode(nodeID, typename="bank")
    
    @pyqtSlot()
    def newtrigger (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addnode(nodeID, typename="trigger")
    
    @pyqtSlot()
    def newtalksub (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addsubnode(nodeID, typename="talk")
    
    @pyqtSlot()
    def newresponsesub (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addsubnode(nodeID, typename="response")
    
    @pyqtSlot()
    def newbanksub (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addsubnode(nodeID, typename="bank")
    
    @pyqtSlot()
    def newtriggersub (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addsubnode(nodeID, typename="trigger")
    
    @pyqtSlot()
    def copynode (self):
        view = self.activeview
        if self.selectednode not in view.nodecontainer.nodes:
            return
        nodeobj = view.nodecontainer.nodes[self.selectednode]
        nodedict = nodeobj.todict()
        nodedict["links"] = []
        nodedict["nodebank"] = -1
        nodedict["subnodes"] = []
        
        if nodeobj.nodebank != -1 or nodeobj.ID in view.trash:
            self.copiednode = NodeCopy(ID=None, view=None, ndict=nodedict)
        else:
            self.copiednode = NodeCopy(ID=nodeobj.ID, view=view, ndict=nodedict)
        
        self.actions["pasteclone"].setText("Paste &Clone (node %s)" % nodeobj.ID)
        self.actions["pastelink"].setText("Paste &Link (node %s)" % nodeobj.ID)
        self.actions["pastesubnode"].setText("&Paste Subnode (node %s)" % nodeobj.ID)
        self.filteractions()
    
    @pyqtSlot()
    def settemplate (self):
        view = self.activeview
        if self.selectednode not in view.nodecontainer.nodes:
            return
        nodeobj = view.nodecontainer.nodes[self.selectednode].copy()
        nodeobj.linkIDs = []
        nodeobj.subnodes = []
        nodeobj.nodebank = -1
        nodedict = nodeobj.todict()
        typename = nodedict["type"]
        view.nodecontainer.templates[typename] = nodedict
    
    @pyqtSlot()
    def pasteclone (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addnode(nodeID, ndict=self.copiednode.ndict)
    
    @pyqtSlot()
    def pastelink (self):
        view = self.activeview
        refID = view.selectednode.realid()
        view.linknode(self.copiednode.ID, refID)
    
    @pyqtSlot()
    def pastesubnode (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addsubnode(nodeID, ndict=self.copiednode.ndict)
    
    @pyqtSlot()
    def unlinkinherit (self):
        self.unlink(inherit=True)
    
    @pyqtSlot()
    def unlink (self, inherit=False):
        view = self.activeview
        selected = view.selectednode
        selID = selected.realid()
        if selected.refID is None:
            return
        if len(view.itemindex[selID]) == 1:
            if inherit or len(selected.nodeobj.linkIDs) == 0:
                text = "Unlink unique node %s?" % selID
            else:
                text = "Unlink unique node %s and its subtree?" % selID
        else:
            text = "Unlink node %s from node %s?" % (selID, selected.refID)
        answer = QMessageBox.question(self, "Unlink", text, defaultButton=QMessageBox.Yes)
        if answer == QMessageBox.No:
            return
        
        if selected.issubnode():
            view.unlinksubnode(selID, selected.refID)
        elif inherit:
            view.unlink_inherit(selID, selected.refID)
        else:
            view.unlink(selID, selected.refID)
    
    @pyqtSlot()
    def moveup (self):
        view = self.activeview
        selnode = view.selectednode
        nodeID = selnode.realid()
        refID = selnode.refID
        if selnode.siblingabove() is not None:
            view.move(nodeID, refID, up=True)
    
    @pyqtSlot()
    def movedown (self):
        view = self.activeview
        selnode = view.selectednode
        nodeID = selnode.realid()
        refID = selnode.refID
        if selnode.siblingbelow() is not None:
            view.move(nodeID, refID, up=False)
    
    @pyqtSlot()
    def parentswap (self):
        view = self.activeview
        selnode = view.selectednode
        nodeID = selnode.realid()
        parID = selnode.refID
        if parID is None:
            return
        gpID = view.itembyID(parID).refID
        if gpID is None or gpID == nodeID:
            return
        view.parentswap(gpID, parID, nodeID)
    
    @pyqtSlot()
    def nodetobank (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.nodetobank(nodeID)
    
    @pyqtSlot()
    def banktonode (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.banktonode(nodeID)
    
    @pyqtSlot()
    def splitnode (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.splitnode(nodeID)
    
    @pyqtSlot()
    def collapse (self):
        view = self.activeview
        fullID = view.selectednode.id()
        view.collapse(fullID)
    
    def undofactory (self, num):
        @pyqtSlot()
        def undo ():
            view = self.activeview
            count = num
            while count:
                action = view.undohistory.popleft()
                action.undo()
                view.redohistory.appendleft(action)
                count -= 1
            view.updateview()
        
        return undo
    
    def redofactory (self, num):
        @pyqtSlot()
        def redo ():
            view = self.activeview
            count = num
            while count:
                action = view.redohistory.popleft()
                action.redo()
                view.undohistory.appendleft(action)
                count -= 1
            view.updateview()
        
        return redo

def elidestring (string, length):
    if len(string) <= length:
        return string
    else:
        return string[:length-1]+"…"

if __name__ == '__main__':
    app = QApplication(sys.argv)
    for arg in sys.argv[1:]:
        split = arg.split("=", maxsplit=1)
        argname = split[0]
        param = split[1] if len(split)>1 else None
        if argname == "--loglevel":
            if param in FlGlob.loglevels:
                FlGlob.loglevel = FlGlob.loglevels[param]
                log("info", "Loglevel: %s" % param)
            else:
                log("warn", "Unrecognized loglevel: %s" % param)
        elif argname == "--icontheme":
            QIcon.setThemeName(param)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec_())
