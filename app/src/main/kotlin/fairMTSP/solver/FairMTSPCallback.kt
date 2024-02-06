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
    private val x: Map<Int, Map<DefaultWeightedEdge, IloNumVar>>,
    private val y: Map<Int, Map<Int, IloNumVar>>,
    private val l: Map<Int, IloNumVar>,
    private val z: IloNumVar,
    private var leps: IloNumVar,
    private var k: Map<Int, IloNumVar>,
    private val objectiveType: String,
    private val fairness: Double
) : IloCplex.Callback.Function {

    override fun invoke(context: IloCplex.Callback.Context) {
        if (context.inRelaxation()) {
            heuristicCallback(context)
            userSubTourEli(context)
        }
        if (context.inCandidate()) {
            lazySubTourEli(context)
        }
    }

    private fun userSubTourEli(context: IloCplex.Callback.Context) {
        log.debug { "In user callback" }
        val m: IloCplexModeler = context.cplex
        val eps = 1e-5

        val graph = instance.graph
        val numVehicles = instance.numVehicles

        (0 until numVehicles).forEach { vehicle ->

            val activeVertices = y[vehicle]!!.map { Pair(it.key, context.getRelaxationPoint(it.value)) }.filter {
                it.second > eps
            }.toMap()

            val activeEdges = x[vehicle]!!.map { Pair(it.key, context.getRelaxationPoint(it.value)) }.filter {
                it.second > eps
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
                    val subset = if (instance.depot in gomoryHuCutTree.sourcePartition) {
                        gomoryHuCutTree.sinkPartition
                    } else {
                        gomoryHuCutTree.sourcePartition
                    }

                    val edgesInSubset = graph.edgeSet().filter {
                        graph.getEdgeSource(it) in subset &&
                                graph.getEdgeTarget(it) in subset
                    }


                    subset.forEach { vertex ->
                        if (minCut < 2 * activeVertices[vertex]!!
                        ) {
                            val subTourExpr: IloLinearNumExpr = m.linearNumExpr()
                            subTourExpr.addTerms(
                                edgesInSubset.map { x[vehicle]?.get(it) }.toTypedArray(),
                                List(edgesInSubset.size) { 1.0 }.toDoubleArray()
                            )
                            subTourExpr.addTerms(
                                subset.map { y[vehicle]?.get(it) }.toTypedArray(),
                                List(subset.size) { -1.0 }.toDoubleArray()
                            )
                            subTourExpr.addTerm(1.0, y[vehicle]?.get(vertex))
                            context.addUserCut(m.le(subTourExpr, 0.0), IloCplex.CutManagement.UseCutPurge, false)
                            log.debug { "adding USER subTour elimination constraint for vehicle $vehicle and subset $subset " }
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
                            edgesInSubset.map { x[vehicle]?.get(it) }.toTypedArray(),
                            List(edgesInSubset.size) { 1.0 }.toDoubleArray()
                        )
                        subTourExpr.addTerms(
                            subset.map { y[vehicle]?.get(it) }.toTypedArray(),
                            List(subset.size) { -1.0 }.toDoubleArray()
                        )
                        subTourExpr.addTerm(1.0, y[vehicle]?.get(vertex))
                        context.addUserCut(m.le(subTourExpr, 0.0), IloCplex.CutManagement.UseCutPurge, false)
                        log.debug { "adding USER subTour elimination constraint for vehicle $vehicle and subset $subset " }
                        subTourExpr.clear()
                    }
                }
            }
        }
    }

    private fun lazySubTourEli(context: IloCplex.Callback.Context) {

        val m: IloCplexModeler = context.cplex
        val connectedSets: MutableList<Set<Int>> = mutableListOf()

        val graph = instance.graph
        val numVehicles = instance.numVehicles

        (0 until numVehicles).forEach { vehicle ->
            // get the active vertices for the vehicle
            val activeVertices = y[vehicle]!!.toList().map {
                Pair(it.first, context.getCandidatePoint(it.second))
            }.filter { it1 ->
                it1.second > 0.9
            }.map { it2 ->
                it2.first
            }

            val activeEdges = x[vehicle]!!.toList().map {
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
            connectedSets += ConnectivityInspector(subGraph).connectedSets().toList()
        }

        (0 until numVehicles).forEach { vehicle ->
            connectedSets.iterator().forEach set@{ subset ->
                if (instance.depot in subset) return@set
                val edgesInSubset = graph.edgeSet().filter {
                    graph.getEdgeSource(it) in subset &&
                            graph.getEdgeTarget(it) in subset
                }
                subset.iterator().forEach { vertex ->
                    val subTourExpr: IloLinearNumExpr = m.linearNumExpr()
                    subTourExpr.addTerms(
                        edgesInSubset.map { x[vehicle]?.get(it) }.toTypedArray(),
                        List(edgesInSubset.size) { 1.0 }.toDoubleArray()
                    )
                    subTourExpr.addTerms(
                        subset.map { y[vehicle]?.get(it) }.toTypedArray(),
                        List(subset.size) { -1.0 }.toDoubleArray()
                    )
                    subTourExpr.addTerm(1.0, y[vehicle]?.get(vertex))
                    context.rejectCandidate(m.le(subTourExpr, 0.0))
                    log.debug { "adding LAZY subTour elimination constraint for vehicle $vehicle and subset $subset " }
                    subTourExpr.clear()
                }
            }
        }
        if (objectiveType == "fair") {
            /*Add tangent cuts*/
            (0 until numVehicles).forEach { vehicle ->
                val li = context.getCandidatePoint(l[vehicle])
                val ki = context.getCandidatePoint(k[vehicle])
                val leps_ = context.getCandidatePoint(leps)

                if (li * li - ki * leps_ > 1e-5) {
                    val projectionPoints = getProjectionPoints(li, ki, leps_)
                    projectionPoints.forEach { (li0, ki0, leps0) ->
                        val cutExpr: IloLinearNumExpr = m.linearNumExpr()
                        cutExpr.addTerms(
                            listOf(l[vehicle], k[vehicle], leps).toTypedArray(),
                            listOf(2 * li0, -leps0, -ki0).toDoubleArray()
                        )
                        context.rejectCandidate(m.le(cutExpr, 0.0))
                        log.debug { "adding OA cut for vehicle $vehicle" }
                        cutExpr.clear()
                    }
                }
            }
        }
    }

    private fun getProjectionPoints(li: Double, ki: Double, leps_: Double): List<List<Double>> {
        val projectionPoints: MutableList<List<Double>> = mutableListOf()
        projectionPoints.add(listOf(sqrt(ki * leps_), ki, leps_))

        return projectionPoints
    }

    private fun heuristicCallback(context: IloCplex.Callback.Context) {

        val graph = instance.graph
        val numVehicles = instance.numVehicles
        val numVertices = instance.graph.numVertices()

        val _vars = mutableListOf<IloNumVar>()
        val _vals = mutableListOf<Double>()

        var objrel = 0.0
        val tourLengths = mutableListOf<Double>()

        val assignments =
            (0 until numVehicles).associateWith { mutableListOf(instance.depot) }
        /*assign each vertex to a vehicle*/
        (0 until graph.numVertices()).forEach vertex@{ vertex ->
            if (vertex == instance.depot) return@vertex

            val list = (0 until numVehicles).map { vehicle ->
                context.getRelaxationPoint(arrayOf(y[vehicle]?.get(vertex))).first()
            }
            assignments[list.indexOf(list.max())]?.add(vertex)
        }

        /*create subgraph for each vehicle*/
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

            /*add all vertex variables and their values for this vehicle*/
            (0 until numVertices).forEach { vertex ->
                _vars.add(y[vehicle]?.get(vertex)!!)
                val temp = if (assignments[vehicle]?.contains(vertex) == true) 1.0 else 0.0
                _vals.add(temp)
            }

            /*add all edge variables and their values for this vehicle*/
            graph.edgeSet().forEach { edge ->
                _vars.add(x[vehicle]?.get(edge)!!)

                val temp = if (tourEdges.contains(edge)) {
                    if (subGraph.edgeSet().size == 1) 2.0 else 1.0
                } else {
                    0.0
                }
                _vals.add(temp)
            }

            _vars.add(l[vehicle]!!)
            _vals.add(tour.weight)
            tourLengths.add(tour.weight)
        }



        if (objectiveType == "min") {
            objrel = tourLengths.sum()
        }
        if (objectiveType == "min-max") {
            objrel = tourLengths.max()
            _vars.add(z)
            _vals.add(objrel)
        }
        if (objectiveType == "fair") {
            objrel = tourLengths.sum()

            _vars.add(leps)
            val eBar = 1.0 + (sqrt(instance.numVehicles.toDouble()) - 1) * fairness
            val leps_ = tourLengths.sum() / eBar
            _vals.add(leps_)

            (0 until numVehicles).forEach { vehicle ->
                _vars.add(k[vehicle]!!)
                _vals.add(tourLengths[vehicle].pow(2.0) / leps_)
            }
        }

        // Post the rounded solution, CPLEX will check feasibility.
        context.postHeuristicSolution(
            _vars.toTypedArray(), _vals.toDoubleArray(), 0, _vars.size, objrel,
            Context.SolutionStrategy.CheckFeasible
        )
    }
}

