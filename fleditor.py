#!/usr/bin/env python

import sys
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtOpenGL import *
import flint_parser as fp

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
    def __init__(self, parent=0, cond=None, **args):
        super().__init__(parent, **args)
        self.cond = cond
    
    def paint(self, painter, style, widget):
        if self.cond(self, widget):
            super().paint(painter, style, widget)

class QGraphicsSimpleTextItemCond (QGraphicsSimpleTextItem):
    def __init__(self, parent=0, cond=None, **args):
        super().__init__(parent, **args)
        self.cond = cond
    
    def paint(self, painter, style, widget):
        if self.cond(self, widget):
            super().paint(painter, style, widget)

class QGraphicsTextItemCond (QGraphicsTextItem):
    def __init__(self, parent=0, cond=None, **args):
        super().__init__(parent, **args)
        self.cond = cond
    
    def paint(self, painter, style, widget):
        if self.cond(self, widget):
            super().paint(painter, style, widget)

class NodeItem(QGraphicsItem):
    def __init__(self, nodeobj, parent=None, view=None, ghost=False, **args):
        super().__init__(**args)
        self.nodeobj = nodeobj
        self.children = []
        self.referrers = []
        self.style = view.window().style
        if parent is None:
            self.parent = None
            self.nodebank = view
        elif nodeobj.nodebank == -1:
            self.nodebank = view
            self.parent = parent
            self.parent.addchild(self)
            self.setX(parent.x()+self.style.rankwidth)
        else:
            self.nodebank = parent
            self.parent = parent
        print("ID: ", nodeobj.ID, ", bank: ", self.nodebank)
        self.setCursor(Qt.ArrowCursor)
        self.view = view
        self.treeviewport = view.viewport()
        self.textheight = 0
        self.collapselayout = False
        self.edge = None
        self.ghost = ghost
        self.yoffset = 0
        self.graphicsetup()
    
    def graphicsetup (self):
        if int(self.nodeobj.ID) % 2 == 0:
            self.maincolor = FlPalette.hl2var
            self.altcolor = FlPalette.hl2
        else:
            self.maincolor = FlPalette.hl1var
            self.altcolor = FlPalette.hl1
        lightbrush = QBrush(FlPalette.light)
        mainbrush = QBrush(self.maincolor)
        altbrush = QBrush(self.altcolor)
        nopen = QPen(0)
         
        self.graphgroup = QGraphicsItemGroup(self)
        
        self.shadowbox = QGraphicsRectItemCond(self, 
            lambda s,w: True)
        self.shadowbox.setBrush(FlPalette.dark)
        self.shadowbox.setPen(nopen)
        self.shadowbox.setPos(*[self.style.shadowoffset]*2)
        self.graphgroup.addToGroup(self.shadowbox)
        
        self.activebox = QGraphicsRectItemCond(self, 
            lambda s,w: True)
        self.activebox.setBrush(mainbrush)
        self.activebox.setPen(nopen)
        self.activebox.hide()
        self.graphgroup.addToGroup(self.activebox)
        
        self.selectbox = QGraphicsRectItemCond(self,
            lambda s,w: True)
        self.selectbox.setBrush(lightbrush)
        self.selectbox.setPen(nopen)
        self.selectbox.hide()
        self.graphgroup.addToGroup(self.selectbox)
        
        self.mainbox = QGraphicsRectItemCond(self, 
            lambda s,w: True)
        self.mainbox.setBrush(mainbrush)
        self.mainbox.setPen(nopen)
        self.graphgroup.addToGroup(self.mainbox)
        
        self.textbox = QGraphicsRectItemCond(self, 
            lambda s,w: w is self.treeviewport and not self.iscollapsed())
        self.textbox.setBrush(lightbrush)
        self.textbox.setPen(nopen)
        self.graphgroup.addToGroup(self.textbox)
        
        self.nodelabel = QGraphicsSimpleTextItemCond(self, 
            lambda s,w: w is self.treeviewport)
        self.nodelabel.setBrush(lightbrush)
        self.nodelabel.setFont(self.style.boldfont)
        self.nodelabel.setText("Node %s" % self.nodeobj.ID)
        self.nodelabel.setPos(self.style.itemmargin, self.style.itemmargin)
        self.graphgroup.addToGroup(self.nodelabel)
        
        self.nodespeaker = QGraphicsSimpleTextItemCond(self, 
            lambda s,w: w is self.treeviewport and not self.iscollapsed())
        self.nodespeaker.setBrush(lightbrush)
        self.nodespeaker.setText(self.nodeobj.speaker)
        self.nodespeaker.setPos(self.style.itemmargin, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin*2)
        self.graphgroup.addToGroup(self.nodespeaker)
        
        self.nodetext = QGraphicsTextItemCond(self, 
            lambda s,w: w is self.treeviewport and not self.iscollapsed())
        self.nodetext.setTextWidth(self.style.nodetextwidth)
        self.nodetext.setPos(0, self.nodespeaker.y()+self.nodespeaker.boundingRect().height()+self.style.itemmargin)
        self.graphgroup.addToGroup(self.nodetext)
        
        self.view.nodedocs[self.nodeobj.ID]["text"].contentsChanged.connect(self.updatelayout)
        self.updatelayout()
        
        if self.isghost():
            self.graphgroup.setOpacity(0.7)
            self.shadowbox.hide()
    
    @pyqtSlot()
    def updatelayout (self, force=False):
        print("UPDATE ", self.id())
        if self.iscollapsed():
            if self.collapselayout and not force:
                return
            else:
                textrect = QRectF()
                self.collapselayout = True
        else:
            ndtxt = self.nodetext
            ndtxt.setPlainText(self.view.nodedocs[self.nodeobj.ID]["text"].toPlainText())
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
    
    def id (self):
        if self.isghost():
            return "<-".join([self.nodeobj.ID, self.parent.id()])
        else:
            return self.nodeobj.ID
    
    def nodeitems (self):
        return self.view.nodegraph
    
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
    
    def isghost (self):
        return self.ghost
    
    def realnode (self):
        return self.view.nodegraph[self.nodeobj.ID]
    
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
            return parent.childlist()
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
                ymin = min(ymin, stree[0]) if ymin is not None else stree[0]
                ymax = max(ymax, stree[1]) if ymax is not None else stree[1]
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
    
    def mouseDoubleClickEvent (self, event):
        super().mouseDoubleClickEvent(event)
        event.accept()
        if event.button() == Qt.LeftButton:
            self.view.setactivenode(self)
    
    def mousePressEvent(self, event):
        print("node click", self.id())
        super().mousePressEvent(event)
        print("node click done")
        """event.accept()
        if event.button() & (Qt.LeftButton | Qt.RightButton) :
            self.view.setselectednode(self)"""
    
    def contextMenuEvent (self, event):
        menu = QMenu()
        if self.isselected():
            window = self.view.window()
            menu.addAction(window.actions["collapse"])
            menu.addAction(window.actions["copynode"])
            pastemenu = QMenu("Paste...")
            pastemenu.addAction(window.actions["pasteclone"])
            pastemenu.addAction(window.actions["pastelink"])
            menu.addMenu(pastemenu)
            menu.addAction(window.actions["addnode"])
            menu.addAction(window.actions["moveup"])
            menu.addAction(window.actions["movedown"])
            menu.addAction(window.actions["unlinknode"])
            menu.addAction(window.actions["unlinkstree"])
        if not menu.isEmpty():
            menu.exec_(event.screenPos())
    
    def __repr__(self):
        return "<NodeItem %s>" % self.id()

class TalkNodeItem(NodeItem):
    def mousePressEvent(self, event):
        print("talk click", self.id())
        super().mousePressEvent(event)
        if event.button() & (Qt.LeftButton | Qt.RightButton) :
            self.view.setselectednode(self)
            event.accept()
        print("talk click done")

class ResponseNodeItem(NodeItem):
    pass

class BankNodeItem (NodeItem):
    maincolor = FlPalette.bank
    altcolor = FlPalette.bankvar
    
    def __init__ (self, nodeobj, parent=None, view=None, ghost=False, **args):
        super().__init__(nodeobj, parent, view, ghost, **args)
        self.subnodes = []
        self.setZValue(-1)
        #self.setFiltersChildEvents(False)
        #self.graphgroup.setFiltersChildEvents(False)
        #self.setAcceptedMouseButtons(Qt.NoButton)
        for subnodeID in nodeobj.subnodes:
            print("adding ", subnodeID, " to subnodes")
            subnode = view.newitem(view.nodecontainer.nodes[subnodeID], self, ghost)
            self.subnodes.append(subnode)
            #subnode.setParentItem(self)
            #self.graphgroup.addToGroup(subnode)
            #subnode.setX(subnode.boundingRect().width()//2)
            subnode.setX(self.x())
            subnode.updatelayout(force=True)
            #subnode.setY(self.boundingRect().height())
    
    def graphicsetup (self):
        lightbrush = QBrush(FlPalette.light)
        darkbrush = QBrush(FlPalette.bg)
        mainbrush = QBrush(self.maincolor)
        altbrush = QBrush(self.altcolor)
        nopen = QPen(0)
        
        self.graphgroup = QGraphicsItemGroup(self)
        
        self.shadowbox = QGraphicsRectItemCond(self, 
            lambda s,w: w is self.treeviewport)
        self.shadowbox.setBrush(FlPalette.dark)
        self.shadowbox.setPen(nopen)
        self.shadowbox.setPos(*[self.style.shadowoffset]*2)
        self.graphgroup.addToGroup(self.shadowbox)
        
        self.activebox = QGraphicsRectItemCond(self, 
            lambda s,w: True)
        self.activebox.setBrush(mainbrush)
        self.activebox.setPen(nopen)
        self.activebox.hide()
        self.graphgroup.addToGroup(self.activebox)
        
        self.selectbox = QGraphicsRectItemCond(self,
            lambda s,w: True)
        self.selectbox.setBrush(lightbrush)
        self.selectbox.setPen(nopen)
        self.selectbox.hide()
        self.graphgroup.addToGroup(self.selectbox)
        
        self.mainbox = QGraphicsRectItemCond(self, 
            lambda s,w: True)
        self.mainbox.setBrush(mainbrush)
        self.mainbox.setPen(nopen)
        self.graphgroup.addToGroup(self.mainbox)
        
        self.nodelabel = QGraphicsSimpleTextItemCond(self, 
            lambda s,w: w is self.treeviewport)
        self.nodelabel.setBrush(lightbrush)
        self.nodelabel.setFont(self.style.boldfont)
        self.nodelabel.setText("Node %s" % self.nodeobj.ID)
        self.nodelabel.setPos(self.style.itemmargin, self.style.itemmargin)
        self.graphgroup.addToGroup(self.nodelabel)
        
        self.centerbox = QGraphicsRectItemCond(self, 
            lambda s,w: w is self.treeviewport and not self.iscollapsed())
        self.centerbox.setRect(QRectF())
        self.centerbox.setBrush(darkbrush)
        self.centerbox.setPen(nopen)
        self.centerbox.setPos(0, self.nodelabel.y()+self.nodelabel.boundingRect().height()+self.style.itemmargin*2)
        self.graphgroup.addToGroup(self.centerbox)
                
        if self.isghost():
            self.graphgroup.setOpacity(0.7)
            self.shadowbox.hide()
    
    def updatelayout (self):
        print("bank layout")
        if self.iscollapsed():
            print("...is collapsed")
            """if self.collapselayout:
                return
            else:"""
            for subnode in self.subnodes:
                subnode.hide()
            centerrect = QRectF()
                #self.collapselayout = True
        else:
            verticalpos = self.centerbox.y()
            print("before: ", verticalpos)
            maxwidth = 0
            for subnode in self.subnodes:
                print(subnode)
                noderect = subnode.boundingRect()
                nodeheight = noderect.height()
                nodewidth = noderect.width()
                subnode.show()
                #subnode.setX(nodewidth//2)
                subnode.yoffset = self.mapToScene(0,verticalpos + nodeheight/2+self.style.activemargin).y()-self.y_low()
                print("offset", subnode.yoffset)
                verticalpos += nodeheight
                maxwidth = max(maxwidth, nodewidth)
            print("after: ", verticalpos)
            centerrect = self.centerbox.rect()
            centerrect.setWidth(maxwidth)
            centerrect.setHeight(verticalpos-self.centerbox.y())
            """if centerrect == self.centerbox.rect():
                return"""
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
            print("diff", newypos - oldypos)
            subnode.yoffset += newypos - oldypos
        self.prepareGeometryChange()
        self.rect = self.graphgroup.mapRectToParent(self.activebox.boundingRect())
        self.nodebank.updatelayout()
    
    def setY (self, y):
        super().setY(y)
        for subnode in self.subnodes:
            subnode.setY(y)
    
    def boundingRect (self):
        return self.rect
    
    def mousePressEvent(self, event):
        print ("bank click", self.id())
        super().mousePressEvent(event)
        if event.button() & (Qt.LeftButton | Qt.RightButton) :
            self.view.setselectednode(self)
            event.ignore()
        print("bank click done")


class EdgeItem(QGraphicsItem):
    arrowsize = 10
    fgcolor = FlPalette.light
    bgcolor = FlPalette.dark
    pensize = 2
    
    def __init__(self, source, view, **args):
        super().__init__(**args)
        self.source = source
        source.setedge(self)
        self.treeviewport = view.viewport()
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
        treeview = widget is self.treeviewport
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
            painter.drawLine(vert_x+off, ty+off, tx+off-arrow, ty+off)
            if treeview:
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
        self.treeview = view
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
    __types = {'talk': TalkNodeItem, 'response': ResponseNodeItem, 'bank': BankNodeItem}
    
    def __init__ (self, parent=None):
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
        
        scene =  QGraphicsScene()
        scene.setBackgroundBrush(FlPalette.bg)
        self.setScene(scene)
        
        self.style = self.window().style
        
        self.nodecontainer = fp.loadjson("test3.json")
        self.nodedocs = dict()
        self.updateview()
        self.setactivenode(self.treeroot())
        self.setselectednode(self.treeroot())
    
    def updatedocs (self):
        newnodedocs = dict()
        for nodeID, nodeobj in self.nodecontainer.nodes.items():
            if nodeID in self.nodedocs:
                newnodedocs[nodeID] = self.nodedocs[nodeID]
            else:
                textdoc = QTextDocument()
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
    
    def constructgraph (self, nodeID="0"):
        queue = []
        queue.append((nodeID, None))
        nodesdict = self.nodecontainer.nodes
        visited = {nodeID: False}
        
        while queue:
            curID, ref = queue.pop(0)
            isghost = visited[curID]
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
            self.nodegraph["<-".join([nodeobj.ID, refid])] = nodeitem
        else:
            self.nodegraph[nodeobj.ID] = nodeitem
        
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
                self.selectedChanged.emit(self.selectednode.nodeobj.ID)
            self.scene().update()
    
    def setactivenode (self, nodeitem, signal=True):
        if nodeitem is not None:
            if self.activenode:
                self.activenode.setactive(False)
            self.activenode = nodeitem.realnode()
            self.activenode.setactive(True)
            if signal:
                self.activeChanged.emit(self.activenode.nodeobj.ID)
            self.scene().update()
    
    def createlink (self, toID):
        fromID = self.selectednode.nodeobj.ID
        self.nodecontainer.newlink(fromID, toID)
        self.updateview()
    
    def addnode (self, nodedict):
        selected = self.selectednode.realnode()
        selectedid = selected.id()        
        newobj = self.nodecontainer.newnode(nodedict, refID=selectedid)
        newid = newobj.ID
        self.updateview()
        self.shownode(self.nodegraph[newid])
    
    def unlink (self, inherit=False):
        selID = self.selectednode.nodeobj.ID
        refID = self.selectednode.parent.id()
        self.nodecontainer.removelink(refID, selID, forceinherit=inherit)
        self.updateview()
    
    def moveup (self):
        selnode = self.selectednode
        sibling = selnode.siblingabove()
        parent = selnode.parent
        if sibling is None or parent is None:
            return
        selID = selnode.nodeobj.ID
        sibID = sibling.nodeobj.ID
        parID = parent.nodeobj.ID
        self.nodecontainer.siblingswap(parID, selID, sibID)
        self.updateview()
    
    def movedown (self):
        selnode = self.selectednode
        sibling = selnode.siblingbelow()
        parent = selnode.parent
        if sibling is None or parent is None:
            return
        selID = selnode.nodeobj.ID
        sibID = sibling.nodeobj.ID
        parID = parent.nodeobj.ID
        self.nodecontainer.siblingswap(parID, selID, sibID)
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
    defaultNodeDict = {"type":"talk","text":"","speaker":"def","links":[]}
    copiedNodeDict = None
    
    def __init__ (self):
        super().__init__()
        
        self.style = FlNodeStyle(QFont())
        
        self.view = TreeView(parent=self)
        
        tabs = QTabWidget(parent=self)
        tabs.addTab(self.view, "Graph")
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
        
        self.actions = dict()
        
        viewtoolbar = QToolBar("View control")
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
        
        viewtoolbar.addAction(self.actions["zoomorig"])
        viewtoolbar.addAction(self.actions["zoomin"])
        viewtoolbar.addAction(self.actions["zoomout"])
        viewtoolbar.addAction(self.actions["gotoactive"])
        self.addToolBar(viewtoolbar)
        
        edittoolbar = QToolBar("Tree editing")
        self.actions["addnode"] = self.createaction("&Add Node", self.addnode,
            None, ["insert-object"], "Add new node")
        self.actions["copynode"] = self.createaction("&Copy Node", self.copynode,
            None, ["edit-copy"], "Copy node")
        self.actions["pasteclone"] = self.createaction("Paste as &Clone", self.pasteclone,
            None, ["edit-paste"], "Paste cloned node")
        self.actions["pastelink"] = self.createaction("Paste as &Link", self.pastelink,
            None, ["insert-link"], "Paste link to node")
        self.actions["pasteclone"].setEnabled(False)
        self.actions["pastelink"].setEnabled(False)
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
        
        edittoolbar.addAction(self.actions["addnode"])
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
    
    def activeview (self):
        return self.tabs.currentWidget()
    
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
    def addnode (self):
        self.activeview().addnode(self.defaultNodeDict)
    
    @pyqtSlot()
    def copynode (self):
        nodeobj = self.activeview().selectednode.nodeobj
        nodedict = nodeobj.todict()
        nodedict["links"] = []
        self.copiedNodeDict = (nodeobj.ID, nodedict)
        self.actions["pasteclone"].setEnabled(True)
        self.actions["pastelink"].setEnabled(True)
    
    @pyqtSlot()
    def pasteclone (self):
        self.activeview().addnode(self.copiedNodeDict[1])
    
    @pyqtSlot()
    def pastelink (self):
        self.activeview().createlink(self.copiedNodeDict[0])
        #FIXME: won't work with multiple TreeViews
    
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
            if inherit:
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
    def collapse (self):
        self.activeview().collapse()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec_())
