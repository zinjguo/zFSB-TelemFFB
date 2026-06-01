#
# This file is part of the TelemFFB distribution (https://github.com/walmis/TelemFFB).
# Copyright (c) 2023 Valmantas Palikša.
# Copyright (c) 2023 Micah Frisby
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#


import inspect
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import winreg
from collections import OrderedDict
from datetime import datetime

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QCoreApplication, Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtGui import (QColor, QCursor, QDesktopServices, QIcon,
                         QKeySequence, QPixmap, QFontMetrics, QAction, QShortcut, QFont,
                         QPainter, QPen, QPainterPath, QLinearGradient, QBrush)
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QCheckBox,
                             QComboBox, QFrame, QGridLayout, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
                             QAbstractButton, QPushButton, QScrollArea,
                             QToolButton, QVBoxLayout, QWidget, QSpacerItem, QSizePolicy, QSystemTrayIcon, QMenu,
                             QDialog, QStackedWidget)

import telemffb.globals as G
import telemffb.utils as utils
import telemffb.xmlutils as xmlutils
import styles
# from telemffb.config_utils import autoconvert_config
from telemffb.ConfiguratorDialog import ConfiguratorDialog
from telemffb.custom_widgets import ClickLogo, InstanceStatusRow, NoKeyScrollArea, NoWheelSlider, NoWheelNumberSlider, \
    SimStatusLabel, colorPrimary, AppStatusWidget
from telemffb.DevicePanel import DeviceIconPanel
from telemffb.hw.ffb_zfsb import HapticEffect
from telemffb.SCOverridesEditor import SCOverridesEditor
from telemffb.SettingsLayout import SettingsLayout
# from telemffb.UserModelDialog import UserModelDialog
from telemffb.NewAircraftWizard import NewAircraftWizard
from telemffb.sim.aircraft_base import effects
from telemffb.telem.SimTelemListener import SimTelemListener
from telemffb.SystemSettingsDialog import SystemSettingsDialog
from telemffb.TeleplotSetupDialog import TeleplotSetupDialog
from telemffb.ProfileManager import ProfileManagerDialog, NewProfileDialog
from telemffb.utils import exit_application, overrides, HiDpiPixmap


class TelemetryPulseWidget(QWidget):
    def __init__(self, parent=None, size=84):
        super().__init__(parent)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.setSingleShot(False)
        self._timer.setTimerType(QtCore.Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._advance_phase)
        self.setFixedSize(size, size)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def start(self):
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()

    def _advance_phase(self):
        self._phase = (self._phase + 0.02) % 1.0
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.start()

    def hideEvent(self, event):
        self.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height())
        center = QtCore.QPointF(self.rect().center())
        min_radius = side * 0.16
        max_radius = side * 0.44
        accent = QColor(styles.colorPrimary)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        for delay in (0.0, 0.33, 0.66):
            progress = (self._phase + delay) % 1.0
            envelope = math.sin(math.pi * progress)
            ring_color = QColor(accent)
            ring_color.setAlpha(int(135 * envelope))
            ring_width = max(1.0, 3.0 * envelope)
            radius = min_radius + ((max_radius - min_radius) * progress)
            painter.setPen(QPen(ring_color, ring_width))
            painter.drawEllipse(center, radius, radius)

        center_color = QColor(accent)
        center_pulse = math.sin(2.0 * math.pi * self._phase)
        center_color.setAlpha(int(220 + (15 * center_pulse)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(center_color)
        center_radius = side * (0.075 + (0.012 * center_pulse))
        painter.drawEllipse(center, center_radius, center_radius)
        painter.end()


class WaitingTelemetryPanel(QFrame):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        panel_rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(panel_rect, 10, 10)

        painter.fillPath(clip_path, QColor(styles.container_bg))
        painter.setClipPath(clip_path)
        self._paint_retrowave_grid(painter)
        painter.setClipping(False)

        painter.setPen(QPen(QColor(styles.menu_border), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(clip_path)
        painter.end()

    def _paint_retrowave_grid(self, painter):
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return

        accent = QColor(styles.colorPrimary_lighter)
        accent.setAlpha(34)
        horizon_y = height * 0.42
        bottom_y = height + 8
        center_x = width / 2

        gradient = QLinearGradient(0, bottom_y, 0, horizon_y)
        bottom_color = QColor(styles.colorPrimary_lighter)
        bottom_color.setAlpha(46)
        horizon_color = QColor(styles.colorPrimary_lighter)
        horizon_color.setAlpha(0)
        gradient.setColorAt(0.0, bottom_color)
        gradient.setColorAt(1.0, horizon_color)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(QPen(QBrush(gradient), 1))

        vertical_count = 16
        for index in range(vertical_count + 1):
            t = (index / vertical_count) - 0.5
            bottom_x = center_x + (t * width * 1.3)
            horizon_x = center_x + (t * width * 0.22)
            painter.drawLine(QtCore.QPointF(bottom_x, bottom_y), QtCore.QPointF(horizon_x, horizon_y))

        horizontal_count = 14
        for index in range(horizontal_count):
            progress = index / horizontal_count
            y = horizon_y + ((bottom_y - horizon_y) * (progress * progress))
            painter.drawLine(QtCore.QPointF(0, y), QtCore.QPointF(width, y))


class VerticalDrawerThumbButton(QAbstractButton):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self._hovered = False
        self.setCheckable(True)
        self.setCursor(QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(26)
        self.setMaximumWidth(26)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def sizeHint(self):
        return QtCore.QSize(26, 180)

    def minimumSizeHint(self):
        return QtCore.QSize(26, 120)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.isDown():
            background = QColor(styles.container_bg)
        elif self._hovered:
            background = QColor(styles.vpf_button_hover)
        else:
            background = QColor(styles.container_bg)

        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(QPen(QColor(styles.status_drawer_thumb_border), 1))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 7, 7)

        caret_center_y = 16
        if self.isChecked():
            caret_points = [
                QtCore.QPointF(self.width() * 0.62, caret_center_y - 5),
                QtCore.QPointF(self.width() * 0.38, caret_center_y),
                QtCore.QPointF(self.width() * 0.62, caret_center_y + 5),
            ]
        else:
            caret_points = [
                QtCore.QPointF(self.width() * 0.38, caret_center_y - 5),
                QtCore.QPointF(self.width() * 0.62, caret_center_y),
                QtCore.QPointF(self.width() * 0.38, caret_center_y + 5),
            ]
        painter.setBrush(QColor("#ffffff"))
        painter.drawPolygon(caret_points)

        font = styles.app_font(8, QFont.Weight.Black)
        font.setPixelSize(styles.status_drawer_thumb_font_size_px)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-90)
        text_rect = QtCore.QRectF(-self.height() / 2 + 18, -self.width() / 2, self.height() - 36, self.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


class MainWindow(QMainWindow):
    APP_VERSION_LABEL = "alpha-1"
    STATUS_DRAWER_WIDTH = 420
    TOOLBAR_MENU_ICON_PATHS = {
        "system": "image/qlementine/toolbar_system.svg",
        "profiles": "image/qlementine/toolbar_profiles.svg",
        "utilities": "image/qlementine/toolbar_utilities.svg",
        "window": "image/qlementine/toolbar_window.svg",
        "log": "image/qlementine/toolbar_log.svg",
        "debug": "image/qlementine/toolbar_debug.svg",
    }
    WINDOW_CONTROL_ICON_PATHS = {
        "minimize": "image/qlementine/window_minimize.svg",
        "maximize": "image/qlementine/window_maximize.svg",
        "restore": "image/qlementine/window_restore.svg",
        "close": "image/qlementine/window_close.svg",
    }
    
    def __init__(self):
        super().__init__()
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_notifications = {}
        self.new_craft_notification_sent = False
        self.error_state = False # True='error' key found in telem_data, False=clean telem_data
        self.error_clean_counter = 0 # counter to use as hysteresis for clearing error condition - not always 'error' from child instance on every loop
        self.telemetry_timed_out = True
        self.last_telemetry_refresh = utils.millis()
        self.show_simvars = False
        self.latest_version = None
        self._update_available = None
        self.show_new_craft_button = False
        self.profile_mgr_dialog = None
        self.all_offline_models = []
        self.default_geometry_width = 12000
        self.default_geometry_height = 700;
        self._toolbar_drag_active = False
        self._toolbar_drag_offset = QtCore.QPoint()
        self._toolbar_logo_source = None
        self._resize_border = 14
        self._resize_edges = QtCore.Qt.Edge(0)
        self._resize_event_filter_installed = False


        if G.release_version:
            dl_url = 'https://github.com/walmis/VPforce-TelemFFB/releases'
        else:
            dl_url = 'https://vpforcecontrols.com/downloads/TelemFFB/?C=M;O=D'

        G.current_device_config_scope = G.device_type

        match G.device_type:
            case 'joystick':
                x_pos = 150
                y_pos = 130
            case 'pedals':
                x_pos = 100
                y_pos = 100
            case 'collective':
                x_pos = 50
                y_pos = 70
            case 'trimwheel':
                x_pos = 40
                y_pos = 30

        self.setGeometry(x_pos, y_pos, self.default_geometry_width, self.default_geometry_height)

        version = utils.get_version()

        self.setWindowTitle(f"zTelem Alpha - {version}")

        # Construct the absolute path of the icon file
        icon = QIcon(utils.get_resource_path('image/zTelemIcon.png', prefer_root=True))

        self.setWindowIcon(icon)

        self.resize(530, 700)

        self.toolbar_logo = QLabel()
        self.toolbar_logo.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.toolbar_logo.setContentsMargins(0, 0, 0, 0)
        self.toolbar_logo.setMinimumWidth(0)
        self.toolbar_logo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._toolbar_logo_source = HiDpiPixmap(G.vpf_logo)
        container_padding = styles.default_container_padding
        container_spacing = max(6, container_padding // 2)

        # Create a layout for the main window
        layout = QVBoxLayout()
        layout.setContentsMargins(container_padding, 0, container_padding, container_padding)
        layout.setSpacing(container_spacing)
        notes_row_layout = QHBoxLayout()


        """ Create the menu bar """

        menubar = self.menuBar()
        self.menu = menubar
        # Set the background color of the menu bar
        # colorPrimary is the app accent color.


        """ Add the "System" menu and its sub-option """

        system_menu = self.menu.addMenu('&System')

        system_settings_action = QAction('System Settings', self)
        system_settings_action.triggered.connect(self.open_system_settings_dialog)
        system_menu.addAction(system_settings_action)

        cfg_log_folder_action = QAction('Open Config/Log Directory', self)
        def do_open_cfg_dir():
            modifiers = QApplication.keyboardModifiers()
            if (modifiers & QtCore.Qt.KeyboardModifier.ControlModifier) and (modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier) and getattr(sys, 'frozen', False):
                os.startfile(getattr(sys, "_MEIPASS"), 'open')
            else:
                os.startfile(G.userconfig_rootpath, 'open')
        cfg_log_folder_action.triggered.connect(do_open_cfg_dir)
        system_menu.addAction(cfg_log_folder_action)

        reset_geometry = QAction('Reset Window Size/Position', self)

        def do_reset_window_size():
            match G.device_type:
                case 'joystick':
                    x_pos = 150
                    y_pos = 130
                case 'pedals':
                    x_pos = 100
                    y_pos = 100
                case 'collective':
                    x_pos = 50
                    y_pos = 70
                case 'trimwheel':
                    x_pos = 40
                    y_pos = 30
            self.set_default_geometry()

        reset_geometry.triggered.connect(do_reset_window_size)
        system_menu.addAction(reset_geometry)

        exit_app_action = QAction('Quit TelemFFB', self)
        exit_app_action.triggered.connect(exit_application)
        system_menu.addAction(exit_app_action)

        if G.master_instance:
            """
            Create profiles menu - only for Master Instance
            """
            self.profiles_menu = self.menu.addMenu('Profiles')

            self.profile_manager_action = QAction('Profile Manager...', self)
            self.profile_manager_action.triggered.connect(self.show_profile_manager)
            self.profiles_menu.addAction(self.profile_manager_action)

            self.offline_config_action = QAction(r'Offline Profile\Sim Default\Class Default Mode', self)
            self.offline_config_action.triggered.connect(lambda: self.toggle_offline_mode(True))
            self.profiles_menu.addAction(self.offline_config_action)


        """ Create the "Utilities" menu """

        utilities_menu = self.menu.addMenu('Utilities')

        # Add the "Reset" action to the "Utilities" menu
        reset_action = QAction('Reset All Effects', self)
        reset_action.triggered.connect(self.reset_all_effects)
        utilities_menu.addAction(reset_action)

        self.update_action = QAction('Install Latest TelemFFB', self)
        self.update_action.triggered.connect(self.update_from_menu)
        # Updater menu entry intentionally hidden for now; keep the action and
        # backing updater code intact so it can be restored later.
        self.update_action.setDisabled(True)

        download_action = QAction('Download Other Versions', self)
        download_action.triggered.connect(lambda: self.open_url(dl_url))
        # Older-version download link is also hidden for now.

        self.reset_user_config_action = QAction('Reset User Config', self)
        self.reset_user_config_action.triggered.connect(self.reset_user_config)
        utilities_menu.addAction(self.reset_user_config_action)

        reload_action = QAction('Force Reload Aircraft (Ctrl+Shift+R)', self)
        reload_action.triggered.connect(self.force_reload_aircraft)
        utilities_menu.addAction(reload_action)

        if G.master_instance and G.system_settings.get('autolaunchMaster', 0):
            """
            Add Window menu to manage child instances if it is a master instance
            """
            self.window_menu = self.menu.addMenu('Window')

            def do_toggle_child_windows(toggle):
                if toggle == 'show':
                    G.ipc_instance.send_broadcast_message("SHOW WINDOW")
                elif toggle == 'hide':
                    G.ipc_instance.send_broadcast_message("HIDE WINDOW")

            self.show_children_action = QAction('Show Child Instance Windows')
            self.show_children_action.triggered.connect(lambda: do_toggle_child_windows('show'))
            self.window_menu.addAction(self.show_children_action)
            self.hide_children_action = QAction('Hide Child Instance Windows')
            self.hide_children_action.triggered.connect(lambda: do_toggle_child_windows('hide'))
            self.window_menu.addAction(self.hide_children_action)

        if G.child_instance:
            """
            Add Child instance window menu
            """
            self.window_menu = self.menu.addMenu('Window')
            self.hide_window_action = QAction('Hide Window')
            def do_hide_window():
                try:
                    self.hide()
                except Exception as e:
                    logging.error(f"EXCEPTION: {e}")
            self.hide_window_action.triggered.connect(do_hide_window)
            self.window_menu.addAction(self.hide_window_action)


        """ Add Log Menu """

        self.log_menu = self.menu.addMenu('Log')
        self.log_window_action = QAction("Open Console Log", self)

        def do_toggle_log_window():
            if G.log_window.isVisible():
                G.log_window.hide()
            else:
                G.log_window.move(self.x()+50, self.y()+100)
                G.log_window.show()

        self.log_window_action.triggered.connect(do_toggle_log_window)
        self.log_menu.addAction(self.log_window_action)


        """ Add app toolbar buttons for root menus and hide native menu bar. """

        self._install_app_toolbar()


        """ Create hidden device panel used for device scope/status state. """

        self.device_panel = DeviceIconPanel()
        self.device_panel.hide()

        if not G.master_instance:
            self.device_panel.set_devices([G.device_type])
            self.device_panel.set_device_status(G.device_type, "ok")
            self.device_panel.set_active_device(G.device_type)


        """ Create Status Panel """

        self.status_container = AppStatusWidget(master_instance=G.master_instance)

        self.status_container.cb_selectProfileCombo.currentIndexChanged.connect(self.on_profile_change)
        self.status_container.sim_status_label.set_waiting()
        self.status_container.set_joystick_connected(G.device_connection_status)

        def on_sims_changed(sim: SimTelemListener):
            self.status_container.update_enabled_sims(sim.name, sim.started)
            self.refresh_telem_status()


        """ Connect sim listeners to sim change function """

        G.sim_listeners.simStarted.connect(on_sims_changed)
        G.sim_listeners.simStopped.connect(on_sims_changed)


        """ Create new craft button - pops when unknown aircraft is detected """

        new_craft_layout = QVBoxLayout()
        new_craft_layout.setContentsMargins(0, 0, 0, 0)
        new_craft_layout.setSpacing(container_spacing)
        self.new_craft_button = QPushButton('Create/clone config for new aircraft')
        ncb_css = f"""QPushButton {{
                            background-color: {colorPrimary};
                            border: 0px solid transparent;
                            border-radius: {styles.default_button_border_radius}px;
                            color: white;
                            font: bold 14px "Roboto";
                            min-width: 10em;
                            padding: 5px 14px;
                        }}"""
        self.new_craft_button.setStyleSheet(ncb_css)
        self.new_craft_button.setCursor(QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        new_craft_layout.addWidget(self.new_craft_button)


        """ Add new craft button to main layout """

        layout.addLayout(new_craft_layout)
        self.new_craft_button.hide()


        """ Create offline config control area QWidget """

        self.offline_config_area = QWidget()
        self.offline_config_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        offline_config_layout = QVBoxLayout()  # vertical layout to hold both rows
        offline_config_layout.setContentsMargins(container_padding, container_padding, container_padding, container_padding)
        offline_config_layout.setSpacing(container_spacing)


        # First row layout (existing widgets)
        # --- Create the Offline Editor GroupBox ---
        self.offline_groupbox = QGroupBox("Offline Editor Setup")


        offline_layout = QVBoxLayout(self.offline_groupbox)
        offline_layout.setContentsMargins(
            container_padding,
            container_padding + 6,
            container_padding,
            container_padding
        )
        offline_layout.setSpacing(container_spacing)


        """ Create Offline controls layout """

        offline_grid_layout = QGridLayout()
        offline_grid_layout.setHorizontalSpacing(container_spacing)
        offline_grid_layout.setVerticalSpacing(container_spacing)

        # --- Labels ---
        offline_sim_lbl = QLabel('Sim:')
        offline_sim_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        offline_class_lbl = QLabel('Class:')
        offline_class_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        offline_name_lbl = QLabel('Aircraft Name:')
        offline_name_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        offline_profile_lbl = QLabel('Profile:')
        offline_profile_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Create filter box
        self.offline_name_filter = QLineEdit()
        self.offline_name_filter.setPlaceholderText("Filter")
        self.offline_name_filter.setEnabled(False)
        self.offline_name_filter.textChanged.connect(self.filter_offline_name_list)

        """ Add label widgets to layout """

        offline_grid_layout.addWidget(offline_sim_lbl, 0, 0)
        offline_grid_layout.addWidget(offline_class_lbl, 0, 1)
        offline_grid_layout.addWidget(offline_name_lbl, 0, 2)
        offline_grid_layout.addWidget(self.offline_name_filter, 0, 3)
        offline_grid_layout.addWidget(offline_profile_lbl, 0, 4)


        """ Create Offline controls combo boxes """

        # --- ComboBoxes ---
        self.offline_sim = QComboBox()
        self.offline_sim.addItems([''] + xmlutils.get_sims())
        self.offline_sim.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.offline_sim.setMinimumContentsLength(10)
        self.offline_sim.setEditable(False)
        self.offline_sim.currentTextChanged.connect(self.offline_sim_changed)

        self.offline_class = QComboBox()
        self.offline_class.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.offline_class.setMinimumContentsLength(15)
        self.offline_class.setEditable(False)
        self.offline_class.currentTextChanged.connect(self.offline_class_changed)

        self.offline_name = QComboBox()
        self.offline_name.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.offline_name.setMinimumContentsLength(20)
        self.offline_name.setEditable(False)
        self.offline_name.currentTextChanged.connect(self.offline_aircraft_changed)

        self.offline_profile = QComboBox()
        self.offline_profile.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.offline_profile.setMinimumContentsLength(15)
        self.offline_profile.setEditable(False)
        self.offline_profile.currentTextChanged.connect(self.offline_profile_changed)


        """ Add offline combo box controls to layout """

        offline_grid_layout.addWidget(self.offline_sim, 1, 0)
        offline_grid_layout.addWidget(self.offline_class, 1, 1)
        offline_grid_layout.addWidget(self.offline_name, 1, 2, 1, 2)
        offline_grid_layout.addWidget(self.offline_profile, 1, 4)

        # --- Column stretch ratios (1:2:4:2) ---
        offline_grid_layout.setColumnStretch(0, 1)
        offline_grid_layout.setColumnStretch(1, 2)
        offline_grid_layout.setColumnStretch(2, 4)
        offline_grid_layout.setColumnStretch(4, 2)

        offline_layout.addLayout(offline_grid_layout)


        """ Add layout for labels/buttons on bottom row of offline config area """

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(container_spacing)


        """ Create offline scope label """

        offline_scope = QLabel("<b>Offline Scope:   </b>")
        self.offline_scope_label = QLabel('None')


        """
        Create 'back to profile manager' button.  Only shows when edit is
        activated via profile manager
        """

        self.back_to_profile_mgr_button = QPushButton('Back to Profile Manager')
        self.back_to_profile_mgr_button.setVisible(False)
        self.back_to_profile_mgr_button.clicked.connect(self.back_to_profile_mgr)


        """ Create offline mode exit button """

        self.exit_offline_button = QPushButton()
        self.exit_offline_button.setText('Exit Offline Mode')
        self.exit_offline_button.clicked.connect(lambda: self.toggle_offline_mode(False))


        """ Add labels/buttons to bottom row layout """

        bottom_row.addWidget(offline_scope, alignment=Qt.AlignmentFlag.AlignLeft)
        bottom_row.addWidget(self.offline_scope_label, alignment=Qt.AlignmentFlag.AlignLeft)
        bottom_row.addStretch()
        bottom_row.addWidget(self.back_to_profile_mgr_button, alignment=Qt.AlignmentFlag.AlignRight)
        bottom_row.addWidget(self.exit_offline_button, alignment=Qt.AlignmentFlag.AlignRight)


        """ Add bottom row to layout """

        offline_layout.addLayout(bottom_row)


        """ Add items to layout """

        offline_config_layout.addWidget(self.offline_groupbox)


        """ Add layout to QWidget """

        self.offline_config_area.setLayout(offline_config_layout)


        """ Hide Offline config area (gets shown when it is enabled) """

        self.offline_config_area.hide()


        """ Add offline panel to main layout """

        layout.addWidget(self.offline_config_area)


        """ Add message widget before the main content. It collapses when empty. """

        layout.addWidget(self.status_container.message_widget)


        """ Create the main content row where the status drawer and settings live. """

        self.content_row = QWidget()
        self.content_row_layout = QHBoxLayout(self.content_row)
        self.content_row_layout.setContentsMargins(0, 0, 0, 0)
        self.content_row_layout.setSpacing(0)

        """ Create the monitor telemetry display panel """

        self.monitor_widget = QWidget()
        self.telem_area = QScrollArea()
        monitor_area_layout = QVBoxLayout()
        monitor_area_layout.setSpacing(container_spacing)
        monitor_area_layout.setContentsMargins(0, 0, 0, 0)
        self.telem_area.setWidgetResizable(True)
        self.telem_area.setMinimumHeight(100)


        """ Create the active effects display panel """

        self.effects_area = QScrollArea()
        self.effects_area.setWidgetResizable(True)
        self.effects_area.setMinimumHeight(100)

        # self.effects_area.setMaximumWidth(200)


        """ Create the Telemetry Label widget and set its properties """

        self.lbl_telem_data = QLabel()

        self.refresh_telem_status()

        self.lbl_telem_data.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_telem_data.setWordWrap(False)
        self.lbl_telem_data.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lbl_telem_data.setStyleSheet("""
            padding: 2px;
            font-family: Roboto;
        """)


        """ Set the QLabel widget as the widget inside the scroll area """

        self.telem_area.setWidget(self.lbl_telem_data)

        self.lbl_effects_data = QLabel("            ")
        self.effects_area.setWidget(self.lbl_effects_data)
        self.lbl_effects_data.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        telem_header_widget = QWidget()
        telem_header_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        telem_header_layout = QHBoxLayout(telem_header_widget)
        telem_header_layout.setContentsMargins(0, 0, 0, 0)
        telem_header_layout.setSpacing(container_spacing)
        
        self.telem_lbl = QLabel('Telemetry:')
        self.telem_filter = QLineEdit()
        self.telem_filter.setToolTip("Comma Separated, Case Insensitive list of telemetry items to show (e.g. 'aoa, ias, rpm')")


        """ Add placeholder for the filter """

        self.telem_filter.setPlaceholderText("Filter")
        self.telem_filter.setMaximumWidth(100)


        """ Add telemetry label and filter placeholder to the layout """
        telem_header_layout.addWidget(self.telem_lbl)
        telem_header_layout.addWidget(self.telem_filter)
        telem_header_layout.addStretch()  # Push everything to the left


        """ Add Active effects header label """

        self.effect_lbl = QLabel('Active Effects')
        """ Add telemetry monitor container to the monitor layout """

        telemetry_monitor_group = QGroupBox()
        telemetry_monitor_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        telemetry_monitor_layout = QVBoxLayout(telemetry_monitor_group)
        telemetry_monitor_layout.setContentsMargins(
            container_padding,
            container_padding,
            container_padding,
            container_padding,
        )
        telemetry_monitor_layout.setSpacing(container_spacing)
        telemetry_monitor_layout.addWidget(telem_header_widget)
        telemetry_monitor_layout.addWidget(self.telem_area, stretch=2)
        telemetry_monitor_layout.addWidget(self.effect_lbl)
        telemetry_monitor_layout.addWidget(self.effects_area, stretch=1)
        monitor_area_layout.addWidget(self.status_container)

        monitor_area_layout.addWidget(telemetry_monitor_group, stretch=1)

        self.monitor_widget.setLayout(monitor_area_layout)


        """ Create settings scroll area widget that will hold the settings page"""

        self.settings_area = NoKeyScrollArea()
        self.settings_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.settings_area.setWidgetResizable(True)


        """ Create widget to hold the settings layout """

        settings_widget = QWidget()


        """ Create settings layout instance """

        self.settings_layout = SettingsLayout(mainwindow=self)
        self.settings_layout.setContentsMargins(
            container_padding,
            container_padding,
            container_padding,
            container_padding
        )
        self.settings_layout.setSpacing(container_spacing)


        """ Add settings and monitor columns to the main splitter. """

        settings_widget.setLayout(self.settings_layout)
        self.settings_area.setWidget(settings_widget)
        self.waiting_telemetry_widget = self._create_waiting_telemetry_panel()
        self.settings_stack = QStackedWidget()
        self.settings_stack.setContentsMargins(0, 0, 0, 0)
        self.settings_stack.addWidget(self.waiting_telemetry_widget)
        self.settings_stack.addWidget(self.settings_area)
        self.settings_stack.setCurrentWidget(self.waiting_telemetry_widget)

        self.status_drawer = QWidget()
        self.status_drawer.setObjectName("statusDrawer")
        self.status_drawer.setMinimumWidth(0)
        self.status_drawer.setMaximumWidth(self.STATUS_DRAWER_WIDTH)
        status_drawer_layout = QVBoxLayout(self.status_drawer)
        status_drawer_layout.setContentsMargins(0, 0, 0, 0)
        status_drawer_layout.setSpacing(0)
        status_drawer_layout.addWidget(self.monitor_widget)

        self.status_drawer_thumb = VerticalDrawerThumbButton("TELEMETRY & STATUS")
        self.status_drawer_thumb.setObjectName("statusDrawerThumb")
        self.status_drawer_thumb.setStyleSheet(styles.STATUS_DRAWER_THUMB_STYLESHEET)
        self.status_drawer_thumb.setChecked(True)
        self.status_drawer_thumb.clicked.connect(self.toggle_status_drawer)
        self.status_drawer_gap = QWidget()
        self.status_drawer_gap.setFixedWidth(styles.default_container_padding//2)

        self.content_row_layout.addWidget(self.status_drawer_thumb)
        self.content_row_layout.addWidget(self.status_drawer_gap)
        self.content_row_layout.addWidget(self.status_drawer)
        self.content_row_layout.addSpacing(container_spacing)
        self.content_row_layout.addWidget(self.settings_stack, stretch=1)
        layout.addWidget(self.content_row, stretch=1)
        layout.addWidget(self._create_app_footer())

        """ Create central widget to whole the entire layout """

        central_widget = QWidget()
        central_widget.setObjectName("mainSurface")
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.layout = layout


        """ Setup hooks to update the telemetry and settings widgets """

        G.telem_manager.telemetryReceived.connect(self.on_update_telemetry)
        G.telem_manager.telemetryTimeout.connect(self.on_telemetry_timeout)
        G.telem_manager.aircraftUpdated.connect(self.update_settings)


        """  Load the stored window geometry from users registry keys """

        self.load_main_window_geometry()

        """ Add Debug Menu to the menu bar - control visibility with Alt+D shortcut or via debug key in registry """

        debug_shortcut = QShortcut(QKeySequence('Alt+D'), self)
        debug_shortcut.activated.connect(self.add_debug_menu)

        reload_shortcut = QShortcut(QKeySequence('Ctrl+Shift+R'), self)
        reload_shortcut.activated.connect(self.force_reload_aircraft)

        if G.system_settings.get('debug', False):
            # debug manu is disabled by default.  change debug = true (1) in registry to permanently enable
            self.add_debug_menu()

        """  Create configurator gain dialog for use during TelemFFB session and store object in globals """

        G.gain_override_dialog = ConfiguratorDialog(self)
        self._install_resize_event_filter()

    def _create_waiting_telemetry_panel(self):
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        panel = WaitingTelemetryPanel()
        panel.setObjectName("waitingTelemetryPanel")
        panel.setStyleSheet(styles.WAITING_TELEMETRY_STYLESHEET)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            styles.default_container_padding,
            styles.default_container_padding,
            styles.default_container_padding,
            styles.default_container_padding,
        )
        panel_layout.setSpacing(8)
        panel_layout.addStretch(1)

        self.waiting_telemetry_pulse = TelemetryPulseWidget(panel)

        title_label = QLabel("Waiting for telemetry")
        title_label.setObjectName("waitingTelemetryTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)

        subtitle_label = QLabel("from supported games...")
        subtitle_label.setObjectName("waitingTelemetrySubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        manage_games_button = QPushButton("Manage Supported Games")
        manage_games_button.setObjectName("manageSupportedGamesButton")
        manage_games_button.clicked.connect(
            lambda _checked=False: self.open_system_settings_dialog(show_simulator_setup=True)
        )

        panel_layout.addWidget(self.waiting_telemetry_pulse, alignment=Qt.AlignmentFlag.AlignHCenter)
        panel_layout.addSpacing(4)
        panel_layout.addWidget(title_label)
        panel_layout.addWidget(subtitle_label)
        panel_layout.addSpacing(28)
        panel_layout.addWidget(manage_games_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        panel_layout.addStretch(1)

        wrapper_layout.addWidget(panel)
        return wrapper

    def _show_waiting_for_telemetry(self):
        if getattr(G.settings_mgr, "offline_mode", False):
            self._show_settings_layout()
            return
        if hasattr(self, "settings_stack"):
            self.settings_stack.setCurrentWidget(self.waiting_telemetry_widget)
        if hasattr(self, "waiting_telemetry_pulse"):
            self.waiting_telemetry_pulse.start()

    def _show_settings_layout(self):
        if hasattr(self, "settings_stack"):
            self.settings_stack.setCurrentWidget(self.settings_area)
        if hasattr(self, "waiting_telemetry_pulse"):
            self.waiting_telemetry_pulse.stop()

    def toggle_status_drawer(self):
        self.set_status_drawer_open(self.status_drawer_thumb.isChecked(), animate=True)

    def set_status_drawer_open(self, open_drawer, animate=False):
        if not hasattr(self, "status_drawer"):
            return

        self.status_drawer_thumb.setChecked(open_drawer)
        self.status_drawer_gap.setVisible(open_drawer)
        self.status_drawer.setVisible(True)
        start_width = self.status_drawer.maximumWidth()
        end_width = self.STATUS_DRAWER_WIDTH if open_drawer else 0

        if not animate:
            self.status_drawer.setMaximumWidth(end_width)
            self.status_drawer.setVisible(open_drawer)
            return

        self.status_drawer_animation = QtCore.QPropertyAnimation(self.status_drawer, b"maximumWidth", self)
        self.status_drawer_animation.setDuration(180)
        self.status_drawer_animation.setStartValue(start_width)
        self.status_drawer_animation.setEndValue(end_width)
        self.status_drawer_animation.setEasingCurve(QtCore.QEasingCurve.Type.InOutCubic)
        if not open_drawer:
            self.status_drawer_animation.finished.connect(lambda: self.status_drawer.setVisible(False))
            self.status_drawer_animation.finished.connect(lambda: self.status_drawer_gap.setVisible(False))
        else:
            self.status_drawer_gap.setVisible(True)
        self.status_drawer_animation.start()

    def _create_app_footer(self):
        footer = QFrame()
        footer.setObjectName("appFooter")
        footer.setStyleSheet(styles.APP_FOOTER_STYLESHEET)
        footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(2, 0, 2, 0)
        footer_layout.setSpacing(6)

        self.footer_joystick_indicator = QLabel()
        self.footer_joystick_indicator.setFixedSize(8, 8)

        self.footer_joystick_label = QLabel("Joystick:")
        self.footer_joystick_label.setObjectName("footerJoystickLabel")

        self.footer_joystick_value = QLabel()
        self.footer_joystick_value.setObjectName("footerJoystickValue")

        joystick_status = QWidget()
        joystick_status_layout = QHBoxLayout(joystick_status)
        joystick_status_layout.setContentsMargins(0, 0, 0, 0)
        joystick_status_layout.setSpacing(6)
        joystick_status_layout.addWidget(self.footer_joystick_label)
        joystick_status_layout.addWidget(self.footer_joystick_value)
        joystick_status_layout.addWidget(self.footer_joystick_indicator)

        self.app_version_label = QLabel(self.APP_VERSION_LABEL)
        self.app_version_label.setObjectName("appVersionLabel")
        self.app_version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        footer_layout.addWidget(joystick_status, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        footer_layout.addStretch()
        footer_layout.addWidget(self.app_version_label, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._set_footer_joystick_connected(G.device_connection_status)
        return footer

    def _set_footer_joystick_connected(self, connected):
        if not hasattr(self, "footer_joystick_value"):
            return

        color = "#00994c" if connected else "#cc3333"
        self.footer_joystick_value.setText("Connected" if connected else "Disconnected")
        self.footer_joystick_value.setProperty("connected", "true" if connected else "false")
        self.footer_joystick_value.style().unpolish(self.footer_joystick_value)
        self.footer_joystick_value.style().polish(self.footer_joystick_value)
        self.footer_joystick_indicator.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)

    def _install_app_toolbar(self):
        self.app_toolbar = QtWidgets.QToolBar("App Toolbar", self)
        self.app_toolbar.setObjectName("appToolbar")
        self.app_toolbar.setMovable(False)
        self.app_toolbar.setFloatable(False)
        self.app_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.app_toolbar.setIconSize(QtCore.QSize(16, 16))
        toolbar_padding = styles.default_container_padding
        toolbar_row_spacing = max(styles.titlebar_row_spacing, toolbar_padding // 3)
        self.app_toolbar.setStyleSheet(f"""

        """)
        self._app_toolbar_menus = set()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.app_toolbar)

        self.toolbar_content = QWidget(self.app_toolbar)
        self.toolbar_content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar_content_layout = QHBoxLayout(self.toolbar_content)
        self.toolbar_content_layout.setContentsMargins(
            toolbar_padding,
            toolbar_padding//2,
            toolbar_padding,
            toolbar_padding//2,
        )
        self.toolbar_content_layout.setSpacing(toolbar_padding)
        self.app_toolbar.addWidget(self.toolbar_content)
        self.toolbar_content_layout.addWidget(self.toolbar_logo)

        self.toolbar_stack = QWidget(self.toolbar_content)
        self.toolbar_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar_stack_layout = QVBoxLayout(self.toolbar_stack)
        self.toolbar_stack_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_stack_layout.setSpacing(toolbar_row_spacing)
        self.toolbar_content_layout.addWidget(self.toolbar_stack, stretch=1)

        self.toolbar_window_controls = QHBoxLayout()
        self.toolbar_window_controls.setContentsMargins(0, 0, 0, 0)
        self.toolbar_window_controls.setSpacing(toolbar_row_spacing)
        self.toolbar_window_controls.addStretch()
        self.toolbar_stack_layout.addLayout(self.toolbar_window_controls)

        self.toolbar_menu_row = QHBoxLayout()
        self.toolbar_menu_row.setContentsMargins(0, 0, 0, 0)
        self.toolbar_menu_row.setSpacing(max(6, toolbar_padding // 2))
        self.toolbar_menu_row.addStretch()
        self.toolbar_stack_layout.addLayout(self.toolbar_menu_row)

        for control_type, label, tooltip, handler in (
            ("minimize", "−", "Minimize", self.showMinimized),
            ("maximize", "□", "Maximize / Restore", self._toggle_maximize_restore),
            ("close", "×", "Close", self.close),
        ):
            button = QPushButton(label, self.toolbar_content)
            button.setProperty("toolbarRole", "window-control")
            button.setProperty("controlType", control_type)
            button.setToolTip(tooltip)
            button.setCursor(QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            button.setText("")
            button.setIconSize(QtCore.QSize(styles.titlebar_control_symbol_size + 2, styles.titlebar_control_symbol_size + 2))
            button.clicked.connect(handler)
            self.toolbar_window_controls.addWidget(button)
            if control_type == "maximize":
                self.maximize_button = button
            else:
                button.setIcon(
                    self._toolbar_svg_icon(
                        self.WINDOW_CONTROL_ICON_PATHS[control_type],
                        "#000",
                        styles.titlebar_control_symbol_size + 2,
                    )
                )

        for action in self.menu.actions():
            menu = action.menu()
            if menu is not None:
                self._add_app_toolbar_menu(menu)
        self._update_toolbar_logo_pixmap()
        self._update_maximize_button()
        self.menu.hide()

    def _add_app_toolbar_menu(self, menu: QMenu):
        menu_id = id(menu)
        if not hasattr(self, "_app_toolbar_menus") or menu_id in self._app_toolbar_menus:
            return

        button = QPushButton(self)
        menu_label = menu.title().replace("&", "")
        button.setText(f"{styles.toolbar_menu_icon_text_gap}{menu_label}")
        button.setProperty("toolbarRole", "menu")
        button.setIcon(self._toolbar_menu_icon(menu_label))
        button.setIconSize(QtCore.QSize(16, 16))
        if menu is self.log_menu:
            button.clicked.connect(self.log_window_action.trigger)
        else:
            button.clicked.connect(
                lambda _, b=button, m=menu: m.popup(b.mapToGlobal(QtCore.QPoint(0, b.height())))
            )
        button.setCursor(QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.toolbar_menu_row.addWidget(button)
        self._app_toolbar_menus.add(menu_id)

    def _toolbar_menu_icon(self, menu_label: str) -> QIcon:
        icon_key = menu_label.strip().lower()
        icon_path = self.TOOLBAR_MENU_ICON_PATHS.get(icon_key, "image/qlementine/toolbar_menu.svg")
        return self._toolbar_svg_icon(icon_path, "#ffffff", 16)

    def _toolbar_svg_icon(self, relative_path: str, color: str, size: int) -> QIcon:
        icon_path = utils.get_resource_path(relative_path, prefer_root=True)
        base_icon = QIcon(icon_path)
        pixmap = base_icon.pixmap(QtCore.QSize(size, size))
        if pixmap.isNull():
            return base_icon

        tinted = QPixmap(pixmap.size())
        tinted.setDevicePixelRatio(pixmap.devicePixelRatio())
        tinted.fill(Qt.GlobalColor.transparent)

        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QColor(color))
        painter.end()

        return QIcon(tinted)

    def _toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._update_maximize_button()

    def _update_maximize_button(self):
        if hasattr(self, "maximize_button"):
            icon_name = "restore" if self.isMaximized() else "maximize"
            self.maximize_button.setIcon(
                self._toolbar_svg_icon(
                    self.WINDOW_CONTROL_ICON_PATHS[icon_name],
                    "#000",
                    styles.titlebar_control_symbol_size + 2,
                )
            )

    def _update_toolbar_logo_pixmap(self):
        if not hasattr(self, "toolbar_content") or self._toolbar_logo_source is None:
            return

        target_height = max(24, self.toolbar_stack.sizeHint().height() * .6)
        scaled_width = max(24, round(self._toolbar_logo_source.width() * target_height / self._toolbar_logo_source.height()))

        content_margins = self.toolbar_content_layout.contentsMargins()
        available_width = (
            self.toolbar_content.width()
            - content_margins.left()
            - content_margins.right()
            - self.toolbar_content_layout.spacing()
            - self.toolbar_stack.minimumSizeHint().width()
        )
        if available_width > 0 and available_width < scaled_width:
            scaled_width = max(24, available_width)
            target_height = max(24, round(self._toolbar_logo_source.height() * scaled_width / self._toolbar_logo_source.width()))

        toolbar_pixmap = self._toolbar_logo_source._scaled(scaled_width, target_height)
        self.toolbar_logo.setPixmap(toolbar_pixmap)
        self.toolbar_logo.setMaximumWidth(toolbar_pixmap.width())
        self.toolbar_logo.setFixedHeight(toolbar_pixmap.height())

    def _is_toolbar_drag_region(self, pos: QtCore.QPoint):
        if not hasattr(self, "app_toolbar") or not self.app_toolbar.geometry().contains(pos):
            return False

        widget = self.childAt(pos)
        if widget is None:
            return True

        if isinstance(widget, (QPushButton, QToolButton, QLineEdit, QComboBox)):
            return False

        return widget is self.toolbar_logo or self.toolbar_content.isAncestorOf(widget) or widget is self.toolbar_content

    def _install_resize_event_filter(self):
        if self._resize_event_filter_installed:
            return

        app = QApplication.instance()
        if app is None:
            return

        app.installEventFilter(self)
        self._resize_event_filter_installed = True
        self._set_resize_mouse_tracking(self)

    def _set_resize_mouse_tracking(self, root: QWidget):
        root.setMouseTracking(True)
        for child in root.findChildren(QWidget):
            child.setMouseTracking(True)

    def _event_local_pos(self, watched: QWidget, event):
        global_position = getattr(event, "globalPosition", None)
        if callable(global_position):
            return self.mapFromGlobal(global_position().toPoint())

        local_position = getattr(event, "position", None)
        if callable(local_position):
            return self.mapFromGlobal(watched.mapToGlobal(local_position().toPoint()))

        return None

    def _get_resize_edges(self, pos: QtCore.QPoint) -> QtCore.Qt.Edge:
        if self.isMaximized() or self.isFullScreen():
            return QtCore.Qt.Edge(0)

        rect = self.rect()
        border = self._resize_border
        edges = QtCore.Qt.Edge(0)

        if pos.x() <= border:
            edges |= QtCore.Qt.Edge.LeftEdge
        elif pos.x() >= rect.width() - border:
            edges |= QtCore.Qt.Edge.RightEdge

        if pos.y() <= border:
            edges |= QtCore.Qt.Edge.TopEdge
        elif pos.y() >= rect.height() - border:
            edges |= QtCore.Qt.Edge.BottomEdge

        return edges

    def _cursor_for_resize_edges(self, edges: QtCore.Qt.Edge):
        if edges in (QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.TopEdge, QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.BottomEdge):
            return QtCore.Qt.CursorShape.SizeFDiagCursor
        if edges in (QtCore.Qt.Edge.RightEdge | QtCore.Qt.Edge.TopEdge, QtCore.Qt.Edge.LeftEdge | QtCore.Qt.Edge.BottomEdge):
            return QtCore.Qt.CursorShape.SizeBDiagCursor
        if edges in (QtCore.Qt.Edge.LeftEdge, QtCore.Qt.Edge.RightEdge):
            return QtCore.Qt.CursorShape.SizeHorCursor
        if edges in (QtCore.Qt.Edge.TopEdge, QtCore.Qt.Edge.BottomEdge):
            return QtCore.Qt.CursorShape.SizeVerCursor
        return None

    def _update_resize_cursor(self, pos: QtCore.QPoint):
        edges = self._get_resize_edges(pos)
        cursor_shape = self._cursor_for_resize_edges(edges)
        if cursor_shape is None:
            self.unsetCursor()
        else:
            self.setCursor(QCursor(cursor_shape))
        return edges

    def _start_system_resize(self, edges: QtCore.Qt.Edge) -> bool:
        if not edges or self.isMaximized() or self.isFullScreen():
            return False

        window_handle = self.windowHandle()
        if window_handle is None:
            return False

        return window_handle.startSystemResize(edges)

    def eventFilter(self, watched, event):
        if isinstance(watched, QWidget) and (watched is self or self.isAncestorOf(watched)):
            event_type = event.type()

            if event_type == QtCore.QEvent.Type.MouseMove:
                local_pos = self._event_local_pos(watched, event)
                if local_pos is not None and not self._toolbar_drag_active:
                    self._update_resize_cursor(local_pos)

            elif event_type == QtCore.QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                local_pos = self._event_local_pos(watched, event)
                if local_pos is not None:
                    resize_edges = self._get_resize_edges(local_pos)
                    if resize_edges and self._start_system_resize(resize_edges):
                        self._resize_edges = resize_edges
                        event.accept()
                        return True

            elif event_type == QtCore.QEvent.Type.MouseButtonRelease:
                self._resize_edges = QtCore.Qt.Edge(0)
                local_pos = self._event_local_pos(watched, event)
                if local_pos is not None and not self._toolbar_drag_active:
                    self._update_resize_cursor(local_pos)

        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.LeftButton:
            resize_edges = self._get_resize_edges(pos)
            if resize_edges and self._start_system_resize(resize_edges):
                self._resize_edges = resize_edges
                event.accept()
                return
        if event.button() == Qt.MouseButton.LeftButton and self._is_toolbar_drag_region(pos):
            self._toolbar_drag_active = True
            self._toolbar_drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._update_resize_cursor(event.position().toPoint())
        if self._toolbar_drag_active and event.buttons() & Qt.MouseButton.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self._toolbar_drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._toolbar_drag_active = False
        self._resize_edges = QtCore.Qt.Edge(0)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_toolbar_drag_region(event.position().toPoint()):
            self._toggle_maximize_restore()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_toolbar_logo_pixmap()
        self._update_maximize_button()

    def leaveEvent(self, event):
        if not self._toolbar_drag_active:
            self.unsetCursor()
        super().leaveEvent(event)

    def get_active_buttons(self):
        input_data = HapticEffect.device.get_input()
        if input_data is not None:
            btns = input_data.getPressedButtons()
            if btns != G.active_buttons:
                # only send if pressed buttons has changed
                G.active_buttons = btns
                if G.master_instance:
                    G.ipc_instance.send_broadcast_message(f"MASTER_BUTTONS:{G.active_buttons}")
                else:
                    G.ipc_instance.send_message(f"BUTTONS:{G.device_type}_{G.active_buttons}")

    def add_system_tray(self):
        self.tray_icon.setIcon(QIcon(utils.get_resource_path('image/zTelemIcon.png', prefer_root=True)))
        self.tray_icon.setToolTip("zTelem")

        # Create the tray menu
        tray_menu = QMenu()
        show_action = QAction("Show Window", self)

        def do_show_main_window(trigger):
            if isinstance(trigger, QSystemTrayIcon.ActivationReason):
                if trigger == QSystemTrayIcon.ActivationReason.DoubleClick:
                    self.showNormal()  # Restore the window to its normal state if minimized
                    self.show()
                    self.raise_()
                    self.activateWindow()
            elif isinstance(trigger, str) and trigger == "show":
                self.showNormal()  # Restore the window to its normal state if minimized
                self.show()
                self.raise_()
                self.activateWindow()
            if G.is_exe:
                start_with_windows_action.setChecked(self.toggle_start_with_windows())
            start_minimized_action.setChecked(G.system_settings.get('startToTray', False))
            send_to_tray_action.setChecked(G.system_settings.get('closeToTray', False))

        self.tray_icon.activated.connect(do_show_main_window)
        show_action.triggered.connect(lambda: do_show_main_window('show'))

        tray_menu.addAction(show_action)

        # Create the "Options" menu
        options_menu = QMenu("Options", self)

        # Setup Start With Windows menu option
        if G.is_exe:
            start_with_windows_action = QAction("Start With Windows", self)
            start_with_windows_action.setCheckable(True)
            start_with_windows_action.setChecked(G.system_settings.get('startWithWindows', False))

            def do_toggle_set_start_with_windows(checked):
                self.toggle_start_with_windows(checked)

            start_with_windows_action.triggered.connect(lambda checked: do_toggle_set_start_with_windows(checked))

            options_menu.addAction(start_with_windows_action)

        # Setup Start Minimized menu option
        start_minimized_action = QAction("Start in Tray", self)
        start_minimized_action.setCheckable(True)
        start_minimized_action.setChecked(G.system_settings.get('startToTray', False))

        def do_toggle_set_start_minimized(checked):
            G.system_settings.setValue('startToTray', checked)

        start_minimized_action.triggered.connect(lambda checked: do_toggle_set_start_minimized(checked))

        options_menu.addAction(start_minimized_action)

        # Setup Send to Tray menu option
        send_to_tray_action = QAction("Closing App Sends to Tray", self)
        send_to_tray_action.setCheckable(True)
        send_to_tray_action.setChecked(G.system_settings.get('closeToTray', False))

        def do_toggle_set_send_to_tray(checked):
            G.system_settings.setValue('closeToTray', checked)

        send_to_tray_action.triggered.connect(lambda checked: do_toggle_set_send_to_tray(checked))

        options_menu.addAction(send_to_tray_action)

        tray_menu.addMenu(options_menu)

        # Create the "Instances" menu
        if G.launched_instances:
            show_menu = QMenu("Instances", self)
            show_child_window_action = {}
            for d in ["joystick", "pedals", "collective", 'trimwheel']:
                if d in G.launched_instances:
                    def do_show_child_window(child=d):
                        G.ipc_instance.send_broadcast_message(f'SHOW WINDOW:{child}')

                    show_child_window_action[d] = QAction(f'Show {d.capitalize()} Instance', self)
                    show_child_window_action[d].triggered.connect(lambda _, child=d: do_show_child_window(child))
                    show_menu.addAction(show_child_window_action[d])
            tray_menu.addMenu(show_menu)

        quit_action = QAction("Quit TelemFFB", self)
        quit_action.triggered.connect(exit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        # Show the tray icon
        self.tray_icon.show()
        if self.isHidden():
            #  don't show, send message to tray icon that will pop to notify user that TelemFFB is running in Tray
            icon = QIcon(utils.get_resource_path('image/zTelemIcon.png', prefer_root=True))
            self.pop_tray_notification(
                None,
                "TelemFFB is running in the system tray.  Double-Click the VPforce Icon to show or right click to set options in the context menu",
                5
            )

    def toggle_start_with_windows(self, set_enabled=None):
        exe_path = sys.executable
        reg_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        reg_key_name = "zTelem"

        try:
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
            if set_enabled is None:
                #if no state defined, just querey and return state
                try:
                    value, _ = winreg.QueryValueEx(reg_key, reg_key_name)
                    winreg.CloseKey(reg_key)
                    return True
                except FileNotFoundError:
                    return False
            else:
                if set_enabled:
                    winreg.SetValueEx(reg_key, reg_key_name, 0, winreg.REG_SZ, exe_path)
                else:
                    try:
                        winreg.DeleteValue(reg_key, reg_key_name)
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(reg_key)
        except FileNotFoundError:
            if set_enabled:
                reg_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_key_path)
                winreg.SetValueEx(reg_key, reg_key_name, 0, winreg.REG_SZ, exe_path)
                winreg.CloseKey(reg_key)

    def add_instance_log_menu(self):
        self.log_menu.addAction(self.log_window_action)
        if G.master_instance and G.system_settings.get('autolaunchMaster', 0):
            self.child_log_menu = self.log_menu.addMenu('Open Child Logs')

            self.log_action = {}
            for d in ["joystick", "pedals", "collective", 'trimwheel']:
                if d in G.launched_instances:
                    def do_show_child_log(child=d):
                        G.ipc_instance.send_broadcast_message(f'SHOW LOG:{child}')

                    self.log_action[d] = QAction(f'{d} Log'.capitalize())
                    self.log_action[d].triggered.connect(lambda _, child=d: do_show_child_log(child))
                    self.child_log_menu.addAction(self.log_action[d])

    def test_function(self):
        self.set_scrollbar(400)

    def refresh_telem_status(self):
        dcs_enabled = G.system_settings.get('enableDCS')
        il2_enabled = G.system_settings.get('enableIL2')
        msfs_enabled = G.system_settings.get('enableMSFS')
        xplane_enabled = G.system_settings.get('enableXPLANE')
        bms_enabled = G.system_settings.get('enableBMS')

        # Convert True/False to "enabled" or "disabled"
        dcs_status = "Enabled" if dcs_enabled else "Disabled"
        il2_status = "Enabled" if il2_enabled else "Disabled"
        msfs_status = "Enabled" if msfs_enabled else "Disabled"
        xplane_status = "Enabled" if xplane_enabled else "Disabled"
        bms_status = "Enabled" if bms_enabled else "Disabled"

        self.lbl_telem_data.setText(
            f"Waiting for data...\n\n"
            f"DCS     : {dcs_status}\n"
            f"IL2     : {il2_status}\n"
            f"MSFS    : {msfs_status}\n"
            f"X-Plane : {xplane_status}\n"
            f"BMS     : {bms_status}\n\n"
            "Enable or Disable in System -> System Settings"
        )

    def force_reload_aircraft(self):
        G.force_reload_aircraft_trigger = True
        G.telem_manager.currentAircraftName = None
        logging.info("Force Reload (Ctrl+Shift+R) initiated.  Reloading config and re-pushing configurator file (if applicable)")
        if G.master_instance:
            G.ipc_instance.send_broadcast_message("RELOAD AIRCRAFT")


    def add_debug_menu(self):
        # debug mode
        for action in self.menu.actions():
            if action.text() == "Debug":
                return
        debug_menu = self.menu.addMenu("Debug")

        teleplot_action = QAction("Teleplot Setup", self)
        def do_open_teleplot_setup_dialog():
            dialog = TeleplotSetupDialog(self)
            dialog.exec()
        teleplot_action.triggered.connect(do_open_teleplot_setup_dialog)
        debug_menu.addAction(teleplot_action)

        show_simvar_action = QAction("Show simvar in telem window", self)
        def do_toggle_simvar_telemetry():
            self.show_simvars = not self.show_simvars
            show_simvar_action.setChecked(self.show_simvars)

        show_simvar_action.triggered.connect(do_toggle_simvar_telemetry)
        show_simvar_action.setCheckable(True)
        debug_menu.addAction(show_simvar_action)

        show_order_action = QAction("Show settings order numbering", self)
        def do_toggle_order_numbering():
            SettingsLayout.show_order_debug = not  SettingsLayout.show_order_debug
            show_order_action.setChecked(SettingsLayout.show_order_debug)

        show_order_action.triggered.connect(do_toggle_order_numbering)
        show_order_action.setCheckable(True)
        debug_menu.addAction(show_order_action)

        show_replaced = QAction("Show settings source", self)
        def do_toggle_replaced():
            SettingsLayout.show_replaced = not SettingsLayout.show_replaced
            show_replaced.setChecked(SettingsLayout.show_replaced)

        show_replaced.triggered.connect(do_toggle_replaced)
        show_replaced.setCheckable(True)
        debug_menu.addAction(show_replaced)


        show_settingname_action = QAction("Show settings internal name", self)
        def do_toggle_settingsnames():
            SettingsLayout.show_settings_names = not  SettingsLayout.show_settings_names
            show_settingname_action.setChecked(SettingsLayout.show_settings_names)

        show_settingname_action.triggered.connect(do_toggle_settingsnames)
        show_settingname_action.setCheckable(True)
        debug_menu.addAction(show_settingname_action)

        configurator_settings_action = QAction('Configurator Gain Override', self)
        def do_open_configurator_dialog():
            dialog = ConfiguratorDialog(self)
            dialog.raise_()
            dialog.activateWindow()
            dialog.show()
        configurator_settings_action.triggered.connect(do_open_configurator_dialog)
        debug_menu.addAction(configurator_settings_action)

        sc_overrides_action = QAction('SimConnect Overrides Editor', self)
        def do_open_sc_override_dialog():
            dialog = SCOverridesEditor(self)
            dialog.raise_()
            dialog.activateWindow()
            dialog.show()
        # dialog.exec_()
        sc_overrides_action.triggered.connect(do_open_sc_override_dialog)
        debug_menu.addAction(sc_overrides_action)

        test_update = QAction('Test updater', self)
        def do_test_update():
            self._update_available = True
            self.perform_update()
        test_update.triggered.connect(do_test_update)
        debug_menu.addAction(test_update)

        if G.master_instance:
            custom_userconfig_action = QAction("Load Custom User Config", self)
            custom_userconfig_action.triggered.connect(lambda: utils.load_custom_userconfig())
            debug_menu.addAction(custom_userconfig_action)

        self._add_app_toolbar_menu(debug_menu)

    def set_scrollbar(self, pos):
        self.settings_area.verticalScrollBar().setValue(pos)

    @pyqtSlot(bool)
    def update_device_status(self, connected):
        G.device_connection_status = connected
        status = "ACTIVE" if connected else "DISCONNECTED"
        self.device_panel.set_device_status(G.device_type, status)
        self.status_container.set_joystick_connected(connected)
        self._set_footer_joystick_connected(connected)

    @pyqtSlot(str, str)
    def update_child_status(self, device, status):
        # self.instance_status_row.set_status(device, status)
        self.device_panel.set_device_status(device, status)

    def show_child_settings(self):
        G.ipc_instance.send_broadcast_message("SHOW SETTINGS")

    def reset_user_config(self):
        ans = QMessageBox.warning(self, "Caution", "Are you sure you want to proceed?  All contents of your user configuration will be erased\n\nA backup of the configuration will be generated containing the current timestamp.", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

        if ans == QMessageBox.StandardButton.Ok:
            try:
                # Get the current timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')

                backup_path = os.path.join(G.userconfig_rootpath, 'cfg_backup')
                os.makedirs(backup_path, exist_ok=True)

                # Create the backup file name with the timestamp
                backup_file = os.path.join(backup_path, ('userconfig_' + timestamp + '.bak'))

                # Copy the file to the backup file
                shutil.copy(G.userconfig_path, backup_file)

                logging.debug(f"Backup created: {backup_file}")

            except Exception as e:
                logging.error(f"Error creating backup: {str(e)}")
                QMessageBox.warning(self, 'Error', f'There was an error resetting the config:\n\n{e}')
                return

            os.remove(G.userconfig_path)
            utils.create_empty_userxml_file(G.userconfig_path)

            logging.info(f"User config Reset:  Backup file created: {backup_file}")
        else:
            return


    def setup_master_instance(self):
        # self.show_device_logo()
        # self.enable_device_logo_click(True)

        #self.devicetype_label.hide()
        current_title = self.windowTitle()
        # new_title = f"** MASTER INSTANCE ** {current_title}"
        # self.setWindowTitle(new_title)
        # self.instance_status_row.show()
        # if "joystick" in G.launched_instances:
        #     self.instance_status_row.joystick_status_icon.show()
        # if "pedals" in G.launched_instances:
        #     self.instance_status_row.pedals_status_icon.show()
        # if "collective" in G.launched_instances:
        #     self.instance_status_row.collective_status_icon.show()
        # if 'trimwheel' in G.launched_instances:
        #     self.instance_status_row.trimwheel_status_icon.show()
        self.add_instance_log_menu()
        self.add_system_tray()
        d_list = [G.device_type]
        for d in G.launched_instances:
            d_list.append(d)
        self.device_panel.set_devices(d_list)
        self.device_panel.set_device_status(G.device_type, "ok")
        self.device_panel.DeviceClicked.connect(self.change_config_scope)
        self.device_panel.set_active_device(G.device_type)


    def show_device_logo(self):
        self.devicetype_label.show()

    def enable_device_logo_click(self, state):
        hover_color = "#444444" if G.useDarkMode else "#DCDCDC"
        self.devicetype_label.setClickable(state)
        self.devicetype_label.setStyleSheet(
            f"""
               QLabel {{
                   border-radius: 4px;
               }}
               QLabel:hover {{
                   background-color: {hover_color};
               }}
               """
        )

    def device_logo_click_event(self):
        # print("External function executed on label click")
        # print(G.current_device_config_scope)
        def check_instance(name):
            return name in G.launched_instances or G.device_type == name
        if G.current_device_config_scope == 'joystick':
            if check_instance("pedals"):
                self.change_config_scope(2)
            elif check_instance("collective"):
                self.change_config_scope(3)
            elif check_instance("trimwheel"):
                self.change_config_scope(4)
        elif G.current_device_config_scope == 'pedals':
            if check_instance("collective"):
                self.change_config_scope(3)
            elif check_instance("trimwheel"):
                self.change_config_scope(4)
            elif check_instance("joystick"):
                self.change_config_scope(1)
        elif G.current_device_config_scope == 'collective':
            if check_instance("trimwheel"):
                self.change_config_scope(4)
            elif check_instance("joystick"):
                self.change_config_scope(1)
            elif check_instance("pedals"):
                self.change_config_scope(2)
        elif G.current_device_config_scope == 'trimwheel':
            if check_instance("joystick"):
                self.change_config_scope(1)
            elif check_instance("pedals"):
                self.change_config_scope(2)
            elif check_instance("collective"):
                self.change_config_scope(3)

    def update_version_result(self, vers, url):
        self.latest_version = vers

        is_exe = getattr(sys, 'frozen', False)

        if vers == "uptodate":
            status_text = "Up To Date"
            self.update_action.setDisabled(True)
            logging.info("Version Status: %s", status_text)
        elif vers == "error":
            status_text = "UNKNOWN"
            logging.info("Version Status: %s", status_text)
        elif vers == 'dev':
            if is_exe:
                logging.info("Version Status: Development Build")
            else:
                logging.info("Version Status: Development - Clean source")

        elif vers == 'needsupdate':
            logging.info("Version Status: Out of Date Source - Git pull needed")
        
        elif vers == 'dirty':
            logging.info("Version Status: Development - Modified Source")

        else:
            # print(_update_available)
            self._update_available = True
            logging.info(f"<<<<Update available - new version={vers}>>>>")

            self.update_action.setDisabled(False)
            self.update_action.setText("Install Latest TelemFFB")
            logging.info("Version Status: New version %s is available: %s", vers, url)

        self.perform_update(auto=True)

    def change_config_scope(self, _arg):
        if isinstance(_arg, str):
            if 'joystick' in _arg: arg = 1
            elif 'pedals' in _arg: arg = 2
            elif 'collective' in _arg: arg = 3
            elif 'trimwheel' in _arg: arg = 4
        else:
            arg = _arg

        types = {
            1 : "joystick",
            2 : "pedals",
            3 : "collective",
            4 : "trimwheel"
        }

        xmlutils.update_vars(types[arg], G.userconfig_path, G.defaults_path)
        G.current_device_config_scope = types[arg]
        self.device_panel.set_active_device(types[arg])

        # pixmap = HiDpiPixmap(utils.get_device_logo(G.current_device_config_scope))
        # self.devicetype_label.setPixmap(pixmap)
        #self.devicetype_label.setFixedSize(pixmap.width(), pixmap.height())

        if G.master_instance:
            self.effect_lbl.setText(f'Active Effects for: {G.current_device_config_scope}')
        self.settings_layout.reload_caller()

    def resize_offline_combos(self):
        """
            Dynamically resizes the minimum width of all offline mode combo boxes
            based on the widest item in each. Adds 50 pixels padding to ensure space.

            This ensures no items are truncated in display and helps with layout alignment.
            """
        for combo in [self.offline_sim, self.offline_class, self.offline_name, self.offline_profile]:
            metrics = QFontMetrics(combo.font())
            max_width = 0

            for i in range(combo.count()):
                text = combo.itemText(i)
                width = metrics.horizontalAdvance(text)
                max_width = max(max_width, width)

            # Add 2 pixels for spacing and set minimum width
            combo.setMinimumWidth(max_width + 50)

        self.settings_layout.reload_caller()

    def show_profile_manager(self):
        xmlutils.update_roots() # make sure roots get updated in case state is timedout and file has changed
        self.profile_mgr_dialog = ProfileManagerDialog(self)
        self.profile_mgr_dialog.raise_()
        self.profile_mgr_dialog.activateWindow()
        self.profile_mgr_dialog.show()

    def exit_offline_mode(self):
        self.toggle_offline_mode(False)
        if self.profile_mgr_dialog:
            self.profile_mgr_dialog.close()


    def back_to_profile_mgr(self):
        self.back_to_profile_mgr_button.setVisible(False)
        try:
            # in case it somehow got closed
            self.profile_mgr_dialog.show()
        except:
            QMessageBox.warning(self, "Profile Manager", "IDK WHY THIS ERROR HAPPENED")
            pass
        self.toggle_offline_mode(False)


    @pyqtSlot(bool)
    def toggle_offline_mode(self, state):
        if state == G.settings_mgr.offline_mode:
            # if already in the same state, do nothing
            return
        if not state:
            # Exiting Offline editing mode

            G.settings_mgr.go_online()

            # clear the layout after going back online
            G.main_window.settings_layout.clear_layout()

            # reset the craft area text to default
            self.status_container.reset()
            self.settings_layout.reload_caller()
            if self.telemetry_timed_out:
                self._show_waiting_for_telemetry()
        else:
            # Entering offline editing mode
            G.settings_mgr.go_offline()
            self.status_container.set_offline("None")
            self._show_settings_layout()
            # clear the layout in case an aircraft was previously loaded live
            G.main_window.settings_layout.clear_layout()

            # Block signals so we don't trigger text change on .clear() calls
            self.offline_name.blockSignals(True)
            self.offline_class.blockSignals(True)
            self.offline_name.blockSignals(True)

            # clear contents of combo boxes so they can be repopulated
            self.offline_name.clear()
            self.offline_class.clear()
            self.offline_sim.clear()

            # unblock signals
            self.offline_name.blockSignals(False)
            self.offline_class.blockSignals(False)
            self.offline_name.blockSignals(False)

            # build sim list
            sims = [''] + xmlutils.get_sims()
            self.offline_sim.addItems(sims)

        if G.master_instance:
            # Show the offline mode widgets, but only for master instance
            self.offline_config_area.setVisible(state)

            # Send command to chile instance to replicate actions
            G.ipc_instance.send_broadcast_message(f"TOGGLE OFFLINE:{state}")

    @pyqtSlot(str, str, str, str)
    def load_single_offline_model(self, sim, cls, model, profile):

        self.toggle_offline_mode(True)
        for cb in {self.offline_sim, self.offline_class, self.offline_name, self.offline_profile}:
            cb.blockSignals(True)
            cb.clear()
            cb.addItem('')

        sim_list = xmlutils.get_sims()
        for s in sim_list:
            self.offline_sim.addItem(s)
        self.offline_sim.setCurrentText(sim)

        cls_list = xmlutils.get_classes_for_sim(sim)
        for c in cls_list:
            self.offline_class.addItem(c)
        self.offline_class.setCurrentText(cls)

        model_list = xmlutils.read_models(sim, cls)
        self.all_offline_models = model_list
        self.filter_offline_name_list(self.offline_name_filter.text())
        self.offline_name.setCurrentText(model)

        profile_list = xmlutils.get_available_profiles(sim, cls, model)
        self.offline_profile.clear()
        for p in profile_list:
            if p != 'Built-In':
                self.offline_profile.addItem(p)
        self.offline_profile.setCurrentText(profile)
        self.offline_profile_changed(profile)

        for cb in {self.offline_sim, self.offline_class, self.offline_name, self.offline_profile}:
            cb.blockSignals(False)

        G.settings_mgr.offline_scope = 'MODEL'

        self.force_sim_aircraft()
        if G.master_instance:
            self.back_to_profile_mgr_button.setVisible(True)
            args = [sim, cls, model, profile]
            G.ipc_instance.send_broadcast_message(f"SHOW_OFFLINE_MODEL:{json.dumps(args)} ")
            self.resize_offline_combos()



    def update_offline_labeling(self):
        pass

    def offline_sim_changed(self, sim=None):
        """
            Triggered when the offline 'Sim' combo box changes.

            Updates all related combo boxes (class, aircraft, profile),
            sets the configuration scope, and broadcasts the change
            if in master mode.

            Args:
                sim (str, optional): The selected simulation name. If None or empty,
                                     resets the offline editing UI.
            """
        self.offline_name.blockSignals(True)
        self.offline_name_filter.blockSignals(True)
        self.offline_class.blockSignals(True)
        self.offline_name.clear()
        self.offline_name_filter.clear()
        self.offline_class.clear()
        self.offline_name.blockSignals(False)
        self.offline_name_filter.blockSignals(False)
        self.offline_class.blockSignals(False)
        if sim is None or sim == '':
            # if sim combobox is cleared, reset everything and clear the layout
            self.offline_class.clear()  # clear class field
            self.offline_name.clear()
            self.offline_profile.clear()
            self.settings_layout.clear_layout()
            self.offline_scope_label.setText(f"None")
            self.offline_name_filter.setEnabled(False)
            return
        self.offline_name_filter.setEnabled(True)
        self.offline_class.clear()  #clear class field
        self.offline_class.addItem('')
        self.offline_name.clear()
        #self.offline_name.setMaximumWidth(200)
        self.offline_profile.clear()
        classes = xmlutils.get_classes_for_sim(sim)  # get classes based on chosen sim

        for class_name in classes:
            self.offline_class.addItem(class_name)  #populate class combobox based on results

        self.offline_name.clear()  #clear aircraft selection combobox

        model_list = xmlutils.read_models(sim)
        self.all_offline_models = model_list
        self.filter_offline_name_list(self.offline_name_filter.text())

        if G.master_instance:
            # send to child instances to mimic action
            G.ipc_instance.send_broadcast_message(f"OFFLINE_SIM:{self.offline_sim.currentText()}")

        G.settings_mgr.offline_scope = 'SIM'  # set config scope to SIM
        self.offline_scope_label.setText(f"Editing SIM Defaults ({sim})")

        self.resize_offline_combos()
        self.force_sim_aircraft() # load settings based on sim

    def offline_class_changed(self, class_name):
        self.offline_name_filter.blockSignals(True)
        self.offline_name_filter.clear()
        self.offline_name_filter.blockSignals(False)
        model_list = xmlutils.read_models(self.offline_sim.currentText(), class_name)  # get all available models based on sim and class
        self.all_offline_models = model_list
        self.offline_name.clear()  # clear the aircraft selection combobox
        self.offline_profile.clear()
        self.filter_offline_name_list(self.offline_name_filter.text())

        if G.master_instance:
            # send to child instances to mimic action
            G.ipc_instance.send_broadcast_message(f"OFFLINE_CLASS:{self.offline_class.currentText()}")
        if class_name == '':
            # reset back to sim mode if class field is cleared
            self.offline_sim_changed(self.offline_sim.currentText())
        else:
            G.settings_mgr.offline_scope = 'CLASS' # set config scope to CLASS
            self.offline_scope_label.setText(f"Editing Class Defaults ({class_name})")

        self.resize_offline_combos()
        self.force_sim_aircraft() # load settings based on class and currently selected sim

    def offline_aircraft_changed(self, ac_name=None):
        cfg, cls = G.telem_manager.get_aircraft_config(ac_name, self.offline_sim.currentText()) # get class based on selected aircraft
        profiles = xmlutils.get_available_profiles(self.offline_sim.currentText(), self.offline_class.currentText(), ac_name)
        self.offline_profile.setEnabled(True)
        self.offline_profile.clear()

        for profile_name in profiles:
            if profile_name != 'Built-In':
                self.offline_profile.addItem(profile_name)

        if not self.offline_profile.count():
            self.offline_profile.addItem('Auto User')  # manually add 'Auto User' so it is at the top and always present even if there is not yet a Auto User Profile
            xmlutils.update_active_profile_entry(sim=self.offline_sim.currentText(), cls=cls, model=ac_name, new_profile="Auto User")
        self.offline_class.blockSignals(True)  # block signals to prevent triggering of offline_class_changed
        self.offline_class.setCurrentText(cls) # set class combobox to learned class from aircraft config
        self.offline_class.blockSignals(False)  # unblock signals

        if ac_name == '':
            self.offline_class_changed(self.offline_class.currentText())
        else:
            G.settings_mgr.offline_scope = 'MODEL'
            self.offline_scope_label.setText(f"Editing Aircraft ({ac_name} - {self.offline_profile.currentText()})")

        if G.master_instance:
            G.ipc_instance.send_broadcast_message(f'OFFLINE_AC:{self.offline_name.currentText()}')

        self.resize_offline_combos()
        self.force_sim_aircraft()

    def offline_profile_changed(self, profile):
        # self.update_craft_text_block(profile=profile)
        if not profile:
            return
        G.settings_mgr.offline_scope = 'MODEL'
        self.resize_offline_combos()
        self.force_sim_aircraft()
        if G.master_instance:
            # send to child instances to mimic action
            G.ipc_instance.send_broadcast_message(f"OFFLINE_PROFILE:{profile}")
        self.offline_scope_label.setText(f"Editing Aircraft ({self.offline_name.currentText()} - {profile})")

    def filter_offline_name_list(self, text):
        self.offline_name.blockSignals(True)
        self.offline_name.clear()
        self.offline_profile.blockSignals(True)
        self.offline_profile.clear()
        self.offline_name.addItems([''])
        filtered = [name for name in self.all_offline_models if text.lower() in name.lower()]
        self.offline_name.addItems(filtered)
        if len(filtered) == 1:
            self.offline_name.setCurrentIndex(1)
            # Manually trigger the downstream handler
            self.offline_aircraft_changed(filtered[0])
        self.offline_name.blockSignals(False)
        self.offline_profile.blockSignals(False)

    def force_sim_aircraft(self):
        G.settings_mgr.current_sim = self.offline_sim.currentText()
        G.settings_mgr.current_class = self.offline_class.currentText()
        G.settings_mgr.current_aircraft_name = self.offline_name.currentText()
        G.settings_mgr.active_profile = self.offline_profile.currentText()
        self._show_settings_layout()
        self.settings_layout.reload_caller()


    def show_new_aircraft_wizard(self, manual=False, sim=None, name=None, cls=None):
        # utils.debug_caller_args("red")
        wizard = NewAircraftWizard(parent=self, manual=manual, auto_sim=sim, auto_name=name, auto_cls=cls)
        wizard.accepted.connect(self.new_ac_wizard_finished)
        if wizard.exec():
            try:
                # make sure no other calls are connected to avoid stacking lambda calls if user cancels and doesn't add new aircraft
                self.new_craft_button.clicked.disconnect()
            except TypeError:
                pass  # No handler connected yet

    @overrides(QWidget)
    def closeEvent(self, event):
        # Perform cleanup before closing the application
        if G.child_instance:
            self.hide()
            event.ignore()
        else:
            if G.system_settings.get('closeToTray', False):
                self.hide()
                event.ignore()
                self.pop_tray_notification(
                    None,
                    "TelemFFB is running in the system tray.  Double-Click the VPforce Icon to re-show or right click to set options in the context menu",
                    5
                )
            else:
                exit_application()

    def is_valid_geometry(self, x, y):
        '''
        Check whether proposed window position is valid on any active screen
        '''
        for screen in QApplication.screens():
            screen_geometry = screen.availableGeometry()
            if screen_geometry.contains(x, y):
                return True
        return False

    def load_main_window_geometry(self):
        settings = G.system_settings
        window_data = settings.get("WindowData")
        
        if window_data is not None:
            try:
                window_data_dict = json.loads(window_data)
                
                # Restore geometry and state if available
                if 'geometry' in window_data_dict:
                    geometry = QtCore.QByteArray.fromBase64(window_data_dict['geometry'].encode())
                    if not self.restoreGeometry(geometry):
                        self.set_default_geometry()

                if 'state' in window_data_dict:
                    state = QtCore.QByteArray.fromBase64(window_data_dict['state'].encode())
                    self.restoreState(state)
                
                status_drawer_open = window_data_dict.get('StatusDrawerOpen', True)
                QTimer.singleShot(0, lambda open_drawer=status_drawer_open: self.set_status_drawer_open(open_drawer))

                # Validate window position is on screen
                if not self.is_valid_geometry(self.x(), self.y()):
                    self.set_default_geometry()
                    
            except Exception as e:
                logging.warning(f"Error restoring window geometry: {e}")
                self.set_default_geometry()
        else:
            self.set_default_geometry()

    def save_main_window_geometry(self):
        # Save both geometry and window state
        settings = G.system_settings
        device_type = G.device_type

        # Convert geometry and state to base64 strings for storage
        geometry = self.saveGeometry().toBase64().data().decode()
        state = self.saveState().toBase64().data().decode()

        window_dict = {
            'geometry': geometry,
            'state': state,
            'StatusDrawerOpen': self.status_drawer_thumb.isChecked()
        }

        settings.setValue(f"{device_type}/WindowData", json.dumps(window_dict))

    def set_default_geometry(self):
        """Set default window position based on device type"""
        match G.device_type:
            case 'joystick':
                x_pos = 160
                y_pos = 130
            case 'pedals':
                x_pos = 110
                y_pos = 100
            case 'collective':
                x_pos = 60
                y_pos = 70
            case 'trimwheel':
                x_pos = 10
                y_pos = 40
                
        self.setGeometry(x_pos, y_pos, self.default_geometry_width, self.default_geometry_height)
        self.set_status_drawer_open(True)

    def open_system_settings_dialog(self, show_simulator_setup=False):
        try:
            dialog = SystemSettingsDialog(self)
            if show_simulator_setup:
                dialog.show_simulator_setup_tab()
            dialog.raise_()
            dialog.activateWindow()
            dialog.show()
        except Exception:
            logging.exception("Exception")
        # dialog.exec_()

    def update_settings(self):
        # utils.debug_caller_args('blue')
        self.populate_profile_combo(None) # populate combo with any new profiles
        self.update_craft_text_block(craft=G.settings_mgr.current_aircraft_name, pattern=G.settings_mgr.current_pattern, profile=G.settings_mgr.active_profile)
        self.settings_layout.reload_caller()

    def open_url(self, url):

        # Open the URL
        QDesktopServices.openUrl(QUrl(url))

    def reset_all_effects(self):
        result = QMessageBox.warning(self, "Are you sure?", "*** Only use this if you have effects which are 'stuck' ***\n\n  Proceeding will result in the destruction"
                                                            " of any effects which are currently being generated by the simulator and may result in requiring a restart of"
                                                            " the sim or a new session.\n\n~~ Proceed with caution ~~", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)

        if result == QMessageBox.StandardButton.Ok:
            try:
                HapticEffect.device.reset_effects()
            except Exception:
                pass



    def update_from_menu(self):
        if self.perform_update(auto=False):
            QCoreApplication.instance().quit()

    def pop_tray_notification(self, title, message, renew_period):
            current_time = time.time()
            notification_key = (title, message)

            # Check if the notification was shown within the specified period
            if notification_key in self.tray_notifications:
                last_shown_time = self.tray_notifications[notification_key]
                if current_time - last_shown_time < renew_period:
                    # Notification was shown recently, do not show again
                    return
            # Show the notification
            icon = QIcon(utils.get_resource_path('image/zTelemIcon.png', prefer_root=True))
            self.tray_icon.showMessage(title, message, icon)
            # Update the last shown time
            self.tray_notifications[notification_key] = current_time
            self.tray_icon.messageClicked.connect(self.show)


    def update_sim_indicators(self, source, paused=False, error=False, message=None):
        """Runs on every telemetry frame
        """
        if source is None:
            return

        if error:
            self.status_container.set_error(source)
        elif paused:
            self.status_container.set_paused(source)
        else:
            self.status_container.set_running(source)


        if G.master_instance:
            if error:
                # error is true and was previously false.  Set sys tray attributes and pop notification

                self.tray_icon.setIcon(QIcon(utils.get_resource_path('image/zTelemIconError.png', prefer_root=True)))
                self.tray_icon.setToolTip(f"zTelem -- There is an error occurring:\n\n{message}")

                self.status_container.flag_error(message)

                self.pop_tray_notification("Error", message, renew_period= 2)


            elif paused:
                self.tray_icon.setIcon(QIcon(utils.get_resource_path('image/zTelemIconDis.png', prefer_root=True)))
                self.tray_icon.setToolTip(f"zTelem\n{source} is Paused ")

            elif not paused:
                self.tray_icon.setIcon(QIcon(utils.get_resource_path('image/zTelemIconRun.png', prefer_root=True)))
                self.tray_icon.setToolTip(f"zTelem\n{source} is Running ")
                # re-show the "current aircraft" label once error cleared





    def interpolate_color(self, color1, color2, value):
        # Ensure value is between 0 and 1
        value = max(0.0, min(1.0, value))

        # Extract individual color components
        r1, g1, b1, a1 = color1.getRgb()
        r2, g2, b2, a2 = color2.getRgb()

        # Interpolate each color component
        r = int(r1 + (r2 - r1) * value)
        g = int(g1 + (g2 - g1) * value)
        b = int(b1 + (b2 - b1) * value)
        a = int(a1 + (a2 - a1) * value)

        # Create and return the interpolated color
        return QColor(r, g, b, a)

    def populate_profile_combo(self, new_items: list[str]=None):
        """
        Updates the profile combo box only if its contents differ (excluding 'Add New...').

        Args:
            new_items (list[str]): List of profiles to populate.
        """
        SELECT_LABEL = 'Select...'
        ADD_NEW_LABEL = "Add New..."
        if not self.status_container.cb_selectProfileCombo.isEnabled():
            self.status_container.cb_selectProfileCombo.setEnabled(True)
        if new_items is None:
            new_items = xmlutils.get_available_profiles(G.settings_mgr.current_sim, G.settings_mgr.current_class, G.settings_mgr.current_pattern)

        self.status_container.cb_selectProfileCombo.blockSignals(True)
        self.status_container.cb_selectProfileCombo.clear()

        self.status_container.cb_selectProfileCombo.addItem(SELECT_LABEL)
        for item in new_items:
                self.status_container.cb_selectProfileCombo.addItem(item)

        self.status_container.cb_selectProfileCombo.addItem(ADD_NEW_LABEL)
        index = self.status_container.cb_selectProfileCombo.findText(ADD_NEW_LABEL)
        if index >= 0:
            font = QFont()
            font.setItalic(True)
            self.status_container.cb_selectProfileCombo.setItemData(index, font, role=Qt.ItemDataRole.FontRole)

        self.status_container.cb_selectProfileCombo.setCurrentIndex(0)
        self.status_container.cb_selectProfileCombo.blockSignals(False)

    def on_profile_change(self, index):
        # utils.debug_caller_args("red")
        """
        Call to xmlutils to update the profile mapping for the aircraft when the user changes the profile
        If the "add new" option is selected, pop a dialog asking for the new profile name.  If the user chooses
        the "make active' option, make a further call to make the new profile the active one
        Args:
            index: The selected index in the combobox.

        Returns: Nothing

        """
        if not G.master_instance:
            return
        if index == 0:
            return

        profile_name = self.status_container.cb_selectProfileCombo.itemText(index)

        self.status_container.cb_selectProfileCombo.blockSignals(True)
        self.status_container.cb_selectProfileCombo.setCurrentIndex(0)
        self.status_container.cb_selectProfileCombo.blockSignals(False)

        sim = G.settings_mgr.current_sim
        cls = G.settings_mgr.current_class
        pattern = G.settings_mgr.current_pattern

        cur_txt = xmlutils.get_active_profile_for_model(sim, cls, pattern)
        if profile_name == 'Add New...':
            ## Quickly block signals and set it back to "Select".. then kick off new profile dialog


            dlg = NewProfileDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                # user canceled
                return
            new_profile, make_active, clone, profile_to_clone = dlg.get_data()
            if not new_profile:
                # user did not enter a string
                return
            # write new profile entry to user config file
            if clone:
                xmlutils.clone_profile_entry(
                    sim=G.settings_mgr.current_sim,
                    cls=G.settings_mgr.current_class,
                    src_model=G.settings_mgr.current_pattern,
                    src_profile=profile_to_clone,
                    dst_profile=new_profile
                )
            else:
                xmlutils.add_new_profile(G.settings_mgr.current_sim, G.settings_mgr.current_class, G.settings_mgr.current_pattern, new_profile)

            if make_active:
                # change the profileMapping for this aircraft to the new profile
                xmlutils.update_active_profile_entry(G.settings_mgr.current_sim, G.settings_mgr.current_class, G.settings_mgr.current_pattern, new_profile)
                G.settings_mgr.update_state_vars(active_profile=new_profile)

            if G.telem_manager.timed_out:
                self.populate_profile_combo(xmlutils.get_available_profiles(G.settings_mgr.current_sim, G.settings_mgr.current_class, G.settings_mgr.current_pattern))
                self.update_craft_text_block(craft=G.settings_mgr.current_aircraft_name, pattern=G.settings_mgr.current_pattern, profile=G.settings_mgr.active_profile)
        else:
            xmlutils.update_active_profile_entry(G.settings_mgr.current_sim, G.settings_mgr.current_class, G.settings_mgr.current_pattern, profile_name)
            if G.telem_manager.timed_out:
                self.update_craft_text_block(craft=G.settings_mgr.current_aircraft_name, pattern=G.settings_mgr.current_pattern, profile=profile_name)
        if G.telem_manager.timed_out:
            self.settings_layout.reload_caller()

    def on_telemetry_timeout(self):
        self.lbl_effects_data.setText("")
        if not self.error_state:
            # Only set icon to pause if error condition is not present when pausing
            self.update_sim_indicators(G.telem_manager.getTelemValue('src'), paused=True)
        self.telemetry_timed_out = True
        self._show_waiting_for_telemetry()

    def on_update_telemetry(self, datadict: dict):
        if utils.millis() - self.last_telemetry_refresh < 50:
            return
        self.last_telemetry_refresh = utils.millis()
        self._show_settings_layout()

        data = OrderedDict(sorted(datadict.items()))  # Alphabetize telemetry data
        keys = data.keys()
        try:
            # use ordereddict and move some telemetry to the top
            # Items to move to the beginning (reverse order)
            if 'SimconnectCategory' in keys: data.move_to_end('SimconnectCategory', last=False)
            if 'AircraftClass' in keys: data.move_to_end('AircraftClass', last=False)
            if 'msfs_vers' in keys: data.move_to_end('msfs_vers', last=False)
            if 'src' in keys: data.move_to_end('src', last=False)
            if 'N' in keys: data.move_to_end('N', last=False)
            if 'FFBType' in keys: data.move_to_end('FFBType', last=False)
            if 'perf' in keys: data.move_to_end('perf', last=False)
            if 'avgFrameTime' in keys: data.move_to_end('avgFrameTime', last=False)
            if 'maxFrameTime' in keys: data.move_to_end('maxFrameTime', last=False)
            if 'frameTimes' in keys: data.move_to_end('frameTimes', last=False)
            if 'T' in keys: data.move_to_end('T', last=False)

            # Items to move to the end
        except Exception:
            pass

        try:

            telem_items = ""
            # Parse filter once per update
            raw = (self.telem_filter.text() or "")
            tokens = [t.strip().lower() for t in raw.split(",") if t.strip()]
            for k, v in data.items():

                # check for msfs and debug mode (alt-d pressed), change to simvar name
                if self.show_simvars:
                    if data["src"] == "MSFS":
                        s = G.telem_manager.simconnect.get_var_name(k)
                        # s = simvarnames.get_var_name(k)
                        if s is not None:
                            k = s

                # Apply simple OR filtering against the key only
                if tokens:
                    k_cf = str(k).lower()
                    if not any(tok in k_cf for tok in tokens):
                        continue

                if isinstance(v, float):
                    telem_items += f"{k}: {v:.3f}\n"
                else:
                    if isinstance(v, list):
                        v = "[" + ", ".join([f"{x:.3f}" if isinstance(x, float) else str(x) if x is not None else "None" for x in v]) + "]"
                    telem_items += f"{k}: {v}\n"

            active_effects = ""
            active_settings = []

            if G.master_instance and G.current_device_config_scope != G.device_type:
                dev = G.current_device_config_scope
                active_effects = G.ipc_instance._ipc_telem_effects.get(f'{dev}_active_effects', '')
                active_settings = G.ipc_instance._ipc_telem_effects.get(f'{dev}_active_settings', [])
            else:
                effect : HapticEffect
                for key, effect in effects.dict.items():
                    if effect.started:
                        descr, settingname = utils.EffectTranslator.get_translation(effect.name)
                        
                        descr = "ID:{} {}".format(effect.id, descr)
                        
                        active_effects += descr + "\n"
                        if settingname not in active_settings and settingname != '':
                            active_settings.append(settingname)

            if G.child_instance:
                child_effects = str(effects.dict.keys())
                if child_effects:
                    G.ipc_instance.send_ipc_effects(active_effects, active_settings)

            settings_visible = True
            monitor_visible = True
            # update slider colors
            pct_max_a = data.get('_pct_max_a', 0)
            pct_max_e = data.get('_pct_max_e', 0)
            pct_max_r = data.get('_pct_max_r', 0)
            pct_steer_f = data.get('_pct_steer_f', 0)
            qcolor_green = QColor("#17c411")
            qcolor_grey = QColor("grey")
            if settings_visible:
                sliders = self.findChildren(NoWheelSlider)
                for my_slider in sliders:
                    slidername = my_slider.objectName().replace('sld_', '')
                    my_slider.blockSignals(True)

                    for a_s in active_settings:
                        if a_s in slidername:
                            my_slider.setHandleColor("#17c411")
                            break
                        else:
                            my_slider.setHandleColor(colorPrimary)
                    my_slider.blockSignals(False)

                n_sliders = self.findChildren(NoWheelNumberSlider)
                for my_slider in n_sliders:
                    """This section updates the labels which are on the "NoWheelNumberSlider elements that reflect
                    the current value of the coeff % values"""
                    slidername = my_slider.objectName().replace('sld_', '')
                    my_slider.blockSignals(True)

                    if slidername == 'max_elevator_coeff':
                        new_color = self.interpolate_color(qcolor_grey, qcolor_green, pct_max_e)
                        my_slider.setHandleColor(new_color.name(), f"{int(pct_max_e *100)}%")
                        # print(int(pct_max_e * 100))
                        my_slider.blockSignals(False)
                        continue
                    if slidername == 'max_aileron_coeff':
                        new_color = self.interpolate_color(qcolor_grey, qcolor_green, pct_max_a)
                        my_slider.setHandleColor(new_color.name(), f"{int(pct_max_a * 100)}%")
                        # print(new_color)
                        my_slider.blockSignals(False)
                        continue
                    if slidername == 'max_rudder_coeff':
                        new_color = self.interpolate_color(qcolor_grey, qcolor_green, pct_max_r)
                        my_slider.setHandleColor(new_color.name(), f"{int(pct_max_r * 100)}%")
                        # print(new_color)
                        my_slider.blockSignals(False)
                        continue
                    if slidername == 'steering_friction_intensity':
                        new_color = self.interpolate_color(qcolor_grey, qcolor_green, pct_steer_f)
                        my_slider.setHandleColor(new_color.name(), f"{int(pct_steer_f * 100)}%")
                        # print(new_color)
                        my_slider.blockSignals(False)
                        continue
                    for a_s in active_settings:
                        if a_s in slidername:
                            my_slider.setHandleColor("#17c411")
                            break
                        else:
                            my_slider.setHandleColor(colorPrimary)
                    my_slider.blockSignals(False)

            is_paused = max(data.get('SimPaused', 0), data.get('Parked', 0))
            error_cond = data.get('error', None)

            if error_cond is None:  # no 'error' key in telemetry
                if self.telemetry_timed_out or self.error_state:  # only set status to run if previously debug_timed out or error status was true
                    if not self.error_clean_counter:  # avoid flapping due to ipc_telem not populating on every frame due to thread timing between instances
                        self.update_sim_indicators(data.get('src'), paused=False)
                        self.error_state = False
                        self.telemetry_timed_out = False
                        self.status_container.clear_error()
                    else:
                        self.error_clean_counter -= 1  # decrement the counter so that it will reach 0 once error is *truly* cleared
            elif error_cond is not None:

                self.error_clean_counter = 5
                if not self.error_state:  # only set error status once when there is error cond but state is not yet true
                    self.update_sim_indicators(data.get('src'), error=True, message=error_cond)
                    logging.error(error_cond)
                    self.error_state = True




            shown_pattern = G.settings_mgr.current_pattern
            if G.settings_mgr.current_pattern == '' and data.get('N', '') != '':
                shown_pattern = 'Using defaults'
                new_sim = data.get('src', None)
                new_aircraft = data.get('N', None)
                new_class = G.settings_mgr.current_class
                if G.master_instance:
                    if not self.new_craft_button.isVisible():
                        self.new_craft_button.clicked.connect(lambda: self.show_new_aircraft_wizard(manual=False,sim=new_sim,cls=new_class,name=new_aircraft))
                        self.new_craft_button.show()

                    if not data.get('STOP', False):
                        if not self.new_craft_notification_sent:

                            self.pop_tray_notification(
                                "** New Aircraft Found **",
                                f"No profile was found for the aircraft\n{data.get('N')}\n\nClick to open TelemFFB.",
                                10,
                            )
                            self.new_craft_notification_sent = True
                            self.show_new_aircraft_wizard(manual=False, sim=data.get('src', None), cls=G.settings_mgr.current_class, name=data.get('N', ''))



            else:
                self.new_craft_button.hide()
                self.new_craft_notification_sent = False

            # Update the status labels and profile selection box
            self.status_container.set_fullname(data['N'])
            ap = G.settings_mgr.active_profile
            active_profile = xmlutils.get_active_profile_for_model(G.settings_mgr.current_sim, G.settings_mgr.current_class, G.settings_mgr.current_pattern)

            self.update_craft_text_block(pattern=shown_pattern, profile=active_profile)

            if monitor_visible:
                self.lbl_telem_data.setText(telem_items)
                self.lbl_effects_data.setText(active_effects)

        except Exception:
            logging.exception("Exception")

    def update_craft_text_block(self, craft=None, pattern=None, profile=None):
        if craft is None:
            craft = G.settings_mgr.current_aircraft_name
        if pattern is None:
            pattern = G.settings_mgr.current_pattern
        if profile is None:
            profile = G.settings_mgr.active_profile
        self.status_container.cur_craft_label.setText(craft)
        self.status_container.cur_pattern_label.setText(pattern)
        self.status_container.active_profile_label.setText(profile)

    def new_ac_wizard_finished(self):
        self.new_craft_button.setVisible(False)
        self.settings_layout.reload_layout(None)


    def perform_update(self, auto=True):
        if G.release_version:
            return False

        ignore_auto_updates = G.system_settings.get('ignoreUpdate', False)
        if not auto:
            ignore_auto_updates = False
        update_ans = QMessageBox.StandardButton.No
        proceed_ans = QMessageBox.StandardButton.Cancel
        try:
            updater_execution_path = os.path.join(utils.get_script_path(), 'updater.exe')
            if os.path.exists(updater_execution_path):
                os.remove(updater_execution_path)
        except Exception as e:
            logging.error(f'Error in perform_update: {e}')

        is_exe = getattr(sys, 'frozen', False)  # TODO: Make sure to swap these comment-outs before build to commit - this line should be active, next line should be commented out
        # is_exe = True
        if G.child_instance: return False
        if ignore_auto_updates: return False
        if not is_exe: return False

        if self._update_available:
            update_ans = QMessageBox.StandardButton.Yes
            if auto:
                update_ans = QMessageBox.information(self, "Update Available!!",
                                                     f"A new version of TelemFFB is available ({self.latest_version}).\n\nWould you like to automatically download and install it now?\n\nYou may also update later from the Utilities menu, or the\nnext time TelemFFB starts.\n\n~~ Note ~~ If you no longer wish to see this message on startup,\nyou may enable `ignore_auto_updates` in your user config.\n\nYou will still be able to update via the Utilities menu",
                                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if update_ans == QMessageBox.StandardButton.Yes:
                proceed_ans = QMessageBox.information(self, "TelemFFB Updater",
                                                      f"TelemFFB will now exit and launch the updater.\n\nPress OK to continue",
                                                      QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)

            if proceed_ans == QMessageBox.StandardButton.Ok:
                updater_execution_path = os.path.join(utils.get_script_path(), 'updater.exe')
                shutil.copy(sys.argv[0], updater_execution_path)

                # Copy the updater executable with forced overwrite

                call = [updater_execution_path, "--current_version", utils.get_version()] + sys.argv[1:]
                subprocess.Popen(call, cwd=utils.get_install_path())
                if auto:
                    for child_widget in self.findChildren(QMessageBox):
                        child_widget.reject()
                    QTimer.singleShot(250, exit_application)
                else:
                    return True

        return False
