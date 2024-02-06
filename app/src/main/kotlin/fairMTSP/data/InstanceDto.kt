package fairMTSP.data

import fairMTSP.main.Coords
import fairMTSP.main.Graph
import io.github.oshai.kotlinlogging.KotlinLogging
import org.jgrapht.graph.DefaultWeightedEdge
import java.io.File
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.round
import kotlin.math.sqrt

private val log = KotlinLogging.logger {}

class InstanceDto(
    private val name: String,
    private val path: String,
    private val numVehicles: Int
) {
    private lateinit var lines: List<String>
    private var numVertices = 0
    private val depot = 0
    private val graph = Graph(DefaultWeightedEdge::class.java)
    private lateinit var coords: List<Coords>

    companion object {
        /**
         * Builds Coords objects from a String containing coordinates
         *
         * @param line string that contains 3 doubles
         * @return vertex object with given coordinates
         */
        private fun parseCoords(line: String): Coords {
            val values: List<Double> = line.trim().split("\\s+".toRegex()).map {
                it.toDouble()
            }
            return Coords(values[1], values[2])
        }
    }

    init {
        log.debug { "starting initialization of instance $name..." }
        collectLinesFromFile()

        val numVerticesLine = lines[3].split("[ \t]".toRegex())
        numVertices = numVerticesLine.last().toInt()
        log.info { "number of vertices $numVertices" }

        val vertexCoordsLines = lines.subList(6, 6 + numVertices)
        val vertexCoords = vertexCoordsLines.map(::parseCoords).toMutableList()

        numVertices += 1  /*adding the depot*/
        coords = listOf(getDepotCoord(vertexCoords)) + vertexCoords

        buildGraph(coords)

    }

    fun getInstance() = Instance(
        instanceName = name,
        graph = graph,
        numVehicles = numVehicles,
        depot = depot,
        vertexCoords = coords
    )

    private fun getEdgeLength(c1: Coords, c2: Coords): Double {
        val dx = c1.x - c2.x
        val dy = c1.y - c2.y
        return round(sqrt(dx * dx + dy * dy))
    }

    private fun collectLinesFromFile() {
        lines = File(path + name).readLines()
    }

    private fun getDepotCoord(targetCoords: MutableList<Coords>): Coords {
        val numTargets = targetCoords.size
        return Coords(
            x = targetCoords.sumOf { it.x } / numTargets.toDouble(),
            y = targetCoords.sumOf { it.y } / numTargets.toDouble())
    }

    private fun buildGraph(vertices: List<Coords>) {
        /* add vertices to the graph */
        for (i in 0 until numVertices)
            graph.addVertex(i)


        for (i in 0 until numVertices) {
            for (j in i + 1 until numVertices) {
                val edgeLength: Double = getEdgeLength(vertices[i], vertices[j])
                val edge = DefaultWeightedEdge()
                graph.addEdge(i, j, edge)
                graph.setEdgeWeight(edge, edgeLength)
            }
        }
    }
}
