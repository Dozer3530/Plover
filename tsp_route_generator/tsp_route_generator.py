# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMainWindow
from qgis.core import QgsProject, Qgis
import qgis.utils
# import resources
from .tsp_route_generator_dialog import TSPRouteGeneratorDialog

class TSPRouteGenerator:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = None
        self.actions = []
        self.menu = self.tr(u'&TSP Route Generator')

    def tr(self, message):
        return QCoreApplication.translate('TSPRouteGenerator', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        icon = QIcon()
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.iface.addToolBarIcon(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        # Clear existing actions to prevent duplicates
        self.unload()
        icon_path = ':/plugins/tsp_route_generator/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Generate TSP Route'),
            callback=self.run,
            parent=self.iface.mainWindow())
        self.add_action(
            icon_path,
            text=self.tr(u'Reload Plugin'),
            callback=self.reload,
            add_to_toolbar=False,
            parent=self.iface.mainWindow())
        self.dlg = TSPRouteGeneratorDialog(self.iface, self.iface.mainWindow())

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&TSP Route Generator'), action)
            self.iface.removeToolBarIcon(action)
        self.actions = []

    def run(self):
        self.dlg.show()
        result = self.dlg.exec()
        if result:
            pass

    def reload(self):
        qgis.utils.reloadPlugin('tsp_route_generator')
        self.initGui()  # Reinitialize GUI components
        self.iface.messageBar().pushMessage("Success", "Plugin reloaded.", level=Qgis.Info)