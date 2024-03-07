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
import kotlin.properties.Delegates
import kotlin.time.Duration.Companion.seconds

private val log = KotlinLogging.logger {}

class InstanceDto(
    private val name: String,
    private val path: String,
    private val numVehicles: Int,
    private var vertexCoords: Map<Int, Coords> = mapOf(),
    private var edgeCosts: Map<Pair<Int, Int>, Double> = mapOf()
) {
    private lateinit var lines: List<String>
    private var numVertices = 0
    private var depot: Int = 0
    private val graph = Graph(DefaultWeightedEdge::class.java)


    companion object {
        /**
         * Builds Coords objects from a String containing coordinates
         * @param line string that contains 3 doubles
         * @return vertex object with given coordinates
         */
        private fun parseCoords(line: String): Pair<Int, Coords> {
            val values: List<Double> = line.trim().split("\\s+".toRegex()).map {
                it.toDouble()
            }
            return Pair(values[0].toInt(), Coords(values[1], values[2]))
        }

        private fun parseEdgeCost(line: String): Pair<Pair<Int, Int>, Double> {
            val values: List<Double> = line.trim().split("\\s+".toRegex()).map {
                it.toDouble()
            }
            return Pair(Pair(values[0].toInt(), values[1].toInt()), values[2])
        }
    }

    init {
        log.debug { "starting initialization of instance $name..." }
        collectLinesFromFile()

        val numVerticesLine = lines[3].split("[ \t]".toRegex())
        numVertices = numVerticesLine.last().toInt()
        log.info { "number of vertices $numVertices" }

        val depotLine = lines[1].split("[ \t]".toRegex())
        val depotFlag = depotLine.first() == "DEPOT"

        val vertexCoordsLines = lines.subList(6, 6 + numVertices)
        val coords = vertexCoordsLines.map(::parseCoords).associate {
            it.first to it.second
        }.toMutableMap()

        if (!depotFlag) {
            /*if the depot is not given*/
            numVertices += 1  /*adding the depot*/
            coords[0] = getDepotCoord(coords) /*assign vertex 0 to the depot*/
            depot = 0
        } else {
            /*if the depot is given*/
            depot = lines[6].trim().split("\\s+".toRegex()).first().toInt()
        }

        vertexCoords = coords

        val costLine = lines[4].split("[ \t]".toRegex())
        val costFlag = costLine.last() == "GIVEN"

        if (costFlag) {
            val edgeCostLines = lines.subList(7 + numVertices, lines.size - 1)
            edgeCosts = edgeCostLines.map(::parseEdgeCost).associate {
                it.first to it.second
            }
        }

        buildGraph() /*build the Graph*/
    }

    fun getInstance() = Instance(
        instanceName = name,
        graph = graph,
        numVehicles = numVehicles,
        depot = depot,
        vertexCoords = vertexCoords
    )

    private fun getEdgeLength(v1: Int, v2: Int): Double {
        if (edgeCosts.isEmpty()) {
            val c1 = vertexCoords[v1]!!
            val c2 = vertexCoords[v2]!!
            val dx = c1.x - c2.x
            val dy = c1.y - c2.y
            return round(sqrt(dx * dx + dy * dy))
        } else {
            return round(edgeCosts[Pair(v1, v2)]!!)
        }
    }

    private fun collectLinesFromFile() {
        lines = File(path + name).readLines()
    }

    private fun getDepotCoord(targetCoords: Map<Int, Coords>): Coords {
        val numTargets = targetCoords.size
        return Coords(
            x = targetCoords.map { it.value.x }.sumOf { it } / numTargets.toDouble(),
            y = targetCoords.map { it.value.y }.sumOf { it } / numTargets.toDouble())
    }

    private fun buildGraph() {
        /* add vertices to the graph */
        vertexCoords.forEach { (vertex, _) ->
            graph.addVertex(vertex)
        }

        val vertexList = vertexCoords.keys.toList()

        vertexList.indices.forEach { i ->
            (i + 1 until vertexList.size).forEach { j ->
                val source = vertexList[i]
                val target = vertexList[j]
                var edgeLength: Double = getEdgeLength(source, target)
                if (Parameters.objectiveType == "p-norm")
                    edgeLength /= Parameters.normalizingLength
                val edge = DefaultWeightedEdge()
                graph.addEdge(source, target, edge)
                graph.setEdgeWeight(edge, edgeLength)

            }
        }
    }
}
