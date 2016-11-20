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

from PyQt5.QtCore import Qt, QRegExp, pyqtSlot
from PyQt5.QtWidgets import (QCompleter, QFormLayout, QLabel, 
	QLineEdit, QPlainTextDocumentLayout, QPlainTextEdit, QVBoxLayout, 
	QWidget)
from PyQt5.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat, 
	QTextCursor, QTextDocument)
from flint.glob import FlGlob

class ParagraphEdit (QPlainTextEdit):
    def keyPressEvent (self, event):
        key = event.key()
        mod = event.modifiers()
        if not (mod & Qt.ShiftModifier) and (key == Qt.Key_Enter or key == Qt.Key_Return):
            FlGlob.mainwindow.activeview.setFocus()
        else:
            super().keyPressEvent(event)

class TextEditWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setEnabled(False)
        layout = QFormLayout(self)
        l_speaker = QLabel("&Speaker")
        self.speaker = QLineEdit(self)
        l_speaker.setBuddy(self.speaker)
        
        l_listener = QLabel("&Listener")
        self.listener = QLineEdit(self)
        l_listener.setBuddy(self.listener)
        
        l_nodetext = QLabel("&Text")
        self.nodetext = ParagraphEdit(self)
        self.nodetext.setTabChangesFocus(True)
        l_nodetext.setBuddy(self.nodetext)
        
        layout.addRow(l_speaker, self.speaker)
        layout.addRow(l_listener, self.listener)
        layout.addRow(l_nodetext, self.nodetext)
        
        self.nodeobj = None
        textdoc = QTextDocument(self)
        textdoc.setDocumentLayout(QPlainTextDocumentLayout(textdoc))
        self.blankdoc = textdoc
        self.speaker.textChanged.connect(self.setnodespeaker)
        self.listener.textChanged.connect(self.setnodelistener)
        self.nodetext.textChanged.connect(self.setnodetext)
        
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        self.nodeobj = nodeobj
        
        if nodeobj is not None and nodeobj.typename in ("talk", "response"):
            self.setEnabled(True)
            nodetextdoc = view.nodedocs[nodeID]["text"]
            self.speaker.setText(nodeobj.speaker)
            self.listener.setText(nodeobj.listener)
            self.nodetext.setDocument(nodetextdoc)
            self.nodetext.moveCursor(QTextCursor.End)
        else:
            self.setEnabled(False)
            self.nodeobj = None
            self.speaker.setText("")
            self.listener.setText("")
            self.nodetext.setDocument(self.blankdoc)
    
    @pyqtSlot()
    def setnodespeaker (self):
        if self.nodeobj is None:
            return
        self.nodeobj.speaker = self.speaker.text()
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatespeaker")
    
    @pyqtSlot()
    def setnodelistener (self):
        if self.nodeobj is None:
            return
        self.nodeobj.listener = self.listener.text()
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "updatespeaker")
    
    @pyqtSlot()
    def setnodetext (self):
        if self.nodeobj is None:
            return
        self.nodeobj.text = self.nodetext.toPlainText()

"""
class ScriptParamWidget (QWidget):
    def __init__ (self, parent, name, annot, default):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(name)
        if annot is bool:
            editor = QCheckBox("True", self)
            signal = editor.stateChanged
            value = lambda: bool(editor.checkState())
            editor.setChecked(bool(default))
        elif annot is int:
            editor = QSpinBox(self)
            signal = editor.valueChanged
            value = editor.value
            if not default:
                default = 0
            editor.setValue(int(default))
        else:
            editor = QLineEdit(self)
            signal = editor.textEdited
            value = editor.text
            if not default:
                default = ""
            editor.setText(str(default))
        
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
        self.setStyleSheet('''
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
            ''')
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
    removed = pyqtSignal(cp.ScriptCall)
    
    def __init__ (self, parent, callobj, nodeID, cond=False):
        name = callobj.funcname
        super().__init__(parent, callobj, name)
        self.nodeID = nodeID
        params = callobj.funcparams
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 4, 9, 4)
        
        if cond:
            notcheck = QCheckBox("Not", self)
            notcheck.setChecked(callobj._not)
            notcheck.stateChanged.connect(self.notchanged)
            layout.addWidget(notcheck)
            self.toggled.connect(notcheck.setVisible)
        
        paramswidget = QWidget(self)
        paramslayout = QVBoxLayout(paramswidget)
        paramslayout.setContentsMargins(0, 0, 0, 0)
        paramslist = []
        if callobj.funccall is not None:
            signature = insp.signature(callobj.funccall)
            for param in signature.parameters.values():
                pname = param.name
                annot = param.annotation if param.annotation is not insp._empty else ""
                default = params.pop(0) if params else None
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
    newCallObj = pyqtSignal(cp.MetaCall)
    
    def __init__ (self, parent, cond=False):
        super().__init__(parent)
        self.cond = cond
        
        self.combobox = QComboBox(self)
        addbutton = QPushButton("Add", self)
        addbutton.clicked.connect(self.newscriptcall)
        
        layout = QHBoxLayout(self)
        layout.addWidget(self.combobox)
        layout.addWidget(addbutton)
        
        self.reload()
    
    def getscripts (self, strict=False):
        view = FlGlob.mainwindow.activeview
        if view is not None and view.nodecontainer.proj is not None:
            return view.nodecontainer.proj.scripts
        elif strict:
            return None
        else:
            return dict()
    
    def reload (self):
        scripts = self.getscripts()
        if self.cond:
            names = ["( )"]
            condcalls = [n for n, sc in scripts.items() if "return" in sc.__annotations__]
            names.extend(sorted(condcalls))
        else:
            names = sorted(scripts.keys())
        self.scriptcalls = names
        
        self.combobox.clear()
        self.combobox.insertItems(len(self.scriptcalls), self.scriptcalls)
    
    @pyqtSlot()
    def newscriptcall (self):
        name = self.combobox.currentText()
        if not name:
            return
        elif name == "( )":
            callobj = cp.MetaCall({"type":"cond","operator":"and","calls":[]})
        else:
            scripts = self.getscripts()
            signature = insp.signature(scripts[name])
            defaults = {int: 0, bool: False}
            params = []
            for param in signature.parameters.values():
                if param.name == "self":
                    continue
                if param.annotation in defaults:
                    params.append(defaults[param.annotation])
                else:
                    params.append("")
            callobj = cp.MetaCall({"type":"script", "command":name, "params":params},
                scripts=self.getscripts(strict=True))
        self.newCallObj.emit(callobj)

class ConditionCallWidget (CallWidget):
    removed = pyqtSignal(cp.ConditionCall)
    
    def __init__ (self, parent, callobj, nodeID, cond=True):
        name = "()"
        super().__init__ (parent, callobj, name)
        self.nodeID = nodeID
        operatorwidget = QWidget(self)
        operatorlabel = QLabel("Operator", operatorwidget)
        operatorcombo = QComboBox(operatorwidget)
        operatorcombo.insertItems(2, ["and", "or"])
        operatorcombo.setCurrentText(callobj.operatorname)
        operatorcombo.currentTextChanged.connect(self.setoperator)
        operatorlayout = QHBoxLayout(operatorwidget)
        operatorlayout.addWidget(operatorlabel)
        operatorlayout.addWidget(operatorcombo)
        
        self.widgets = dict()
        callswidget = QWidget(self)
        self.callswidget = callswidget
        callslayout = QVBoxLayout(callswidget)
        callslayout.setContentsMargins(0, 0, 0, 0)
        self.types = {"cond": ConditionCallWidget, "script": ScriptCallWidget}
        for call in callobj.calls:
            self.addcallwidget(call)
        
        newwidget = CallCreateWidget(self, cond=True)
        newwidget.layout().addStretch()
        newwidget.newCallObj.connect(self.addcall)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(operatorwidget)
        layout.addWidget(callswidget)
        layout.addWidget(newwidget)
        
        self.toggled.connect(callswidget.setVisible)
        self.toggled.connect(operatorwidget.setVisible)
        self.toggled.connect(newwidget.setVisible)
    
    @pyqtSlot(cp.MetaCall)
    def addcall (self, metacall):
        callobj = metacall.callobj
        self.callobj.calls.append(callobj)
        self.addcallwidget(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeID, "updatecondition")
    
    def addcallwidget (self, callobj):
        widget = self.types[callobj.typename](self, callobj, self.nodeID, cond=True)
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
        
    @pyqtSlot()
    def newtitle (self):
        fullname = self.fullname(self.callobj, recursive=True)
        shortname = self.fullname(self.callobj)
        self.setTitle(elidestring(shortname,30))
        self.setToolTip(fullname)
        self.changed.emit()
    
    @pyqtSlot(str)
    def setoperator (self, operatorname):
        self.callobj.setoperator(operatorname)
        self.newtitle()
    
    @pyqtSlot(cp.ScriptCall)
    @pyqtSlot(cp.ConditionCall)
    def removecall (self, callobj):
        prompt = QMessageBox.question(self, "Prompt", "Remove call?", defaultButton=QMessageBox.Yes)
        if prompt == QMessageBox.No:
            return
        widget = self.widgets.pop(callobj)
        self.callswidget.layout().removeWidget(widget)
        widget.deleteLater()
        self.callobj.calls.remove(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeID, "updatecondition")
        widget = None
        gc.collect()

class CallEditWidget (QWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.setEnabled(False)
        callsarea = QScrollArea(self)
        callsarea.setWidgetResizable(True)
        self.callsarea = callsarea
        self.resetwidget()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
    
    def resetwidget (self):
        callswidget = self.callsarea.widget()
        if callswidget is not None:
            callswidget.setParent(None)
            callswidget.deleteLater()
            callswidget = None
            gc.collect()
        callswidget = QWidget(self.callsarea)
        callslayout = QVBoxLayout(callswidget)
        callslayout.setAlignment(Qt.AlignTop)
        self.callsarea.setWidget(callswidget)
        return callswidget

class ConditionEditWidget (CallEditWidget):
    def __init__ (self, parent):
        super().__init__(parent)
        self.layout().addWidget(self.callsarea)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        self.nodeobj = nodeobj
 
        if nodeobj is not None:
            callobj = nodeobj.condition
            callswidget = self.resetwidget()
            scwidget = ConditionCallWidget(callswidget, callobj, nodeID)
            scwidget.actremove.setEnabled(False)
            callswidget.layout().addWidget(scwidget)
            if view.nodecontainer.proj is not None:
                self.setEnabled(True)
            else:
                self.setEnabled(False)
        else:
            self.setEnabled(False)
            self.resetwidget()

class ScriptEditWidget (CallEditWidget):
    def __init__ (self, parent, slot="enter"):
        super().__init__(parent)
        if slot in ("enter", "exit"):
            self.slot = slot
        else:
            return
        
        newwidget = CallCreateWidget(self)
        newwidget.newCallObj.connect(self.addscriptcall)
        self.newwidget = newwidget
        
        self.widgets = dict()
        
        layout = self.layout()
        layout.addWidget(newwidget)
        layout.addWidget(self.callsarea)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        self.nodeobj = nodeobj
        
        if nodeobj is not None:
            self.resetwidget()
            self.newwidget.reload()
            if self.slot == "enter":
                self.scripts = nodeobj.enterscripts
            elif self.slot == "exit":
                self.scripts = nodeobj.exitscripts
            for callobj in self.scripts:
                self.addscriptcallwidget(callobj)
            if view.nodecontainer.proj is not None:
                self.setEnabled(True)
            else:
                self.setEnabled(False)
        else:
            self.setEnabled(False)
            self.resetwidget()
    
    @pyqtSlot(cp.MetaCall)
    def addscriptcall (self, metacall):
        callobj = metacall.callobj
        self.scripts.append(callobj)
        self.addscriptcallwidget(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "update%sscripts" % self.slot)
    
    def addscriptcallwidget (self, callobj):
        callswidget = self.callsarea.widget()
        scwidget = ScriptCallWidget(callswidget, callobj, self.nodeobj.ID)
        scwidget.removed.connect(self.removescriptcall)
        self.widgets[callobj] = scwidget
        callswidget.layout().addWidget(scwidget)
    
    @pyqtSlot(cp.ScriptCall)
    def removescriptcall (self, callobj):
        prompt = QMessageBox.question(self, "Prompt", "Remove call?", defaultButton=QMessageBox.Yes)
        if prompt == QMessageBox.No:
            return
        callswidget = self.callsarea.widget()
        scwidget = self.widgets.pop(callobj)
        callswidget.layout().removeWidget(scwidget)
        scwidget.deleteLater()
        self.scripts.remove(callobj)
        view = FlGlob.mainwindow.activeview
        view.callupdates(self.nodeobj.ID, "update%sscripts" % self.slot)
        scwidget = None
        gc.collect()
"""

class ScriptHighlighter (QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        styles = {
            'keyword': self.textformat('blue', 'bold'),
            'bool': self.textformat('green', 'bold'),
            'string': self.textformat('yellowgreen'),
            'numbers': self.textformat('green'),
        }
        
        rules = []
        
        rules += [(r'\b%s\b' % w, styles['keyword']) for w in ('and', 'or', 'not')]
        rules += [(r'\b%s\b' % w, styles['bool']) for w in ('true', 'false')]
        rules += [(r'\s!' , styles['keyword'])]
        
        rules += [
            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', styles['string']),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", styles['string']),

            # Numeric literals
            (r'\b[+-]?[0-9]+\b', styles['numbers']),
            (r'\b[+-]?0[bB][01]+\b', styles['numbers']),
            (r'\b[+-]?0[oO][0-7]+\b', styles['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+\b', styles['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', styles['numbers']),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QRegExp(pat, cs=Qt.CaseInsensitive), fmt) for (pat, fmt) in rules]

    def textformat (self, color, style=''):
        tformat = QTextCharFormat()
        tformat.setForeground(QColor(color))
        if 'bold' in style:
            tformat.setFontWeight(QFont.Bold)
        if 'italic' in style:
            tformat.setFontItalic(True)
    
        return tformat

    
    def highlightBlock(self, text):
        for exp, fmt in self.rules:
            index = exp.indexIn(text, 0)

            while index >= 0:
                length = len(exp.cap())
                self.setFormat(index, length, fmt)
                index = exp.indexIn(text, index + length)

        self.setCurrentBlockState(0)

class ScriptTextEdit (QPlainTextEdit):
    def __init__ (self, parent):
        super().__init__(parent)
        self.completer = None
        self.highlighter = ScriptHighlighter(self)
    
    def setcompleter (self, completer):
        completer.setWidget(self)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.activated.connect(self.insertcompletion)
        self.completer = completer
    
    def setDocument (self, document):
        super().setDocument(document)
        self.highlighter.setDocument(document)
    
    @pyqtSlot(str)
    def insertcompletion (self, completion):
        c = self.completer
        tc = self.textCursor();
        extra = len(c.completionPrefix())
        print(completion, c.completionPrefix(), extra)
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[extra:])
        self.setTextCursor(tc)
    
    def textundercursor (self):
        cur = self.textCursor()
        cur.select(QTextCursor.WordUnderCursor)
        return cur.selectedText()
    
    def keyPressEvent (self, event):
        c = self.completer
        if c and c.popup().isVisible():
            if event.key() in (Qt.Key_Enter,Qt.Key_Return,Qt.Key_Escape,Qt.Key_Tab,Qt.Key_Backtab):
                event.ignore()
                return
        super().keyPressEvent(event)
        if not c:
            return
        p = c.popup()
        t = event.text()
        prefix = self.textundercursor()
        if not t or len(prefix) < 3 or t[-1] in "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-=":
            c.popup().hide()
            return
        #print(prefix)
        if prefix != c.completionPrefix():
            c.setCompletionPrefix(prefix)
            p.setCurrentIndex(c.completionModel().index(0, 0))
        cr = self.cursorRect()
        cr.setWidth(p.sizeHintForColumn(0) + p.verticalScrollBar().sizeHint().width())
        c.complete(cr)

class ScriptWidget (QWidget):
    def __init__ (self, parent, slot):
        super().__init__(parent)
        
        self.setEnabled(False)
        self.slot = slot
        
        layout = QVBoxLayout(self)
        
        textedit = ScriptTextEdit(self)
        #textedit = QPlainTextEdit(self)
        #completer = QCompleter(self.getscripts().keys(), self)
        #textedit.setcompleter(completer)
        #self.highlight = ScriptHighlighter(textedit.document())
        #textedit.setPlainText("QWE('rty') and not asd(false)")
        self.textedit = textedit
        
        layout.addWidget(textedit)
    
    @pyqtSlot(str)
    def loadnode (self, nodeID):
        view = FlGlob.mainwindow.activeview
        if view is not None:
            nodeobj = view.nodecontainer.nodes.get(nodeID, None)
        else:
            nodeobj = None
        
        if nodeobj is not None:
            #scriptdoc = view.nodedocs[nodeID].get("script", None)
            #if self.slot not in view.nodedocs[nodeID]:
            #    view.nodedocs[nodeID][self.slot] = self.scripttodoc(nodeID)
                
            scriptdoc = view.nodedocs[nodeID][self.slot]
            completer = QCompleter(self.getscripts().keys(), self)
            self.textedit.setcompleter(completer)
            self.textedit.setDocument(scriptdoc)
            self.setEnabled(True)
        else:
            self.setEnabled(False)
        
    
    def getscripts (self, strict=False):
        view = FlGlob.mainwindow.activeview
        if view is not None and view.nodecontainer.proj is not None:
            return view.nodecontainer.proj.scripts
        elif strict:
            return None
        else:
            return dict()
