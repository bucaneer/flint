from .fleditor import FlGlob, EditorWindow, log
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
