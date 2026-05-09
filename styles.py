"""
Stylesheet definitions for TelemFFB application.
Contains the dark-mode stylesheet used by zTelem.
"""

from string import Template


zBlue = "#204c7d"
zBlue_translucent = f"#44{zBlue[-6:]}"


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


zBlue_light = _mix(zBlue, "#ffffff", 0.35)
zBlue_lighter = _mix(zBlue, "#ffffff", 0.55)
zBlue_dark = _mix(zBlue, "#000000", 0.20)
zBlue_darker = _mix(zBlue, "#000000", 0.38)
vpf_button_hover = _mix(zBlue, "#ffffff", 0.24)
vpf_button_disabled = "#bbbbbb"

_accent_values = {
    "zBlue": zBlue,
    "zBlue_light": zBlue_light,
    "zBlue_lighter": zBlue_lighter,
    "zBlue_dark": zBlue_dark,
    "zBlue_darker": zBlue_darker,
    "vpf_button_hover": vpf_button_hover,
    "vpf_button_disabled": vpf_button_disabled,
}


DARK_MODE_STYLESHEET = Template("""
QPushButton:!pressed, #styledButton:!pressed {
    background-color: $zBlue;
    padding: 2px;
    color: white; /* Ensures consistency */
    border: 1px solid $zBlue_dark;
    min-width: 70px;
}

QPushButton:disabled:!pressed, #styledButton:disabled:!pressed {
    background-color: $vpf_button_disabled;
    color: #666666;
    padding: 3px;
    margin: 0px;
    border: 1px solid #999999;
}

QPushButton:pressed, #styledButton:pressed {
    background-color: $zBlue_darker;
    padding: 4px 8px;
    border: 1px solid $zBlue;
}

QPushButton:hover:!pressed, #styledButton:hover:!pressed {
    background-color: $vpf_button_hover;
    padding: 3px;
    margin: 0px;
    color: white;
    border: 1px solid $zBlue_dark;
}

QPushButton[buttonType="erase_button"] {
    font-size: 16px;  /* Adjust the font size */
    font-family: Cascadia Code;
    font-weight: bold;
    color: black;
    padding: 0px;
    border: none;  /* Remove any border */
    margin: 0px;   /* Remove any margin */
    background-color: transparent;  /* Transparent background */
    min-width: 25px;
    min-height: 25px;
}
            
QPushButton[buttonType="erase_button"]:hover {
    background-color: palett(window);  /* Optional: Change background on hover */
    min-height: 25px;
    min-width: 25px;
}

QPushButton[buttonType="erase_button"]:pressed {
    background-color: #666;  /* Optional: Change background on press */
    border: 1px solid $zBlue;
    min-height: 25px;
    min-width: 25px;
}

QPushButton[buttonType="p_m_button"] {                                  
    font-size: 16px;  /* Adjust the font size */                        
    font-family: Cascadia Code;                                         
    font-weight: bold;                                                  
    color: $zBlue;
    padding: 0px;                                                       
    border: none;  /* Remove any border */                              
    margin: 0px;   /* Remove any margin */                              
    background-color: transparent;  /* Transparent background */  
    min-width: 20px;
}   
                                                                    
QPushButton[buttonType="p_m_button"]:hover {                            
    background-color: palett(window);  /* Optional: Change background on hover */ 
    min-width: 20px;
}    
                                                                   
QPushButton[buttonType="p_m_button"]:pressed {                          
    background-color: #666;  /* Optional: Change background on press */
    border: 1px solid $zBlue;
    min-width: 20px;
}     

QToolButton[buttonType="expand_button"] {                                                          
    font-size: 16px;  /* Adjust the font size */                       
    font-family: Cascadia Code;                                        
    font-weight: bold;                                                 
    color: $zBlue_light;
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
    background-color: #414141;
    color: #ffffff;
    border: 1px solid #666666;
    border-radius: 2px;
    padding: 1px;
    selection-background-color: $zBlue;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid $zBlue;  /* match your accent */
}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {
    color: palette(disabled, text);
    background-color: #3a3a3a;     /* optional, a touch darker */
    border-color: #555555;         /* optional */
}

QSlider::handle:horizontal {
    background: $zBlue;
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
    background-color: #353535;
    color: palette(text);
}

QMenuBar::item:selected {
    background-color: $zBlue;
    color: palette(text);
}

QMenuBar::item:pressed {
    background-color: $zBlue;
    color: palette(text);
}

QMenu {
    background-color: #2b2b2b;
    color: palette(text);
    border: 1px solid #444444;
}

QMenu::item {
    padding: 6px 20px;
    background-color: transparent;
}

QMenu::item:selected {
    background-color: $zBlue;
    color: palette(text);
}

QCheckBox:disabled {
  color: rgb(155, 155, 155);  /* lighter grey for better visibility */
}

QLabel#OfflineBannerLabel {
    background-color: rgba(255, 165, 0, 100);  /* Orange-ish translucent */
    color: palette(windowText);
    padding: 6px 10px;
    font: Cascadia Mono;
    font-weight: bold;
    border: 1px solid palette(dark);
    border-radius: 6px;
}

QLabel#StatusLabel:hover {
    padding-right: 5px; 
    color: $zBlue;
    text-decoration: underline; 
    background-color: transparent;
}

QLabel#StatusLabel:!hover {
    padding-right: 5px; 
    color: $zBlue_light;
    text-decoration: underline; 
    background-color: transparent;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid gray;
    border-radius: 5px;
    margin-top: 6px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 3px 0 3px;
}
""").substitute(_accent_values)

GROUP_LABEL_STYLESHEET = Template("""
QLabel {
    color: $zBlue;
    font-family: "Black Ops One";
    font-size: 14pt;
}

QLabel:hover {
    color: $zBlue_light;
    text-decoration: underline; 
}

QLabel:!hover {
    color: $zBlue;
    text-decoration: underline; 
}
""").substitute(_accent_values)

LOCKED_GROUP_LABEL_STYLESHEET = Template("""
QLabel {
    color: $zBlue;
    font-family: "Black Ops One";
    font-size: 14pt;
}

""").substitute(_accent_values)


EXPAND_LABEL_STYLESHEET = Template("""
QLabel:hover {
    color: $zBlue;
    text-decoration: underline; 
}

QLabel:!hover {
    color: $zBlue_light;
    text-decoration: underline; 
}
""").substitute(_accent_values)
