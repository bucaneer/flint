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

class FlGlob:
    loglevels = {"quiet": 0, "error": 1, "warn": 2, "info": 3, "debug": 4, "verbose": 5}
    loglevel = 3
    mainwindow = None

def log (level, text):
    if level not in FlGlob.loglevels:
        print("[warn] Unknown loglevel: %s" % level)
        level = "warn"
    if FlGlob.loglevels[level] <= FlGlob.loglevel:
        print("[%s] %s" % (level, text))
        if level == "warn":
            QMessageBox.warning(FlGlob.mainwindow, "Warning", text)
        elif level == "error":
            QMessageBox.critical(FlGlob.mainwindow, "Error", text)

def elidestring (string, length):
    if len(string) <= length:
        return string
    else:
        return string[:length-1]+"…"
