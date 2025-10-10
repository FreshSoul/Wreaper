from reapy import reascript_api as rpp
import reapy
retval, isRegion, pos, endpos, regionIndex, name, id = rpp.EnumProjectMarkers(0, 0, 0.0, 0.0, '', 0)
print(retval, isRegion, pos, endpos, regionIndex, name, id)
fs = rpp.SNM_CreateFastString("")
rpp.SNM_GetProjectMarkerName(0, 1, 1, fs)
name111 = rpp.SNM_GetFastString(fs)

print(name111)
