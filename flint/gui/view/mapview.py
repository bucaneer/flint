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
from PyQt5.QtOpenGL import (QGL, QGLFormat, QGLWidget)
from PyQt5.QtGui import QPainter
from flint.glob import FlGlob


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
