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

from PyQt5.QtCore import QMarginsF
from PyQt5.QtGui import (QFont, QFontMetrics, QColor)

class FlPalette (object):
    """Palette of custom colors for quick reference."""
    dark    = QColor( 38,  39,  41) # shadows, node text
    light   = QColor(250, 250, 250) # highlights, node labels
    hl1var  = QColor(255, 121,  13) # talk active
    hl1     = QColor(224, 111,  19) # talk normal
    hl2var  = QColor(102, 183, 204) # response active
    hl2     = QColor(108, 158, 171) # response normal
    bankvar = QColor(134, 179, 156) # bank active
    bank    = QColor(130, 150, 140) # bank normal
    rootvar = QColor(153, 153, 153) # root active
    root    = QColor(128, 128, 128) # root normal
    trigvar = QColor(181, 219,  29) # trigger active
    trig    = QColor(172, 204,  42) # trigger normal
    bg      = QColor( 90,  94,  98) # scene, bank background
    hit     = QColor(120, 255, 180) # search input BG on hit
    miss    = QColor(255, 150, 150) # search input BG on miss

class FlNodeStyle (object):    
    def __init__ (self, font):
        basefont = font
        boldfont = QFont(basefont)
        boldfont.setBold(True)
        italicfont = QFont(basefont)
        italicfont.setItalic(True)
        self.basefont = basefont
        self.boldfont = boldfont
        self.italicfont = italicfont
        
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
        
        self.nodemargins = QMarginsF(*(nodemargin,)*4)
        self.banknodemargins = QMarginsF(*(nodemargin//2,)*4)
        self.itemmargins = QMarginsF(*(itemmargin,)*4)
        self.activemargins = QMarginsF(*(selectmargin//2,)*4)
        self.selectmargins = QMarginsF(*(selectmargin//2,)*4)
        
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
        self.arrowsize = self.pensize * 3.5
