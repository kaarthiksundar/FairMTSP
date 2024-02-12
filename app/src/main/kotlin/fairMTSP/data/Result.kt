package fairMTSP.data

import fairMTSP.main.Coords
import kotlinx.serialization.Serializable

@Serializable
data class Result(
    val instanceName: String,
    val numVertices: Int,
    val depot: Int,
    val numVehicles: Int,
    val objectiveType: String,
    val vertexCoords: Map<Int, Coords>,
    val tours: List<List<Int>>,
    val tourCost: List<Double>,
    val objectiveValue: Double,
    val computationTimeInSec: Double,
    val fairness: Double
)
