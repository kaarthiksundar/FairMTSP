package fairMTSP.solver

import fairMTSP.data.Instance
import fairMTSP.main.Graph
import fairMTSP.main.numVertices
import ilog.concert.IloLinearNumExpr
import ilog.concert.IloNumVar
import ilog.cplex.IloCplex
import ilog.cplex.IloCplex.Callback.Context
import ilog.cplex.IloCplexModeler
import io.github.oshai.kotlinlogging.KotlinLogging
import org.jgrapht.alg.connectivity.ConnectivityInspector
import org.jgrapht.alg.flow.GusfieldGomoryHuCutTree
import org.jgrapht.alg.tour.NearestInsertionHeuristicTSP
import org.jgrapht.alg.tour.TwoOptHeuristicTSP
import org.jgrapht.graph.DefaultWeightedEdge
import kotlin.math.pow
import kotlin.math.sqrt

private val log = KotlinLogging.logger {}

class FairMTSPCallback(
    private val instance: Instance,
    private val edgeVariable: Map<Int, Map<DefaultWeightedEdge, IloNumVar>>,
    private val vertexVariable: Map<Int, Map<Int, IloNumVar>>,
    private val vehicleLength: Map<Int, IloNumVar>,
    private val minMaxAuxiliaryVariable: IloNumVar,
    private var fairnessFactor: IloNumVar,
    private var conicAuxiliaryVariable: Map<Int, IloNumVar>,
    private var pNormAuxiliaryVariable: IloNumVar,
    private val objectiveType: String,
    private val fairnessCoefficient: Double,
    private val pNorm: Int,
) : IloCplex.Callback.Function {

    override fun invoke(context: Context) {

        if (context.inRelaxation()) {
            roundingHeuristic(context)
            fractionalSECs(context)
        }

        if (context.inCandidate()) {
            integerSECs(context)
            if (objectiveType == "eps-fair")
                fairnessOuterApproximations(context)
            if (objectiveType == "p-norm")
                pNormOuterApproximations(context)
        }
    }

    private fun roundingHeuristic(context: Context) {
        val graph = instance.graph
        val numVehicles = instance.numVehicles
        val numVertices = instance.graph.numVertices()

        val vars = mutableListOf<IloNumVar>()
        val vals = mutableListOf<Double>()

        var newSolutionObjectiveValue = 0.0
        val tourLengths = mutableListOf<Double>()

        val assignments =
            (0 until numVehicles).associateWith { mutableListOf(instance.depot) }
        /* assign each vertex to a vehicle */
        (0 until graph.numVertices()).forEach vertex@{ vertex ->
            if (vertex == instance.depot) return@vertex

            val list = (0 until numVehicles).map { vehicle ->
                context.getRelaxationPoint(arrayOf(vertexVariable[vehicle]?.get(vertex))).first()
            }
            assignments[list.indexOf(list.max())]?.add(vertex)
        }

        /* create subgraph for each vehicle */
        (0 until numVehicles).forEach { vehicle ->
            val subGraph = Graph(DefaultWeightedEdge::class.java)
            assignments[vehicle]?.forEach { subGraph.addVertex(it) }

            val edgesInSubset = graph.edgeSet().filter {
                graph.getEdgeSource(it) in subGraph.vertexSet() &&
                        graph.getEdgeTarget(it) in subGraph.vertexSet()
            }

            edgesInSubset.forEach { edge ->
                subGraph.addEdge(graph.getEdgeSource(edge), graph.getEdgeTarget(edge), edge)
                subGraph.setEdgeWeight(edge, graph.getEdgeWeight(edge))
            }

            val tspSolver = TwoOptHeuristicTSP(
                5,
                NearestInsertionHeuristicTSP<Int, DefaultWeightedEdge>()
            )

            val tour = tspSolver.getTour(subGraph)
            val tourEdges = tour.edgeList

            /* add all vertex variables and their values for this vehicle */
            (0 until numVertices).forEach { vertex ->
                vars.add(vertexVariable[vehicle]?.get(vertex)!!)
                val temp = if (assignments[vehicle]?.contains(vertex) == true) 1.0 else 0.0
                vals.add(temp)
            }

            /* add all edge variables and their values for this vehicle */
            graph.edgeSet().forEach { edge ->
                vars.add(edgeVariable[vehicle]?.get(edge)!!)
                val temp = if (tourEdges.contains(edge)) {
                    if (subGraph.edgeSet().size == 1)
                        2.0
                    else
                        1.0
                } else
                    0.0
                vals.add(temp)
            }

            vars.add(vehicleLength[vehicle]!!)
            vals.add(tour.weight)
            tourLengths.add(tour.weight)
        }

        if (objectiveType == "min") {
            newSolutionObjectiveValue = tourLengths.sum()
        }
        if (objectiveType == "min-max") {
            newSolutionObjectiveValue = tourLengths.max()
            vars.add(minMaxAuxiliaryVariable)
            vals.add(newSolutionObjectiveValue)
        }
        if (objectiveType == "fair") {
            newSolutionObjectiveValue = tourLengths.sum()

            vars.add(fairnessFactor)
            val epsBar = 1.0 + (sqrt(instance.numVehicles.toDouble()) - 1) * fairnessCoefficient
            val fairnessFactorValue = tourLengths.sum() / epsBar
            vals.add(fairnessFactorValue)

            (0 until numVehicles).forEach { vehicle ->
                vars.add(conicAuxiliaryVariable[vehicle]!!)
                vals.add(tourLengths[vehicle].pow(2.0) / fairnessFactorValue)
            }
        }
        if (objectiveType == "p-norm") {
            newSolutionObjectiveValue = tourLengths.sumOf { it.pow(pNorm) }

            (0 until numVehicles).forEach { vehicle ->
                vars.add(conicAuxiliaryVariable[vehicle]!!)
                vals.add(tourLengths[vehicle].pow(pNorm) / newSolutionObjectiveValue.pow(pNorm - 1))
            }
        }

        // Post the rounded solution, CPLEX will check feasibility.
        context.postHeuristicSolution(
            vars.toTypedArray(), vals.toDoubleArray(), 0, vars.size, newSolutionObjectiveValue,
            Context.SolutionStrategy.Propagate
        )
    }

    private fun fractionalSECs(context: Context) {
        val m: IloCplexModeler = context.cplex
        val tolerance = 1e-5

        val graph = instance.graph
        val numVehicles = instance.numVehicles

        (0 until numVehicles).forEach { vehicle ->
            val activeVertices =
                vertexVariable[vehicle]!!.map { Pair(it.key, context.getRelaxationPoint(it.value)) }.filter {
                    it.second > tolerance
                }.toMap()
            val activeEdges =
                edgeVariable[vehicle]!!.map { Pair(it.key, context.getRelaxationPoint(it.value)) }.filter {
                    it.second > tolerance
                }.toMap()

            val subGraph = Graph(DefaultWeightedEdge::class.java)
            activeVertices.forEach { subGraph.addVertex(it.key) }
            activeEdges.forEach { (e, weight) ->
                val edge = DefaultWeightedEdge()
                subGraph.addEdge(graph.getEdgeSource(e), graph.getEdgeTarget(e), edge)
                subGraph.setEdgeWeight(edge, weight)
            }

            val connectedSets = ConnectivityInspector(subGraph).connectedSets().toList()

            if (connectedSets.size == 1 && subGraph.vertexSet().size != 1) {
                val gomoryHuCutTree = GusfieldGomoryHuCutTree(subGraph)
                val minCut = gomoryHuCutTree.calculateMinCut()
                if (minCut < 2.0) {
                    val vertexSubset = if (instance.depot in gomoryHuCutTree.sourcePartition)
                        gomoryHuCutTree.sinkPartition
                    else
                        gomoryHuCutTree.sourcePartition

                    val edgesInSubset = graph.edgeSet().filter {
                        graph.getEdgeSource(it) in vertexSubset &&
                                graph.getEdgeTarget(it) in vertexSubset
                    }

                    vertexSubset.forEach { vertex ->
                        if (minCut - 2.0 * activeVertices[vertex]!! < tolerance) {
                            val subTourExpr: IloLinearNumExpr = m.linearNumExpr()
                            subTourExpr.addTerms(
                                edgesInSubset.map { edgeVariable[vehicle]?.get(it) }.toTypedArray(),
                                List(edgesInSubset.size) { 1.0 }.toDoubleArray()
                            )
                            subTourExpr.addTerms(
                                vertexSubset.map { vertexVariable[vehicle]?.get(it) }.toTypedArray(),
                                List(vertexSubset.size) { -1.0 }.toDoubleArray()
                            )
                            subTourExpr.addTerm(1.0, vertexVariable[vehicle]?.get(vertex))
                            context.addUserCut(m.le(subTourExpr, 0.0), IloCplex.CutManagement.UseCutPurge, false)
//                            log.debug { "adding fractional SEC for vehicle $vehicle and subset $vertexSubset " }
                            subTourExpr.clear()
                        }
                    }
                }
            } else {
                connectedSets.forEach set@{ subset ->
                    if (instance.depot in subset) return@set
                    val edgesInSubset = graph.edgeSet().filter {
                        graph.getEdgeSource(it) in subset &&
                                graph.getEdgeTarget(it) in subset
                    }
                    subset.iterator().forEach { vertex ->
                        val subTourExpr: IloLinearNumExpr = m.linearNumExpr()
                        subTourExpr.addTerms(
                            edgesInSubset.map { edgeVariable[vehicle]?.get(it) }.toTypedArray(),
                            List(edgesInSubset.size) { 1.0 }.toDoubleArray()
                        )
                        subTourExpr.addTerms(
                            subset.map { vertexVariable[vehicle]?.get(it) }.toTypedArray(),
                            List(subset.size) { -1.0 }.toDoubleArray()
                        )
                        subTourExpr.addTerm(1.0, vertexVariable[vehicle]?.get(vertex))
                        context.addUserCut(m.le(subTourExpr, 0.0), IloCplex.CutManagement.UseCutPurge, false)
//                        log.debug { "adding fractional SEC for vehicle $vehicle and subset $subset " }
                        subTourExpr.clear()
                    }
                }
            }
        }
    }

    private fun integerSECs(context: Context) {
        val m: IloCplexModeler = context.cplex
        val connectedSets: MutableList<Set<Int>> = mutableListOf()
        val graph = instance.graph
        val numVehicles = instance.numVehicles

        (0 until numVehicles).forEach { vehicle ->
            // get the active vertices for the vehicle
            val activeVertices = vertexVariable[vehicle]!!.toList().map {
                Pair(it.first, context.getCandidatePoint(it.second))
            }.filter { it1 ->
                it1.second > 0.9
            }.map { it2 ->
                it2.first
            }

            val activeEdges = edgeVariable[vehicle]!!.toList().map {
                Pair(it.first, context.getCandidatePoint(it.second))
            }.filter { it1 ->
                it1.second > 0.9
            }.map { it2 ->
                it2.first
            }

            val subGraph = Graph(DefaultWeightedEdge::class.java)
            activeVertices.forEach { subGraph.addVertex(it) }
            activeEdges.forEach {
                subGraph.addEdge(graph.getEdgeSource(it), graph.getEdgeTarget(it), it)
            }
            connectedSets += ConnectivityInspector(subGraph).connectedSets().filter { !it.contains(instance.depot) }
                .toList()
        }
        if (connectedSets.isEmpty())
            return

        /* symmetric breaking included */
        (0 until numVehicles).forEach { vehicle ->
            connectedSets.iterator().forEach set@{ vertexSubset ->
                val edgesInSubset = graph.edgeSet().filter {
                    graph.getEdgeSource(it) in vertexSubset &&
                            graph.getEdgeTarget(it) in vertexSubset
                }
                vertexSubset.iterator().forEach { vertex ->
                    val subTourExpr: IloLinearNumExpr = m.linearNumExpr()
                    subTourExpr.addTerms(
                        edgesInSubset.map { edgeVariable[vehicle]?.get(it) }.toTypedArray(),
                        List(edgesInSubset.size) { 1.0 }.toDoubleArray()
                    )
                    subTourExpr.addTerms(
                        vertexSubset.map { vertexVariable[vehicle]?.get(it) }.toTypedArray(),
                        List(vertexSubset.size) { -1.0 }.toDoubleArray()
                    )
                    subTourExpr.addTerm(1.0, vertexVariable[vehicle]?.get(vertex))
                    context.rejectCandidate(m.le(subTourExpr, 0.0))
//                    log.debug { "adding integer SEC for vehicle $vehicle and subset $vertexSubset " }
                    subTourExpr.clear()
                }
            }
        }
    }

    private fun fairnessOuterApproximations(context: Context) {
        val m: IloCplexModeler = context.cplex
        val numVehicles = instance.numVehicles
        val tolerance = 1e-5
        /* Add outer approximations for x^2 <= y*z with y, z >= 0 */
        (0 until numVehicles).forEach { vehicle ->
            val x = context.getCandidatePoint(vehicleLength[vehicle])
            val y = context.getCandidatePoint(conicAuxiliaryVariable[vehicle])
            val z = context.getCandidatePoint(fairnessFactor)

            if (x.pow(2) - y * z > tolerance) {
                val projectionPoints = getFairnessProjectionPoints(x, y, z)
                projectionPoints.forEach { (x0, y0, z0) ->
                    val cutExpr: IloLinearNumExpr = m.linearNumExpr()
                    cutExpr.addTerms(
                        listOf(
                            vehicleLength[vehicle],
                            conicAuxiliaryVariable[vehicle],
                            fairnessFactor
                        ).toTypedArray(),
                        listOf(2.0 * x0, -z0, -y0).toDoubleArray()
                    )
                    context.rejectCandidate(m.le(cutExpr, 0.0))
                    log.debug { "adding fairness OA for vehicle $vehicle" }
                    cutExpr.clear()
                }
            }
        }
    }

    private fun getFairnessProjectionPoints(x: Double, y: Double, z: Double): List<List<Double>> {
        val tolerance = 1e-5
        val projectionPoints: MutableList<List<Double>> = mutableListOf()
        projectionPoints.add(listOf(sqrt(y * z), y, z))
        if (z > tolerance) projectionPoints.add(listOf(x, x.pow(2) / z, z))
        if (y > tolerance) projectionPoints.add(listOf(x, y, x.pow(2) / y))
        return projectionPoints
    }

    private fun pNormOuterApproximations(context: Context) {
        val m: IloCplexModeler = context.cplex
        val numVehicles = instance.numVehicles
        val tolerance = 1e-5
        val alpha = 1.0 / pNorm

        (0 until numVehicles).forEach { vehicle ->
            val x = context.getCandidatePoint(conicAuxiliaryVariable[vehicle])
            val y = context.getCandidatePoint(pNormAuxiliaryVariable)
            val z = context.getCandidatePoint(vehicleLength[vehicle])

            if (z - x.pow(alpha) * y.pow(1.0 - alpha) > tolerance) {
                val projectionPoints = getpNormProjectionPoints(x, y, z)
                projectionPoints.forEach { (x0, y0, z0) ->
                    val cutExpr: IloLinearNumExpr = m.linearNumExpr()
                    cutExpr.addTerms(
                        listOf(
                            conicAuxiliaryVariable[vehicle],
                            pNormAuxiliaryVariable,
                            vehicleLength[vehicle]
                        ).toTypedArray(),
                        listOf(
                            alpha * (x0 / y0).pow(alpha - 1),
                            (1 - alpha) * (x0 / y0).pow(alpha),
                            -1.0
                        ).toDoubleArray()
                    )
                    context.rejectCandidate(m.ge(cutExpr, 0.0))
                    log.debug { "adding p-norm OA for vehicle $vehicle" }
                    log.debug { cutExpr }
                    cutExpr.clear()
                }
            }
        }
    }

    private fun getpNormProjectionPoints(x: Double, y: Double, z: Double): List<List<Double>> {
        /* z <= x^alpha * y^(1-alpha) */
        val alpha = 1.0 / pNorm
        val tolerance = 1e-5
        val projectionPoints: MutableList<List<Double>> = mutableListOf()
//        projectionPoints.add(listOf(x, y, x.pow(alpha) * y.pow(1 - alpha)))
        if (y > tolerance) projectionPoints.add(listOf(z.pow(pNorm) / (y.pow(pNorm - 1.0)), y, z))
        if (x > tolerance) projectionPoints.add(listOf(x, z.pow(pNorm / (pNorm - 1)) / x.pow(1.0 / (pNorm - 1)), z))
        return projectionPoints
    }
}

