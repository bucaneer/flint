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

from PyQt5.QtWidgets import (QGraphicsRectItem, QGraphicsSimpleTextItem,
	QGraphicsTextItem, QGraphicsPixmapItem)

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
        self.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)
        self.cond = cond
    
    def paint (self, painter, style, widget):
        if widget is self.cond:
            super().paint(painter, style, widget)
