#!/usr/bin/env python

import sys
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtOpenGL import *
import flint_parser as fp
import os
import weakref

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

class NodeItem(QGraphicsItem):
    def __init__(self, nodeobj, parent=None, view=None, ghost=False):
        super().__init__()
        self.nodeobj = nodeobj
        self.children = []
        self.referrers = []
        self.style = view.window().style
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
        if self.isghost():
            return "<-".join([self.nodeobj.ID, self.parent.id()])
        else:
            return self.nodeobj.ID
    
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
        return self.view.nodegraph[self.nodeobj.ID]
    
    def isactive (self):
        return self.view.activenode is self
    
    def isselected (self):
        return self.view.selectednode is self
    
    def iscollapsed (self):
        if self.parent is not None:
            ids = (self.realid(), self.parent.realid())
        else:
            ids = (self.realid(), None)
        return ids in self.view.collapsednodes
    
    def setY (self, y):
        self.edge.prepareGeometryChange()
        y += self.yoffset
        super().setY(y)    
    
    def y_up (self):
        return self.y() - self.boundingRect().height()//2
    
    def y_low (self):
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
        localranks[rank] = [self.y_up, self.y_low]
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
                ymin = min(ymin, child.y_up(), stree[0]) if ymin is not None else stree[0]
                ymax = max(ymax, child.y_low(), stree[1]) if ymax is not None else stree[1]
                maxdepth = max(maxdepth, stree[2])
        else:
            ymin = self.y_up()
            ymax = self.y_low()
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
        mainrect = self.nodelabel.mapRectToParent(self.nodelabel.boundingRect()).marginsAdded(QMarginsF(*[self.style.nodemargin]*4))
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
            window = self.view.window()
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
            window = self.view.window()
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
                subnode.yoffset = self.mapToScene(0,verticalpos + nodeheight/2+self.style.activemargin).y()-self.y_low()
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
            window = self.view.window()
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
    fgcolor = FlPalette.light
    bgcolor = FlPalette.dark
    pensize = 2
    
    def __init__(self, source, view):
        super().__init__()
        self.source = source
        source.setedge(self)
        self.view = weakref.proxy(view)
        self.style = view.window().style
    
    def boundingRect(self):
        xmin = self.source.x()
        xmax = xmin + self.style.rankwidth
        children = self.source.childlist()
        if children:
            ymin = children[0].y()-self.arrowsize/2
            ymax = children[-1].y()+self.arrowsize/2
        else:
            ymin = self.source.y()-self.arrowsize/2
            ymax = self.source.y()+self.arrowsize/2
        return QRectF(xmin, ymin, abs(xmax-xmin), abs(ymax-ymin))
    
    def paint(self, painter, style, widget, color=None, off=0, main=True):
        assert(isinstance(painter, QPainter))
        children = self.source.childlist()
        treeview = widget is self.view.viewport()
        if not children:
            return
        if main and treeview:
            self.paint(painter, style, widget, color=self.bgcolor, off=self.style.shadowoffset, main=False)
        arrow = self.arrowsize
        if color is None:
            color = self.fgcolor
        pen = QPen(color, self.pensize, cap = Qt.FlatCap, join=Qt.MiterJoin)
        if not treeview:
            pen.setWidth(0)
            pen.setCosmetic(True)
        brush = QBrush(color)
        painter.setPen(pen)
        painter.setBrush(brush)
        x0 = self.source.x() + self.source.boundingRect().right()
        y0 = self.source.y()
        vert_x = self.source.x() + self.style.rankwidth/2
        painter.drawLine(x0+off, y0+off, vert_x+off, y0+off)
        for target in children:
            tx = target.x() + target.boundingRect().left()
            ty = target.y()
            painter.setPen(pen)
            corr = self.pensize/2
            painter.drawLine(vert_x+off-corr, ty+off, tx+off-arrow, ty+off)
            arrowtip = [QPointF(tx+off, ty+off), QPointF(tx-arrow+off, ty-(arrow/2)+off), QPointF(tx-arrow+off, ty+(arrow/2)+off)]
            nopen = QPen(0)
            painter.setPen(nopen)
            painter.drawPolygon(*arrowtip)
        if len(children) > 1:
            vert_top = children[0].y()
            vert_bottom = children[-1].y()
            painter.setPen(pen)
            painter.drawLine(vert_x+off, vert_top+off, vert_x+off, vert_bottom+off)

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
        window = self.window()
        activeview = window.activeview()
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
            self.viewport().update()

class ParagraphEdit (QPlainTextEdit):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setTabChangesFocus(True)
    
    def keyPressEvent (self, event):
        key = event.key()
        mod = event.modifiers()
        if not (mod & Qt.ShiftModifier) and (key == Qt.Key_Enter or key == Qt.Key_Return):
            self.window().activeview().setFocus()
        else:
            super().keyPressEvent(event)

class NodeEditWidget (QWidget):
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
        view = self.window().activeview()
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
    
    def search (self):
        query = self.inputline.text().casefold()
        view = self.window().activeview()
        view.search(query)   

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
        
        self.style = self.window().style
        
        self.selectedChanged.connect(self.filteractions)
        
        self.nodecontainer = nodecontainer
        self.nodedocs = dict()
        self.updateview()
        self.setactivenode(self.treeroot())
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
            activeID = self.activenode.id()
        if self.selectednode is not None:
            selectedID = self.selectednode.id()
            selparent = self.selectednode.parent
            if selparent is not None:
                selparentID = selparent.id()
        self.activenode = self.selectednode = None
        
        self.constructed = False
        self.updatedocs()
        self.scene().clear()
        self.nodegraph = dict()
        self.viewframe = FrameItem(view=self)
        self.scene().addItem(self.viewframe)
        self.constructed = self.constructgraph()
        self.updatelayout()
        
        if activeID and activeID in self.nodegraph:
            self.setactivenode(self.nodegraph[activeID], signal=False)
        else:
            self.setactivenode(self.treeroot())
        
        if selectedID and selectedID in self.nodegraph:
            self.setselectednode(self.nodegraph[selectedID], signal=False)
        elif selparentID and selparentID in self.nodegraph:
            self.setselectednode(self.nodegraph[selparentID])
        else:
            self.setselectednode(self.activenode)
    
    def constructgraph (self):
        queue = []
        queue.append(("0", None))
        nodesdict = self.nodecontainer.nodes
        visited = {"0": False}
        
        while queue:
            curID, ref = queue.pop(0)
            isghost = visited[curID]
            if ref is not None:
                visited[curID] = visited[curID] or (curID, ref.realid()) not in self.collapsednodes
            else:
                visited[curID] = True
            curnodeobj = nodesdict[curID]
            nodeitem = self.newitem(curnodeobj, ref, isghost)
            if not (isghost or nodeitem.iscollapsed()):
                for nextID in curnodeobj.linkIDs:
                    queue.append((nextID, nodeitem))
                    visited[nextID] = nextID in visited and visited[nextID]
        return True
    
    def newitem (self, nodeobj, parent, isghost=False):
        if parent is None:
            refid = None
        else:
            refid = parent.id()
        nodeitem = self.__types[nodeobj.typename](nodeobj, parent=parent, view=self, ghost=isghost)
        edgeitem = EdgeItem(nodeitem, view=self)
        self.scene().addItem(edgeitem)
        self.scene().addItem(nodeitem)
        if isghost:
            graphid = "<-".join([nodeobj.ID, refid])
        elif nodeobj.ID in self.nodegraph:
            oldnode = self.nodegraph[nodeobj.ID]
            oldnode.setghost(True)
            self.nodegraph[oldnode.id()] = oldnode
            nodeitem.referrers = oldnode.referrers
            oldnode.referrers = []
            graphid = nodeobj.ID
        else:
            graphid = nodeobj.ID
        self.nodegraph[graphid] = nodeitem
        
        if refid is not None:
            self.nodegraph[nodeobj.ID].addreferrer(refid)
        
        return nodeitem
    
    def treeroot (self):
        return self.nodegraph["0"]
    
    def updatelayout (self):
        if not self.constructed:
            return
        root = self.treeroot()
        root.treeposition()
        self.updatescenerect(root)
        self.scene().update()
    
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
            self.scene().update()
    
    def setactivenode (self, nodeitem, signal=True):
        if nodeitem is not None:
            if self.activenode:
                self.activenode.setactive(False)
            self.activenode = nodeitem.realnode()
            self.activenode.setactive(True)
            if signal:
                self.activeChanged.emit(self.activenode.realid())
            self.scene().update()
    
    def createlink (self, toID):
        fromID = self.selectednode.realid()
        self.nodecontainer.newlink(fromID, toID)
        self.updateview()
    
    def addnode (self, nodedict, subnode=False):
        selected = self.selectednode.realnode()
        selectedid = selected.id()
        if subnode:
            nodedictmod = nodedict.copy()
            nodedictmod["nodebank"] = selectedid
            newobj = self.nodecontainer.newnode(nodedictmod, bankID=selectedid)
        else:
            newobj = self.nodecontainer.newnode(nodedict, refID=selectedid)
        newid = newobj.ID
        self.updateview()
        self.shownode(self.nodegraph[newid])
    
    def unlink (self, inherit=False):
        selID = self.selectednode.realid()
        refID = self.selectednode.parent.id()
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
        selID = self.selectednode.realid()
        if self.selectednode.parent is not None:
            refID = self.selectednode.parent.realid()
        else:
            refID = None
        ids = (selID, refID)
        if ids in self.collapsednodes:
            if collapse is None or not collapse:
                self.collapsednodes.remove(ids)
        else:
            if collapse is None or collapse:
                self.collapsednodes.append(ids)
        self.updateview()
    
    @pyqtSlot(str)
    def filteractions (self, nodeID=""):
        if nodeID == "":
            nodeID = self.selectednode.id()
        nodeitem = self.nodegraph[nodeID]
        genericactions = ["zoomin", "zoomout", "zoomorig", "gotoactive",
            "collapse", "openfile", "save", "saveas", "newtree"]
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
        windowactions = self.window().actions
        copiednode = self.window().copiednode
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
        self.scene().update()
    
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
        
        self.style = FlNodeStyle(QFont())
        self.initactions()
        self.initmenus()
        self.inittoolbars()
        
        self.view = TreeView(fp.loadjson("test3.json"), parent=self)
        
        tabs = QTabWidget(parent=self)
        tabs.addTab(self.view, "Graph")
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
        
        editwidget = NodeEditWidget(self)
        editwidget.setMinimumWidth(300)
        editwidget.loadnode(self.view.activenode.id())
        self.view.activeChanged.connect(editwidget.loadnode)
        
        rightpanel = QSplitter(Qt.Vertical, self)
        rightpanel.addWidget(mapview)
        rightpanel.addWidget(editwidget)        
        
        splitter = QSplitter(self)
        splitter.addWidget(tabs)
        splitter.addWidget(rightpanel)
        
        self.setCentralWidget(splitter)
    
    def activeview (self):
        return self.tabs.currentWidget()
    
    def initactions (self):
        self.actions["openfile"] = self.createaction("Open", self.openfile,
            [QKeySequence.Open], ["document-open"], "Open dialogue file")
        self.actions["save"] = self.createaction("Save", self.save,
            [QKeySequence.Save], ["document-save"], "Save dialogue file")
        self.actions["saveas"] = self.createaction("Save As", self.saveas,
            [QKeySequence.SaveAs], ["document-save-as"], "Save dialogue file as")
        self.actions["newtree"] = self.createaction("New", self.newtree,
            [QKeySequence.New], ["document-new"], "New dialogue tree")
        
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
            None, ["insert-object"], "Add new Talk node")
        self.actions["newresponse"] = self.createaction("New &Response Node", self.newresponse,
            None, ["insert-object"], "Add new Response node")
        self.actions["newbank"] = self.createaction("New &Bank Node", self.newbank,
            None, ["insert-object"], "Add new Bank node")
        self.actions["copynode"] = self.createaction("&Copy Node", self.copynode,
            None, ["edit-copy"], "Copy node")
        self.actions["pasteclone"] = self.createaction("Paste &Clone", self.pasteclone,
            None, ["edit-paste"], "Paste cloned node")
        self.actions["pastelink"] = self.createaction("Paste &Link", self.pastelink,
            None, ["insert-link"], "Paste link to node")
        self.actions["unlinkstree"] = self.createaction("Unlink &Subtree", self.unlink,
            None, ["edit-clear"], "Unlink subtree from parent")
        self.actions["unlinknode"] = self.createaction("Unlink &Node", self.unlinkinherit,
            None, ["edit-delete"], "Unlink node and let parent inherit its child nodes")
        self.actions["moveup"] = self.createaction("Move &Up", self.moveup,
            None, ["go-up"], "Move node up")
        self.actions["movedown"] = self.createaction("Move &Down", self.movedown,
            None, ["go-down"], "Move node down")
        self.actions["collapse"] = self.createaction("(Un)Colla&pse subtree", self.collapse,
            None, None, "(Un)Collapse subtree")
        self.actions["newtalksub"] = self.createaction("New &Talk Subnode", self.newtalksub,
            None, ["insert-object"], "Add new Talk subnode")
        self.actions["newresponsesub"] = self.createaction("New &Response Subnode", self.newresponsesub,
            None, ["insert-object"], "Add new Response subnode")
        self.actions["pastesubnode"] = self.createaction("&Paste Subnode", self.pastesubnode,
            None, ["edit-paste"], "Paste cloned node as subnode")
        self.actions["parentswap"] = self.createaction("S&wap with Parent", self.parentswap,
            None, ["go-left"], "Swap places with parent node")
    
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
    
    @pyqtSlot()
    def openfile (self):
        filename = QFileDialog.getOpenFileName(self, "Open file", os.getcwd(), "Dialog files (*.json)")[0]
        if filename == "":
            return
        nodecontainer = fp.loadjson(filename)
        treeview = TreeView(nodecontainer, parent=self)
        tabindex = self.tabs.addTab(treeview, nodecontainer.name)
        self.tabs.setCurrentIndex(tabindex)
    
    @pyqtSlot()
    def newtree (self):
        nodecontainer = fp.newcontainer()
        treeview = TreeView(nodecontainer, parent=self)
        tabindex = self.tabs.addTab(treeview, nodecontainer.name)
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
        if len(selected.referrers) == 1:
            if inherit or len(selected.childlist()) == 0:
                text = "This will remove the only instance of node %s.\n\nContinue?" % selected.id()
            else:
                text = "This will remove the only instance of node %s and all unique nodes in its subtree.\n\nContinue?" % selected.id()
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
