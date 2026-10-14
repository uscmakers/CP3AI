# config.py (physical dimensions and system settings and stuff)

"""
effecctive length is local to each gantry system if we have two of them

                         local table length                       local table length

              |<------------------------------------>|<-------------------------------------->|
^             ---------------------------------------------------------------------------------
|             |                                      |                                        |
|             |                                      |                                        |
|             |                                      |                                        |
|             |  ( )                                 |                                   ( )  |
| width       |  ( )( )                              |                                ( )( )  |
|             |  ( )( )( )                           |                             ( )( )( )  |
|             |  ( )( )                              |                                ( )( )  |
|             |  ( )                                 |                                   ( )  |
|             |                                      |                                        |
|             |                                      |                                        |
v             ---------------------------------------------------------------------------------
                                              full table view


also ik the cups aren't positioned right but whatever

"""

# all dimensions in millimeters mm

from dataclasses import dataclass

@dataclass(frozen=True)
class TableDimensions:
    width: float
    length: float

@dataclass(frozen=True)
class CupDimensions:
    rim_diameter : float
    height: float

cup = CupDimensions(rim_diameter=92, height=123)
table = TableDimensions(width=610, length=2438) # total length not local length
gantry_workspace = TableDimensions(width=610, length=1219)
