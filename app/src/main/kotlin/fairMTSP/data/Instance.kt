package fairMTSP.data

import fairMTSP.main.Coords
import fairMTSP.main.Graph

data class Instance(
    val instanceName: String,
    val graph: Graph,
    val numVehicles: Int,
    val depot: Int = 0,
    val vertexCoords: List<Coords>
)