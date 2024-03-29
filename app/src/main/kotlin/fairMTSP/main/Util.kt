package fairMTSP.main

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.jgrapht.graph.DefaultWeightedEdge
import org.jgrapht.graph.SimpleWeightedGraph

/**
 * Custom exception to throw problem-specific exception.
 */
class FairMTSPException(message: String) : Exception(message)

@Serializable
data class Coords(val x: Double, val y: Double)

typealias Graph = SimpleWeightedGraph<Int, DefaultWeightedEdge>

typealias VertexType = ULong

fun Graph.numVertices() = this.vertexSet().size

@OptIn(ExperimentalSerializationApi::class)
val prettyJson = Json { // this returns the JsonBuilder
    prettyPrint = true
    // optional: specify indent
    prettyPrintIndent = " "
    explicitNulls = true
}