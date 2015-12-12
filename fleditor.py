#!/usr/bin/env python3

import sys
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtOpenGL import *
import flint_parser as fp
import os
import weakref
import inspect as insp
from collections import deque, OrderedDict

def log (level, text):
    if level in FlGlob.loglevels:
        if FlGlob.loglevels[level] <= FlGlob.loglevel:
            print("[%s] %s" % (level, text))
    else:
        log("warn", "Unknown loglevel: %s" % level)

class FlGlob:
    loglevels = {"quiet": 0, "error": 1, "warn": 2, "info": 3, "debug": 4, "verbose": 5}
    loglevel = 3
    mainwindow = None

class FlPalette (object):
    """Palette of custom colors for quick reference."""
    dark    = QColor( 38,  39,  41)
    light   = QColor(250, 250, 250)
    hl1     = QColor(200,  60,  19)
    hl1var  = QColor(224, 111,  19)
    hl2     = QColor( 39, 118, 153)
    hl2var  = QColor(108, 158, 171)
    bank    = QColor(150, 170, 160)
    bankvar = QColor(130, 150, 140)
    root    = QColor(128, 128, 128)
    rootvar = QColor(112, 112, 112)
    bg      = QColor( 90,  94,  98)

class FlNodeStyle (object):    
    def __init__ (self, font):
        basefont = font
        boldfont = QFont(basefont)
        boldfont.setBold(True)
        self.basefont = basefont
        self.boldfont = boldfont
        
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
        
        self.nodemargins = QMarginsF(*[nodemargin]*4)
        self.banknodemargins = QMarginsF(*[nodemargin//2]*4)
        self.itemmargins = QMarginsF(*[itemmargin]*4)
        self.activemargins = QMarginsF(*[selectmargin//2]*4)
        self.selectmargins = QMarginsF(*[selectmargin//2]*4)
        
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
        self.arrowsize = self.pensize * 5

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
        self.cond = cond
    
    def paint (self, painter, style, widget):
        if widget is self.cond:
            super().paint(painter, style, widget)

class NodeItem(QGraphicsItem):
    def __init__ (self, nodeobj, parent=None, view=None, state=1):
        super().__init__()
        self.edge = None
        self.children = None
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
    
    def childlist (self, generate=True):
        if generate or self.children is None:
            ID = self.nodeobj.ID
            itemtable = self.view.itemtable
            if self.state == 1 and ID in itemtable and not self.iscollapsed():
                children = []
                for child in self.nodeobj.linkIDs:
                    if child in itemtable[ID]:
                        item = itemtable[ID][child]
                    else:
                        continue
                    children.append(item)
                ret = children
            else:
                ret = []
            self.children = ret
            if self.edge:
                self.edge.prepareGeometryChange()
            return self.children
        else:
            return self.children
    
    def setedge (self, edge):
        self.edge = edge
    
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
    
    def setY (self, y):
        if self.edge is not None:
            self.edge.prepareGeometryChange()
        parent = self.view.itembyID(self.refID)
        if parent and parent.edge is not None:
            parent.edge.prepareGeometryChange()
        y += self.getyoffset()
        super().setY(y)
    
    def setrank (self, parent):
        if self.edge is not None:
            self.edge.prepareGeometryChange()
        if parent is None:
            return
        
        if self.issubnode():
            self.setX(parent.x())
        else:
            self.setX(parent.x()+self.style.rankwidth)
            self.nudgechildren()
    
    def nudgechildren (self):
        for child in self.childlist():
            child.setrank(self)
    
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
    
    def bulkshift (self, diff):
        self.setY(self.y() + diff)
        for child in self.childlist():
            child.bulkshift(diff)
    
    def treeposition (self, ranks=None):
        if ranks is None:
            ranks = dict()
        localranks = dict()
        children = self.childlist()
        for child in children:
            localranks = child.treeposition(localranks)
        rank = self.x() // self.style.rankwidth
        if children:
            top, bottom, depth = self.subtreesize(1)
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
            self.bulkshift(streeshift)
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

        children = self.childlist()
        maxdepth = abs(depth)
        if children and depth:
            nextdepth = depth-1
            ymin = ymax = None
            """Doing this as a single list comprehension causes slowdowns with big trees."""
            for child in children:
                stree = child.subtreesize(nextdepth)
                ymin = min(ymin, child.y_top(), stree[0]) if ymin is not None else stree[0]
                ymax = max(ymax, child.y_bottom(), stree[1]) if ymax is not None else stree[1]
                maxdepth = max(maxdepth, stree[2])
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
        self.shadowbox.setBrush(FlPalette.dark)
        self.shadowbox.setPen(nopen)
        self.shadowbox.setPos(*[self.style.shadowoffset]*2)
        self.graphgroup.addToGroup(self.shadowbox)
        
        self.activebox = QGraphicsRectItem(self)
        activepen = QPen(self.altcolor, self.style.selectmargin, join=Qt.MiterJoin)
        self.activebox.setPen(activepen)
        self.activebox.hide()
        self.graphgroup.addToGroup(self.activebox)
        
        self.selectbox = QGraphicsRectItem(self)
        selectpen = QPen(FlPalette.light, self.style.selectmargin, join=Qt.MiterJoin)
        self.selectbox.setPen(selectpen)
        self.selectbox.hide()
        self.graphgroup.addToGroup(self.selectbox)
        
        self.mainbox = QGraphicsRectItem(self)
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
    
    def updateenterscripts (self):
        icons = {True: "script-enter", False: "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.hasenterscripts()])
        self.entericon.setPixmap(pixmap)
    
    def updateexitscripts (self):
        icons = {True: "script-exit", False: "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.hasexitscripts()])
        self.exiticon.setPixmap(pixmap)
    
    def updaterandweight (self):
        icons = {True: "dice", False: "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[bool(self.nodeobj.randweight)])
        self.randicon.setPixmap(pixmap)
    
    def updatepersistence (self):
        icons = {"Mark": "mark", "OncePerConv": "once", "OnceEver": "onceever", "": "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.persistence])
        self.persisticon.setPixmap(pixmap)
    
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
            rect = self.fggroup.boundingRect()
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
        self.fggroup.removeFromGroup(self.textbox)
        self.fggroup.addToGroup(self.textbox)
        self.fggroup.removeFromGroup(ndtxt)
        self.fggroup.addToGroup(ndtxt)
        
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
    maincolor = FlPalette.hl1var
    altcolor = FlPalette.hl1
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

class ResponseNodeItem (TextNodeItem):
    maincolor = FlPalette.hl2var
    altcolor = FlPalette.hl2
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
        self.updatecomment()
        self.updatebanktype()
    
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
        self.centerbox.setRect(QRectF())
        self.centerbox.setBrush(darkbrush)
        self.centerbox.setPen(nopen)
        self.centerbox.setPos(0, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin*2)
        self.fggroup.addToGroup(self.centerbox)
    
    def updatebanktype (self):
        icons = {"First": "bank-first", "All": "bank-all", "Append": "bank-append", "": "blank"}
        pixmap = self.pixmap("images/%s.png" % icons[self.nodeobj.banktype])
        self.btypeicon.setPixmap(pixmap)
    
    def updatecenterbox (self):
        verticalpos = self.centerbox.y()
        maxwidth = 0
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
        
        self.fggroup.removeFromGroup(self.centerbox)
        self.fggroup.addToGroup(self.centerbox)
    
    def updatelayout (self, external=False):
        subnodes = self.sublist()
        if self.iscollapsed():
            rect = self.nodelabel.mapRectToParent(self.nodelabel.boundingRect())
        else:
            self.updatecenterbox()
            rect = self.fggroup.boundingRect()
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


class EdgeItem (QGraphicsItem):
    def __init__ (self, source, view):
        super().__init__()
        self.source = source
        source.setedge(self)
        self.view = weakref.proxy(view)
        self.style = FlGlob.mainwindow.style
        self.arrowsize = self.style.arrowsize
        self.pensize = self.style.pensize
        
        pen = QPen(FlPalette.light, self.pensize, cap = Qt.FlatCap, join=Qt.MiterJoin)
        pen.setCosmetic(True)
        brush = QBrush(FlPalette.light)
        
        pen2 = QPen(pen)
        pen2.setColor(FlPalette.dark)
        brush2 = QBrush(FlPalette.dark)
        
        visuals = dict()
        visuals[True] = (pen, brush)
        visuals[False] = (pen2, brush2)
        self.visuals = visuals
        
        self.nopen = QPen(0)
    
    def boundingRect (self):
        xmin = self.source.x()
        xmax = xmin + self.style.rankwidth
        children = self.source.childlist(generate=False)
        self.children = [(t.x()+t.boundingRect().left()-self.style.activemargin, t.y()) for t in children]
        halfarrow = self.arrowsize/2
        if children:
            ymin = self.children[0][1] - halfarrow
            ymax = self.children[-1][1] + halfarrow + self.style.shadowoffset
        else:
            y = self.source.y()
            ymin = y - halfarrow
            ymax = y + halfarrow
        return QRectF(xmin, ymin, abs(xmax-xmin), abs(ymax-ymin))
    
    def paint (self, painter, style, widget, off=0, main=True):
        if not self.source:
            return
        children = self.children
        if not children:
            return
        treeview = widget is self.view.viewport()
        
        if main and treeview:
            self.paint(painter, style, widget, off=self.style.shadowoffset, main=False)
        
        pen, brush = self.visuals[main]
        if not treeview:
            pen.setWidth(1)
            pen.setCosmetic(True)
        elif self.view.zoomscale >= 1:
            pen.setWidth(self.pensize)
            pen.setCosmetic(False)
        
        painter.setPen(pen)
        painter.setBrush(brush)
        
        x0 = self.source.x() + self.source.boundingRect().right() + off
        y0 = self.source.y() + off
        vert_x = self.source.x() + self.style.rankwidth/2 + off
        painter.drawLine(x0, y0, vert_x, y0)
        
        arrow = self.arrowsize
        corr = pen.width()/2
        for tx, ty in children:
            tx += off
            ty += off
            painter.drawLine(vert_x-corr, ty, tx-arrow+1, ty)
            arrowtip = [QPointF(tx, ty),
                        QPointF(tx-arrow, ty-(arrow/2)),
                        QPointF(tx-arrow, ty+(arrow/2))]
            painter.setPen(self.nopen)
            painter.drawPolygon(*arrowtip)
            painter.setPen(pen)
        
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

class ScriptParamWidget (QWidget):
    def __init__ (self, parent, name, annot, default):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*[0]*4)
        label = QLabel(name)
        if annot is bool:
            editor = QCheckBox("True", self)
            signal = editor.stateChanged
            value = lambda: bool(editor.checkState())
            if default:
                state = Qt.Checked
            else:
                state = Qt.Unchecked
            editor.setCheckState(state)
        elif annot is int:
            editor = QSpinBox(self)
            signal = editor.valueChanged
            value = editor.value
            if default == "":
                default = 0
            editor.setValue(int(default))
        else:
            editor = QLineEdit(self)
            signal = editor.textEdited
            value = editor.text
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
        self.setStyleSheet("""
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
            """)
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
    removed = pyqtSignal(fp.ScriptCall)
    
    def __init__ (self, parent, callobj, nodeID, cond=False):
        name = callobj.funcname
        super().__init__(parent, callobj, name)
        self.nodeID = nodeID
        params = callobj.funcparams[::-1]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*[9, 4]*2)
        
        if cond:
            notcheck = QCheckBox("Not", self)
            if callobj._not:
                notcheck.setCheckState(Qt.Checked)
            else:
                notcheck.setCheckState(Qt.Unchecked)
            notcheck.stateChanged.connect(self.notchanged)
            layout.addWidget(notcheck)
            self.toggled.connect(notcheck.setVisible)
        
        paramswidget = QWidget(self)
        paramslayout = QVBoxLayout(paramswidget)
        paramslayout.setContentsMargins(*[0]*4)
        paramslist = []
        signature = insp.signature(callobj.funccall)
        for param in signature.parameters.values():
            pname = param.name
            annot = param.annotation if param.annotation is not insp._empty else ""
            default = params.pop()
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
    newCallObj = pyqtSignal(fp.MetaCall)
    
    def __init__ (self, parent, cond=False):
        super().__init__(parent)
        scripts = fp.ScriptCall.scripts
        if cond:
            names = ["( )"]
            condcalls = [n for n, sc in scripts.items() if "return" in sc.__annotations__]
            names.extend(sorted(condcalls))
        else:
            names = sorted(scripts.keys())
        self.scriptcalls = names
        
        combobox = QComboBox(self)
        combobox.insertItems(len(self.scriptcalls), self.scriptcalls)
        self.combobox = combobox
        addbutton = QPushButton("Add", self)
        addbutton.clicked.connect(self.newscriptcall)
        
        layout = QHBoxLayout(self)
        layout.addWidget(combobox)
        layout.addWidget(addbutton)
    
    @pyqtSlot()
    def newscriptcall (self):
        name = self.combobox.currentText()
        if name == "( )":
            callobj = fp.MetaCall({"type":"cond","operator":"and","calls":[]})
        else:
            signature = insp.signature(fp.ScriptCall.scripts[name])
            defaults = {int: 0, bool: False}
            params = []
            for param in signature.parameters.values():
                if param.name == "self":
                    continue
                if param.annotation in defaults:
                    params.append(defaults[param.annotation])
                else:
                    params.append("")
            callobj = fp.MetaCall({"type":"script", "command":name, "params":params})
        self.newCallObj.emit(callobj)

class ConditionCallWidget (CallWidget):
    removed = pyqtSignal(fp.ConditionCall)
    
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
        callslayout.setContentsMargins(*[0]*4)
        self.types = {"cond": ConditionCallWidget, "script": ScriptCallWidget}
        for call in callobj.calls:
            self.addcallwidget(call)
        
        newwidget = CallCreateWidget(self, cond=True)
        newwidget.newCallObj.connect(self.addcall)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*[4]*4)
        layout.addWidget(operatorwidget)
        layout.addWidget(callswidget)
        layout.addWidget(newwidget)
        
        self.toggled.connect(callswidget.setVisible)
        self.toggled.connect(operatorwidget.setVisible)
        self.toggled.connect(newwidget.setVisible)
    
    @pyqtSlot(fp.MetaCall)
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
    
    @pyqtSlot(fp.ScriptCall)
    @pyqtSlot(fp.ConditionCall)
    def removecall (self, callobj):
        prompt = QMessageBox.question(self, "Prompt", "Remove call?")
        if prompt == QMessageBox.No:
            return
        widget = self.widgets.pop(callobj)
        self.callswidget.layout().removeWidget(widget)
        widget.deleteLater()
        self.callobj.calls.remove(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeID, "updatecondition")

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
            self.setEnabled(True)
            callobj = nodeobj.condition
            callswidget = self.resetwidget()
            scwidget = ConditionCallWidget(callswidget, callobj, nodeID)
            scwidget.actremove.setEnabled(False)
            callswidget.layout().addWidget(scwidget)
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
            self.setEnabled(True)
            self.resetwidget()
            if self.slot == "enter":
                self.scripts = nodeobj.enterscripts
            elif self.slot == "exit":
                self.scripts = nodeobj.exitscripts
            for callobj in self.scripts:
                self.addscriptcallwidget(callobj)
        else:
            self.setEnabled(False)
            self.resetwidget()
    
    @pyqtSlot(fp.MetaCall)
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
    
    @pyqtSlot(fp.ScriptCall)
    def removescriptcall (self, callobj):
        prompt = QMessageBox.question(self, "Prompt", "Remove call?")
        if prompt == QMessageBox.No:
            return
        callswidget = self.callsarea.widget()
        scwidget = self.widgets.pop(callobj)
        callswidget.layout().removeWidget(scwidget)
        scwidget.deleteLater()
        self.scripts.remove(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "update%sscripts" % self.slot)

class PropertiesEditWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setEnabled(False)
        layout = QFormLayout(self)
        
        l_persistence = QLabel("&Persistence", self)
        persistence = QComboBox(self)
        persvals = ["", "Mark", "OnceEver", "OncePerConv"]
        persistence.insertItems(len(persvals), persvals)
        persistence.currentTextChanged.connect(self.persistencechanged)
        l_persistence.setBuddy(persistence)
        self.persistence = persistence
        
        l_banktype = QLabel("&Bank play type", self)
        banktype = QComboBox(self)
        banktypes = ["First", "All", "Append"]
        banktype.insertItems(len(banktypes), banktypes)
        banktype.currentTextChanged.connect(self.banktypechanged)
        l_banktype.setBuddy(banktype)
        self.banktype = banktype
        
        l_questionhub = QLabel("&Question hub", self)
        questionhub = QComboBox(self)
        qhubtypes = ["", "ShowOnce", "ShowNever"]
        questionhub.insertItems(len(qhubtypes), qhubtypes)
        questionhub.currentTextChanged.connect(self.questionhubchanged)
        l_questionhub.setBuddy(questionhub)
        self.questionhub = questionhub
        
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
        layout.addRow(l_banktype, banktype)
        layout.addRow(l_questionhub, questionhub)
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
                self.banktype.setCurrentText(nodeobj.banktype)
                self.banktype.setEnabled(True)
            else:
                self.banktype.setEnabled(False)
            
            if nodeobj.typename == "talk":
                self.questionhub.setCurrentText(nodeobj.questionhub)
                self.questionhub.setEnabled(True)
            else:
                self.questionhub.setEnabled(False)
            
            self.randweight.setText(str(nodeobj.randweight))
            
            commentdoc = view.nodedocs[nodeID]["comment"]
            self.comment.setDocument(commentdoc)
            self.comment.moveCursor(QTextCursor.End)
        else:
            self.setEnabled(False)
            self.persistence.setCurrentText("")
            self.banktype.setCurrentText("")
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
    def banktypechanged (self):
        if self.nodeobj is None:
            return
        banktype = self.banktype.currentText()
        self.nodeobj.banktype = banktype
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatebanktype")
    
    @pyqtSlot()
    def questionhubchanged (self):
        if self.nodeobj is None:
            return
        questionhub = self.questionhub.currentText()
        self.nodeobj.questionhub = questionhub
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatequestionhub")
    
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
        
        layout.addWidget(self.inputline)
        layout.addWidget(searchbutton)
    
    def search (self):
        query = self.inputline.text().casefold()
        view = self.parent().view
        if view is not None:
            view.search(query)
            self.searched.emit()

class NodeListItem (QListWidgetItem):
    IDRole = Qt.UserRole + 1
    
    def __lt__ (self, other):
        return self.data(self.IDRole) < other.data(self.IDRole)

class NodeListWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.search = SearchWidget(self)
        self.search.searched.connect(self.populatelist)
        
        self.nodelist = QListWidget(self)
        self.nodelist.setSortingEnabled(True)
        self.nodelist.setIconSize(QSize(*[FlGlob.mainwindow.style.boldheight]*2))
        self.nodelist.currentItemChanged.connect(self.selectnode)
        self.nodelist.itemActivated.connect(self.activatenode)
        self.nodelist.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.nodelist)
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
        if self.view.selectednode is not None:
            self.selectbyID(self.view.selectednode.realid())
    
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
            descr = "(%s) %s" % (nodeobj.banktype, ", ".join(nodeobj.subnodes))
        elif typename == "talk":
            descr = "[%s]" % elidestring(nodeobj.text, 30)
        elif typename == "response":
            descr = "[%s]" % elidestring(nodeobj.text, 30)
        else:
            descr = ""
        
        label = "%s: %s %s" % (nodeID, typename, descr) 
        if nodeID in view.trash:
            icon = QIcon.fromTheme("user-trash")
        else:
            icon = QIcon.fromTheme("text-x-generic")
        item = NodeListItem(icon, label)
        item.setData(NodeListItem.IDRole, int(nodeID))        
        return item
    
    @pyqtSlot(NodeListItem, NodeListItem)
    def selectnode (self, listitem, olditem):
        if listitem is None:
            return
        window = FlGlob.mainwindow
        view = window.activeview
        nodeID = str(listitem.data(listitem.IDRole))
        window.setselectednode(view, nodeID)
    
    @pyqtSlot(NodeListItem)
    def activatenode (self, listitem):
        window = FlGlob.mainwindow
        view = window.activeview
        nodeID = str(listitem.data(listitem.IDRole))
        window.setactivenode(view, nodeID)

class MapView (QGraphicsView):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setOptimizationFlags(QGraphicsView.DontAdjustForAntialiasing | QGraphicsView.DontSavePainterState)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.treeview = None
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
        self.nodedocs = newnodedocs
    
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
        
        if not undo:
            pos = self.nodecontainer.nodes[nodeID].subnodes.index(newid)
            hist = HistoryAction(self.unlinksubnode,
                {"subID": newid, "bankID": nodeID},
                self.linksubnode,
                {"subID": newid, "bankID": nodeID, "pos": pos},
                "Add new subnode %s to node %s" % (newid, nodeID))
            self.addundoable(hist)
        return newid
    
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
    
    def nodetobank (self, nodeID, undo=False):
        cont = self.nodecontainer
        selnode = cont.nodes[nodeID]
        nodedict = selnode.todict()
        
        bankdict = nodedict.copy()
        bankdict["type"] = "bank"
        clonedict = nodedict.copy()
        clonedict["links"] = []
        clonedict["nodebank"] = nodeID
        
        cont.newnode(bankdict, newID=nodeID, force=True)
        newobj = cont.newnode(clonedict, bankID=nodeID)
        
        self.nodedocs[newobj.ID] = self.nodedocs[nodeID]
        self.nodedocs.pop(nodeID)
        
        if not undo:
            hist = HistoryAction(self.banktonode, {"nodeID": nodeID},
                self.nodetobank, {"nodeID": nodeID},
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
        
        cont.nodes.pop(subID)
        cont.newnode(clonedict, newID=nodeID, force=True)
        
        self.nodedocs[nodeID] = self.nodedocs[subID]
        
        if not undo:
            hist = HistoryAction(self.nodetobank, {"nodeID": nodeID}, 
                self.banktonode, {"nodeID": nodeID},
                "Transform node %s from Bank" % nodeID)
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
    
    def search (self, query):
        if not query:
            self.hits = None
        else:
            hits = []
            for nodeID, nodeobj in self.nodecontainer.nodes.items():
                if query in nodeobj.text.casefold():
                    hits.append(nodeID)
            self.hits = hits

class TreeView (TreeEditor, QGraphicsView):
    __types = {'talk': TalkNodeItem, 'response': ResponseNodeItem, 
        'bank': BankNodeItem, 'root': RootNodeItem}
    
    def __init__ (self, nodecontainer, parent=None):
        TreeEditor.__init__(self, nodecontainer)
        QGraphicsView.__init__(self, parent)
        self.zoomscale = 1
        self.activenode = None
        self.selectednode = None
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
        nodeitem = self.__types[nodeobj.typename](nodeobj, parent=parent, view=self, state=state)
        edgeitem = EdgeItem(nodeitem, view=self)
        scene = self.scene()
        scene.addItem(edgeitem)
        scene.addItem(nodeitem)
        
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
        scene.removeItem(edgeitem)
        edgeitem.source = None
        nodeitem.edge = None
        if self.activenode is nodeitem:
            self.activenode = None
        if self.selectednode is nodeitem:
            self.selectednode = None
        nodeitem = None
        edgeitem = None
    
    def setstate (self, fullID, state):
        log("verbose", "%s.stestate(%s, %s)" % (self, fullID, state))
        fromID, toID = fullID
        nodeitem = self.itemtable[fromID][toID]
        if state == 1:
            index = self.itemindex[toID]
            i = self.itemindex[toID].index(nodeitem)
            index[0], index[i] = index[i], index[0]
        nodeitem.setstate(state)
        if state != -1:
            nodeitem.setrank(self.itembyID(fromID))
    
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
        log("debug", "%s.setselectednode(%s)" % (self, nodeitem))
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
        log("debug", "%s.selectbyID(%s)" % (self, nodeID))
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
        log("debug", "%s.setactivenode(%s)" % (self, nodeitem))
        if nodeitem is not None:
            nodeID = nodeitem.realid()
        else:
            nodeID = "-1"
        FlGlob.mainwindow.setactivenode(self, nodeID)
    
    @pyqtSlot(str)
    def activatebyID (self, nodeID):
        if FlGlob.mainwindow.activeview is not self:
            return
        log("debug", "%s.activatebyID(%s)" % (self, nodeID))
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
    
    def nodetobank (self, nodeID, undo=False):
        if nodeID in self.itemindex:
            for item in self.itemindex[nodeID]:
                fullID = item.id()
                self.nodeorder[fullID] = None
        super().nodetobank(nodeID, undo)
        self.updateview()
    
    def banktonode (self, nodeID, undo=False):
        if nodeID in self.itemindex:
            for item in self.itemindex[nodeID]:
                fullID = item.id()
                self.nodeorder[fullID] = None
        super().banktonode(nodeID, undo)
        self.updateview()
    
    def collapse (self, fullID, collapse=None):
        super().collapse(fullID, collapse)
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
                    self.setselectednode(children[count//2])
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
    actions = dict()
    editdocks = dict()
    activeview = None
    activenode = ""
    selectednode = ""
    viewChanged = pyqtSignal()
    viewUpdated = pyqtSignal()
    activeChanged = pyqtSignal(str)
    selectedChanged = pyqtSignal(str)
    
    def __init__ (self):
        super().__init__()
        
        FlGlob.mainwindow = self
        self.activeChanged.connect(self.loadnode)
        self.selectedChanged.connect(self.filteractions)
        self.viewChanged.connect(self.filteractions)
        
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
        self.filteractions()
    
    def initactions (self):
        self.actions["openfile"] = self.createaction("&Open", self.selectopenfile,
            [QKeySequence.Open], ["document-open"], "Open dialogue file")
        self.actions["save"] = self.createaction("&Save", self.save,
            [QKeySequence.Save], ["document-save"], "Save dialogue file")
        self.actions["saveas"] = self.createaction("Save &As", self.saveas,
            [QKeySequence.SaveAs], ["document-save-as"], "Save dialogue file as")
        self.actions["newtree"] = self.createaction("&New", self.newtree,
            [QKeySequence.New], ["document-new"], "New dialogue tree")
        self.actions["close"] = self.createaction("Close", self.closefile,
            None, ["window-close"], "Close file")
        
        self.actions["undo"] = self.createaction("&Undo", self.undofactory(1),
            [QKeySequence.Undo], ["edit-undo"], "Undo last action")
        self.actions["redo"] = self.createaction("&Redo", self.redofactory(1),
            [QKeySequence.Redo], ["edit-redo"], "Redo action")
        
        self.actions["zoomin"] = self.createaction("Zoom &In", self.zoomin, 
            [QKeySequence.ZoomIn, QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_Plus)], 
            ["gtk-zoom-in", "zoom-in"], "Zoom in")
        self.actions["zoomout"] = self.createaction("Zoom &Out", self.zoomout, 
            [QKeySequence.ZoomOut, QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_Minus)], 
            ["gtk-zoom-out", "zoom-out"], "Zoom out")
        self.actions["zoomorig"] = self.createaction("Zoom O&riginal", self.zoomorig, 
            [QKeySequence(Qt.ControlModifier + Qt.Key_0), QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_0)], 
            ["gtk-zoom-100", "zoom-original"], "Zoom to original size")
        self.actions["gotoactive"] = self.createaction("Go To &Active", self.gotoactive, 
            None, ["go-jump"], "Center on active node")
        self.actions["refresh"] = self.createaction("Refresh", self.refresh,
            [QKeySequence.Refresh], ["view-refresh"], "Refresh view")
        
        self.actions["newtalk"] = self.createaction("New &Talk Node", self.newtalk,
            [QKeySequence(Qt.ControlModifier+Qt.Key_T)], ["insert-object"], "Add new Talk node")
        self.actions["newresponse"] = self.createaction("New &Response Node", self.newresponse,
            [QKeySequence(Qt.ControlModifier+Qt.Key_R)], ["insert-object"], "Add new Response node")
        self.actions["newbank"] = self.createaction("New &Bank Node", self.newbank,
            [QKeySequence(Qt.ControlModifier+Qt.Key_B)], ["insert-object"], "Add new Bank node")
        self.actions["copynode"] = self.createaction("&Copy Node", self.copynode,
            [QKeySequence.Copy], ["edit-copy"], "Copy node")
        self.actions["pasteclone"] = self.createaction("Paste &Clone", self.pasteclone,
            [QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_V)], ["edit-paste"], "Paste cloned node")
        self.actions["pastelink"] = self.createaction("Paste &Link", self.pastelink,
            [QKeySequence.Paste], ["insert-link"], "Paste link to node")
        self.actions["unlinkstree"] = self.createaction("Unlink &Subtree", self.unlink,
            [QKeySequence.Delete], ["edit-clear"], "Unlink subtree from parent")
        self.actions["unlinknode"] = self.createaction("Unlink &Node", self.unlinkinherit,
            [QKeySequence(Qt.ControlModifier+Qt.Key_Delete)], ["edit-delete"], "Unlink node and let parent inherit its child nodes")
        self.actions["moveup"] = self.createaction("Move &Up", self.moveup,
            [QKeySequence(Qt.ShiftModifier+Qt.Key_Up)], ["go-up"], "Move node up")
        self.actions["movedown"] = self.createaction("Move &Down", self.movedown,
            [QKeySequence(Qt.ShiftModifier+Qt.Key_Down)], ["go-down"], "Move node down")
        self.actions["collapse"] = self.createaction("(Un)Colla&pse subtree", self.collapse,
            [QKeySequence(Qt.ControlModifier+Qt.Key_Space)], None, "(Un)Collapse subtree")
        self.actions["newtalksub"] = self.createaction("New &Talk Subnode", self.newtalksub,
            [QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_T)], ["insert-object"], "Add new Talk subnode")
        self.actions["newbanksub"] = self.createaction("New &Bank Subnode", self.newbanksub,
            [QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_B)], ["insert-object"], "Add new Bank subnode")
        self.actions["newresponsesub"] = self.createaction("New &Response Subnode", self.newresponsesub,
            [QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_R)], ["insert-object"], "Add new Response subnode")
        self.actions["pastesubnode"] = self.createaction("&Paste Subnode", self.pastesubnode,
            [QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_C)], ["edit-paste"], "Paste cloned node as subnode")
        self.actions["parentswap"] = self.createaction("S&wap with Parent", self.parentswap,
            [QKeySequence(Qt.ShiftModifier+Qt.Key_Left)], ["go-left"], "Swap places with parent node")
        self.actions["settemplate"] = self.createaction("Set as Te&mplate", self.settemplate,
            None, ["text-x-generic-template"], "Set node as the template for its type")
        
        self.actions["nodetobank"] = self.createaction("Regular -> Bank", self.nodetobank,
            None, None, "Transform node into a Bank node")
        self.actions["banktonode"] = self.createaction("Bank -> Regular", self.banktonode,
            None, None, "Transform Bank node into a regular node")
    
    @pyqtSlot()
    def filteractions (self):
        view = self.activeview
        if view is None:
            defaultactions = ("openfile", "newtree")
            for name, action in self.actions.items():
                if name not in defaultactions:
                    action.setEnabled(False)
                else:
                    action.setEnabled(True)
        else:
            genericactions = ["zoomin", "zoomout", "zoomorig", "gotoactive",
                "collapse", "openfile", "save", "saveas", "newtree", "close", "refresh"]
            if view.undohistory:
                genericactions.extend(["undo"])
            if view.redohistory:
                genericactions.extend(["redo"])
            nodes = view.nodecontainer.nodes
            if not self.selectednode or self.selectednode not in nodes:
                actions = []
            else:
                nodeobj = nodes[self.selectednode]
                if self.selectednode not in view.itemindex:
                    if nodeobj.typename != "root":
                        actions = ["copynode", "settemplate"]
                    else:
                        actions = []
                elif nodeobj.typename in ("talk", "response"):
                    actions = ["copynode", "moveup", "movedown", "unlinknode", 
                        "unlinkstree", "settemplate", "nodetobank"]
                    if nodeobj.nodebank == -1:
                        actions.extend(["newtalk", "newresponse", "newbank", 
                            "pasteclone", "pastelink", "parentswap"])
                elif nodeobj.typename == "bank":
                    actions = ["copynode", "moveup", "movedown", "unlinknode",
                        "unlinkstree", "newtalksub", "newresponsesub", "pastesubnode",
                        "newbanksub", "settemplate"]
                    if nodeobj.nodebank == -1:
                        actions.extend(["newtalk", "newresponse", "newbank", 
                            "pasteclone", "pastelink", "parentswap"])
                    if len(nodeobj.subnodes) == 1:
                        actions.extend(["banktonode"])
                elif nodeobj.typename == "root":
                    actions = ["newtalk", "newresponse", "newbank", "pasteclone",
                        "pastelink"]
            
            actions.extend(genericactions)
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
    
    def createaction (self, text, slot=None, shortcuts=None, icons=None,
                     tip=None, checkable=False):
        action = QAction(text, self)
        if icons is not None:
            if len(icons) > 1:
                fallbacks = QIcon.fromTheme(icons.pop(-1))
                for icon in reversed(icons):
                    fallbacks = QIcon.fromTheme(icon, fallbacks)
                action.setIcon(fallbacks)
            else:
                action.setIcon(QIcon.fromTheme(icons[0]))
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
        filemenu.addAction(self.actions["openfile"])
        filemenu.addAction(self.actions["newtree"])
        filemenu.addSeparator()
        filemenu.addAction(self.actions["save"])
        filemenu.addAction(self.actions["saveas"])
        filemenu.addSeparator()
        filemenu.addAction(self.actions["close"])
        
        addmenu = QMenu("Add &link...")
        addmenu.addAction(self.actions["pasteclone"])
        addmenu.addAction(self.actions["pastelink"])
        addmenu.addSeparator()
        addmenu.addAction(self.actions["newtalk"])
        addmenu.addAction(self.actions["newresponse"])
        addmenu.addAction(self.actions["newbank"])
        addmenu.setIcon(QIcon.fromTheme("insert-object"))
        self.addmenu = addmenu
        
        subnodemenu = QMenu("Add &subnode...")
        subnodemenu.addAction(self.actions["pastesubnode"])
        subnodemenu.addSeparator()
        subnodemenu.addAction(self.actions["newtalksub"])
        subnodemenu.addAction(self.actions["newresponsesub"])
        subnodemenu.addAction(self.actions["newbanksub"])
        subnodemenu.setIcon(QIcon.fromTheme("insert-object"))
        self.subnodemenu = subnodemenu
        
        transformmenu = QMenu("Trans&form...")
        transformmenu.addAction(self.actions["nodetobank"])
        transformmenu.addAction(self.actions["banktonode"])
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
        viewmenu.addAction(self.actions["zoomin"])
        viewmenu.addAction(self.actions["zoomout"])
        viewmenu.addAction(self.actions["zoomorig"])
        viewmenu.addAction(self.actions["gotoactive"])
        viewmenu.addAction(self.actions["collapse"])
        viewmenu.addAction(self.actions["refresh"])
        
        windowmenu = menubar.addMenu("&Window")
        def generatemenu ():
            windowmenu.clear()
            menu = self.createPopupMenu()
            menu.setTitle("Tools")
            windowmenu.addMenu(menu)
        windowmenu.aboutToShow.connect(generatemenu)
    
    def inittoolbars (self):
        filetoolbar = QToolBar("File actions")
        filetoolbar.addAction(self.actions["openfile"])
        filetoolbar.addAction(self.actions["newtree"])
        filetoolbar.addAction(self.actions["save"])
        self.addToolBar(filetoolbar)
        
        historytoolbar = QToolBar("History")
        historytoolbar.addAction(self.actions["undo"])
        historytoolbar.addAction(self.actions["redo"])
        self.addToolBar(historytoolbar)
        
        viewtoolbar = QToolBar("View control")
        viewtoolbar.addAction(self.actions["zoomorig"])
        viewtoolbar.addAction(self.actions["zoomin"])
        viewtoolbar.addAction(self.actions["zoomout"])
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
        conddock.setWidget(ConditionEditWidget(self))
        self.editdocks["cond"] = conddock
        
        onenterdock = QDockWidget("On E&nter", self)
        onenterdock.setWidget(ScriptEditWidget(self, slot="enter"))
        self.editdocks["enter"] = onenterdock
        
        onexitdock = QDockWidget("On E&xit", self)
        onexitdock.setWidget(ScriptEditWidget(self, slot="exit"))
        self.editdocks["exit"] = onexitdock
        
        propdock = QDockWidget("&Properties", self)
        propdock.setWidget(PropertiesEditWidget(self))
        self.editdocks["prop"] = propdock
        
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
        textdock.raise_()
        
        self.addDockWidget(Qt.LeftDockWidgetArea, listdock)
    
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
        filename = QFileDialog.getOpenFileName(self, "Open file", os.getcwd(), "Dialog files (*.json)")[0]
        if filename == "":
            return
        self.openfile(filename)
    
    def openfile (self, filename):
        nodecontainer = fp.loadjson(filename)
        treeview = TreeView(nodecontainer, parent=self)
        self.newtab(treeview)
    
    @pyqtSlot()
    def newtree (self):
        nodecontainer = fp.newcontainer()
        treeview = TreeView(nodecontainer, parent=self)
        self.newtab(treeview)
    
    def newtab (self, treeview):
        name = treeview.nodecontainer.name
        self.selectedChanged.connect(treeview.selectbyID)
        self.activeChanged.connect(treeview.activatebyID)
        tabindex = self.tabs.addTab(treeview, name)
        self.tabs.setCurrentIndex(tabindex)
    
    @pyqtSlot()
    def save (self, newfile=False):
        view = self.activeview
        if view is None:
            return
        nodecont = view.nodecontainer
        if nodecont.filename == "" or newfile:
            filename = QFileDialog.getSaveFileName(self, "Save as...", 
                os.path.join(os.getcwd(), (nodecont.name or "Untitled")+".json"),
                "Dialog files (*.json)")[0]
            nodecont.filename = filename
        nodecont.savetofile()
    
    @pyqtSlot()
    def saveas (self):
        self.save(newfile=True)
    
    @pyqtSlot()
    def closefile (self):
        view = self.activeview
        if view is None:
            return
        index = self.tabs.indexOf(view)
        self.closetab(index)
    
    @pyqtSlot(int)
    def closetab (self, index):
        view = self.tabs.widget(index)
        self.tabs.removeTab(index)
        view.deleteLater()
        view = None
    
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
    def copynode (self):
        view = self.activeview
        if self.selectednode not in view.nodecontainer.nodes:
            return
        nodeobj = view.nodecontainer.nodes[self.selectednode]
        nodedict = nodeobj.todict()
        nodedict["links"] = []
        nodedict["nodebank"] = -1
        nodedict["subnodes"] = []
        
        if nodeobj.nodebank != -1:
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
                text = "This will remove the only instance of node %s.\n\nContinue?" % selID
            else:
                text = "This will remove the only instance of node %s and all unique nodes in its subtree.\n\nContinue?" % selID
        else:
            text = "Unlink node %s from node %s?" % (selID, selected.refID)
        answer = QMessageBox.question(self, "Node removal", text)
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
        if gpID is None:
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
            self.filteractions()
        
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
            self.filteractions()
        
        return redo

def elidestring (string, length):
    if len(string) <= length:
        return string
    else:
        return string[:length-1]+"…"

if __name__ == '__main__':
    for arg in sys.argv[1:]:
        split = arg.split("=", maxsplit=1)
        argname = split[0]
        param = split[1] if len(split)>1 else None
        if argname == "--loglevel":
            if param in FlGlob.loglevels:
                FlGlob.loglevel = FlGlob.loglevels[param]
                log("info", "Loglevel: %s" % param)
            else:
                log("warn", "Unknown loglevel: %s" % param)
    app = QApplication(sys.argv)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec_())
