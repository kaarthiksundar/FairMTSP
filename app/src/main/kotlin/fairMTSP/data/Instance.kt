package fairMTSP.data

import fairMTSP.main.Graph

data class Instance(
    val graph: Graph,
    val numVehicles: Int,
    val depot: Int = 0
)