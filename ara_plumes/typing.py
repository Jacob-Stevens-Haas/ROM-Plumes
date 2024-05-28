from typing import Any
from typing import List
from typing import NewType

import numpy as np
from numpy.typing import NBitBase

Frame = NewType("Frame", int)
Width = NewType("Width", int)
Height = NewType("Height", int)
Channel = NewType("Channel", int)

GrayImage = np.ndarray[tuple[Height, Width], np.dtype[np.uint8]]
ColorImage = np.ndarray[tuple[Height, Width, Channel], np.dtype[np.uint8]]
FloatImage = np.ndarray[tuple[Height, Width], np.dtype[np.floating[NBitBase]]]
GrayVideo = np.ndarray[tuple[Frame, Height, Width], np.dtype[np.uint8]]
ColorVideo = np.ndarray[tuple[Frame, Height, Width, Channel], np.dtype[np.uint8]]

Y_pos = NewType("Y_pos", int)
X_pos = NewType("X_pos", int)
Contour_List = List[np.ndarray[tuple[Y_pos, X_pos], np.dtype[Any]]]

Radius = NewType("Radius", int)

PlumePoints = np.ndarray[tuple[Radius, X_pos, Y_pos], np.dtype[np.floating[NBitBase]]]

AX_FRAME = -3
AX_HEIGHT = -2
AX_WIDTH = -1