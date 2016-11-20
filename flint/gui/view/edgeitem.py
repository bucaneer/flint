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

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtWidgets import QGraphicsItem
from PyQt5.QtGui import (QBrush, QPen)
from flint.gui.style import FlPalette
from flint.glob import FlGlob

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
