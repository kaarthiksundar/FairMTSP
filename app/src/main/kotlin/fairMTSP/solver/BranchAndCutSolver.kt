package fairMTSP.solver

import fairMTSP.data.Instance
import fairMTSP.data.Parameters
import fairMTSP.data.Result
import fairMTSP.main.FairMTSPException
import fairMTSP.main.Graph
import fairMTSP.main.numVertices
import ilog.concert.IloIntVar
import ilog.concert.IloLinearNumExpr
import ilog.concert.IloNumVar
import ilog.cplex.IloCplex
import io.github.oshai.kotlinlogging.KotlinLogging
import org.jgrapht.graph.DefaultWeightedEdge
import kotlin.math.pow
import kotlin.math.round
import kotlin.math.sqrt
import kotlin.properties.Delegates

private val log = KotlinLogging.logger {}

class BranchAndCutSolver(
    private val instance: Instance,
    private val cplex: IloCplex,
    config: Parameters,
    private val graph: Graph = instance.graph
) {

    private val objectiveType = config.objectiveType
    private val fairnessCoefficient = config.fairnessCoefficient
    private val pNorm = config.pNorm
    private val timeLimitInSeconds = config.timeLimitInSeconds
    private var computationTime by Delegates.notNull<Double>()
    private lateinit var edgeVariable: Map<Int, Map<DefaultWeightedEdge, IloIntVar>>
    private lateinit var vertexVariable: Map<Int, Map<Int, IloIntVar>>
    private lateinit var vehicleLength: Map<Int, IloNumVar>
    private lateinit var minMaxAuxiliaryVariable: IloNumVar
    private lateinit var fairnessFactor: IloNumVar  /*Leps*/
    private lateinit var conicAuxiliaryVariable: Map<Int, IloNumVar> /* common conic variable for fair and p-norm objective */
    private lateinit var pNormAuxiliaryVariable: IloNumVar /* objective variable for p-norm */

    init {
        addVariables()
        addConstraints()
        addObjective()
        setupCallback()
    }

    private fun addVariables() {

        edgeVariable = (0 until instance.numVehicles).associateWith { vehicle ->
            graph.edgeSet().associateWith { edge ->
                if (graph.getEdgeSource(edge) == instance.depot)
                    cplex.intVar(0, 2, "x_${vehicle}_${edge}")
                else
                    cplex.boolVar("x_${vehicle}_${edge}")
            }
        }


        vertexVariable = (0 until instance.numVehicles).associateWith { vehicle ->
            graph.vertexSet().associateWith { vertex ->
                cplex.boolVar("y_${vehicle}_${vertex}")
            }
        }

        vehicleLength = (0 until instance.numVehicles).associateWith { vehicle ->
            cplex.numVar(0.0, Double.POSITIVE_INFINITY, "l_${vehicle}")
        }

        minMaxAuxiliaryVariable = cplex.numVar(0.0, Double.POSITIVE_INFINITY, "z")

        conicAuxiliaryVariable = (0 until instance.numVehicles).associateWith { vehicle ->
            cplex.numVar(0.0, Double.POSITIVE_INFINITY, "k_${vehicle}")
        }

        fairnessFactor = cplex.numVar(0.0, Double.POSITIVE_INFINITY, "leps")

        pNormAuxiliaryVariable = cplex.numVar(0.0, Double.POSITIVE_INFINITY, "pNormAuxVar${pNorm}")


    }

    private fun addConstraints() {
        addDegreeConstraints()
        addVertexVisitConstraints()
        addLengthDefinition()
        addDepotVisitRedundantConstraints()
        addTwoVertexSECs()
        addSymmetryConstraints()
        if (objectiveType == "min-max")
            addMinMaxConstraints()
        if (objectiveType == "p-norm")
            addpNormConstraints()
        if (objectiveType == "eps-fair")
            addEPSFairConstraints()
        if (objectiveType == "delta-fair") {
            addDeltaFairConstraints()
        }
    }

    private fun addDegreeConstraints() {
        (0 until instance.numVehicles).forEach vehicle@{ vehicle ->
            graph.vertexSet().forEach vertex@{ vertex ->
                if (vertex == instance.depot) return@vertex

                val degreeExpr: IloLinearNumExpr = cplex.linearNumExpr()
                degreeExpr.addTerms(
                    graph.edgesOf(vertex).map { edgeVariable[vehicle]?.get(it) }.toTypedArray(),
                    List(graph.edgesOf(vertex).size) { 1.0 }.toDoubleArray()
                )
                degreeExpr.addTerm(-2.0, vertexVariable[vehicle]?.get(vertex))
                cplex.addEq(degreeExpr, 0.0, "deg_${vehicle}_${vertex}")
                degreeExpr.clear()
            }
        }
    }

    private fun addLengthDefinition() {
        (0 until instance.numVehicles).forEach { vehicle ->
            cplex.addGe(vehicleLength[vehicle], 0.0)
            val lenExpr: IloLinearNumExpr = cplex.linearNumExpr()
            lenExpr.addTerms(
                graph.edgeSet().map { edge -> edgeVariable[vehicle]?.get(edge) }.toTypedArray(),
                graph.edgeSet().map { edge -> -graph.getEdgeWeight(edge) }.toDoubleArray()
            )
            lenExpr.addTerm(1.0, vehicleLength[vehicle])
            cplex.addEq(lenExpr, 0.0, "TourLen_${vehicle}")
            lenExpr.clear()
        }
    }

    private fun addVertexVisitConstraints() {
        graph.vertexSet().forEach vertex@{ vertex ->
            if (vertex == instance.depot) return@vertex

            val visitExpr: IloLinearNumExpr = cplex.linearNumExpr()
            visitExpr.addTerms(
                (0 until instance.numVehicles).map { vertexVariable[it]?.get(vertex) }.toTypedArray(),
                List(instance.numVehicles) { 1.0 }.toDoubleArray()
            )
            cplex.addEq(visitExpr, 1.0, "visit_${vertex}")
            visitExpr.clear()
        }
    }

    /* this set of constraints is to make life easy during callbacks */
    private fun addDepotVisitRedundantConstraints() {
        (0 until instance.numVehicles).forEach { vehicle ->
            cplex.addEq(vertexVariable[vehicle]?.get(instance.depot), 1.0, "depot_visit_${vehicle}")
        }
    }

    private fun addTwoVertexSECs() {
        (0 until instance.numVehicles).forEach { vehicle ->
            graph.edgeSet().forEach edge@{ edge ->
                val i = graph.getEdgeSource(edge)
                val j = graph.getEdgeTarget(edge)
                if (i == instance.depot || j == instance.depot) return@edge
                val iExpr: IloLinearNumExpr = cplex.linearNumExpr()
                iExpr.addTerms(
                    listOf(edgeVariable[vehicle]!![edge], vertexVariable[vehicle]!![i]).toTypedArray(),
                    listOf(1.0, -1.0).toDoubleArray()
                )
                cplex.addLe(iExpr, 0.0, "2SEC_${vehicle}_($i,$j)_$i")
                val jExpr: IloLinearNumExpr = cplex.linearNumExpr()
                jExpr.addTerms(
                    listOf(edgeVariable[vehicle]!![edge], vertexVariable[vehicle]!![j]).toTypedArray(),
                    listOf(1.0, -1.0).toDoubleArray()
                )
                cplex.addLe(jExpr, 0.0, "2SEC_${vehicle}_($i,$j)_$j")
                iExpr.clear()
                jExpr.clear()
            }
        }
    }

    private fun addSymmetryConstraints() {
        /* Add constraints l1 >= l2 >= l3 >= ... >= ln */
        (0 until instance.numVehicles - 1).forEach { vehicle ->
            val symExpr: IloLinearNumExpr = cplex.linearNumExpr()
            symExpr.addTerms(
                listOf(vehicleLength[vehicle], vehicleLength[vehicle + 1]).toTypedArray(),
                listOf(1.0, -1.0).toDoubleArray()
            )
            cplex.addGe(symExpr, 0.0, "TourLenVehi${vehicle}_${vehicle + 1}")
        }
    }

    private fun addMinMaxConstraints() {
        (0 until instance.numVehicles).forEach { vehicle ->
            val minMaxExpr: IloLinearNumExpr = cplex.linearNumExpr()
            minMaxExpr.addTerms(
                listOf(minMaxAuxiliaryVariable, vehicleLength[vehicle]!!).toTypedArray(),
                listOf(1.0, -1.0).toDoubleArray()
            )
            cplex.addGe(minMaxExpr, 0.0, "min-max_${vehicle}")
            minMaxExpr.clear()
        }
    }

    private fun addEPSFairConstraints() {
        /*
        * ||l||_2 <= ||l||_1 <= sqrt(n)*||l||_2
        * Lower bound of ||l||_1      (1+(sqrt(n)-1)*eps)||l||_2 <= |l|_1
        * eps in [0,1]
        * leps = ||l||_1/(1+(sqrt(n)-1)*eps)
        * ||l||_2 <= leps
        * sum_i k_i <= lesp
        * where l_i^2 <= k_i * leps
        * taylor expansion of above constraint around (1,1,1) will be
        * 2*l_i <= leps + k_i
        * taylor expansion of constraint around (0, 1, 0) and (0, 0, 1) will be
        * leps, k_i >= 0 for all i
        * */

        /*Add leps definition */
        val epsBar = 1.0 + (sqrt(instance.numVehicles.toDouble()) - 1) * fairnessCoefficient
        val fairnessFactorExpr: IloLinearNumExpr = cplex.linearNumExpr()
        fairnessFactorExpr.addTerms(
            (0 until instance.numVehicles).map { vehicleLength[it] }.toTypedArray(),
            List(instance.numVehicles) { -1.0 }.toDoubleArray()
        )
        fairnessFactorExpr.addTerm(epsBar, fairnessFactor)
        cplex.addEq(fairnessFactorExpr, 0.0, "lepsEq")
        fairnessFactorExpr.clear()

        /* sum_i k_i <= Leps */
        val conicAuxiliaryVariableExpr: IloLinearNumExpr = cplex.linearNumExpr()
        conicAuxiliaryVariableExpr.addTerms(
            (0 until instance.numVehicles).map { conicAuxiliaryVariable[it] }.toTypedArray(),
            List(instance.numVehicles) { 1.0 }.toDoubleArray()
        )
        conicAuxiliaryVariableExpr.addTerm(-1.0, fairnessFactor)
        cplex.addLe(conicAuxiliaryVariableExpr, 0.0, "fairnessFactor_constraint")
        conicAuxiliaryVariableExpr.clear()

        /*Add OA of each conic constraint around (1, 1, 1) */
        (0 until instance.numVehicles).forEach { vehicle ->
            val expr: IloLinearNumExpr = cplex.linearNumExpr()
            expr.addTerms(
                listOf(vehicleLength[vehicle], conicAuxiliaryVariable[vehicle], fairnessFactor).toTypedArray(),
                listOf(2.0, -1.0, -1.0).toDoubleArray()
            )
            cplex.addLe(expr, 0.0, "tangent_$vehicle")
            expr.clear()
        }
    }

    private fun addpNormConstraints() {
        /*
        alpha = 1/pNorm
        z = pNormAuxVar
        Li = conicAuxVar
        li <= Li^alpha * z^(1-alpha)  for all vehicles i
        Taylor expansion around (L0, z0, l0)
        l <= alpha*(L0/z0)^(alpha-1)*L + (1-alpha)*(L0/z0)^alpha*z
        this tangent at (1,1,1) will be
        l <= alpha*L + (1-alpha)*z
         */
        val alpha: Double = 1.0 / pNorm

        val pNormAuxiliaryVariableExpr: IloLinearNumExpr = cplex.linearNumExpr()
        pNormAuxiliaryVariableExpr.addTerms(
            (0 until instance.numVehicles).map { conicAuxiliaryVariable[it] }.toTypedArray(),
            List(instance.numVehicles) { 1.0 }.toDoubleArray()
        )
        cplex.addEq(pNormAuxiliaryVariableExpr, pNormAuxiliaryVariable, "p_norm_auxiliary_constraint")
        pNormAuxiliaryVariableExpr.clear()

        /*Add tangents @ (1,1,1)*/
        (0 until instance.numVehicles).forEach { vehicle ->
            val expr: IloLinearNumExpr = cplex.linearNumExpr()
            expr.addTerms(
                listOf(
                    conicAuxiliaryVariable[vehicle],
                    pNormAuxiliaryVariable,
                    vehicleLength[vehicle]
                ).toTypedArray(),
                listOf(alpha, 1.0 - alpha, -1.0).toDoubleArray()
            )
            cplex.addGe(expr, 0.0, "pNormTangent_$vehicle")
            expr.clear()
        }
    }

    private fun addDeltaFairConstraints() {
        /*Sigma(i) ( (1-eps)n+1+eps -2i )*li <= 0*/

        val giniExpr: IloLinearNumExpr = cplex.linearNumExpr()
        giniExpr.addTerms(
            (0 until instance.numVehicles).map { vehicleLength[it] }.toTypedArray(),
            (1..instance.numVehicles).map {
                (1.0 - fairnessCoefficient) * instance.numVehicles.toDouble() +
                        1.0 + fairnessCoefficient - 2.0 * it.toDouble()
            }.toDoubleArray()
        )
        cplex.addLe(giniExpr, 0.0, "Gini Fairness Constraint")
        giniExpr.clear()
    }

    private fun addObjective() {
        if (objectiveType in listOf("min", "eps-fair", "delta-fair")) {
            /*minimize the l 1-norm*/
            val objExpr = cplex.linearNumExpr()
            objExpr.addTerms(
                (0 until instance.numVehicles).map { vehicleLength[it] }.toTypedArray(),
                List(instance.numVehicles) { 1.0 }.toDoubleArray()
            )
            cplex.addMinimize(objExpr)
            objExpr.clear()
        }
        if (objectiveType == "min-max") {
            cplex.addMinimize(minMaxAuxiliaryVariable)
        }
        if (objectiveType == "p-norm") {
            cplex.addMinimize(pNormAuxiliaryVariable)
        }
    }

    private fun addBranchingPriorities() {
        val x = edgeVariable.values.flatMap { it.values }.toTypedArray()
        val xPriority = List(x.size) { 1 }
        cplex.setPriorities(x, xPriority.toIntArray())

        val y = vertexVariable.values.flatMap { it.values }.toTypedArray()
        val yPriority = List(y.size) { 2 }
        cplex.setPriorities(y, yPriority.toIntArray())
    }

    private fun setupCallback() {
        val cb = FairMTSPCallback(
            instance = instance,
            edgeVariable = edgeVariable,
            vertexVariable = vertexVariable,
            vehicleLength = vehicleLength,
            minMaxAuxiliaryVariable = minMaxAuxiliaryVariable,
            fairnessFactor = fairnessFactor,
            conicAuxiliaryVariable = conicAuxiliaryVariable,
            pNormAuxiliaryVariable = pNormAuxiliaryVariable,
            objectiveType = objectiveType,
            fairnessCoefficient = fairnessCoefficient,
            pNorm = pNorm
        )
        val contextMask = IloCplex.Callback.Context.Id.Relaxation or IloCplex.Callback.Context.Id.Candidate
        cplex.use(cb, contextMask)
    }

    /**
     * Function to export the model
     */
    fun exportModel() {
        cplex.exportModel("logs/branch_and_cut_model.lp")
    }

    fun getInfeasibleResult(): Result {
        return Result(
            instanceName = instance.instanceName,
            numVertices = instance.graph.numVertices(),
            depot = instance.depot,
            numVehicles = instance.numVehicles,
            objectiveType = objectiveType,
            vertexCoords = instance.vertexCoords,
            computationTimeInSec = round(computationTime * 100.0) / 100.0,
            fairnessCoefficient = fairnessCoefficient,
            pNorm = pNorm
        )
    }

    private fun getResult(): Result {
        val tours = (0 until instance.numVehicles).associateWith { vehicle ->
            val activeEdges = edgeVariable[vehicle]!!.filter { cplex.getValue(it.value) > 0.9 }.keys.toList()
            val activeVertices = vertexVariable[vehicle]!!.filter { cplex.getValue(it.value) > 0.9 }.keys.toList()
            val isVisitedVertex = activeVertices.associateWith { false }.toMutableMap()
            val isVisitedEdge = activeEdges.associateWith { false }.toMutableMap()
            val tour = mutableListOf(instance.depot)
            var currentVertex = instance.depot
            isVisitedVertex[instance.depot] = true
            if (activeVertices.size == 2) {
                val incidentEdges = activeEdges.filter {
                    (graph.getEdgeSource(it) == currentVertex ||
                            graph.getEdgeTarget(it) == currentVertex) &&
                            isVisitedEdge[it] == false
                }
                val edge = incidentEdges.first()
                isVisitedEdge[edge] = true
                val nextVertex = if (graph.getEdgeSource(edge) == currentVertex)
                    graph.getEdgeTarget(edge)
                else
                    graph.getEdgeSource(edge)
                tour.add(nextVertex)
                isVisitedVertex[nextVertex] = true
                tour.add(instance.depot)
            }
            if (activeVertices.size > 2) {
                for (i in 1..activeVertices.size) {
                    val incidentEdges = activeEdges.filter {
                        (graph.getEdgeSource(it) == currentVertex ||
                                graph.getEdgeTarget(it) == currentVertex) &&
                                isVisitedEdge[it] == false
                    }
                    val edge = incidentEdges.first()
                    isVisitedEdge[edge] = true
                    val nextVertex = if (graph.getEdgeSource(edge) == currentVertex)
                        graph.getEdgeTarget(edge)
                    else
                        graph.getEdgeSource(edge)
                    tour.add(nextVertex)
                    isVisitedVertex[nextVertex] = true
                    currentVertex = nextVertex
                }
            }
            tour
        }
        val tourCost = (0 until instance.numVehicles).map { cplex.getValue(vehicleLength[it]!!) }
        val jainIndex = tourCost.sumOf { it }.pow(2.0) / tourCost.sumOf { it.pow(2.0) } / instance.numVehicles
        val giniIndex =
            (0 until instance.numVehicles).sumOf { (instance.numVehicles + 1.0 - 2.0 * (it + 1.0)) * tourCost[it] } /
                    tourCost.sumOf { it } / (instance.numVehicles - 1.0)
        val normIndex =
            (tourCost.sumOf { it } / (tourCost.sumOf { it.pow(2.0) }).pow(0.5) - 1) / (sqrt(instance.numVehicles.toDouble()) - 1.0)

        val result = Result(
            instanceName = instance.instanceName,
            numVertices = instance.graph.numVertices(),
            depot = instance.depot,
            numVehicles = instance.numVehicles,
            objectiveType = objectiveType,
            vertexCoords = instance.vertexCoords,
            tours = tours.values.toList(),
            tourCost = tourCost,
            objectiveValue = cplex.objValue,
            computationTimeInSec = round(computationTime * 100.0) / 100.0,
            fairnessCoefficient = fairnessCoefficient,
            pNorm = pNorm,
            optimalityGapPercent = round(cplex.mipRelativeGap * 10000.0) / 100.0,
            jainIndex = jainIndex,
            giniIndex = giniIndex,
            normIndex = normIndex
        )
        return result
    }

    fun solve(): Result {
        cplex.setParam(IloCplex.Param.MIP.Display, 3)
        cplex.setParam(IloCplex.Param.TimeLimit, timeLimitInSeconds)
//        cplex.setParam(IloCplex.Param.Threads, 10)
//        cplex.setParam(IloCplex.Param.MIP.Limits.CutsFactor, 0.0)
//        cplex.setParam(BooleanParam(1132, "MyParamName"), true)
//        cplex.setParam(IloCplex.Param.Emphasis.MIP, IloCplex.MIPEmphasis.Balanced)
        cplex.setParam(IloCplex.Param.MIP.Strategy.Search, IloCplex.MIPSearch.Traditional)
//        cplex.setParam(IloCplex.Param.Parallel, IloCplex.ParallelMode.Opportunistic)
        addBranchingPriorities()
        val startTime = cplex.cplexTime
        if (!cplex.solve()) {
            computationTime = cplex.cplexTime.minus(startTime)
            throw FairMTSPException("Fair M-TSP is infeasible for fairness coefficient: $fairnessCoefficient")
        }
        computationTime = cplex.cplexTime.minus(startTime)
        log.info { "Tour Lengths ${cplex.getValues(vehicleLength.values.toTypedArray()).toList()}" }
        log.info { "Sum of Tour Lengths ${cplex.getValues(vehicleLength.values.toTypedArray()).toList().sumOf { it }}" }
        log.info { "best MIP obj. value: ${cplex.objValue}" }
        return getResult()
    }
}