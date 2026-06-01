"""
Stylesheet definitions for TelemFFB application.
Contains the dark-mode stylesheet used by zTelem.
"""

from string import Template

from PyQt6 import QtCore, QtGui
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QPushButton, QToolButton


colorPrimary = "#806f58"
colorPrimary_translucent = f"#44{colorPrimary[-6:]}"


def _hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(round(channel)))):02x}" for channel in rgb)


def _mix(color, target, ratio):
    color_rgb = _hex_to_rgb(color)
    target_rgb = _hex_to_rgb(target)
    return _rgb_to_hex(
        color_channel + (target_channel - color_channel) * ratio
        for color_channel, target_channel in zip(color_rgb, target_rgb)
    )


colorPrimary_light = _mix(colorPrimary, "#ffffff", 0.35)
colorPrimary_lighter = _mix(colorPrimary, "#ffffff", 0.55)
colorPrimary_dark = _mix(colorPrimary, "#000000", 0.20)
colorPrimary_darker = _mix(colorPrimary, "#000000", 0.38)
vpf_button_hover = colorPrimary_dark
vpf_button_disabled = colorPrimary_darker
default_container_padding = 20
system_settings_button_bar_spacing = 24
settings_group_expanded_bottom_padding = 16
advanced_spring_dialog_padding = 20
advanced_spring_section_spacing = 16
advanced_spring_control_spacing = 10
default_container_border_radius = 10
default_button_border_radius = 16
default_button_height = default_button_border_radius * 2
default_button_font_size = 9
default_button_disabled_font_color = "#aaaaaa"
titlebar_control_diameter = 18
titlebar_control_radius = titlebar_control_diameter // 2
titlebar_control_symbol_size = 8
titlebar_row_spacing = 8
status_drawer_thumb_font_size_px = 16
toolbar_menu_icon_text_gap = "   "
status_drawer_thumb_border = "#333"
window_control_minimize = "#d3a23f"
window_control_maximize = "#3ca66b"
window_control_close = "#c55a5a"
window_control_minimize_hover = _mix(window_control_minimize, "#ffffff", 0.18)
window_control_maximize_hover = _mix(window_control_maximize, "#ffffff", 0.18)
window_control_close_hover = _mix(window_control_close, "#ffffff", 0.18)
window_control_symbol = "#101010"
button_font_weight = 900
font_family = "Roboto"
window = "#000"
container_bg = "#090909"
window_text = "#dddddd"
base = "#232323"
alternate_base = window
tooltip_base = "#2b2b2b"
tooltip_text = window_text
text = "#cccccc"
button = window
button_text = window_text
bright_text = "#ff0000"
highlighted_text = "#ffffff"
disabled_text = "#7f7f7f"
input_background = "#414141"
input_disabled_background = "#3a3a3a"
input_border = "#666666"
input_disabled_border = "#555555"
menu_background = "#2b2b2b"
menu_border = "#333"
scrollbar_track = "transparent"
scrollbar_handle = "#4a4f57"
scrollbar_handle_hover = colorPrimary
scrollbar_handle_pressed = colorPrimary_dark

_accent_values = {
    "colorPrimary": colorPrimary,
    "colorPrimary_translucent": colorPrimary_translucent,
    "colorPrimary_light": colorPrimary_light,
    "colorPrimary_lighter": colorPrimary_lighter,
    "colorPrimary_dark": colorPrimary_dark,
    "colorPrimary_darker": colorPrimary_darker,
    "vpf_button_hover": vpf_button_hover,
    "vpf_button_disabled": vpf_button_disabled,
    "default_container_border_radius": default_container_border_radius,
    "default_button_border_radius": default_button_border_radius,
    "default_button_height": default_button_height,
    "default_button_font_size": default_button_font_size,
    "default_button_disabled_font_color": default_button_disabled_font_color,
    "titlebar_control_diameter": titlebar_control_diameter,
    "titlebar_control_radius": titlebar_control_radius,
    "default_container_padding": default_container_padding,
    "system_settings_button_bar_spacing": system_settings_button_bar_spacing,
    "settings_group_expanded_bottom_padding": settings_group_expanded_bottom_padding,
    "advanced_spring_dialog_padding": advanced_spring_dialog_padding,
    "advanced_spring_section_spacing": advanced_spring_section_spacing,
    "advanced_spring_control_spacing": advanced_spring_control_spacing,
    "titlebar_control_symbol_size": titlebar_control_symbol_size,
    "titlebar_row_spacing": titlebar_row_spacing,
    "status_drawer_thumb_font_size_px": status_drawer_thumb_font_size_px,
    "toolbar_menu_icon_text_gap": toolbar_menu_icon_text_gap,
    "status_drawer_thumb_border": status_drawer_thumb_border,
    "window_control_minimize": window_control_minimize,
    "window_control_maximize": window_control_maximize,
    "window_control_close": window_control_close,
    "window_control_minimize_hover": window_control_minimize_hover,
    "window_control_maximize_hover": window_control_maximize_hover,
    "window_control_close_hover": window_control_close_hover,
    "window_control_symbol": window_control_symbol,
    "button_font_weight": button_font_weight,
    "font_family": font_family,
    "window": window,
    "container_bg": container_bg,
    "window_text": window_text,
    "base": base,
    "alternate_base": alternate_base,
    "tooltip_base": tooltip_base,
    "tooltip_text": tooltip_text,
    "text": text,
    "button": button,
    "button_text": button_text,
    "bright_text": bright_text,
    "highlighted_text": highlighted_text,
    "disabled_text": disabled_text,
    "input_background": input_background,
    "input_disabled_background": input_disabled_background,
    "input_border": input_border,
    "input_disabled_border": input_disabled_border,
    "menu_background": menu_background,
    "menu_border": menu_border,
    "scrollbar_track": scrollbar_track,
    "scrollbar_handle": scrollbar_handle,
    "scrollbar_handle_hover": scrollbar_handle_hover,
    "scrollbar_handle_pressed": scrollbar_handle_pressed,
}


def apply_dark_mode_palette(app, palette):
    """Apply the app's dark mode color palette."""
    accent_color = QtGui.QColor(colorPrimary)
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, accent_color)
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(highlighted_text))
    palette.setColor(QtGui.QPalette.ColorRole.Link, accent_color)

    palette.setColor(QtGui.QPalette.ColorRole.Window, QColor(window))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(window_text))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QColor(base))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QColor(alternate_base))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(tooltip_base))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(tooltip_text))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(text))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QColor(button))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(button_text))
    palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor(bright_text))

    palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText, QColor(disabled_text))
    palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, QColor(disabled_text))
    palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, QColor(disabled_text))

    app.setPalette(palette)


def app_font(point_size=10, weight=QFont.Weight.Normal):
    return QFont(font_family, point_size, weight)


def uppercase_button_text(button):
    if not isinstance(button, (QPushButton, QToolButton)):
        return
    if button.property("preserveCase"):
        return

    text = button.text()
    uppercase_text = text.upper()
    if text and text != uppercase_text:
        was_blocked = button.blockSignals(True)
        button.setText(uppercase_text)
        button.blockSignals(was_blocked)


def apply_button_cursor(button):
    if not isinstance(button, (QPushButton, QToolButton)):
        return

    cursor_shape = QtCore.Qt.CursorShape.PointingHandCursor if button.isEnabled() else QtCore.Qt.CursorShape.ArrowCursor
    if button.cursor().shape() != cursor_shape:
        button.setCursor(cursor_shape)


def uppercase_buttons(root):
    for button_type in (QPushButton, QToolButton):
        for button in root.findChildren(button_type):
            uppercase_button_text(button)
            apply_button_cursor(button)


class _ButtonTextEventFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        if event.type() in (
            QtCore.QEvent.Type.Polish,
            QtCore.QEvent.Type.Show,
            QtCore.QEvent.Type.ShowToParent,
            QtCore.QEvent.Type.UpdateRequest,
            QtCore.QEvent.Type.EnabledChange,
        ):
            uppercase_button_text(obj)
            apply_button_cursor(obj)
        return super().eventFilter(obj, event)


def install_button_text_filter(app):
    if getattr(app, "_zTelem_button_text_filter", None) is not None:
        return

    button_text_filter = _ButtonTextEventFilter(app)
    app.installEventFilter(button_text_filter)
    app._zTelem_button_text_filter = button_text_filter


def apply_font_family(font):
    font.setFamily(font_family)
    return font


def rich_text_body_style(point_size=9, weight=400, font_style="normal"):
    return (
        f" font-family:'{font_family}';"
        f" font-size:{point_size}pt;"
        f" font-weight:{weight};"
        f" font-style:{font_style};"
    )


RICH_TEXT_FONT_FAMILY_STYLE = Template("font-family: $font_family").substitute(_accent_values)


MONITOR_TEXT_STYLESHEET = Template("""
QLabel {
    padding: 2px;
    font-family: "$font_family";
}
""").substitute(_accent_values)


NEW_CRAFT_BUTTON_STYLESHEET = Template("""
QPushButton {
    background-color: $colorPrimary;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    color: white;
    font-family: "$font_family";
    font-size: 14px;
    font-weight: $button_font_weight;
    min-width: 10em;
    padding: 5px 14px;
}
""").substitute(_accent_values)


SETTINGS_GROUP_CONTAINER_STYLESHEET = Template("""
QFrame#settingsGroupContainer {
    background-color: $container_bg;
    border: 1px solid $menu_border;
    border-radius: 8px;
}
""").substitute(_accent_values)


WAITING_TELEMETRY_STYLESHEET = Template("""
QFrame#waitingTelemetryPanel {
    background-color: $container_bg;
    border: 1px solid $menu_border;
    border-radius: 10px;
}

QLabel#waitingTelemetryTitle {
    color: $highlighted_text;
    font-family: "$font_family";
    font-size: 28pt;
    font-weight: 900;
}

QLabel#waitingTelemetrySubtitle {
    color: $highlighted_text;
    font-family: "$font_family";
    font-size: 13pt;
    font-weight: 900;
}

QPushButton#manageSupportedGamesButton {
    background-color: $colorPrimary;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    color: white;
    font-family: "$font_family";
    font-size: ${default_button_font_size}pt;
    font-weight: $button_font_weight;
    min-width: 210px;
    min-height: ${default_button_height}px;
    padding: 0
}

QPushButton#manageSupportedGamesButton:hover {
    background-color: $vpf_button_hover;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
}

QPushButton#manageSupportedGamesButton:pressed {
    background-color: $colorPrimary_darker;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
}
""").substitute(_accent_values)


APP_FOOTER_STYLESHEET = Template("""
QFrame#appFooter {
    background-color: transparent;
    border: 0px solid transparent;
}

QLabel#footerJoystickLabel,
QLabel#footerJoystickValue,
QLabel#appVersionLabel {
    color: $disabled_text;
    font-family: "$font_family";
    font-size: 8pt;
    font-weight: 700;
}

QLabel#footerJoystickValue[connected="true"] {
    color: $window_text;
}
""").substitute(_accent_values)


STATUS_DRAWER_THUMB_STYLESHEET = Template("""
QAbstractButton#statusDrawerThumb {
    background-color: $container_bg;
    border: 1px solid $status_drawer_thumb_border;
    border-radius: ${default_button_border_radius}px;
    font-size: ${status_drawer_thumb_font_size_px}px;
    padding: 5px;
    margin: 0px;
    min-width: 26px;
    max-width: 26px;
    
}
""").substitute(_accent_values)


SETTINGS_EDIT_BUTTON_STYLESHEET = Template("""
QPushButton {
    background-color: $colorPrimary;
    color: white;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    font-size: ${default_button_font_size}pt;
    font-weight: $button_font_weight;
    padding: 5px 14px;
}

QPushButton:hover {
    background-color: $vpf_button_hover;
}

QPushButton:pressed {
    background-color: $colorPrimary_darker;
}

QPushButton:disabled {
    background-color: $vpf_button_disabled;
    color: $default_button_disabled_font_color;
}
""").substitute(_accent_values)


SETTINGS_GROUP_HEADER_STYLESHEET = Template("""
QFrame#settingsGroupHeader {
    background-color: transparent;
    border: 0;
    padding: 4px 8px;
    border-radius: 6px;
}

QFrame#settingsGroupHeader[accordion="true"]:hover {
    background-color: $colorPrimary_darker;
}

QFrame#settingsGroupHeader[accordion="true"][expanded="true"] {
    border-bottom: 1px solid $menu_border;
    border-bottom-left-radius: 0px;
    border-bottom-right-radius: 0px;
}

QFrame#settingsGroupHeader QToolButton {
    background-color: transparent;
    border: 0;
    padding: 0;
    min-width: 20px;
    max-width: 20px;
}

QFrame#settingsGroupHeader QWidget,
QFrame#settingsGroupHeader QLabel {
    background-color: transparent;
}
""").substitute(_accent_values)


SYSTEM_SETTINGS_MAIN_TABS_STYLESHEET = Template("""

""").substitute(_accent_values)


SYSTEM_SETTINGS_SIM_TABS_STYLESHEET = Template("""
QTabWidget::tab-bar:left {
    alignment: center;
}

QTabBar::tab {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 16px;
    margin: 6px 10px 6px 0px;
    padding: 8px;
    width: 56px;
    height: 56px;
}

QTabBar::tab:hover {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
}

QTabBar::tab:selected {
    background-color: $colorPrimary_translucent;
    border: 1px solid $colorPrimary_light;
}

QTabBar::tab:selected:hover {
    background-color: $colorPrimary_translucent;
    border: 1px solid $colorPrimary_lighter;
}
""").substitute(_accent_values)


DARK_MODE_STYLESHEET = Template("""
                                
QTabWidget::pane {
    background-color: $container_bg;
    border: 1px solid $menu_border;
    border-radius: 0px;
    top: -1px;
}

QTabWidget::tab-bar:top {
    alignment: left;
}

QTabBar::tab {
    background-color: transparent;
    color: $disabled_text;
    border: 1px solid transparent;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    padding: 9px 16px;
    margin: 0px 6px 0px 0px;
    min-width: 112px;
    left: 20px;
}

QTabBar::tab:hover {
    color: $window_text;
    background-color: rgba(255, 255, 255, 0.04);
}

QTabBar::tab:selected {
    color: $highlighted_text;
    background-color: $base;
    border: 1px solid $menu_border;
    border-bottom-color: $base;
}

QTabBar::tab:!selected {
    margin-top: 2px;
}
QSplitter::handle {
    padding: 5px;
}

QToolBar#appToolbar {
    background-color: $window;
    border: 1px solid $menu_border;
    border-bottom: 0;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
}
QToolBar#appToolbar QPushButton[toolbarRole="menu"] {
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    background: $colorPrimary;
    color: white;
    qproperty-iconSize: 16px 16px;
    margin: 1px 2px;
    padding: 0px 24px 0px 24px;
    min-height: ${default_button_height}px;
    max-height: ${default_button_height}px;
}
QToolBar#appToolbar QPushButton[toolbarRole="menu"]:hover {
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    background: $vpf_button_hover;
}
QToolBar#appToolbar QPushButton[toolbarRole="menu"]:pressed {
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    background: $colorPrimary_darker;
    color: white;
}
QToolBar#appToolbar QPushButton[toolbarRole="menu"]:focus {
    border: 0px solid transparent;
    outline: none;
    border-radius: ${default_button_border_radius}px;
}
QToolBar#appToolbar QPushButton[toolbarRole="window-control"] {
    min-width: ${titlebar_control_diameter}px;
    max-width: ${titlebar_control_diameter}px;
    min-height: ${titlebar_control_diameter}px;
    max-height: ${titlebar_control_diameter}px;
    border-radius: ${titlebar_control_radius}px;
    padding: 0px;
    margin: 0px;
    border: 0px solid transparent;
    color: $window_control_symbol;
    font-size: ${titlebar_control_symbol_size}pt;
    font-weight: 900;
}
QToolBar#appToolbar QPushButton[toolbarRole="window-control"]:focus {
    outline: none;
}
QToolBar#appToolbar QPushButton[controlType="minimize"] {
    background: $window_control_minimize;
}
QToolBar#appToolbar QPushButton[controlType="maximize"] {
    background: $window_control_maximize;
}
QToolBar#appToolbar QPushButton[controlType="close"] {
    background: $window_control_close;
}
QToolBar#appToolbar QPushButton[controlType="minimize"]:hover {
    background: $window_control_minimize_hover;
    border: 1px solid rgba(255, 255, 255, 0.25);
}
QToolBar#appToolbar QPushButton[controlType="maximize"]:hover {
    background: $window_control_maximize_hover;
    border: 1px solid rgba(255, 255, 255, 0.25);
}
QToolBar#appToolbar QPushButton[controlType="close"]:hover {
    background: $window_control_close_hover;
    border: 1px solid rgba(255, 255, 255, 0.25);
}

QWidget {
    font-family: "$font_family";
    color: $window_text;
    selection-background-color: $colorPrimary;
    selection-color: $highlighted_text;
}

QMainWindow {
    background: transparent;
    border: 0;
}

QWidget#mainSurface {
    background-color: $window;
    border: 1px solid $menu_border;
    border-top: 0;
    border-bottom-left-radius: 10px;
    border-bottom-right-radius: 10px;
}

QMainWindow, QDialog {
    color: $window_text;
}

QDialog {
    background-color: $window;
}

QToolTip {
    background-color: $tooltip_base;
    color: $tooltip_text;
    border: 1px solid $menu_border;
}

QAbstractItemView {
    background-color: $base;
    alternate-background-color: $alternate_base;
    color: $text;
    border: 1px solid $input_border;
    selection-background-color: $colorPrimary;
    selection-color: $highlighted_text;
}

QScrollBar:vertical {
    background: $scrollbar_track;
    border: 0px;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: $scrollbar_handle;
    border: 0px;
    border-radius: 4px;
    min-height: 36px;
    margin: 2px 3px;
}

QScrollBar::handle:vertical:hover {
    background: $scrollbar_handle_hover;
}

QScrollBar::handle:vertical:pressed {
    background: $scrollbar_handle_pressed;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    background: transparent;
    border: 0px;
    height: 0px;
    subcontrol-origin: margin;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: $scrollbar_track;
}

QScrollBar:horizontal {
    background: $scrollbar_track;
    border: 0px;
    height: 12px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: $scrollbar_handle;
    border: 0px;
    border-radius: 4px;
    min-width: 36px;
    margin: 3px 2px;
}

QScrollBar::handle:horizontal:hover {
    background: $scrollbar_handle_hover;
}

QScrollBar::handle:horizontal:pressed {
    background: $scrollbar_handle_pressed;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    background: transparent;
    border: 0px;
    width: 0px;
    subcontrol-origin: margin;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: $scrollbar_track;
}

QPushButton, QToolButton, #styledButton {
    background-color: $colorPrimary;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    color: white;
    font-size: ${default_button_font_size}pt;
    font-weight: $button_font_weight;
    max-height: ${default_button_height}px;
    min-height: ${default_button_height}px;
    min-width: 70px;
    padding: 0px 14px;
}

QPushButton:!pressed, QToolButton:!pressed, #styledButton:!pressed {
    background-color: $colorPrimary;
    padding: 0px 14px;
    color: white;
    font-weight: $button_font_weight;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    min-width: 70px;
    max-height: ${default_button_height}px;
    min-height: ${default_button_height}px;
}

QPushButton:disabled:!pressed, QToolButton:disabled:!pressed, #styledButton:disabled:!pressed {
    background-color: $vpf_button_disabled;
    color: $default_button_disabled_font_color;
    padding: 0px 14px;
    margin: 0px;
    font-weight: $button_font_weight;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    max-height: ${default_button_height}px;
    min-height: ${default_button_height}px;
}

QPushButton:pressed, QToolButton:pressed, #styledButton:pressed {
    background-color: $colorPrimary_darker;
    padding: 0px 14px;
    font-weight: $button_font_weight;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    max-height: ${default_button_height}px;
    min-height: ${default_button_height}px;
}

QPushButton:hover:!pressed, QToolButton:hover:!pressed, #styledButton:hover:!pressed {
    background-color: $vpf_button_hover;
    padding: 0px 14px;
    margin: 0px;
    color: white;
    font-weight: $button_font_weight;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    max-height: ${default_button_height}px;
    min-height: ${default_button_height}px;
}

QPushButton:focus, QPushButton:default, QPushButton:flat, QToolButton:focus, QToolButton:default, QToolButton:flat, #styledButton:focus, #styledButton:default {
    border: 0px solid transparent;
    outline: none;
    border-radius: ${default_button_border_radius}px;
}

QPushButton[buttonType="erase_button"] {
    font-size: 16px;  /* Adjust the font size */
    font-family: "$font_family";
    font-weight: $button_font_weight;
    color: white;
    padding: 0px 8px;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    margin: 0px;   /* Remove any margin */
    background-color: transparent;
    min-width: 25px;
    min-height: 25px;
}
            
QPushButton[buttonType="erase_button"]:hover,
QPushButton[buttonType="erase_button"]:pressed {
    background-color: transparent;
    padding: 0px 8px;
    margin: 0px;
    border: 0px solid transparent;
    min-width: 25px;
    min-height: 25px;
}

QPushButton[buttonType="p_m_button"] {                                  
    font-size: 16px;  /* Adjust the font size */                        
    font-family: "$font_family";
    font-weight: $button_font_weight;
    color: white;
    padding: 0px 8px;
    border: 0px solid transparent;
    border-radius: ${default_button_border_radius}px;
    margin: 0px;   /* Remove any margin */                              
    background-color: transparent;
    min-width: 20px;
}   
                                                                    
QPushButton[buttonType="p_m_button"]:hover {                            
    background-color: $vpf_button_hover;
    min-width: 20px;
}    
                                                                   
QPushButton[buttonType="p_m_button"]:pressed {                          
    background-color: $colorPrimary_darker;
    border: 0px solid transparent;
    min-width: 20px;
}     

QToolButton[buttonType="expand_button"] {                                                          
    font-size: 16px;  /* Adjust the font size */                       
    font-family: "$font_family";
    font-weight: $button_font_weight;
    color: $colorPrimary_light;
    border: none;  /* Remove any border */                             
    margin: 0px;   /* Remove any margin */                             
    background-color: transparent;  /* Transparent background */       
}              
                                                        
QToolButton[button_type="expand_button"]:hover {                                                    
    background-color: #666;  /* Optional: Change background on hover */
}   
                                                                   
QToolButton[button_type="expand_button"]:pressed {                                                  
    background-color: #bbb;  /* Optional: Change background on press */
}                                                                      

QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: $input_background;
    color: $highlighted_text;
    border: 1px solid $input_border;
    border-radius: 2px;
    padding: 1px;
    selection-background-color: $colorPrimary;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid $colorPrimary;  /* match your accent */
}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {
    color: $disabled_text;
    background-color: $input_disabled_background;
    border-color: $input_disabled_border;
}

QComboBox, QComboBox[noWheelCombo="true"], QComboBox:editable, QComboBox[noWheelCombo="true"]:editable, QComboBox:!editable, QComboBox[noWheelCombo="true"]:!editable {
    background-color: $input_background;
    color: $highlighted_text;
    border: 1px solid $input_border;
    border-radius: 0px;
    padding: 1px 24px 1px 6px;
    selection-background-color: $colorPrimary;
}

QComboBox[noWheelCombo="true"] {
    border: 1px solid #aaa;
    border-radius: 0px;
}
                                
QComboBox[noWheelCombo="true"] QAbstractItemView {
    border: none;
    border-radius: 0px;
    background: transparent;
}
                                

QComboBox:focus, QComboBox[noWheelCombo="true"]:focus {
    border: 1px solid $colorPrimary;
}

QComboBox:disabled, QComboBox[noWheelCombo="true"]:disabled {
    color: $disabled_text;
    background-color: $input_disabled_background;
    border-color: $input_disabled_border;
}

QComboBox QAbstractItemView, QComboBox[noWheelCombo="true"] QAbstractItemView {
    background-color: $base;
    color: $text;
    border-radius: 0px;
    padding: 0px;
    outline: 0px;
    selection-background-color: $colorPrimary;
    selection-color: $highlighted_text;
}

QComboBox QAbstractItemView::item, QComboBox[noWheelCombo="true"] QAbstractItemView::item {
    border: 0px solid transparent;
    border-radius: 0px;
    margin: 0px;
    padding: 3px 8px;
}

QComboBox QAbstractItemView::item:selected, QComboBox[noWheelCombo="true"] QAbstractItemView::item:selected {
    background-color: $colorPrimary;
    color: $highlighted_text;
}

QComboBox[noWheelCombo="true"],
QComboBox[noWheelCombo="true"]:editable,
QComboBox[noWheelCombo="true"]:!editable,
QComboBox[noWheelCombo="true"]:focus,
QComboBox[noWheelCombo="true"]:on {
    border-radius: 0px;
}

QComboBox[noWheelCombo="true"]:editable::drop-down,
QComboBox[noWheelCombo="true"]:!editable::drop-down,
QComboBox[noWheelCombo="true"]:focus::drop-down,
QComboBox[noWheelCombo="true"]:on::drop-down {
    border-top-right-radius: 0px;
    border-bottom-right-radius: 0px;
}

QSlider::handle:horizontal {
    background: $colorPrimary;
    border: 1px solid #565a5e;
    width: 16px;
    height: 20px;
    border-radius: 5px;
    margin-top: -5px;
    margin-bottom: -5px;
    margin-left: -1px;
    margin-right: -1px;
}

QSlider::handle:horizontal:disabled {
    background: #888888;
}

QSlider::groove:horizontal {
    border: 1px solid #333333;
    height: 8px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #5a5a5a, stop: 1 #3e3e3e
    );
    margin: 0;
    border-radius: 3px;
}

QMenuBar {
    background-color: $window;
    color: $text;
}

QMenuBar::item:selected {
    background-color: $colorPrimary;
    color: $text;
}

QMenuBar::item:pressed {
    background-color: $colorPrimary;
    color: $text;
}

QMenu {
    background-color: $menu_background;
    color: $text;
    border: 0;
}

QMenu::item {
    padding: 6px 20px;
    background-color: transparent;
}

QMenu::item:selected {
    background-color: $colorPrimary;
    color: $text;
}

QCheckBox:disabled {
  color: rgb(155, 155, 155);  /* lighter grey for better visibility */
}

QLabel#OfflineBannerLabel {
    background-color: rgba(255, 165, 0, 100);  /* Orange-ish translucent */
    color: $window_text;
    padding: 6px 10px;
    font-family: "$font_family";
    font-weight: bold;
    border: 1px solid $menu_border;
    border-radius: 6px;
}

QLabel#StatusLabel:hover {
    padding-right: 5px; 
    color: $colorPrimary;
    text-decoration: underline; 
    background-color: transparent;
}

QLabel#StatusLabel:!hover {
    padding-right: 5px; 
    color: $colorPrimary_light;
    text-decoration: underline; 
    background-color: transparent;
}

QGroupBox {
    font-weight: bold;
    border-radius: 10px;
    margin-top: 6px;
    background-color: ${container_bg};
}

QGroupBox::title {
    left: 10px;
    subcontrol-origin: margin;
    subcontrol-position: top left;
}

""").substitute(_accent_values)

GROUP_LABEL_STYLESHEET = Template("""
QLabel {
    font-family: "$font_family";
    font-size: 14pt;
    font-weight: 900;
}
""").substitute(_accent_values)

LOCKED_GROUP_LABEL_STYLESHEET = Template("""
QLabel {
    color: $colorPrimary;
    font-family: "$font_family";
    font-size: 14pt;
}

""").substitute(_accent_values)


EXPAND_LABEL_STYLESHEET = Template("""
QLabel:hover {
    color: $colorPrimary;
    text-decoration: underline; 
}

QLabel:!hover {
    color: $colorPrimary_light;
    text-decoration: underline; 
}
""").substitute(_accent_values)
