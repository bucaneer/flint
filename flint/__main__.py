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

from flint.editorwindow import FlGlob, EditorWindow, log
import sys
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)
for arg in sys.argv[1:]:
	split = arg.split("=", maxsplit=1)
	argname = split[0]
	param = split[1] if len(split)>1 else None
	if argname == "--loglevel":
		if param in FlGlob.loglevels:
			FlGlob.loglevel = FlGlob.loglevels[param]
			log("info", "Loglevel: %s" % param)
		else:
			log("warn", "Unrecognized loglevel: %s" % param)
	elif argname == "--icontheme":
		QIcon.setThemeName(param)
window = EditorWindow()
window.show()
sys.exit(app.exec_())
