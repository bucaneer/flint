#!/usr/bin/env python

import sys
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtOpenGL import *
import flint_parser as fp

"""NODETEXTWIDTH = 300
NODEHEIGHT = 140

MINRANKGAP = 50
MINROWGAP = 30
RANKGAP = max(int(NODETEXTWIDTH * 1.1), NODETEXTWIDTH + MINRANKGAP)
ROWGAP = max(int(NODEHEIGHT * 1.1), NODEHEIGHT + MINROWGAP)"""

nextID = 100

class FlPalette (object):
    """Palette of custom colors for quick reference."""
    dark    = QColor( 38,  39,  41)
    light   = QColor(250, 250, 250)
    hl1     = QColor(200,  60,  19) # QColor(224,  70,  19)
    hl1var  = QColor(224, 111,  19)
    hl2     = QColor( 39, 118, 153)
    hl2var  = QColor(108, 158, 171)
    bg      = QColor( 90,  94,  98)

class FlNodeStyle (object):    
    def __init__ (self, font):
        basefont = font
        boldfont = QFont(basefont)
        boldfont.setBold(True)
        self.basefont = basefont
        self.boldfont = boldfont
        
        basemetrics = QFontMetrics(basefont)
        boldmetrics = QFontMetrics(boldfont)
        self.basemetrics = basemetrics
        self.boldmetrics = boldmetrics
        
        baseem = basemetrics.height()
        baseen = baseem // 2
        boldem = boldmetrics.height()
        bolden = boldem // 2
        """self.baseem = baseem
        self.baseen = baseen
        self.boldem = boldem
        self.bolden = bolden"""
        
        baselead = basemetrics.leading()
        baselspace = basemetrics.lineSpacing()
        boldlead = boldmetrics.leading()
        boldlspace = boldmetrics.lineSpacing()
        
        nodemargin = baseen*3//5
        itemmargin = baseen//2
        activemargin = baseen*3//4
        selectmargin = activemargin//2
        self.nodemargin = nodemargin
        self.itemmargin = itemmargin
        self.activemargin = activemargin
        self.selectmargin = selectmargin
        
        minnodewidth = min(boldmetrics.width("Node 0000")*2, boldem*6)+2*(activemargin+nodemargin+itemmargin)
        prefnodewidth = basemetrics.averageCharWidth()*40 + 2*(activemargin+nodemargin+itemmargin)
        nodewidth = max(minnodewidth, prefnodewidth)
        self.nodewidth = nodewidth
        
        minnodeheight = boldlspace+1*baselspace+2*(activemargin+nodemargin+3*itemmargin)
        prefnodeheight = boldlspace+1*baselspace+2*(activemargin+nodemargin+3*itemmargin)
        nodeheight = max(minnodeheight, prefnodeheight)
        self.nodeheight = nodeheight
        
        minrankgap = 5*activemargin + nodewidth
        rankgap = max(minrankgap, round(nodewidth*1.1))
        self.rankgap = rankgap
        
        minrowgap = 3*activemargin #+ nodeheight
        rowgap = max(minrowgap, round(nodeheight*0.1))
        self.rowgap = rowgap

class FlGlobals (object):
    defaultNodeDict = {"type":"talk","text":"","speaker":"def","links":[]}
    copiedNodeDict = None
    actions = dict()
    ranks = dict()
    
    def newnode (paste=False):
        if paste:
            return FlGlobals.copiedNodeDict
        else:
            return FlGlobals.defaultNodeDict
    
    def copynode (nodeitem):
        nodedict = nodeitem.nodeobj.todict()
        nodedict["links"] = []
        FlGlobals.copiedNodeDict = nodedict
        FlGlobals.actions["pastenode"].setEnabled(True)

class NodeItem(QGraphicsItem):
    def __init__(self, nodeobj, parent=None, treeviewport=None, **args):
        super().__init__(**args)
        self.nodeobj = nodeobj
        self.childlist = []
        if parent is None:
            self.parent = None
            self.ref = None
        else:
            self.ref = parent.id()
            self.parent = parent
            self.parent.addchild(self)
        #self.textdocument = QTextDocument()
        #self.textdocument.setDocumentLayout(QPlainTextDocumentLayout(self.textdocument))
        #self.textdocument.setPlainText(self.nodeobj.text)
        self.setCursor(Qt.ArrowCursor)
        self.treeviewport = treeviewport
        self.textheight = self.gettextheight()
    
    def id (self):
        if self.isghost():
            return "<-".join([self.nodeobj.ID, self.ref])
        else:
            return self.nodeobj.ID
    
    def nodeitems (self):
        return self.getview().nodegraph
    
    def addchild (self, nodeitem):
        self.childlist.append(nodeitem)
        
    def isghost (self):
        return self.ref != self.nodeobj.realref
    
    def realnode (self):
        if self.isghost():
            return self.getview().nodegraph[self.nodeobj.ID]
        else:
            return self
    
    def isactive (self):
        return self.getview().activenode is self
    
    def isselected (self):
        return self.getview().selectednode is self
    
    def y_up (self):
        return self.y() - self.boundingRect().height()//2
    
    def y_low (self):
        return self.y() + self.boundingRect().height()//2
    
    def gettextheight (self):
        width = FlGlobals.style.nodewidth
        margins = sum([FlGlobals.style.__dict__[x] for x in ["nodemargin", "activemargin", "itemmargin"]])
        return FlGlobals.style.basemetrics.boundingRect(QRect(0,0,width-2*margins,0),Qt.AlignLeft | Qt.TextWordWrap,self.nodeobj.text).height()
       
    def treeposition (self):
        """Recursively set node position in a basic tree.
        
        Postion of all ancestor and previous sibling nodes has to be known for
        proper positioning."""
        
        parent = self.parent #node()
        if parent:
            x = parent.x() + FlGlobals.style.rankgap #RANKGAP
            sib = self.siblingabove()
            if sib:
                y = sib.subtreesize(-1)[1] + (self.boundingRect().height()/2) + FlGlobals.style.rowgap #ROWGAP
            else:
                y = parent.y() #+ (self.gettextheight()-parent.gettextheight())/2
        else:
            x = 0
            y = 0 
        if x != self.x() or y != self.y():
            self.setPos(QPoint(x, y))
            self.posinit = True
            #self.getview().updatedimensions(x, y)      
        for child in self.childlist: #ren():
            child.treeposition()
    
    def subtreerootdrop(self, recursive=False):
        """Reposition subtree root node to midpoint of subtree height."""
        
        children = self.childlist #ren()
        if children:
            if recursive:
                for child in children:
                    child.subtreerootdrop(recursive)
            top, bottom, depth = self.subtreesize(1)
            new_y = (top+bottom)//2
            if new_y != self.y():
                self.setY(new_y)
    
    def bulkshift (self, diff):
        self.setY(self.y() + diff)
        for child in self.childlist:
            child.bulkshift(diff)
    
    def graphcompact (self, ranks=None):
        if ranks is None:
            ranks = dict()
        localranks = dict()
        for child in self.childlist:
            localranks = child.graphcompact(localranks)
        rank = self.x() // FlGlobals.style.rankgap #RANKGAP
        self.subtreerootdrop()
        localranks[rank] = [self.y_up, self.y_low]
        streeshift = None
        for r in localranks:
            if r in ranks:
                rankshift = ranks[r][1]() + FlGlobals.style.rowgap - localranks[r][0]()
                if streeshift is None or rankshift > streeshift:
                    streeshift = rankshift
                ranks[r][1] = localranks[r][1]
            else:
                ranks[r] = localranks[r]
        if streeshift:
            self.bulkshift(streeshift)
        return ranks
    
    def siblings (self):
        parent = self.parent #node()
        if parent:
            return parent.childlist #ren()
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

        children = self.childlist
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
        width = FlGlobals.style.nodewidth
        baseheight = FlGlobals.style.nodeheight
        #margins = FlGlobals.style.nodemargin + FlGlobals.style.activemargin;
        #textheight = FlGlobals.style.basemetrics.boundingRect(QRect(0,0,width-2*margins,0),Qt.AlignLeft | Qt.TextWordWrap,self.nodeobj.text).height();
        #self.textheight = self.gettextheight();
        height = baseheight + self.gettextheight();
        return QRectF(-width//2, -height//2, width, height)
    
    def drawlabel (self, painter, rect, string, flags=Qt.AlignLeft):
        textrect = painter.boundingRect(rect, flags | Qt.TextDontClip, string)
        painter.drawText(textrect, flags, string)
        return textrect.bottom()
    
    def paint(self, painter, style, widget):
        assert isinstance(painter, QPainter)
        
        boxmargins = QMarginsF(*[FlGlobals.style.nodemargin]*4)
        itemmargins = QMarginsF(*[FlGlobals.style.itemmargin]*4)
        activeborder = FlGlobals.style.activemargin
        fullbound = self.boundingRect()
        smallbound = fullbound.marginsRemoved(QMarginsF(*[activeborder]*4))
        
        ghost = self.isghost()
        active = self.isactive()
        selected = self.isselected()
        mapview = widget is not self.treeviewport
        
        if ghost:
            painter.setOpacity(0.7)
        
        if int(self.nodeobj.ID) % 2 == 0:
            color1 = FlPalette.hl2var
            color2 = FlPalette.hl2
        else:
            color1 = FlPalette.hl1var
            color2 = FlPalette.hl1
                
        lightbrush = QBrush(FlPalette.light)
        darkbrush = QBrush(FlPalette.dark)
        
        if active:
            maincolor = color2
        else: 
            maincolor = color1
        
        mainbrush = QBrush(maincolor)
        painter.setBrush(mainbrush)
        
        if mapview:
            pen = QPen(maincolor, 0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(mainbrush)
            painter.drawRect(fullbound)
            return
        
        metricsbold = FlGlobals.style.boldmetrics
        metricsbase = FlGlobals.style.basemetrics
        boldfont = FlGlobals.style.boldfont
        basefont = FlGlobals.style.basefont
        
        lineleading = metricsbold.leading()
        linespace = metricsbold.lineSpacing()
        
        painter.setPen(QPen(0))
                
        if not ghost:                
            painter.fillRect(smallbound.translated(2, 2), darkbrush)
        
        if active:
            painter.fillRect(fullbound, lightbrush)
        elif selected:
            painter.fillRect(fullbound.marginsRemoved(QMarginsF(*[activeborder//2]*4)), lightbrush)        
        
        painter.drawRect(smallbound)
        
        bound = smallbound.marginsRemoved(boxmargins)
        
        painter.setPen(QPen(FlPalette.light))
        painter.setFont(boldfont)
        
        if self.isghost():
            title = "Ghost %s" % self.nodeobj.ID
        else:
            title = "Node %s" % self.nodeobj.ID
        cur_y = self.drawlabel(painter, bound.marginsRemoved(itemmargins), title)
        
        bound.setTop(cur_y)
        painter.setFont(basefont)
        cur_y = self.drawlabel(painter, bound.marginsRemoved(itemmargins), self.nodeobj.speaker)
        
        bound.setTop(cur_y+lineleading)
             
        textrect = bound.marginsRemoved(itemmargins)
        #text = metricsbase.elidedText(self.nodeobj.text, Qt.ElideRight, (textrect.height() // metricsbase.lineSpacing())*textrect.width())
        text = self.nodeobj.text
        mainrect = painter.boundingRect(bound.marginsRemoved(itemmargins), Qt.AlignLeft | Qt.TextWordWrap, text)
        
        #painter.setBrush(lightbrush)
        #painter.setPen(QPen(0))
        if self.nodeobj in self.getview().hits:
            painter.fillRect(bound, QBrush(QColor(255, 255, 100)))
        else:
            painter.fillRect(bound, lightbrush)
        
        painter.setPen(QPen(FlPalette.dark))
        
        painter.drawText(textrect, Qt.AlignLeft | Qt.TextWordWrap, text)
        
    def getview (self):
        return self.scene().views()[0]
        
    def mouseDoubleClickEvent (self, event):
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.LeftButton:
            self.getview().setactivenode(self)
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() & (Qt.LeftButton | Qt.RightButton) :
            self.getview().setselectednode(self)
    
    def contextMenuEvent (self, event):
        menu = QMenu()
        if self.isselected():
            menu.addAction(FlGlobals.actions["copynode"])
            menu.addAction(FlGlobals.actions["pastenode"])
            menu.addAction(FlGlobals.actions["addnode"])
            menu.addAction(FlGlobals.actions["moveup"])
            menu.addAction(FlGlobals.actions["movedown"])
            menu.addAction(FlGlobals.actions["createlink"])
            menu.addAction(FlGlobals.actions["unlinknode"])
            menu.addAction(FlGlobals.actions["unlinkstree"])
        if not menu.isEmpty():
            menu.exec_(event.screenPos())
    
    def __repr__(self):
        return "<NodeItem %s>" % self.id()


class EdgeItem(QGraphicsItem):
    arrowsize = 10
    fgcolor = FlPalette.light
    bgcolor = FlPalette.dark
    shadowoffset = 2
    pensize = 2
    
    def __init__(self, source, treeviewport, **args):
        super().__init__(**args)
        self.source = source
        self.treeviewport = treeviewport
    
    def boundingRect(self):
        xmin = self.source.x()
        xmax = xmin + FlGlobals.style.rankgap #RANKGAP
        children = self.source.childlist
        if children:
            ymin = children[0].y()-self.arrowsize/2
            ymax = children[-1].y()+self.arrowsize/2
        else:
            ymin = self.source.y()-self.arrowsize/2
            ymax = self.source.y()+self.arrowsize/2
        return QRectF(xmin, ymin, abs(xmax-xmin), abs(ymax-ymin))
    
    def paint(self, painter, style, widget, color=None, off=0, main=True):
        assert(isinstance(painter, QPainter))
        children = self.source.childlist
        treeview = widget is self.treeviewport
        if not children:
            return
        if main and treeview:
            self.paint(painter, style, widget, color=self.bgcolor, off=self.shadowoffset, main=False)
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
        vert_x = self.source.x() + FlGlobals.style.rankgap/2 #RANKGAP/2 #(RANKGAP-arrow)/2
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
    def __init__ (self, treeview):
        super().__init__()
        self.treeview = treeview
        self.setZValue(1)
    
    def boundingRect (self):
        viewport = self.treeview.viewport()
        viewportrect = QRect(0, 0, viewport.width(), viewport.height())
        visiblerect = self.treeview.mapToScene(viewportrect).boundingRect()
        return visiblerect #.intersected(self.treeview.sceneRect())
    
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
        #self.setViewportUpdateMode(QGraphicsView.NoViewportUpdate)
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
        window = FlGlobals.window
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
            FlGlobals.window.activeview().setFocus()
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
        view = FlGlobals.window.activeview()
        self.nodeobj = view.nodecontainer.nodes[nodeID]
        nodetextdoc = view.nodedocs[nodeID]["text"]
        #self.nodeitem = FlGlobals.window.activeview().nodegraph[nodeID]
        self.speaker.setText(self.nodeobj.speaker)
        #self.nodetext.setPlainText(self.nodeobj.text)
        self.nodetext.setDocument(nodetextdoc)
        self.nodetext.setFocus()
        self.nodetext.moveCursor(QTextCursor.End)
    
    @pyqtSlot()
    def setnodespeaker (self):
        self.nodeobj.speaker = self.speaker.text()
        FlGlobals.window.activeview().scene().update()
    
    @pyqtSlot()
    def setnodetext (self):
        self.nodeobj.text = self.nodetext.toPlainText()
        FlGlobals.window.activeview().layoutgraph()

class SearchWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self.inputline = QLineEdit(self)
        self.inputline.editingFinished.connect(self.search)
        self.inputline.setPlaceholderText("Search")
        #self.inputline.setMaximumWidth(200)
        searchbutton = QPushButton(self)
        searchbutton.setIcon(QIcon.fromTheme("edit-find"))
        searchbutton.setToolTip("Search")
        searchbutton.clicked.connect(self.search)
        #searchbutton.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setMaximumWidth(200)
        
        layout.addWidget(self.inputline)
        layout.addWidget(searchbutton)
    
    def search (self):
        query = self.inputline.text().casefold()
        view = FlGlobals.window.activeview()
        view.search(query)   

class TreeView (QGraphicsView):
    
    activeChanged = pyqtSignal(str)
    selectedChanged = pyqtSignal(str)
    
    def __init__ (self, parent=None):
        super().__init__(parent)
        self.zoomscale = 1
        self.activenode = None
        self.selectednode = None
        #self.treewidth = self.treeheight = 0
        
        self.hits = []
        
        self.setOptimizationFlags(QGraphicsView.DontAdjustForAntialiasing | QGraphicsView.DontSavePainterState)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        """OPTIONS: OpenGL rendering; FullViewportUpdate; MinimalViewportUpdate"""
        #self.setViewport(QGLWidget(QGLFormat(QGL.SampleBuffers)))
        #self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        
        scene =  QGraphicsScene()
        scene.setBackgroundBrush(FlPalette.bg)
        self.setScene(scene)
        
        self.nodecontainer = fp.loadjson("test3.json")
        self.nodedocs = dict()
        """self.nodegraph = dict()
        self.constructgraph()
        self.layoutgraph()
        scene.addItem(FrameItem(widget=self.viewport()))"""
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
        
        self.updatedocs()
        self.scene().clear()
        self.nodegraph = dict()
        #self.treewidth = self.treeheight = 0
        self.viewframe = FrameItem(treeview=self)
        self.scene().addItem(self.viewframe)
        self.constructgraph()
        self.layoutgraph()
        
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
        queue.append((nodeID, None, False))
        nodegraph = self.nodecontainer.nodegraph
        nodesdict = self.nodecontainer.nodes       
        itemdict = dict()
                
        while queue:
            curID, ref, isghost = queue.pop(0)
            nodeitem = self.newitem(nodesdict[curID], ref, isghost)
            if not isghost:
                for nextID, ghost in nodegraph[curID]:
                    ref = nodeitem
                    queue.append((nextID, ref, ghost)) 
    
    def newitem (self, nodeobj, parent, isghost=False):
        if parent is None:
            refid = None
        else:
            refid = parent.id()
        nodeitem = NodeItem(nodeobj, parent=parent, treeviewport=self.viewport())
        edgeitem = EdgeItem(nodeitem, treeviewport=self.viewport())
        self.scene().addItem(edgeitem)
        self.scene().addItem(nodeitem)
        if isghost:
            self.nodegraph["<-".join([nodeobj.ID, refid])] = nodeitem
        else:
            self.nodegraph[nodeobj.ID] = nodeitem
        return nodeitem
    
    def treeroot (self):
        return self.nodegraph["0"]
    
    def layoutgraph (self):
        root = self.treeroot()
        root.treeposition()
        # OPTION : 
        #if compactlayout:
        root.graphcompact()
        #else:
        #root.subtreerootdrop(recursive=True)
        self.updatescenerect(root)
        self.scene().update()
    
    def updatescenerect (self, root):
        top, bottom, depth = root.subtreesize(-1)
        height = abs(bottom - top)
        #print(treedims)
        rank = FlGlobals.style.rankgap
        row = FlGlobals.style.rowgap
        self.setSceneRect(QRectF(-rank/2, top-row/2, depth*(rank+0.5), height+row))
        #self.setSceneRect(QRectF(-RANKGAP/2, -ROWGAP/2, self.treewidth+RANKGAP, self.treeheight+ROWGAP))
    
    """def updatedimensions (self, x, y):
        if x > self.treewidth:
            self.treewidth = x
        if y > self.treeheight:
            self.treeheight = y"""
       
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
            FlGlobals.style.rankgap-FlGlobals.style.nodewidth, 
            FlGlobals.style.rowgap)
    
    def setselectednode (self, nodeitem, signal=True):
        if nodeitem is not None:
            self.selectednode = nodeitem
            self.shownode(self.selectednode)
            if signal:
                self.selectedChanged.emit(self.selectednode.nodeobj.ID)
            self.scene().update()
    
    def setactivenode (self, nodeitem, signal=True):
        if nodeitem is not None:
            self.activenode = nodeitem.realnode()
            #self.shownode(self.activenode)
            if signal:
                self.activeChanged.emit(self.activenode.nodeobj.ID)
            self.scene().update()
    
    def createlink (self):
        fromID = self.activenode.nodeobj.ID
        toID = self.selectednode.nodeobj.ID
        self.nodecontainer.newlink(fromID, toID)
        self.updateview()
    
    def addnode (self, paste=False):
        selected = self.selectednode.realnode()
        #if selected.isghost():
        #    return
        selectedid = selected.id()        
        newobj = self.nodecontainer.newnode(FlGlobals.newnode(paste), refID=selectedid)
        newid = newobj.ID
        self.updateview()
        self.shownode(self.nodegraph[newid])
        """newitem = self.newitem(newobj, selected)
        self.layoutgraph()
        self.shownode(newitem)"""
    
    def unlink (self, inherit=False):
        selID = self.selectednode.nodeobj.ID
        refID = self.selectednode.ref
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
        #mod = event.modifiers() & ~Qt.KeypadModifier
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
            children = node.childlist
            count = len(children)-1
            if children:
                self.setselectednode(children[count//2])
        elif key == Qt.Key_Enter or key == Qt.Key_Return:
            if self.selectednode:
                self.setactivenode(self.selectednode)
        else:
            super().keyPressEvent(event)

class EditorWindow (QMainWindow):
    def __init__ (self):
        super().__init__()
        
        FlGlobals.window = self
        FlGlobals.style = FlNodeStyle(QFont())
        
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
        
        viewtoolbar = QToolBar("View control")
        FlGlobals.actions["zoomin"] = self.createaction("Zoom In", self.zoomin, 
            [QKeySequence.ZoomIn, QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_Plus)], 
            ["gtk-zoom-in", "zoom-in"], "Zoom in")
        FlGlobals.actions["zoomout"] = self.createaction("Zoom Out", self.zoomout, 
            [QKeySequence.ZoomOut, QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_Minus)], 
            ["gtk-zoom-out", "zoom-out"], "Zoom out")
        FlGlobals.actions["zoomorig"] = self.createaction("Zoom Original", self.zoomorig, 
            [QKeySequence(Qt.ControlModifier + Qt.Key_0), QKeySequence(Qt.ControlModifier + Qt.KeypadModifier + Qt.Key_0)], 
            ["gtk-zoom-100", "zoom-original"], "Zoom to original size")
        FlGlobals.actions["gotoactive"] = self.createaction("Go To Active", self.gotoactive, 
            None, ["go-jump"], "Center on active node")
        
        viewtoolbar.addAction(FlGlobals.actions["zoomorig"])
        viewtoolbar.addAction(FlGlobals.actions["zoomin"])
        viewtoolbar.addAction(FlGlobals.actions["zoomout"])
        viewtoolbar.addAction(FlGlobals.actions["gotoactive"])
        self.addToolBar(viewtoolbar)
        
        edittoolbar = QToolBar("Tree editing")
        FlGlobals.actions["addnode"] = self.createaction("&Add Node", self.addnode,
            None, ["insert-object"], "Add new node")
        FlGlobals.actions["createlink"] = self.createaction("&Link to active node", self.createlink,
            None, ["insert-link"], "Create link from active node to selected node")
        FlGlobals.actions["copynode"] = self.createaction("&Copy Node", self.copynode,
            None, ["edit-copy"], "Copy node")
        FlGlobals.actions["pastenode"] = self.createaction("&Paste Node", self.pastenode,
            None, ["edit-paste"], "Paste node")
        FlGlobals.actions["pastenode"].setEnabled(False)
        FlGlobals.actions["unlinkstree"] = self.createaction("Unlink &Subtree", self.unlink,
            None, ["edit-clear"], "Unlink subtree from parent")
        FlGlobals.actions["unlinknode"] = self.createaction("Unlink &Node", self.unlinkinherit,
            None, ["edit-delete"], "Unlink node and let parent inherit its child nodes")
        FlGlobals.actions["moveup"] = self.createaction("Move &Up", self.moveup,
            None, ["go-up"], "Move node up")
        FlGlobals.actions["movedown"] = self.createaction("Move &Down", self.movedown,
            None, ["go-down"], "Move node down")
        
        edittoolbar.addAction(FlGlobals.actions["addnode"])
        edittoolbar.addAction(FlGlobals.actions["createlink"])
        edittoolbar.addAction(FlGlobals.actions["copynode"])
        edittoolbar.addAction(FlGlobals.actions["pastenode"])
        edittoolbar.addAction(FlGlobals.actions["unlinknode"])
        edittoolbar.addAction(FlGlobals.actions["unlinkstree"])
        edittoolbar.addAction(FlGlobals.actions["moveup"])
        edittoolbar.addAction(FlGlobals.actions["movedown"])
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
        self.activeview().addnode()
       
    @pyqtSlot()
    def createlink (self):
        self.activeview().createlink()
    
    @pyqtSlot()
    def copynode (self):
        FlGlobals.copynode(self.activeview().selectednode)
    
    @pyqtSlot()
    def pastenode (self):
        self.activeview().addnode(paste=True)
    
    @pyqtSlot()
    def unlinkinherit (self):
        self.unlink(inherit=True)
    
    @pyqtSlot()
    def unlink (self, inherit=False):
        view = self.activeview()
        selected = view.selectednode
        if selected.ref is None:
            return
        if len(selected.nodeobj.referrers) == 1:
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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec_())
