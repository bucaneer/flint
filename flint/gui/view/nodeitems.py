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

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsItemGroup, 
    QGraphicsRectItem, QMenu)
from PyQt5.QtGui import (QBrush, QPen, QPixmap)
from flint.gui.style import FlPalette
from flint.glob import (FlGlob, elidestring)
from flint.gui.view.conditems import (QGraphicsRectItemCond, 
    QGraphicsSimpleTextItemCond, QGraphicsTextItemCond, 
    QGraphicsPixmapItemCond)
import weakref

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
