# -*- coding: utf-8 -*-
"""Plover plugin entry point: menu/toolbar wiring and Processing registration."""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication


class TSPRouteGenerator:
    """QGIS plugin shell. The class name is kept for plugin identity."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.menu = "&Plover"
        self.actions = []
        self.dlg = None
        self.provider = None

    def initGui(self):
        icon = QIcon(os.path.join(self.plugin_dir, "icon.png"))
        action = QAction(icon, "Plover — Generate TSP Route",
                         self.iface.mainWindow())
        action.setStatusTip("Boundary-aware TSP route through a point layer")
        action.triggered.connect(self.run)
        self.iface.addToolBarIcon(action)
        # Plover is a vector tool (category=Vector), so it belongs in the
        # Vector menu rather than the generic Plugins menu.
        self.iface.addPluginToVectorMenu(self.menu, action)
        self.actions.append(action)
        self.initProcessing()

    def initProcessing(self):
        from .processing_provider import PloverProcessingProvider
        self.provider = PloverProcessingProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginVectorMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        self.actions = []
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        if self.dlg is not None:
            self.dlg.close()
            self.dlg = None

    def run(self):
        if self.dlg is None:
            from .tsp_route_generator_dialog import TSPRouteGeneratorDialog
            self.dlg = TSPRouteGeneratorDialog(self.iface,
                                               self.iface.mainWindow())
        # Modeless: the map stays usable while the dialog is open.
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()
