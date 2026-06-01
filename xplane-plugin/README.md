# X-Plane Plugin Source Assets

`zTelem-XPP` is the zTelem X-Plane plugin package. The runtime app installs it into X-Plane as:

`resources/plugins/zTelem-XPP/64/win.xpl`

The plugin C/C++ source is not present in this repository. The checked-in `win.xpl` is a patched copy of the bundled TelemFFB X-Plane plugin with these embedded values changed for coexistence:

- plugin folder/name: `zTelem-XPP`
- plugin signature: `zfsb.ztelem.xpplugin`
- debug log: `zTelem_DebugLog.txt`
- telemetry UDP port: `34392`
- command UDP port: `34393`

`zTelem.spec` packages `xplane-plugin/src/zTelem-XPP/64/win.xpl` into the runtime asset path `xplane-plugin/zTelem-XPP/64`.