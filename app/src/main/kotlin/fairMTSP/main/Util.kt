package fairMTSP.main

import org.jgrapht.graph.DefaultWeightedEdge
import org.jgrapht.graph.SimpleWeightedGraph

/**
 * Custom exception to throw problem-specific exception.
 */
class OrienteeringException(message: String) : Exception(message)

data class Coords(val x: Double, val y: Double)

typealias Graph = SimpleWeightedGraph<Int, DefaultWeightedEdge>

fun Graph.numVertices() = this.vertexSet().size