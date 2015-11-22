#!/usr/bin/env python

import sys
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtOpenGL import *
import flint_parser as fp
import os
import weakref
import inspect as insp
from collections import OrderedDict

class FlGlob:
    mainwindow = None

class FlPalette (object):
    """Palette of custom colors for quick reference."""
    dark    = QColor( 38,  39,  41)
    light   = QColor(250, 250, 250)
    hl1     = QColor(200,  60,  19) # QColor(224,  70,  19)
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

class QGraphicsRectItemCond (QGraphicsRectItem):
    def __init__(self, parent=0, cond=None):
        super().__init__(parent)
        self.cond = cond
    
    def paint(self, painter, style, widget):
        if self.cond(self, widget):
            super().paint(painter, style, widget)

class QGraphicsSimpleTextItemCond (QGraphicsSimpleTextItem):
    def __init__(self, parent=0, cond=None):
        super().__init__(parent)
        self.cond = cond
    
    def paint(self, painter, style, widget):
        if self.cond(self, widget):
            super().paint(painter, style, widget)

class QGraphicsTextItemCond (QGraphicsTextItem):
    def __init__(self, parent=0, cond=None):
        super().__init__(parent)
        self.cond = cond
    
    def paint(self, painter, style, widget):
        if self.cond(self, widget):
            super().paint(painter, style, widget)

class QGraphicsPixmapItemCond (QGraphicsPixmapItem):
    def __init__ (self, pixmap, parent, cond=None):
        super().__init__(pixmap, parent)
        self.cond = cond
    
    def paint(self, painter, style, widget):
        if self.cond(self, widget):
            super().paint(painter, style, widget)

class NodeItem(QGraphicsItem):
    def __init__(self, nodeobj, parent=None, view=None, ghost=False):
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
        return self.view.nodedict[self.nodeobj.ID]
    
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
        
    def boundingRect(self):
        return self.rect
        
    def paint(self, painter, style, widget):
        """if self.nodeobj in self.view.hits:
            self.textbox.setBrush(QBrush(QColor(255, 255, 100)))
        else:
            self.textbox.setBrush(QBrush(QColor(FlPalette.light)))"""
    
    def graphicsetup (self):
        lightbrush = QBrush(FlPalette.light)
        mainbrush = QBrush(self.maincolor)
        altbrush = QBrush(self.altcolor)
        nopen = QPen(0)
        
        self.graphgroup = QGraphicsItemGroup(self)
        
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
        
        self.nodelabel = QGraphicsSimpleTextItemCond(self, 
            lambda s,w: w is self.view.viewport())
        self.nodelabel.setBrush(lightbrush)
        self.nodelabel.setFont(self.style.boldfont)
        self.nodelabel.setText(self.label % self.realid())
        self.nodelabel.setPos(self.style.itemmargin, self.style.itemmargin)
        self.graphgroup.addToGroup(self.nodelabel)
        
        condpix = QPixmap("images/key.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.condicon = QGraphicsPixmapItemCond(condpix, self,
            lambda s,w: w is self.view.viewport() and self.nodeobj.hascond() and not self.iscollapsed())
        self.condicon.setPos(self.style.nodetextwidth-condpix.width(), self.style.itemmargin)
        self.graphgroup.addToGroup(self.condicon)
        
        exitpix = QPixmap("images/script-exit.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.exiticon = QGraphicsPixmapItemCond(exitpix, self,
            lambda s,w: w is self.view.viewport() and self.nodeobj.hasexitscripts() and not self.iscollapsed())
        self.exiticon.setPos(self.condicon.x()-self.style.itemmargin-exitpix.width(), self.style.itemmargin)
        self.graphgroup.addToGroup(self.exiticon)
        
        enterpix = QPixmap("images/script-enter.png").scaledToWidth(self.style.boldheight, Qt.SmoothTransformation)
        self.entericon = QGraphicsPixmapItemCond(enterpix, self,
            lambda s,w: w is self.view.viewport() and self.nodeobj.hasenterscripts() and not self.iscollapsed())
        self.entericon.setPos(self.exiticon.x()-self.style.itemmargin-enterpix.width(), self.style.itemmargin)
        self.graphgroup.addToGroup(self.entericon)
    
    def mouseDoubleClickEvent (self, event):
        super().mouseDoubleClickEvent(event)
        event.accept()
        if event.button() == Qt.LeftButton:
            self.view.setactivenode(self)
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() & (Qt.LeftButton | Qt.RightButton) :
            self.view.setselectednode(self)
            event.accept()
    
    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.id())


class RootNodeItem (NodeItem):
    maincolor = FlPalette.root
    altcolor = FlPalette.rootvar
    label = "%s Root"
    
    def graphicsetup (self):
        super().graphicsetup()
        self.updatelayout()
    
    def updatelayout (self):
        if self.iscollapsed():
            labelrect = self.nodelabel.mapRectToParent(self.nodelabel.boundingRect())
        else:
            labelrect = self.nodelabel.mapRectToParent(self.nodelabel.boundingRect().united(self.condicon.mapRectToParent(self.condicon.boundingRect())))
        mainrect = labelrect.marginsAdded(QMarginsF(*[self.style.nodemargin]*4))
        self.mainbox.setRect(mainrect)
        self.shadowbox.setRect(mainrect)
        self.selectbox.setRect(mainrect.marginsAdded(QMarginsF(*[self.style.selectmargin]*4)))
        activerect = mainrect.marginsAdded(QMarginsF(*[self.style.activemargin]*4))
        self.activebox.setRect(activerect)
        self.graphgroup.setPos(-activerect.width()//2-activerect.x(), -activerect.height()//2-activerect.y())
        self.prepareGeometryChange()
        self.rect = self.graphgroup.mapRectToParent(self.activebox.boundingRect())
        self.nodebank.updatelayout()
    
    def contextMenuEvent (self, event):
        menu = QMenu()
        if self.isselected():
            window = FlGlob.mainwindow
            menu.addAction(window.actions["collapse"])
            menu.addMenu(window.addmenu)
        if not menu.isEmpty():
            menu.exec_(event.screenPos())


class TextNodeItem (NodeItem):
    def __init__(self, nodeobj, parent=None, view=None, ghost=False):
        self.textheight = 0
        self.collapselayout = False
        super().__init__(nodeobj, parent, view, ghost)
    
    def graphicsetup (self):
        super().graphicsetup()
        
        lightbrush = QBrush(FlPalette.light)
        nopen = QPen(0)
        viewport = self.view.viewport()
        
        self.textbox = QGraphicsRectItemCond(self, 
            lambda s,w: w is viewport and not self.iscollapsed())
        self.textbox.setBrush(lightbrush)
        self.textbox.setPen(nopen)
        self.graphgroup.addToGroup(self.textbox)
        
        self.nodespeaker = QGraphicsSimpleTextItemCond(self,
            lambda s,w: w is viewport and not self.iscollapsed())
        self.nodespeaker.setBrush(lightbrush)
        self.nodespeaker.setText(self.nodeobj.speaker)
        self.nodespeaker.setPos(self.style.itemmargin, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin*2)
        self.graphgroup.addToGroup(self.nodespeaker)
        
        self.nodetext = QGraphicsTextItemCond(self,
            lambda s,w: w is viewport and not self.iscollapsed())
        self.nodetext.setTextWidth(self.style.nodetextwidth)
        self.nodetext.setDefaultTextColor(FlPalette.dark)
        self.nodetext.setPos(0, self.nodespeaker.y()+self.nodespeaker.boundingRect().height()+self.style.itemmargin)
        self.graphgroup.addToGroup(self.nodetext)
        
        self.view.nodedocs[self.realid()]["text"].contentsChanged.connect(self.updatelayout)
        self.updatelayout()
    
    @pyqtSlot()
    def updatelayout (self, force=False):
        if self.iscollapsed():
            if self.collapselayout and not force:
                return
            else:
                textrect = QRectF()
                self.collapselayout = True
        else:
            ndtxt = self.nodetext
            ndtxt.setPlainText(self.view.nodedocs[self.realid()]["text"].toPlainText())
            textrect = ndtxt.mapRectToParent(ndtxt.boundingRect())
            textheight = textrect.height()
            if textheight == self.textheight and not force:
                return
            self.textheight = textheight
            self.textbox.setRect(textrect)
        mainrect = textrect.united(self.nodelabel.mapRectToParent(self.nodelabel.boundingRect())).marginsAdded(QMarginsF(*[self.style.nodemargin]*4))
        self.mainbox.setRect(mainrect)
        self.shadowbox.setRect(mainrect)
        self.selectbox.setRect(mainrect.marginsAdded(QMarginsF(*[self.style.selectmargin]*4)))
        activerect = mainrect.marginsAdded(QMarginsF(*[self.style.activemargin]*4))
        self.activebox.setRect(activerect)
        self.graphgroup.setPos(-activerect.width()//2-activerect.x(), -activerect.height()//2-activerect.y())
        self.prepareGeometryChange()
        self.rect = self.graphgroup.mapRectToParent(self.activebox.boundingRect())
        self.nodebank.updatelayout()
    
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
        if not menu.isEmpty():
            menu.exec_(event.screenPos())

class TalkNodeItem(TextNodeItem):
    maincolor = FlPalette.hl1var
    altcolor = FlPalette.hl1
    label = "%s Talk"

class ResponseNodeItem(TextNodeItem):
    maincolor = FlPalette.hl2var
    altcolor = FlPalette.hl2
    label = "%s Response"

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
            subnode.updatelayout(force=True)
        self.updatelayout()
    
    def graphicsetup (self):
        super().graphicsetup()
        darkbrush = QBrush(FlPalette.bg)
        nopen = QPen(0)
        
        self.centerbox = QGraphicsRectItemCond(self, 
            lambda s,w: w is self.view.viewport() and not self.iscollapsed())
        self.centerbox.setRect(QRectF())
        self.centerbox.setBrush(darkbrush)
        self.centerbox.setPen(nopen)
        self.centerbox.setPos(0, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin*2)
        self.graphgroup.addToGroup(self.centerbox)
    
    def updatelayout (self):
        if self.iscollapsed():
            for subnode in self.subnodes:
                subnode.hide()
            centerrect = QRectF()
        else:
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
        mainrect = centerrect.united(self.nodelabel.mapRectToParent(self.nodelabel.boundingRect())).marginsAdded(QMarginsF(*[self.style.nodemargin]*4))
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
            menu.addMenu(window.subnodemenu)
            menu.addMenu(window.addmenu)
            menu.addAction(window.actions["moveup"])
            menu.addAction(window.actions["movedown"])
            menu.addAction(window.actions["parentswap"])
            menu.addAction(window.actions["unlinknode"])
            menu.addAction(window.actions["unlinkstree"])
        if not menu.isEmpty():
            menu.exec_(event.screenPos())


class EdgeItem(QGraphicsItem):
    arrowsize = 10
    
    def __init__(self, source, view):
        super().__init__()
        self.source = source
        source.setedge(self)
        self.view = weakref.proxy(view)
        self.style = FlGlob.mainwindow.style
        
        pen = QPen(FlPalette.light, 2, cap = Qt.FlatCap, join=Qt.MiterJoin)
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
    
    def boundingRect(self):
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
    
    def paint(self, painter, style, widget, off=0, main=True):
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
            pen.setWidth(2)
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
            FlGlob.mainwindow.activeview().setFocus()
        else:
            super().keyPressEvent(event)

class TextEditWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        l_speaker = QLabel("Speaker")
        self.speaker = QLineEdit(self)
        l_speaker.setBuddy(self.speaker)
        
        l_nodetext = QLabel("Text")
        self.nodetext = ParagraphEdit(self)
        l_nodetext.setBuddy(self.nodetext)
        
        layout.addWidget(l_speaker)
        layout.addWidget(self.speaker)
        layout.addWidget(l_nodetext)
        layout.addWidget(self.nodetext)
        
        self.nodeobj = None
        self.speaker.textChanged.connect(self.setnodespeaker)
        self.nodetext.textChanged.connect(self.setnodetext)
        
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview()
        self.nodeobj = view.nodecontainer.nodes[nodeID]
        if not isinstance(self.nodeobj, fp.TextNode):
            return
        nodetextdoc = view.nodedocs[nodeID]["text"]
        self.speaker.setText(self.nodeobj.speaker)
        self.nodetext.setDocument(nodetextdoc)
        self.nodetext.setFocus()
        self.nodetext.moveCursor(QTextCursor.End)
    
    @pyqtSlot()
    def setnodespeaker (self):
        self.nodeobj.speaker = self.speaker.text()
    
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
        else: #elif annot is str:
            editor = QLineEdit(self)
            signal = editor.textEdited
            value = editor.text
            editor.setText(default)
        
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
    
    def __init__ (self, parent, callobj, cond=False):
        name = callobj.funcname
        super().__init__(parent, callobj, name)
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
        scriptcalls = [sc for sc in dir(fp.ScriptCall) if sc[:3] == "sc_"]
        if cond:
            scriptcalls.insert(0, "( )")
        self.scriptcalls = scriptcalls
        
        combobox = QComboBox(self)
        combobox.insertItems(len(scriptcalls), scriptcalls)
        self.combobox = combobox
        addbutton = QPushButton("Add", self)
        addbutton.clicked.connect(self.newscriptcall)
        
        layout = QHBoxLayout(self)
        #layout.setContentsMargins(*[0]*4)
        layout.addWidget(combobox)
        layout.addWidget(addbutton)
    
    @pyqtSlot()
    def newscriptcall (self):
        name = self.combobox.currentText()
        if name == "( )":
            callobj = fp.MetaCall({"type":"cond","operator":"and","calls":[]})
        else:
            signature = insp.signature(getattr(fp.ScriptCall, name))
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
    
    def __init__ (self, parent, callobj, cond=True):
        name = "()"
        super().__init__ (parent, callobj, name)
        operatorwidget = QWidget(self)
        operatorlabel = QLabel("Operator", operatorwidget)
        operatorcombo = QComboBox(operatorwidget)
        operatorcombo.insertItems(2, ["and", "or"])
        operatorcombo.setCurrentText(callobj.operatorname)
        operatorcombo.currentTextChanged.connect(self.setoperator)
        operatorlayout = QHBoxLayout(operatorwidget)
        #operatorlayout.setContentsMargins(*[0]*4)
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
        FlGlob.mainwindow.activeview().viewport().update()
    
    def addcallwidget (self, callobj):
        widget = self.types[callobj.typename](self, callobj, cond=True)
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
    
    def elidestring (self, string, length):
        if len(string) <= length:
            return string
        else:
            return string[:length-1]+"…"
    
    @pyqtSlot()
    def newtitle (self):
        fullname = self.fullname(self.callobj, recursive=True)
        shortname = self.fullname(self.callobj)
        self.setTitle(self.elidestring(shortname,30))
        self.setToolTip(fullname)
        self.changed.emit()
    
    @pyqtSlot(str)
    def setoperator (self, operatorname):
        self.callobj.setoperator(operatorname)
        self.newtitle()
    
    @pyqtSlot(fp.ScriptCall)
    @pyqtSlot(fp.ConditionCall)
    def removecall (self, callobj):
        widget = self.widgets.pop(callobj)
        self.callswidget.layout().removeWidget(widget)
        widget.deleteLater()
        self.callobj.calls.remove(callobj)
        FlGlob.mainwindow.activeview().viewport().update()

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
        #layout.setContentsMargins(*[0]*4)
        layout.setAlignment(Qt.AlignTop)

class ConditionEditWidget (CallEditWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.layout().addWidget(self.callsarea)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview()
        nodeobj = view.nodecontainer.nodes[nodeID]
        self.nodeobj = nodeobj
        callobj = nodeobj.condition
        callswidget = self.callsarea.widget()
        scwidget = ConditionCallWidget(callswidget, callobj)
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
        view = FlGlob.mainwindow.activeview()
        nodeobj = view.nodecontainer.nodes[nodeID]
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
        FlGlob.mainwindow.activeview().viewport().update()
    
    def addscriptcallwidget (self, callobj):
        callswidget = self.callsarea.widget()
        scwidget = ScriptCallWidget(callswidget, callobj)
        scwidget.removed.connect(self.removescriptcall)
        self.widgets[callobj] = scwidget
        callswidget.layout().addWidget(scwidget)
    
    @pyqtSlot(fp.ScriptCall)
    def removescriptcall (self, callobj):
        callswidget = self.callsarea.widget()
        scwidget = self.widgets.pop(callobj)
        callswidget.layout().removeWidget(scwidget)
        scwidget.deleteLater()
        self.scripts.remove(callobj)
        FlGlob.mainwindow.activeview().viewport().update()

class PropertiesEditWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        layout = QFormLayout(self)
        
        l_memory = QLabel("Memory", self)
        memory = QComboBox(self)
        memoryvals = ["", "Mark", "OnceEver", "OncePerConv"]
        memory.insertItems(len(memoryvals), memoryvals)
        memory.currentTextChanged.connect(self.propertychanged)
        self.memory = memory
        
        layout.addRow(l_memory, memory)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview()
        nodeobj = view.nodecontainer.nodes[nodeID]
        self.nodeobj = nodeobj
        self.memory.setCurrentText(str(nodeobj.memory))
    
    @pyqtSlot()
    def propertychanged (self):
        memory = self.memory.currentText()
        self.nodeobj.memory = memory

class SearchWidget (QWidget):
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
        self.setMaximumWidth(200)
        
        layout.addWidget(self.inputline)
        layout.addWidget(searchbutton)
        
        self.setEnabled(False)
    
    def search (self):
        query = self.inputline.text().casefold()
        view = FlGlob.mainwindow.activeview()
        view.search(query)

class MapView (QGraphicsView):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setOptimizationFlags(QGraphicsView.DontAdjustForAntialiasing | QGraphicsView.DontSavePainterState)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.treeview = None
        self.scenerect = self.viewrect = QRectF()
    
    def mousePressEvent (self, event):
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
        activeview = window.activeview()
        if activeview is None:
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

class TreeView (QGraphicsView):
    
    activeChanged = pyqtSignal(str)
    selectedChanged = pyqtSignal(str)
    __types = {'talk': TalkNodeItem, 'response': ResponseNodeItem, 
        'bank': BankNodeItem, 'root': RootNodeItem}
    
    def __init__ (self, nodecontainer, parent=None):
        super().__init__(parent)
        self.zoomscale = 1
        self.activenode = None
        self.selectednode = None
        self.collapsednodes = []
        self.hits = []
        
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
        
        self.selectedChanged.connect(self.filteractions)
        
        self.nodecontainer = nodecontainer
        self.nodedocs = dict()
        self.updateview()
        self.setselectednode(self.treeroot())
    
    def updatedocs (self):
        newnodedocs = dict()
        for nodeID, nodeobj in self.nodecontainer.nodes.items():
            if nodeID in self.nodedocs:
                newnodedocs[nodeID] = self.nodedocs[nodeID]
            elif isinstance(nodeobj, fp.TextNode):
                textdoc = QTextDocument(self)
                textdoc.setDocumentLayout(QPlainTextDocumentLayout(textdoc))
                textdoc.setPlainText(nodeobj.text)
                newnodedocs[nodeID] = {"text": textdoc}
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
        self.nodedict = dict()
        self.viewframe = FrameItem(view=self)
        self.scene().addItem(self.viewframe)
        self.constructed = self.constructgraph()
        self.updatelayout()
        
        if activeID and activeID in self.nodedict:
            self.setactivenode(self.nodedict[activeID], signal=False)
        else:
            self.setactivenode(None)
        
        baseID = ""
        while selectedID:
            swappedID = "<-".join([baseID, selectedID])
            if baseID and swappedID in self.nodedict:
                self.setselectednode(self.nodedict[swappedID], signal=False)
                break
            elif selectedID in self.nodedict:
                self.setselectednode(self.nodedict[selectedID])
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
        defaultid = "<-".join([nodeobj.ID, refid])
        if isghost:
            graphid = defaultid
        elif nodeobj.ID in self.nodedict:
            oldnode = self.nodedict[nodeobj.ID]
            oldnode.setghost(True)
            self.nodedict[oldnode.id()] = oldnode
            nodeitem.referrers = oldnode.referrers
            oldnode.referrers = []
            graphid = nodeobj.ID
        else:
            graphid = nodeobj.ID
        self.nodedict[graphid] = nodeitem
        self.nodedict[defaultid] = nodeitem
        
        if refid:
            self.nodedict[nodeobj.ID].addreferrer(refid)
        
        return nodeitem
    
    def treeroot (self):
        return self.nodedict["0"]
    
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
    
    def setselectednode (self, nodeitem, signal=True):
        if nodeitem is not None:
            if self.selectednode:
                self.selectednode.setselected(False)
            self.selectednode = nodeitem
            self.selectednode.setselected(True)
            self.shownode(self.selectednode)
            if signal:
                self.selectedChanged.emit(self.selectednode.realid())
    
    def setactivenode (self, nodeitem, signal=True):
        if nodeitem is not None:
            if self.activenode:
                self.activenode.setactive(False)
            self.activenode = nodeitem.realnode()
            self.activenode.setactive(True)
            if signal:
                self.activeChanged.emit(self.activenode.realid())
        else:
            if self.activenode is not None:
                self.activenode = None
            if signal:
                self.activeChanged.emit("-1")
    
    def createlink (self, toID):
        fromID = self.selectednode.realid()
        self.nodecontainer.newlink(fromID, toID)
        self.updateview()
    
    def addnode (self, nodedict, subnode=False):
        selectedid = self.selectednode.realid()
        if subnode:
            nodedictmod = nodedict.copy()
            nodedictmod["nodebank"] = selectedid
            newobj = self.nodecontainer.newnode(nodedictmod, bankID=selectedid)
        else:
            newobj = self.nodecontainer.newnode(nodedict, refID=selectedid)
        newid = newobj.ID
        self.updateview()
        self.shownode(self.nodedict[newid])
    
    def unlink (self, inherit=False):
        selID = self.selectednode.realid()
        refID = self.selectednode.parent.realid()
        if self.selectednode.issubnode():
            self.nodecontainer.removesubnode(refID, selID)
        else:
            self.nodecontainer.removelink(refID, selID, forceinherit=inherit)
        self.updateview()
    
    def moveup (self):
        selnode = self.selectednode
        sibling = selnode.siblingabove()
        parent = selnode.parent
        if sibling is None or parent is None:
            return
        selID = selnode.realid()
        sibID = sibling.realid()
        parID = parent.realid()
        if selnode.issubnode():
            self.nodecontainer.subnodeswap(parID, selID, sibID)
        else:
            self.nodecontainer.siblingswap(parID, selID, sibID)
        self.updateview()
    
    def movedown (self):
        selnode = self.selectednode
        sibling = selnode.siblingbelow()
        parent = selnode.parent
        if sibling is None or parent is None:
            return
        selID = selnode.realid()
        sibID = sibling.realid()
        parID = parent.realid()
        if selnode.nodebank is parent:
            self.nodecontainer.subnodeswap(parID, selID, sibID)
        else:
            self.nodecontainer.siblingswap(parID, selID, sibID)
        self.updateview()
    
    def parentswap (self):
        selnode = self.selectednode
        parent = selnode.parent
        grandparent = parent.parent
        if grandparent is None:
            return
        self.nodecontainer.parentswap(grandparent.realid(), parent.realid(), selnode.realid())
        self.updateview()
    
    def collapse (self, collapse=None):
        selID = self.selectednode.id()
        if selID in self.collapsednodes:
            if collapse is None or not collapse:
                self.collapsednodes.remove(selID)
        else:
            if collapse is None or collapse:
                self.collapsednodes.append(selID)
        self.updateview()
    
    @pyqtSlot(str)
    def filteractions (self, nodeID=""):
        if nodeID == "":
            nodeID = self.selectednode.id()
        nodeitem = self.nodedict[nodeID]
        genericactions = ["zoomin", "zoomout", "zoomorig", "gotoactive",
            "collapse", "openfile", "save", "saveas", "newtree", "close"]
        if isinstance(nodeitem, TextNodeItem):
            actions = ["copynode", "moveup", "movedown", "unlinknode", 
                "unlinkstree"]
            if not nodeitem.issubnode():
                actions.extend(["newtalk", "newresponse", "newbank", 
                    "pasteclone", "pastelink", "parentswap"])
        elif isinstance(nodeitem, BankNodeItem):
            actions = ["copynode", "moveup", "movedown", "unlinknode", 
                "newtalk", "newresponse", "newbank", "pasteclone", "pastelink",
                "unlinkstree", "newtalksub", "newresponsesub", "pastesubnode",
                "parentswap"]
        elif isinstance(nodeitem, RootNodeItem):
            actions = ["newtalk", "newresponse", "newbank", "pasteclone",
                "pastelink"]
        
        actions.extend(genericactions)
        windowactions = FlGlob.mainwindow.actions
        copiednode = FlGlob.mainwindow.copiednode
        for name, action in windowactions.items():
            if name in actions:
                if name == "pasteclone" or name == "pastesubnode":
                    if copiednode[2] is not None:
                        action.setEnabled(True)
                    else:
                        action.setEnabled(False)
                elif name == "pastelink":
                    if copiednode[0] is not None and copiednode[1] is self:
                        action.setEnabled(True)
                    else:
                        action.setEnabled(False)
                else:
                    action.setEnabled(True)
                    if name == "collapse":
                        if nodeitem.iscollapsed():
                            action.setText("Uncolla&pse Subtree")
                        else:
                            action.setText("Colla&pse Subtree")
            else:
                action.setEnabled(False)
    
    def search (self, query):
        if not query:
            self.hits = []
        else:
            hits = []
            for nodeobj in self.nodecontainer.nodes.values():
                if query in nodeobj.text.casefold():
                    hits.append(nodeobj)
            self.hits = hits
    
    def wheelEvent (self, event):
        mod = event.modifiers()
        if mod == Qt.ControlModifier:
            delta = event.angleDelta().y()
            step = delta/120
            self.zoomstep(step) 
        else:
            super().wheelEvent(event)
    
    def keyPressEvent(self, event):
        key = event.key()
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
    
    def __init__ (self):
        super().__init__()
        
        FlGlob.mainwindow = self
        
        self.style = FlNodeStyle(QFont())
        self.initactions()
        self.initmenus()
        self.inittoolbars()
        
        tabs = QTabWidget(parent=self)
        tabs.setTabsClosable(True)
        tabs.setTabBarAutoHide(True)
        tabs.tabCloseRequested.connect(self.closetab)
        tabs.tabBarDoubleClicked.connect(self.nametab)
        self.tabs = tabs                        
        
        mapview = MapView(self)
        mapview.setMinimumSize(200, 200)
        maptimer = QTimer(self)
        maptimer.timeout.connect(mapview.update)
        maptimer.start(100) # OPTION: mapview frame rate
        
        mapdock = QDockWidget("Map view", self)
        mapdock.setWidget(mapview)
        
        textdock = QDockWidget("Text", self)
        textdock.newWidget = lambda: TextEditWidget(self)
        textdock.setWidget(TextEditWidget(self))
        textdock.setEnabled(False)
        self.textdock = textdock
        
        conddock = QDockWidget("Condition", self)
        conddock.newWidget = lambda: ConditionEditWidget(self)
        conddock.setWidget(ConditionEditWidget(self))
        conddock.setEnabled(False)
        self.conddock = conddock
        
        onenterdock = QDockWidget("On Enter", self)
        onenterdock.newWidget = lambda: ScriptEditWidget(self, slot="enter")
        onenterdock.setWidget(ScriptEditWidget(self, slot="enter"))
        onenterdock.setEnabled(False)
        self.onenterdock = onenterdock
        
        onexitdock = QDockWidget("On Exit", self)
        onexitdock.newWidget = lambda: ScriptEditWidget(self, slot="exit")
        onexitdock.setWidget(ScriptEditWidget(self, slot="exit"))
        onexitdock.setEnabled(False)
        self.onexitdock = onexitdock
        
        propdock = QDockWidget("Properties", self)
        propdock.newWidget = lambda: PropertiesEditWidget(self)
        propdock.setWidget(PropertiesEditWidget(self))
        propdock.setEnabled(False)
        self.propdock = propdock
        
        self.setCentralWidget(tabs)
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)
        self.addDockWidget(Qt.RightDockWidgetArea, mapdock)
        self.addDockWidget(Qt.RightDockWidgetArea, textdock)
        self.tabifyDockWidget(textdock, conddock)
        self.tabifyDockWidget(conddock, onenterdock)
        self.tabifyDockWidget(onenterdock, onexitdock)
        self.tabifyDockWidget(onexitdock, propdock)
    
    def activeview (self):
        return self.tabs.currentWidget()
    
    def initactions (self):
        self.actions["openfile"] = self.createaction("Open", self.selectopenfile,
            [QKeySequence.Open], ["document-open"], "Open dialogue file")
        self.actions["save"] = self.createaction("Save", self.save,
            [QKeySequence.Save], ["document-save"], "Save dialogue file")
        self.actions["saveas"] = self.createaction("Save As", self.saveas,
            [QKeySequence.SaveAs], ["document-save-as"], "Save dialogue file as")
        self.actions["newtree"] = self.createaction("New", self.newtree,
            [QKeySequence.New], ["document-new"], "New dialogue tree")
        self.actions["close"] = self.createaction("Close", self.closefile,
            None, ["window-close"], "Close file")
        
        self.actions["zoomin"] = self.createaction("Zoom In", self.zoomin, 
            [QKeySequence.ZoomIn, QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_Plus)], 
            ["gtk-zoom-in", "zoom-in"], "Zoom in")
        self.actions["zoomout"] = self.createaction("Zoom Out", self.zoomout, 
            [QKeySequence.ZoomOut, QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_Minus)], 
            ["gtk-zoom-out", "zoom-out"], "Zoom out")
        self.actions["zoomorig"] = self.createaction("Zoom Original", self.zoomorig, 
            [QKeySequence(Qt.ControlModifier + Qt.Key_0), QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_0)], 
            ["gtk-zoom-100", "zoom-original"], "Zoom to original size")
        self.actions["gotoactive"] = self.createaction("Go To Active", self.gotoactive, 
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
        #addmenu.setIcon(QIcon.fromTheme("insert-object"))
        self.addmenu = addmenu
        
        subnodemenu = QMenu("Add &subnode...")
        subnodemenu.addAction(self.actions["pastesubnode"])
        subnodemenu.addSeparator()
        subnodemenu.addAction(self.actions["newtalksub"])
        subnodemenu.addAction(self.actions["newresponsesub"])
        self.subnodemenu = subnodemenu
        
        editmenu = menubar.addMenu("&Edit")
        editmenu.addMenu(addmenu)
        editmenu.addMenu(subnodemenu)
        editmenu.addAction(self.actions["copynode"])
        editmenu.addAction(self.actions["moveup"])
        editmenu.addAction(self.actions["movedown"])
        editmenu.addAction(self.actions["parentswap"])
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
    
    def inittoolbars (self):
        filetoolbar = QToolBar("File actions")
        filetoolbar.addAction(self.actions["openfile"])
        filetoolbar.addAction(self.actions["newtree"])
        filetoolbar.addAction(self.actions["save"])
        filetoolbar.addAction(self.actions["saveas"])
        self.addToolBar(filetoolbar)
        
        viewtoolbar = QToolBar("View control")
        viewtoolbar.addAction(self.actions["zoomorig"])
        viewtoolbar.addAction(self.actions["zoomin"])
        viewtoolbar.addAction(self.actions["zoomout"])
        viewtoolbar.addAction(self.actions["gotoactive"])
        self.addToolBar(viewtoolbar)
        
        edittoolbar = QToolBar("Tree editing")
        #edittoolbar.addAction(self.addmenu.menuAction())
        edittoolbar.addAction(self.actions["copynode"])
        edittoolbar.addAction(self.actions["pasteclone"])
        edittoolbar.addAction(self.actions["pastelink"])
        edittoolbar.addAction(self.actions["unlinknode"])
        edittoolbar.addAction(self.actions["unlinkstree"])
        edittoolbar.addAction(self.actions["moveup"])
        edittoolbar.addAction(self.actions["movedown"])
        self.addToolBar(edittoolbar)
        
        searchtoolbar = QToolBar("Search")
        searchwidget = SearchWidget(self)
        searchtoolbar.addWidget(searchwidget)
        self.addToolBar(searchtoolbar)
    
    def resetdocks (self):
        for dock in (self.textdock, self.onenterdock, self.onexitdock, self.conddock, self.propdock):
            dock.setEnabled(False)
            olddock = dock.widget()
            dock.setWidget(dock.newWidget())
            olddock.deleteLater()
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        self.resetdocks()
        if nodeID == "-1":
            return
        view = self.activeview()
        nodeobj = view.nodecontainer.nodes[nodeID]
        if nodeobj.typename in ["talk", "response"]:
            self.textdock.setEnabled(True)
            self.textdock.widget().loadnode(nodeID)
        else:
            self.textdock.setEnabled(False)
        
        self.onenterdock.setEnabled(True)
        self.onenterdock.widget().loadnode(nodeID)
        self.onexitdock.setEnabled(True)
        self.onexitdock.widget().loadnode(nodeID)
        self.conddock.setEnabled(True)
        self.conddock.widget().loadnode(nodeID)
        self.propdock.setEnabled(True)
        self.propdock.widget().loadnode(nodeID)
    
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
        treeview.activeChanged.connect(self.loadnode)
        tabindex = self.tabs.addTab(treeview, name)
        self.tabs.setCurrentIndex(tabindex)
    
    @pyqtSlot()
    def save (self, newfile=False):
        nodecont = self.activeview().nodecontainer
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
        view = self.activeview()
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
        self.activeview().zoomstep(1)
    
    @pyqtSlot()
    def zoomout (self):
        self.activeview().zoomstep(-1)
    
    @pyqtSlot()
    def zoomorig (self):
        self.activeview().zoomfixed(1)
    
    @pyqtSlot()
    def gotoactive (self):
        view = self.activeview()
        view.centerOn(view.activenode)
    
    @pyqtSlot()
    def newtalk (self):
        self.activeview().addnode({"type":"talk"})
    
    @pyqtSlot()
    def newresponse (self):
        self.activeview().addnode({"type":"response"})
    
    @pyqtSlot()
    def newbank (self):
        self.activeview().addnode({"type":"bank"})
    
    @pyqtSlot()
    def newtalksub (self):
        self.activeview().addnode({"type":"talk"}, subnode=True)
    
    @pyqtSlot()
    def newresponsesub (self):
        self.activeview().addnode({"type":"response"}, subnode=True)
    
    @pyqtSlot()
    def copynode (self):
        view = self.activeview()
        nodeobj = view.selectednode.nodeobj
        nodedict = nodeobj.todict()
        nodedict["links"] = []
        nodedict["nodebank"] = -1
        if "subnodes" in nodedict:
            nodedict["subnodes"] = []
        
        if view.selectednode.issubnode():
            self.copiednode = (None, None, nodedict)
        else:
            self.copiednode = (nodeobj.ID, view, nodedict)
        
        self.actions["pasteclone"].setText("Paste &Clone (node %s)" % nodeobj.ID)
        self.actions["pastelink"].setText("Paste &Link (node %s)" % nodeobj.ID)
        self.actions["pastesubnode"].setText("&Paste Subnode (node %s)" % nodeobj.ID)
        view.filteractions()
    
    @pyqtSlot()
    def pasteclone (self):
        self.activeview().addnode(self.copiednode[2])
    
    @pyqtSlot()
    def pastelink (self):
        self.activeview().createlink(self.copiednode[0])
    
    @pyqtSlot()
    def pastesubnode (self):
        self.activeview().addnode(self.copiednode[2], subnode=True)
    
    @pyqtSlot()
    def unlinkinherit (self):
        self.unlink(inherit=True)
    
    @pyqtSlot()
    def unlink (self, inherit=False):
        view = self.activeview()
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
        self.activeview().unlink(inherit)
    
    @pyqtSlot()
    def moveup (self):
        self.activeview().moveup()
    
    @pyqtSlot()
    def movedown (self):
        self.activeview().movedown()
    
    @pyqtSlot()
    def parentswap (self):
        self.activeview().parentswap()
    
    @pyqtSlot()
    def collapse (self):
        self.activeview().collapse()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec_())
