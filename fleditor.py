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
from collections import deque

class FlGlob:
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
    def __init__ (self, nodeobj, parent=None, view=None, ghost=False):
        super().__init__()
        self.nodeobj = nodeobj
        self.children = []
        self.referrers = []
        self.style = FlGlob.mainwindow.style
        if parent is None:
            self.parent = None
            self.nodebank = weakref.proxy(view)
        elif nodeobj.nodebank == -1:
            self.nodebank = weakref.proxy(view)
            self.parent = parent
            self.parent.addchild(self)
            self.setX(parent.x()+self.style.rankwidth)
        else:
            self.nodebank = parent
            self.parent = parent
        self.setCursor(Qt.ArrowCursor)
        self.view = weakref.proxy(view)
        self.edge = None
        self.yoffset = 0
        self.graphicsetup()
        self.setghost(ghost)
        
    def id (self):
        if self.parent is not None:
            refid = self.parent.id()
        else:
            refid = ""
        return "<-".join([self.nodeobj.ID, refid])
    
    def realid (self):
        return self.nodeobj.ID
    
    def addchild (self, nodeitem):
        self.children.append(nodeitem)
    
    def childlist (self):
        if self.iscollapsed():
            return []
        else:
            return self.children
    
    def addreferrer (self, refID):
        self.referrers.append(refID)
    
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
    
    def setghost (self, ghost):
        self.ghost = ghost
        
        if ghost:
            self.graphgroup.setOpacity(0.7)
            self.shadowbox.hide()
        else:
            self.graphgroup.setOpacity(1)
            self.shadowbox.show()
    
    def issubnode (self):
        return self.nodebank is self.parent
    
    def isghost (self):
        return self.ghost
    
    def realnode (self):
        return self.view.itembyID(self.nodeobj.ID)
    
    def isactive (self):
        return self.view.activenode is self
    
    def isselected (self):
        return self.view.selectednode is self
    
    def iscollapsed (self):
        return self.id() in self.view.collapsednodes
    
    def setY (self, y):
        self.edge.prepareGeometryChange()
        y += self.yoffset
        super().setY(y)    
    
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
        parent = self.parent
        if parent:
            if self.nodebank is self.view:
                return parent.childlist()
            else:
                return parent.subnodes
        else:
            return None
    
    def siblingabove (self):
        sibs = self.siblings()
        if sibs is None:
            return None
        myindex = sibs.index(self)
        if myindex:
            return sibs[myindex-1]
        else:
            return None
    
    def siblingbelow (self):
        sibs = self.siblings()
        if sibs is None:
            return None
        myindex = sibs.index(self)
        if len(sibs) > myindex+1:
            return sibs[myindex+1]
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
        self.activebox.setBrush(mainbrush)
        self.activebox.setPen(nopen)
        self.activebox.hide()
        self.graphgroup.addToGroup(self.activebox)
        
        self.selectbox = QGraphicsRectItem(self)
        self.selectbox.setBrush(lightbrush)
        self.selectbox.setPen(nopen)
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
        
        self.iconx = self.style.nodetextwidth
        
        condpix = QPixmap("images/key.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.condicon = QGraphicsPixmapItemCond(condpix, self, viewport)
        self.condicon.setPos(self.iconx-condpix.width(), self.style.itemmargin)
        self.iconx = self.condicon.x()
        self.fggroup.addToGroup(self.condicon)
        
        randpix = QPixmap("images/dice.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.randicon = QGraphicsPixmapItemCond(randpix, self, viewport)
        self.randicon.setPos(self.iconx-self.style.itemmargin-randpix.width(), self.style.itemmargin)
        self.iconx = self.randicon.x()
        self.fggroup.addToGroup(self.randicon)
        
        exitpix = QPixmap("images/script-exit.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.exiticon = QGraphicsPixmapItemCond(exitpix, self, viewport)
        self.exiticon.setPos(self.iconx-self.style.itemmargin-exitpix.width(), self.style.itemmargin)
        self.iconx = self.exiticon.x()
        self.fggroup.addToGroup(self.exiticon)
        
        enterpix = QPixmap("images/script-enter.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.entericon = QGraphicsPixmapItemCond(enterpix, self, viewport)
        self.entericon.setPos(self.iconx-self.style.itemmargin-enterpix.width(), self.style.itemmargin)
        self.iconx = self.entericon.x()
        self.fggroup.addToGroup(self.entericon)
        
        blankpix = QPixmap("images/blank.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.persisticon = QGraphicsPixmapItemCond(blankpix, self, viewport)
        self.persisticon.setPos(self.iconx-self.style.itemmargin-blankpix.width(), self.style.itemmargin)
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
    
    def updatecondition (self):
        if self.nodeobj.hascond() and not self.iscollapsed():
            self.condicon.show()
        else:
            self.condicon.hide()
    
    def updateenterscripts (self):
        if self.nodeobj.hasenterscripts() and not self.iscollapsed():
            self.entericon.show()
        else:
            self.entericon.hide()
    
    def updateexitscripts (self):
        if self.nodeobj.hasexitscripts() and not self.iscollapsed():
            self.exiticon.show()
        else:
            self.exiticon.hide()
    
    def updaterandweight (self):
        if self.nodeobj.randweight and not self.iscollapsed():
            self.randicon.show()
        else:
            self.randicon.hide()
    
    def updatepersistence (self):
        icons = {"Mark": "mark", "OncePerConv": "once", "OnceEver": "onceever", "": "blank"}
        if self.nodeobj.persistence in icons and not self.iscollapsed():
            pixmap = QPixmap("images/%s.png" % icons[self.nodeobj.persistence]).scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
            self.persisticon.setPixmap(pixmap)
            self.persisticon.show()
        else:
            self.persisticon.hide()
    
    def updatecomment (self):
        self.fggroup.removeFromGroup(self.comment)
        contents = self.view.nodedocs[self.realid()]["comment"].toPlainText()
        if not contents or self.iscollapsed():
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
        mainrect = rect.marginsAdded(QMarginsF(*[self.style.nodemargin]*4))
        self.mainbox.setRect(mainrect)
        self.shadowbox.setRect(mainrect)
        self.selectbox.setRect(mainrect.marginsAdded(QMarginsF(*[self.style.selectmargin]*4)))
        activerect = mainrect.marginsAdded(QMarginsF(*[self.style.activemargin]*4))
        self.activebox.setRect(activerect)
        self.graphgroup.setPos(-activerect.width()//2-activerect.x(), -activerect.height()//2-activerect.y())
        self.prepareGeometryChange()
        self.rect = self.graphgroup.mapRectToParent(self.activebox.boundingRect())
        self.nodebank.updatelayout()
    
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
    def __init__ (self, nodeobj, parent=None, view=None, ghost=False):
        self.textheight = 0
        self.collapselayout = False
        super().__init__(nodeobj, parent, view, ghost)
    
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
        if not self.iscollapsed():
            speaker = self.nodeobj.speaker
            listener = self.nodeobj.listener
            label = "%s -> %s" % (elidestring(speaker, 15), elidestring(listener, 15))
            fixedwidth = self.style.basemetrics.elidedText(label, Qt.ElideRight, self.style.nodetextwidth)
            self.nodespeaker.setText(fixedwidth)
            self.nodespeaker.show()
        else:
            self.nodespeaker.hide()
    
    def updatetext (self):
        if not self.iscollapsed():
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
            self.nodetext.show()
            self.textbox.show()
        else:
            self.nodetext.hide()
            self.textbox.hide()
    
    def contextMenuEvent (self, event):
        menu = QMenu()
        if self.isselected():
            window = FlGlob.mainwindow
            menu.addAction(window.actions["collapse"])
            menu.addAction(window.actions["copynode"])
            menu.addAction(window.actions["settemplate"])
            menu.addMenu(window.addmenu)
            menu.addAction(window.actions["moveup"])
            menu.addAction(window.actions["movedown"])
            menu.addAction(window.actions["parentswap"])
            menu.addAction(window.actions["unlinknode"])
            menu.addAction(window.actions["unlinkstree"])
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
        
        blankpix = QPixmap("images/blank.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.qhubicon = QGraphicsPixmapItemCond(blankpix, self, viewport)
        self.qhubicon.setPos(self.iconx-self.style.itemmargin-blankpix.width(), self.style.itemmargin)
        self.iconx = self.qhubicon.x()
        self.fggroup.addToGroup(self.qhubicon)
        
        self.updatespeaker()
        self.updatecomment()
        self.updatetext()
        self.updatequestionhub()
    
    def updatequestionhub (self):
        icons = {"ShowOnce": "question-once", "ShowNever": "question-never"}
        if not self.iscollapsed() and self.nodeobj.questionhub in icons:
            pixmap = QPixmap("images/%s.png" % icons[self.nodeobj.questionhub]).scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
            self.qhubicon.setPixmap(pixmap)
            self.qhubicon.show()
        else:
            self.qhubicon.hide()

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
    
    def __init__ (self, nodeobj, parent=None, view=None, ghost=False):
        super().__init__(nodeobj, parent, view, ghost)
        self.subnodes = []
        self.setZValue(-1)
        for subnodeID in nodeobj.subnodes:
            subnode = view.newitem(view.nodecontainer.nodes[subnodeID], self, ghost)
            self.subnodes.append(subnode)
            subnode.setX(self.x())
        self.updatecomment()
        self.updatebanktype()
        self.updatecenterbox()
    
    def graphicsetup (self):
        super().graphicsetup()
        darkbrush = QBrush(FlPalette.bg)
        nopen = QPen(0)
        viewport = self.view.viewport()
        
        firstpix = QPixmap("images/bank-first.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.btypeicon = QGraphicsPixmapItemCond(firstpix, self, viewport)
        self.btypeicon.setPos(self.iconx-self.style.itemmargin-firstpix.width(), self.style.itemmargin)
        self.iconx = self.btypeicon.x()
        self.fggroup.addToGroup(self.btypeicon)
        
        self.centerbox = QGraphicsRectItemCond(self, viewport)
        self.centerbox.setRect(QRectF())
        self.centerbox.setBrush(darkbrush)
        self.centerbox.setPen(nopen)
        self.centerbox.setPos(0, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin*2)
        self.fggroup.addToGroup(self.centerbox)
    
    def updatebanktype (self):
        icons = {"First": "bank-first", "All": "bank-all", "Append": "bank-append"}
        if not self.iscollapsed() and self.nodeobj.banktype in icons:
            pixmap = QPixmap("images/%s.png" % icons[self.nodeobj.banktype]).scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
            self.btypeicon.setPixmap(pixmap)
            self.btypeicon.show()
        else:
            self.btypeicon.hide()
    
    def updatecenterbox (self):
        if not self.iscollapsed():
            verticalpos = self.centerbox.y()
            maxwidth = 0
            for subnode in self.subnodes:
                noderect = subnode.boundingRect()
                nodeheight = noderect.height()
                nodewidth = noderect.width()
                subnode.show()
                subnode.yoffset = self.mapToScene(0,verticalpos + nodeheight/2+self.style.activemargin).y()-self.y_bottom()
                verticalpos += nodeheight
                maxwidth = max(maxwidth, nodewidth)
            centerrect = self.centerbox.rect()
            centerrect.setWidth(maxwidth)
            centerrect.setHeight(verticalpos-self.centerbox.y())
            self.centerbox.setRect(centerrect)
            centerrect = self.centerbox.mapRectToParent(centerrect)
            
            self.comment.setY(centerrect.bottom()+self.style.itemmargin)
            
            self.fggroup.removeFromGroup(self.centerbox)
            self.fggroup.addToGroup(self.centerbox)
            self.centerbox.show()
        else:
            self.centerbox.hide()
    
    def updatelayout (self):
        if self.iscollapsed():
            for subnode in self.subnodes:
                subnode.hide()
            rect = self.nodelabel.mapRectToParent(self.nodelabel.boundingRect())
        else:
            self.updatecenterbox()
            rect = self.fggroup.boundingRect()
        mainrect = rect.marginsAdded(QMarginsF(*[self.style.nodemargin]*4))
        self.mainbox.setRect(mainrect)
        self.shadowbox.setRect(mainrect)
        self.selectbox.setRect(mainrect.marginsAdded(QMarginsF(*[self.style.selectmargin]*4)))
        activerect = mainrect.marginsAdded(QMarginsF(*[self.style.activemargin]*4))
        self.activebox.setRect(activerect)
        oldypos = self.centerbox.mapToScene(self.centerbox.pos()).y()
        self.graphgroup.setPos(-activerect.width()//2-activerect.x(), -activerect.height()//2-activerect.y())
        newypos = self.centerbox.mapToScene(self.centerbox.pos()).y()
        for subnode in self.subnodes:
            subnode.yoffset += newypos - oldypos
            subnode.setY(self.y())
        self.prepareGeometryChange()
        self.rect = self.graphgroup.mapRectToParent(self.activebox.boundingRect())
        self.nodebank.updatelayout()
    
    def setY (self, y):
        super().setY(y)
        for subnode in self.subnodes:
            subnode.setY(y)
    
    def contextMenuEvent (self, event):
        menu = QMenu()
        if self.isselected():
            window = FlGlob.mainwindow
            menu.addAction(window.actions["collapse"])
            menu.addAction(window.actions["copynode"])
            menu.addAction(window.actions["settemplate"])
            menu.addMenu(window.subnodemenu)
            menu.addMenu(window.addmenu)
            menu.addAction(window.actions["moveup"])
            menu.addAction(window.actions["movedown"])
            menu.addAction(window.actions["parentswap"])
            menu.addAction(window.actions["unlinknode"])
            menu.addAction(window.actions["unlinkstree"])
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
        children = self.source.childlist()
        halfarrow = self.arrowsize/2
        if children:
            ymin = children[0].y() - halfarrow
            ymax = children[-1].y() + halfarrow
        else:
            y = self.source.y()
            ymin = y - halfarrow
            ymax = y + halfarrow
        return QRectF(xmin, ymin, abs(xmax-xmin), abs(ymax-ymin))
    
    def paint (self, painter, style, widget, off=0, main=True):
        children = self.source.childlist()
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
        for target in children:
            tx = target.x() + target.boundingRect().left() + off
            ty = target.y() + off
            painter.drawLine(vert_x-corr, ty, tx-arrow, ty)
            arrowtip = [QPointF(tx, ty),
                        QPointF(tx-arrow, ty-(arrow/2)),
                        QPointF(tx-arrow, ty+(arrow/2))]
            painter.setPen(self.nopen)
            painter.drawPolygon(*arrowtip)
            painter.setPen(pen)
        
        if len(children) > 1:
            vert_top = children[0].y() + off
            vert_bottom = children[-1].y() + off
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
    def __init__ (self, parent):
        super().__init__(parent)
        self.setTabChangesFocus(True)
    
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
        layout = QFormLayout(self)
        l_speaker = QLabel("&Speaker")
        self.speaker = QLineEdit(self)
        l_speaker.setBuddy(self.speaker)
        
        l_listener = QLabel("&Listener")
        self.listener = QLineEdit(self)
        l_listener.setBuddy(self.listener)
        
        l_nodetext = QLabel("&Text")
        self.nodetext = ParagraphEdit(self)
        l_nodetext.setBuddy(self.nodetext)
        
        layout.addRow(l_speaker, self.speaker)
        layout.addRow(l_listener, self.listener)
        layout.addRow(l_nodetext, self.nodetext)
        
        self.nodeobj = None
        self.speaker.textChanged.connect(self.setnodespeaker)
        self.listener.textChanged.connect(self.setnodelistener)
        self.nodetext.textChanged.connect(self.setnodetext)
        
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        self.nodeobj = view.nodecontainer.nodes[nodeID]
        if not isinstance(self.nodeobj, fp.TextNode):
            return
        nodetextdoc = view.nodedocs[nodeID]["text"]
        self.speaker.setText(self.nodeobj.speaker)
        self.listener.setText(self.nodeobj.listener)
        self.nodetext.setDocument(nodetextdoc)
        self.nodetext.moveCursor(QTextCursor.End)
    
    @pyqtSlot()
    def setnodespeaker (self):
        self.nodeobj.speaker = self.speaker.text()
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatespeaker")
    
    @pyqtSlot()
    def setnodelistener (self):
        self.nodeobj.listener = self.listener.text()
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatespeaker")
    
    @pyqtSlot()
    def setnodetext (self):
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
        callsarea = QScrollArea(self)
        callsarea.setWidgetResizable(True)
        self.callsarea = callsarea
        
        callswidget = QWidget(self.callsarea)
        callslayout = QVBoxLayout(callswidget)
        callslayout.setAlignment(Qt.AlignTop)
        self.callsarea.setWidget(callswidget)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

class ConditionEditWidget (CallEditWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.layout().addWidget(self.callsarea)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        nodeobj = view.nodecontainer.nodes[nodeID]
        self.nodeobj = nodeobj
        callobj = nodeobj.condition
        callswidget = self.callsarea.widget()
        scwidget = ConditionCallWidget(callswidget, callobj, nodeID)
        scwidget.actremove.setEnabled(False)
        callswidget.layout().addWidget(scwidget)

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
        nodeobj = view.nodecontainer.nodes[nodeID]
        self.nodeobj = nodeobj
        if self.slot == "enter":
            self.scripts = nodeobj.enterscripts
        elif self.slot == "exit":
            self.scripts = nodeobj.exitscripts
        for callobj in self.scripts:
            self.addscriptcallwidget(callobj)
    
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
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        nodeobj = view.nodecontainer.nodes[nodeID]
        self.nodeobj = nodeobj
        
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
    
    @pyqtSlot()
    def persistencechanged (self):
        persistence = self.persistence.currentText()
        self.nodeobj.persistence = persistence
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatepersistence")
    
    @pyqtSlot()
    def banktypechanged (self):
        banktype = self.banktype.currentText()
        self.nodeobj.banktype = banktype
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatebanktype")
    
    @pyqtSlot()
    def questionhubchanged (self):
        questionhub = self.questionhub.currentText()
        self.nodeobj.questionhub = questionhub
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatequestionhub")
    
    @pyqtSlot()
    def randweightchanged (self):
        randweight = float(self.randweight.text())
        self.nodeobj.randweight = randweight
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updaterandweight")
    
    @pyqtSlot()
    def commentchanged (self):
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
        if nodeID not in view.itemindex:
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
        self.unfunc(**self.unargs)
    
    def redo (self):
        self.refunc(**self.reargs)

class TreeView (QGraphicsView):
    __types = {'talk': TalkNodeItem, 'response': ResponseNodeItem, 
        'bank': BankNodeItem, 'root': RootNodeItem}
    
    def __init__ (self, nodecontainer, parent=None):
        super().__init__(parent)
        self.zoomscale = 1
        self.activenode = None
        self.selectednode = None
        self.collapsednodes = []
        self.hits = None
        
        historysize = 10 # OPTION
        self.undohistory = deque(maxlen=historysize)
        self.redohistory = deque(maxlen=historysize)
        
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
        self.setScene(scene)
        
        self.style = FlGlob.mainwindow.style
        
        self.nodecontainer = nodecontainer
        self.nodedocs = dict()
        self.updateview()
        self.setselectednode(self.treeroot())
    
    def updatedocs (self):
        newnodedocs = dict()
        for nodeID, nodeobj in self.nodecontainer.nodes.items():
            if nodeID in self.nodedocs:
                newnodedocs[nodeID] = self.nodedocs[nodeID]
            else:
                newnodedocs[nodeID] = dict()
                if isinstance(nodeobj, fp.TextNode):
                    textdoc = QTextDocument(self)
                    textdoc.setDocumentLayout(QPlainTextDocumentLayout(textdoc))
                    textdoc.setPlainText(nodeobj.text)
                    newnodedocs[nodeID]["text"] = textdoc
                commentdoc = QTextDocument(self)
                commentdoc.setDocumentLayout(QPlainTextDocumentLayout(commentdoc))
                commentdoc.setPlainText(nodeobj.comment)
                newnodedocs[nodeID]["comment"] = commentdoc
        self.nodedocs = newnodedocs
    
    def updateview (self):
        selectedID = activeID = selparentID = None
        if self.activenode is not None:
            activeID = self.activenode.realid()
        if self.selectednode is not None:
            selectedID = self.selectednode.id()
        self.activenode = self.selectednode = None
        
        self.constructed = False
        self.updatedocs()
        self.scene().clear()
        self.nodeitems = dict()
        self.itemindex = dict()
        self.viewframe = FrameItem(view=self)
        self.scene().addItem(self.viewframe)
        self.constructed = self.constructgraph()
        self.updatelayout()
        FlGlob.mainwindow.viewUpdated.emit()
        
        if activeID and activeID in self.itemindex:
            self.setactivenode(self.itembyID(activeID))
        else:
            self.setactivenode(None)
        
        baseID = ""
        while selectedID:
            swappedID = "<-".join([baseID, selectedID])
            if baseID and swappedID in self.nodeitems:
                self.setselectednode(self.nodeitems[swappedID])
                break
            elif selectedID in self.nodeitems:
                self.setselectednode(self.nodeitems[selectedID])
                break
            split = selectedID.split("<-", 1)
            selectedID = split[1]
            if not baseID:
                baseID = split[0]
    
    def constructgraph (self):
        queue = []
        queue.append(("0", None))
        nodesdict = self.nodecontainer.nodes
        visited = {"0": False}
        
        while queue:
            curID, ref = queue.pop(0)
            isghost = visited[curID]
            curnodeobj = nodesdict[curID]
            nodeitem = self.newitem(curnodeobj, ref, isghost)
            visited[curID] = visited[curID] or nodeitem.id() not in self.collapsednodes
            if not (isghost or nodeitem.iscollapsed()):
                for nextID in curnodeobj.linkIDs:
                    queue.append((nextID, nodeitem))
                    visited[nextID] = nextID in visited and visited[nextID]
        return True
    
    def newitem (self, nodeobj, parent, isghost=False):
        if parent is None:
            refid = ""
        else:
            refid = parent.id()
        nodeitem = self.__types[nodeobj.typename](nodeobj, parent=parent, view=self, ghost=isghost)
        edgeitem = EdgeItem(nodeitem, view=self)
        self.scene().addItem(edgeitem)
        self.scene().addItem(nodeitem)
        
        if nodeobj.ID in self.itemindex:
            if not isghost:
                oldnode = self.itemindex[nodeobj.ID][0]
                oldnode.setghost(True)
                nodeitem.referrers = oldnode.referrers
                oldnode.referrers = []
                self.itemindex[nodeobj.ID].insert(0, nodeitem)
            else:
                self.itemindex[nodeobj.ID].append(nodeitem)
        else:
            self.itemindex[nodeobj.ID] = [nodeitem]
        
        idstring = "<-".join([nodeobj.ID, refid])
        self.nodeitems[idstring] = nodeitem
        
        if refid:
            self.itembyID(nodeobj.ID).addreferrer(refid)
        
        return nodeitem
    
    def itembyID (self, nodeID):
        if nodeID in self.itemindex:
            return self.itemindex[nodeID][0]
        else:
            return #EXCEPTION
    
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
        self.ensureVisible(nodeitem, 
            self.style.rankgap/2,
            self.style.rowgap/2)
    
    def setselectednode (self, nodeitem):
        if nodeitem is not None:
            if self.selectednode:
                self.selectednode.setselected(False)
            self.selectednode = nodeitem
            self.selectednode.setselected(True)
            self.shownode(self.selectednode)
            FlGlob.mainwindow.setselectednode(self, nodeitem.realid())
    
    @pyqtSlot(str)
    def selectbyID (self, nodeID):
        if FlGlob.mainwindow.activeview is not self:
            return
        if self.selectednode is not None and self.selectednode.realid() == nodeID:
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
        if nodeitem is not None:
            nodeID = nodeitem.realid()
        else:
            nodeID = "-1"
        FlGlob.mainwindow.setactivenode(self, nodeID)
    
    @pyqtSlot(str)
    def activatebyID (self, nodeID):
        if FlGlob.mainwindow.activeview is not self:
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
    
    def addundoable (self, hist):
        self.undohistory.appendleft(hist)
        self.redohistory.clear()
    
    def linknode (self, nodeID, refID, pos=None, undo=False):
        self.nodecontainer.newlink(refID, nodeID, pos)
        
        if not undo:
            hist = HistoryAction(self.unlink,
                {"nodeID": nodeID, "refID": refID, "inherit": False},
                self.linknode,
                {"nodeID": nodeID, "refID": refID, "pos": pos},
                "Link node %s to node %s" % (nodeID, refID))
            self.addundoable(hist)
        self.updateview()
    
    def linksubnode (self, subID, bankID, pos, undo=False):
        """Only called as Undo action, assume sane arguments."""
        self.nodecontainer.nodes[bankID].subnodes.insert(pos, subID)
        self.updateview()
    
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
                {"nodeID": nodeID, "refID": newid},
                "Link new node %s to node %s" % (newid, nodeID))
            self.addundoable(hist)
        self.updateview()
        self.shownode(self.itembyID(newid))
    
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
            hist = HistoryAction(self.unlinksubnode,
                {"subID": newid, "bankID": nodeID},
                self.linksubnode,
                {"subID": newid, "bankID": nodeID},
                "Add new subnode %s to node %s" % (newid, nodeID))
            self.addundoable(hist)
        self.updateview()
        self.shownode(self.itembyID(newid))
    
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
        self.updateview()
    
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
        self.updateview()
    
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
        self.updateview()
    
    def undoinherit (self, nodeID, refID, pos, inherited, undo=False):
        """Only called as Undo action, assume sane arguments."""
        cont = self.nodecontainer
        ref = cont.nodes[refID]
        for childID in inherited:
            ref.linkIDs.remove(childID)
        cont.newlink(refID, nodeID, pos)
        self.updateview()
    
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
        self.updateview()
    
    def parentswap (self, gpID, parID, nodeID, undo=False):
        nodes = self.nodecontainer.nodes
        parlinks = nodes[parID].linkIDs
        childlinks = nodes[nodeID].linkIDs
        grandpalinks = nodes[gpID].linkIDs
        
        childindex = parlinks.index(nodeID)
        parlinks.remove(nodeID)
        parlinks.insert(childindex, parID)
        
        parindex = grandpalinks.index(parID)
        grandpalinks.remove(parID)
        grandpalinks.insert(parindex, nodeID)
        
        nodes[parID].linkIDs = childlinks
        nodes[nodeID].linkIDs = parlinks
        
        if not undo:
            hist = HistoryAction(self.parentswap,
                {"gpID": gpID, "parID": nodeID, "nodeID": parID},
                self.parentswap,
                {"gpID": gpID, "parID": parID, "nodeID": nodeID},
                "Swap node %s with parent %s" % (nodeID, parID))
            self.addundoable(hist)
        self.updateview()
    
    def nodetobank (self, nodeID, undo=False):
        cont = self.nodecontainer
        selnode = cont.nodes[nodeID]
        nodedict = selnode.nodeobj.todict()
        
        bankdict = nodedict.copy()
        bankdict["type"] = "bank"
        clonedict = nodedict.copy()
        clonedict["nodebank"] = nodeID
        
        cont.newnode(bankdict, newID=nodeID, force=True)
        newobj = cont.newnode(clonedict, bankID=nodeID)
        
        self.nodedocs[newobj.ID] = self.nodedocs[nodeID]
        
        if not undo:
            hist = HistoryAction(self.banktonode, {"nodeID": nodeID},
                self.nodetobank, {"nodeID": nodeID},
                "Transform node %s to Bank" % nodeID)
            self.addundoable(hist)
        self.updateview()
    
    def banktonode (self, nodeID, undo=False):
        cont = self.nodecontainer
        selnode = cont.nodes[nodeID]
        subID = selnode.subnodes[0]
        nodedict = cont.nodes[subID].todict()
        
        clonedict = nodedict.copy()
        clonedict["nodebank"] = -1
        
        cont.nodes.pop(subID)
        cont.newnode(clonedict, newID=nodeID, force=True)
        
        self.nodedocs[nodeID] = self.nodedocs[subID]
        
        if not undo:
            hist = HistoryAction(self.nodetobank, {"nodeID": nodeID}, 
                self.banktonode, {"nodeID": nodeID},
                "Transform node %s from Bank" % nodeID)
            self.addundoable(hist)
        self.updateview()
    
    def collapse (self, longid, collapse=None, undo=False):
        selID = longid
        if selID in self.collapsednodes:
            if collapse is None or not collapse:
                desc = "Uncollapse"
                self.collapsednodes.remove(selID)
        else:
            if collapse is None or collapse:
                desc = "Collapse"
                self.collapsednodes.append(selID)
        
        if not undo:
            nodeID = self.nodeitems[longid].realid()
            hist = HistoryAction(self.collapse, {"longid": longid},
                self.collapse, {"longid": longid},
                "%s node %s" % (desc, nodeID))
            self.addundoable(hist)
        self.updateview()
    
    def search (self, query):
        if not query:
            self.hits = None
        else:
            hits = []
            for nodeID, nodeobj in self.nodecontainer.nodes.items():
                if query in nodeobj.text.casefold():
                    hits.append(nodeID)
            self.hits = hits
    
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
        if key == Qt.Key_Left:
            if node.parent:
                self.setselectednode(node.parent)
        elif key == Qt.Key_Up:
            sib = node.siblingabove()
            if sib:
                self.setselectednode(sib)
        elif key == Qt.Key_Down:
            sib = node.siblingbelow()
            if sib:
                self.setselectednode(sib)
        elif key == Qt.Key_Right:
            if mod & Qt.ControlModifier and isinstance(node, BankNodeItem):
                if node.subnodes:
                    subnode = node.subnodes[0]
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

class EditorWindow (QMainWindow):
    copiednode = (None, None, None)
    actions = dict()
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
        
        mapview = MapView(self)
        maptimer = QTimer(self)
        maptimer.timeout.connect(mapview.update)
        maptimer.start(100) # OPTION: mapview frame rate
        
        mapdock = QDockWidget("Map view", self)
        mapdock.setWidget(mapview)
        
        textdock = QDockWidget("&Text", self)
        textdock.newWidget = lambda: TextEditWidget(self)
        textdock.setWidget(TextEditWidget(self))
        textdock.widget().setEnabled(False)
        self.textdock = textdock
        
        conddock = QDockWidget("&Condition", self)
        conddock.newWidget = lambda: ConditionEditWidget(self)
        conddock.setWidget(ConditionEditWidget(self))
        conddock.widget().setEnabled(False)
        self.conddock = conddock
        
        onenterdock = QDockWidget("On E&nter", self)
        onenterdock.newWidget = lambda: ScriptEditWidget(self, slot="enter")
        onenterdock.setWidget(ScriptEditWidget(self, slot="enter"))
        onenterdock.widget().setEnabled(False)
        self.onenterdock = onenterdock
        
        onexitdock = QDockWidget("On E&xit", self)
        onexitdock.newWidget = lambda: ScriptEditWidget(self, slot="exit")
        onexitdock.setWidget(ScriptEditWidget(self, slot="exit"))
        onexitdock.widget().setEnabled(False)
        self.onexitdock = onexitdock
        
        propdock = QDockWidget("&Properties", self)
        propdock.newWidget = lambda: PropertiesEditWidget(self)
        propdock.setWidget(PropertiesEditWidget(self))
        propdock.widget().setEnabled(False)
        self.propdock = propdock
        
        nodelist = NodeListWidget(self)
        self.viewChanged.connect(nodelist.setview)
        self.viewUpdated.connect(nodelist.populatelist)
        self.selectedChanged.connect(nodelist.selectbyID)
        listdock = QDockWidget("Node &List", self)
        listdock.setWidget(nodelist)
        self.listdock = listdock
        
        self.setCentralWidget(tabs)
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)
        self.addDockWidget(Qt.RightDockWidgetArea, mapdock)
        self.addDockWidget(Qt.RightDockWidgetArea, textdock)
        self.tabifyDockWidget(textdock, conddock)
        self.tabifyDockWidget(conddock, onenterdock)
        self.tabifyDockWidget(onenterdock, onexitdock)
        self.tabifyDockWidget(onexitdock, propdock)
        textdock.raise_()
        
        self.addDockWidget(Qt.LeftDockWidgetArea, listdock)
        
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
        self.actions["newresponsesub"] = self.createaction("New &Response Subnode", self.newresponsesub,
            [QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_R)], ["insert-object"], "Add new Response subnode")
        self.actions["pastesubnode"] = self.createaction("&Paste Subnode", self.pastesubnode,
            [QKeySequence(Qt.ControlModifier+Qt.ShiftModifier+Qt.Key_B)], ["edit-paste"], "Paste cloned node as subnode")
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
                "collapse", "openfile", "save", "saveas", "newtree", "close"]
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
                elif nodeobj.typename in ["talk", "response"]:
                    actions = ["copynode", "moveup", "movedown", "unlinknode", 
                        "unlinkstree", "settemplate"]
                    if nodeobj.nodebank == -1:
                        actions.extend(["newtalk", "newresponse", "newbank", 
                            "pasteclone", "pastelink", "parentswap", "nodetobank"])
                elif nodeobj.typename == "bank":
                    actions = ["copynode", "moveup", "movedown", "unlinknode", 
                        "newtalk", "newresponse", "newbank", "pasteclone", "pastelink",
                        "unlinkstree", "newtalksub", "newresponsesub", "pastesubnode",
                        "parentswap", "settemplate"]
                    if len(nodeobj.subnodes) == 1:
                        actions.extend(["banktonode"])
                elif nodeobj.typename == "root":
                    actions = ["newtalk", "newresponse", "newbank", "pasteclone",
                        "pastelink"]
            
            actions.extend(genericactions)
            for name, action in self.actions.items():
                if name in actions:
                    if name == "pasteclone" or name == "pastesubnode":
                        if self.copiednode[2] is not None:
                            action.setEnabled(True)
                        else:
                            action.setEnabled(False)
                    elif name == "pastelink":
                        if self.copiednode[0] is not None and self.copiednode[1] is view:
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
        editmenu.addMenu(addmenu)
        editmenu.addMenu(subnodemenu)
        editmenu.addAction(self.actions["copynode"])
        editmenu.addAction(self.actions["settemplate"])
        editmenu.addAction(self.actions["moveup"])
        editmenu.addAction(self.actions["movedown"])
        editmenu.addAction(self.actions["parentswap"])
        editmenu.addMenu(transformmenu)
        editmenu.addSeparator()
        editmenu.addAction(self.actions["unlinknode"])
        editmenu.addAction(self.actions["unlinkstree"])
        editmenu.addAction(self.actions["undo"])
        editmenu.addAction(self.actions["redo"])
        self.editmenu = editmenu
        
        viewmenu = menubar.addMenu("&View")
        viewmenu.addAction(self.actions["zoomin"])
        viewmenu.addAction(self.actions["zoomout"])
        viewmenu.addAction(self.actions["zoomorig"])
        viewmenu.addAction(self.actions["gotoactive"])
        viewmenu.addAction(self.actions["collapse"])
        
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
        filetoolbar.addAction(self.actions["saveas"])
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
        self.viewChanged.emit()
    
    def setactivenode (self, view, nodeID):
        self.setactiveview(view)
        self.activenode = nodeID
        self.activeChanged.emit(nodeID)
    
    def setselectednode (self, view, nodeID):
        self.setactiveview(view)
        self.selectednode = nodeID
        self.selectedChanged.emit(nodeID)
    
    def resetdocks (self):
        for dock in (self.textdock, self.onenterdock, self.onexitdock, self.conddock, self.propdock):
            olddock = dock.widget()
            dock.setWidget(dock.newWidget())
            dock.widget().setEnabled(False)
            olddock.deleteLater()
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        self.resetdocks()
        if nodeID == "-1":
            return
        view = self.activeview
        nodeobj = view.nodecontainer.nodes[nodeID]
        if nodeobj.typename in ["talk", "response"]:
            self.textdock.widget().setEnabled(True)
            self.textdock.widget().loadnode(nodeID)
        else:
            self.textdock.widget().setEnabled(False)
        
        for dock in (self.onenterdock, self.onexitdock, self.conddock, self.propdock):
            dock.widget().setEnabled(True)
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
        self.resetdocks()
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
            self.copiednode = (None, None, nodedict)
        else:
            self.copiednode = (nodeobj.ID, view, nodedict)
        
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
        view.addnode(nodeID, ndict=self.copiednode[2])
    
    @pyqtSlot()
    def pastelink (self):
        view = self.activeview
        refID = view.selectednode.realid()
        view.linknode(self.copiednode[0], refID)
    
    @pyqtSlot()
    def pastesubnode (self):
        view = self.activeview
        nodeID = view.selectednode.realid()
        view.addsubnode(nodeID, ndict=self.copiednode[2])
    
    @pyqtSlot()
    def unlinkinherit (self):
        self.unlink(inherit=True)
    
    @pyqtSlot()
    def unlink (self, inherit=False):
        view = self.activeview
        selected = view.selectednode
        if selected.parent is None:
            return
        if len(selected.realnode().referrers) == 1:
            if inherit or len(selected.childlist()) == 0:
                text = "This will remove the only instance of node %s.\n\nContinue?" % selected.realid()
            else:
                text = "This will remove the only instance of node %s and all unique nodes in its subtree.\n\nContinue?" % selected.realid()
        else:
            text = "Unlink node %s from node %s?" % (selected.realid(), selected.parent.realid())
        answer = QMessageBox.question(self, "Node removal", text)
        if answer == QMessageBox.No:
            return
        
        if selected.issubnode():
            view.unlinksubnode(selected.realid(), selected.parent.realid())
        elif inherit:
            view.unlink_inherit(selected.realid(), selected.parent.realid())
        else:
            view.unlink(selected.realid(), selected.parent.realid())
    
    @pyqtSlot()
    def moveup (self):
        view = self.activeview
        selnode = view.selectednode
        nodeID = selnode.realid()
        refID = selnode.parent.realid()
        if selnode.siblingabove() is not None:
            view.move(nodeID, refID, up=True)
    
    @pyqtSlot()
    def movedown (self):
        view = self.activeview
        selnode = view.selectednode
        nodeID = selnode.realid()
        refID = selnode.parent.realid()
        if selnode.siblingbelow() is not None:
            view.move(nodeID, refID, up=False)
    
    @pyqtSlot()
    def parentswap (self):
        view = self.activeview
        selnode = view.selectednode
        parent = selnode.parent
        grandpa = parent.parent
        if grandpa is None:
            return
        view.parentswap(grandpa.realid(), parent.realid(), selnode.realid())
    
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
        longid = view.selectednode.id()
        view.collapse(longid)
    
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
            self.filteractions()
        
        return redo

def elidestring (string, length):
    if len(string) <= length:
        return string
    else:
        return string[:length-1]+"…"

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec_())
