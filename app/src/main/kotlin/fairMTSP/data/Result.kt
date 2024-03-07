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
    val tours: List<List<Int>>? = null,
    val tourCost: List<Double>? = null,
    val objectiveValue: Double? = null,
    val computationTimeInSec: Double,
    val fairnessCoefficient: Double,
    val pNorm: Int,
    val optimalityGapPercent: Double? = null
)
