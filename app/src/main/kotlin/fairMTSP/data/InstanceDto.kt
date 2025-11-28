package fairMTSP.data

import fairMTSP.main.Coords
import fairMTSP.main.Graph
import io.github.oshai.kotlinlogging.KotlinLogging
import org.jgrapht.graph.DefaultWeightedEdge
import java.io.File
import kotlin.math.round
import kotlin.math.sqrt

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
    private var edgeWeightFormat: String? = null
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
        log.debug { "number of vertices $numVertices" }

        val depotLine = lines[1].split("[ \t]".toRegex())
        val depotFlag = depotLine.first() == "DEPOT"

        // Parse EDGE_WEIGHT_TYPE - extract value after colon, handling both ":" and " : " formats
        val edgeWeightType = lines[4]
            .substringAfter(":", lines[4])
            .trim()
            .split(Regex("\\s+"))
            .first()
        log.debug { "edge weight type: $edgeWeightType" }

        val coords = mutableMapOf<Int, Coords>()

        if (edgeWeightType == "EXPLICIT") {
            // Read line 5 (0-indexed) and check if it starts with "EDGE_WEIGHT_FORMAT"
            if (lines.size > 5) {
                val line5 = lines[5].trim()
                if (line5.startsWith("EDGE_WEIGHT_FORMAT")) {
                    // Extract the value after the colon
                    edgeWeightFormat = line5
                        .substringAfter(":", "")
                        .trim()
                    log.debug { "edge weight format: $edgeWeightFormat" }
                }
            }
            
            // Populate with dummy coordinates (0,0) for numVertices
            for (i in 0 until numVertices) {
                coords[i] = Coords(0.0, 0.0)
            }
            depot = 0
            
            // Parse edge costs based on format
            edgeWeightFormat?.let { format ->
                when (format) {
                    "LOWER_DIAG_ROW" -> edgeCosts = parseLowerDiagRow()
                    "LOWER_ROW" -> edgeCosts = parseLowerRow()
                    "UPPER_ROW" -> edgeCosts = parseUpperRow()
                    else -> log.warn { "Unknown edge weight format: $format" }
                }
            }

        }
        else if (edgeWeightType == "EUC_2D" || edgeWeightType == "GEO" || edgeWeightType == "GIVEN") {
            val vertexCoordsLines = lines.subList(6, 6 + numVertices)
            vertexCoordsLines.map(::parseCoords).forEach { (vertex, coord) ->
                coords[vertex] = coord
            }
    
            if (!depotFlag) {
                /*if the depot is not given*/
                numVertices += 1  /*adding the depot*/
                coords[0] = getDepotCoord(coords) /*assign vertex 0 to the depot*/
                depot = 0
            } else {
                /*if the depot is given*/
                depot = lines[6].trim().split("\\s+".toRegex()).first().toInt()
            }
            if (edgeWeightType == "GIVEN") {
                val edgeCostLines = lines.subList(7 + numVertices, lines.size - 1)
                edgeCosts = edgeCostLines.map(::parseEdgeCost).associate {
                    it.first to it.second
                }
            }
        }

        vertexCoords = coords

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
                val edgeLength: Double = getEdgeLength(source, target)
                val edge = DefaultWeightedEdge()
                graph.addEdge(source, target, edge)
                graph.setEdgeWeight(edge, edgeLength)

            }
        }
    }

    /**
     * Extracts all numeric values from EDGE_WEIGHT_SECTION until EOF or next section
     * @return List of edge weight values as Doubles
     */
    private fun extractEdgeWeightValues(): List<Double> {
        val values = mutableListOf<Double>()
        var inEdgeWeightSection = false
        
        for (line in lines) {
            val trimmedLine = line.trim()
            
            if (trimmedLine.startsWith("EDGE_WEIGHT_SECTION")) {
                inEdgeWeightSection = true
                continue
            }
            
            if (inEdgeWeightSection) {
                // Stop at EOF or next section
                if (trimmedLine == "EOF" || 
                    trimmedLine.startsWith("DISPLAY_DATA_SECTION") ||
                    trimmedLine.startsWith("DEMAND_SECTION") ||
                    trimmedLine.startsWith("DEPOT_SECTION")) {
                    break
                }
                
                // Parse all numbers from the line
                val numbers = trimmedLine.split(Regex("\\s+"))
                    .filter { it.isNotBlank() }
                    .mapNotNull { it.toDoubleOrNull() }
                values.addAll(numbers)
            }
        }
        
        return values
    }

    /**
     * Parses LOWER_DIAG_ROW format: lower triangular matrix including diagonal
     * For n vertices, contains n*(n+1)/2 values
     * Row i contains: d(i,0), d(i,1), ..., d(i,i)
     * @return Map of edge costs with vertices numbered 0 to numVertices-1
     */
    private fun parseLowerDiagRow(): Map<Pair<Int, Int>, Double> {
        val values = extractEdgeWeightValues()
        val costs = mutableMapOf<Pair<Int, Int>, Double>()
        var index = 0
        
        for (i in 0 until numVertices) {
            for (j in 0..i) {
                if (index < values.size) {
                    val weight = values[index]
                    // Store both (i,j) and (j,i) since graph is undirected
                    costs[Pair(i, j)] = weight
                    costs[Pair(j, i)] = weight
                    index++
                }
            }
        }
        
        log.debug { "Parsed edge costs from LOWER_DIAG_ROW format for $numVertices vertices (${costs.size} entries)" }
        return costs
    }

    /**
     * Parses LOWER_ROW format: lower triangular matrix excluding diagonal
     * For n vertices, contains n*(n-1)/2 values
     * Row i contains: d(i,0), d(i,1), ..., d(i,i-1)
     * @return Map of edge costs with vertices numbered 0 to numVertices-1
     */
    private fun parseLowerRow(): Map<Pair<Int, Int>, Double> {
        val values = extractEdgeWeightValues()
        val costs = mutableMapOf<Pair<Int, Int>, Double>()
        var index = 0
        
        for (i in 1 until numVertices) {
            for (j in 0 until i) {
                if (index < values.size) {
                    val weight = values[index]
                    // Store both (i,j) and (j,i) since graph is undirected
                    costs[Pair(i, j)] = weight
                    costs[Pair(j, i)] = weight
                    index++
                }
            }
        }
        
        // Diagonal elements are 0 (distance from vertex to itself)
        for (i in 0 until numVertices) {
            costs[Pair(i, i)] = 0.0
        }
        
        log.debug { "Parsed edge costs from LOWER_ROW format for $numVertices vertices (${costs.size} entries)" }
        return costs
    }

    /**
     * Parses UPPER_ROW format: upper triangular matrix excluding diagonal
     * For n vertices, contains n*(n-1)/2 values
     * Row i contains: d(i,i+1), d(i,i+2), ..., d(i,n-1)
     * @return Map of edge costs with vertices numbered 0 to numVertices-1
     */
    private fun parseUpperRow(): Map<Pair<Int, Int>, Double> {
        val values = extractEdgeWeightValues()
        val costs = mutableMapOf<Pair<Int, Int>, Double>()
        var index = 0
        
        for (i in 0 until numVertices) {
            for (j in (i + 1) until numVertices) {
                if (index < values.size) {
                    val weight = values[index]
                    // Store both (i,j) and (j,i) since graph is undirected
                    costs[Pair(i, j)] = weight
                    costs[Pair(j, i)] = weight
                    index++
                }
            }
        }
        
        // Diagonal elements are 0 (distance from vertex to itself)
        for (i in 0 until numVertices) {
            costs[Pair(i, i)] = 0.0
        }
        
        log.debug { "Parsed edge costs from UPPER_ROW format for $numVertices vertices (${costs.size} entries)" }
        return costs
    }
}
