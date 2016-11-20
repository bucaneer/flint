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

from PyQt5.QtGui import QFont, QIcon, QKeySequence
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (QAction, QDockWidget, QFileDialog, 
    QInputDialog, QMessageBox, QMainWindow, QMenu, QTabWidget, QToolBar)

import flint.parsers.conv as cp
import flint.parsers.proj as pp
import flint.conv_player as play
from flint.gui.view.treeview import TreeView
from flint.gui.view.mapview import MapView
from flint.gui.style import FlNodeStyle
from flint.gui.textwidgets import TextEditWidget, ScriptWidget
from flint.gui.propeditwidget import PropertiesEditWidget
from flint.gui.nodelistwidget import NodeListWidget
from flint.gui.projectwidget import ProjectWidget
from flint.glob import (FlGlob, log, elidestring)

import os
import weakref
from collections import OrderedDict
import gc

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
