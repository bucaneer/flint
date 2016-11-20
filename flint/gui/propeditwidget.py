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

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import (QComboBox, QFormLayout, QLabel, 
	QLineEdit, QPlainTextDocumentLayout, QWidget)
from PyQt5.QtGui import (QDoubleValidator, QTextCursor, QTextDocument)
from flint.glob import FlGlob
from flint.gui.textwidgets import ParagraphEdit

class PropertiesEditWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setEnabled(False)
        layout = QFormLayout(self)
        
        l_persistence = QLabel("&Persistence", self)
        persistence = QComboBox(self)
        persvals = ("", "Mark", "OnceEver", "OncePerConv")
        persistence.insertItems(len(persvals), persvals)
        persistence.currentTextChanged.connect(self.persistencechanged)
        l_persistence.setBuddy(persistence)
        self.persistence = persistence
        
        l_bankmode = QLabel("&Bank play mode", self)
        bankmode = QComboBox(self)
        bankmodes = ("First", "All", "Append")
        bankmode.insertItems(len(bankmodes), bankmodes)
        bankmode.currentTextChanged.connect(self.bankmodechanged)
        l_bankmode.setBuddy(bankmode)
        self.bankmode = bankmode
        
        l_questionhub = QLabel("&Question hub", self)
        questionhub = QComboBox(self)
        qhubtypes = ("", "ShowOnce", "ShowNever")
        questionhub.insertItems(len(qhubtypes), qhubtypes)
        questionhub.currentTextChanged.connect(self.questionhubchanged)
        l_questionhub.setBuddy(questionhub)
        self.questionhub = questionhub
        
        l_trigger = QLabel("&Trigger conversation", self)
        trigger = QComboBox(self)
        trigger.currentTextChanged.connect(self.triggerchanged)
        l_trigger.setBuddy(trigger)
        self.trigger = trigger
        
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
        layout.addRow(l_bankmode, bankmode)
        layout.addRow(l_questionhub, questionhub)
        layout.addRow(l_trigger, trigger)
        layout.addRow(l_randweight, randweight)
        layout.addRow(l_comment, comment)
        
        textdoc = QTextDocument(self)
        textdoc.setDocumentLayout(QPlainTextDocumentLayout(textdoc))
        self.blankdoc = textdoc
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        self.nodeobj = nodeobj
        
        if nodeobj is not None:
            self.setEnabled(True)
            self.persistence.setCurrentText(nodeobj.persistence)
            
            if nodeobj.typename == "bank":
                self.bankmode.setCurrentText(nodeobj.bankmode)
                self.bankmode.setEnabled(True)
            else:
                self.bankmode.setEnabled(False)
            
            if nodeobj.typename == "talk":
                self.questionhub.setCurrentText(nodeobj.questionhub)
                self.questionhub.setEnabled(True)
            else:
                self.questionhub.setEnabled(False)
            
            if nodeobj.typename == "trigger" and view.nodecontainer.proj is not None:
                proj = view.nodecontainer.proj
                convs = [""] + proj.convs
                # nodeobj.triggerconv will be reset with clear(), so we save it
                triggerconv = nodeobj.triggerconv
                self.trigger.clear()
                self.trigger.insertItems(len(convs), convs)
                self.trigger.setCurrentText(triggerconv)
                self.trigger.setEnabled(True)
            else:
                self.trigger.setEnabled(False)
            
            self.randweight.setText(str(nodeobj.randweight))
            
            commentdoc = view.nodedocs[nodeID]["comment"]
            self.comment.setDocument(commentdoc)
            self.comment.moveCursor(QTextCursor.End)
        else:
            self.setEnabled(False)
            self.persistence.setCurrentText("")
            self.bankmode.setCurrentText("")
            self.questionhub.setCurrentText("")
            self.randweight.setText("")
            self.comment.setDocument(self.blankdoc)
    
    @pyqtSlot()
    def persistencechanged (self):
        if self.nodeobj is None:
            return
        persistence = self.persistence.currentText()
        self.nodeobj.persistence = persistence
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatepersistence")
    
    @pyqtSlot()
    def bankmodechanged (self):
        if self.nodeobj is None:
            return
        bankmode = self.bankmode.currentText()
        self.nodeobj.bankmode = bankmode
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatebankmode")
    
    @pyqtSlot()
    def questionhubchanged (self):
        if self.nodeobj is None:
            return
        questionhub = self.questionhub.currentText()
        self.nodeobj.questionhub = questionhub
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatequestionhub")
    
    @pyqtSlot()
    def triggerchanged (self):
        if self.nodeobj is None:
            return
        trigger = self.trigger.currentText()
        self.nodeobj.triggerconv = trigger
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatetrigger")
    
    @pyqtSlot()
    def randweightchanged (self):
        if self.nodeobj is None:
            return
        randweight = float(self.randweight.text())
        self.nodeobj.randweight = randweight
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updaterandweight")
    
    @pyqtSlot()
    def commentchanged (self):
        if self.nodeobj is None:
            return
        comment = self.comment.toPlainText()
        self.nodeobj.comment = comment
