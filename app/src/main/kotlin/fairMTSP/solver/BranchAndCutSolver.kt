package fairMTSP.solver

import fairMTSP.data.Instance
import fairMTSP.main.Graph
import fairMTSP.data.Result
import fairMTSP.main.numVertices
import ilog.concert.IloIntVar
import ilog.concert.IloLinearNumExpr
import ilog.concert.IloNumVar
import ilog.cplex.IloCplex
import io.github.oshai.kotlinlogging.KotlinLogging
import org.jgrapht.graph.DefaultWeightedEdge
import kotlin.math.round
import kotlin.math.sqrt
import kotlin.properties.Delegates

private val log = KotlinLogging.logger {}

class BranchAndCutSolver(
    private val instance: Instance,
    private val cplex: IloCplex,
    private val objectiveType: String,
    private val fairness: Double,   /* fairness variable (eps) */
    private val graph: Graph = instance.graph
) {

    private var computationTime by Delegates.notNull<Double>()
    private lateinit var x: Map<Int, Map<DefaultWeightedEdge, IloIntVar>>
    private lateinit var y: Map<Int, Map<Int, IloIntVar>>
    private lateinit var l: Map<Int, IloNumVar>
    private lateinit var z: IloNumVar
    private lateinit var leps: IloNumVar
    private lateinit var k: Map<Int, IloNumVar>


    init {
        // Populate model
        addVariables()
        addConstraints()
        addObjective()
        setupCallback()
    }

    private fun addVariables() {
        /*
        x: edge variables
        y: vertex variables
        l: length variable
        k: conic variable
        leps: upper bound on 2-norm of l (for fairness constraint)
         */
        x = (0 until instance.numVehicles).associateWith { vehicle ->
            graph.edgeSet().associateWith { edge ->
                if (graph.getEdgeSource(edge) == instance.depot)
                    cplex.intVar(0, 2, "x_${vehicle}_${edge}")
                else
                    cplex.boolVar("x_${vehicle}_${edge}")
            }
        }


        y = (0 until instance.numVehicles).associateWith { vehicle ->
            graph.vertexSet().associateWith { vertex ->
                cplex.boolVar("y_${vehicle}_${vertex}")
            }
        }

        l = (0 until instance.numVehicles).associateWith { vehicle ->
            cplex.numVar(0.0, Double.POSITIVE_INFINITY, "l_${vehicle}")
        }

        z = cplex.numVar(0.0, Double.POSITIVE_INFINITY, "z")

        k = (0 until instance.numVehicles).associateWith { vehicle ->
            cplex.numVar(0.0, Double.POSITIVE_INFINITY, "k_${vehicle}")
        }

        leps = cplex.numVar(0.0, Double.POSITIVE_INFINITY, "leps")

    }

    private fun addConstraints() {
        addDegreeConstraints()
        addVisitConstraints()
        addLengthConstraints()
        addDepotConstraints()
        addTwoSECs()
//        addSymmetryConstraints()
        if (objectiveType == "min-max") {
            addMinMaxConstraints()
        }
        if (objectiveType == "fair") {
            addFairnessConstraints()
        }
    }

    private fun addLengthConstraints() {
        (0 until instance.numVehicles).forEach { vehicle ->
            val lenExpr: IloLinearNumExpr = cplex.linearNumExpr()
            lenExpr.addTerms(
                graph.edgeSet().map { edge -> x[vehicle]?.get(edge) }.toTypedArray(),
                graph.edgeSet().map { edge -> -graph.getEdgeWeight(edge) }.toDoubleArray()
            )
            lenExpr.addTerm(1.0, l[vehicle])
            cplex.addEq(lenExpr, 0.0, "TourLen_${vehicle}")
            lenExpr.clear()
        }
    }

    private fun addDegreeConstraints() {
        (0 until instance.numVehicles).forEach vehicle@{ vehicle ->
            graph.vertexSet().forEach vertex@{ vertex ->
                if (vertex == instance.depot) return@vertex

                val degreeExpr: IloLinearNumExpr = cplex.linearNumExpr()
                degreeExpr.addTerms(
                    graph.edgesOf(vertex).map { x[vehicle]?.get(it) }.toTypedArray(),
                    List(graph.edgesOf(vertex).size) { 1.0 }.toDoubleArray()
                )
                degreeExpr.addTerm(-2.0, y[vehicle]?.get(vertex))
                cplex.addEq(degreeExpr, 0.0, "deg_${vehicle}_${vertex}")
                degreeExpr.clear()
            }
        }
    }

    private fun addVisitConstraints() {
        graph.vertexSet().forEach vertex@{ vertex ->
            if (vertex == instance.depot) return@vertex

            val visitExpr: IloLinearNumExpr = cplex.linearNumExpr()
            visitExpr.addTerms(
                (0 until instance.numVehicles).map { y[it]?.get(vertex) }.toTypedArray(),
                List(instance.numVehicles) { 1.0 }.toDoubleArray()
            )
            cplex.addEq(visitExpr, 1.0, "visit_${vertex}")
            visitExpr.clear()
        }
    }

    private fun addTwoSECs() {
        (0 until instance.numVehicles).forEach { vehicle ->
            graph.edgeSet().forEach edge@{ edge ->
                val i = graph.getEdgeSource(edge)
                val j = graph.getEdgeTarget(edge)
                if (i == instance.depot || j == instance.depot) return@edge
                val iExpr: IloLinearNumExpr = cplex.linearNumExpr()
                iExpr.addTerms(
                    listOf(x[vehicle]!![edge], y[vehicle]!![i]).toTypedArray(),
                    listOf(1.0, -1.0).toDoubleArray()
                )
                cplex.addLe(iExpr, 0.0, "2SEC_${vehicle}_($i,$j)_$i")
                val jExpr: IloLinearNumExpr = cplex.linearNumExpr()
                jExpr.addTerms(
                    listOf(x[vehicle]!![edge], y[vehicle]!![j]).toTypedArray(),
                    listOf(1.0, -1.0).toDoubleArray()
                )
                cplex.addLe(jExpr, 0.0, "2SEC_${vehicle}_($i,$j)_$j")
                iExpr.clear()
                jExpr.clear()
            }
        }
    }

    private fun addDepotConstraints() {
        (0 until instance.numVehicles).forEach { vehicle ->
            cplex.addEq(y[vehicle]?.get(instance.depot), 1.0, "depot_visit_${vehicle}")
        }
    }

    private fun addSymmetryConstraints() {
        /* Add constraints l1 <= l2 <= l3 <= ... <= ln */
        (0 until instance.numVehicles - 1).forEach { vehicle ->
            val symExpr: IloLinearNumExpr = cplex.linearNumExpr()
            symExpr.addTerms(
                listOf(l[vehicle], l[vehicle + 1]).toTypedArray(),
                listOf(1.0, -1.0).toDoubleArray()
            )
            cplex.addGe(symExpr, 0.0, "TourLenVehi${vehicle}_${vehicle + 1}")
        }
    }

    private fun addMinMaxConstraints() {
        (0 until instance.numVehicles).forEach { vehicle ->
            val minmaxExpr: IloLinearNumExpr = cplex.linearNumExpr()
            minmaxExpr.addTerms(
                listOf(z, l[vehicle]!!).toTypedArray(),
                listOf(1.0, -1.0).toDoubleArray()
            )
            cplex.addGe(minmaxExpr, 0.0, "min-max_${vehicle}")
            minmaxExpr.clear()
        }
    }

    private fun addFairnessConstraints() {
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
        val eBar = 1.0 + (sqrt(instance.numVehicles.toDouble()) - 1) * fairness
        val lepsExpr: IloLinearNumExpr = cplex.linearNumExpr()
        lepsExpr.addTerms(
            (0 until instance.numVehicles).map { l[it] }.toTypedArray(),
            List(instance.numVehicles) { -1.0 }.toDoubleArray()
        )
        lepsExpr.addTerm(eBar, leps)
        cplex.addEq(lepsExpr, 0.0, "lepsEq")
        lepsExpr.clear()

        /* sum_i k_i <= Leps */
        val kExpr: IloLinearNumExpr = cplex.linearNumExpr()
        kExpr.addTerms(
            (0 until instance.numVehicles).map { k[it] }.toTypedArray(),
            List(instance.numVehicles) { 1.0 }.toDoubleArray()
        )
        kExpr.addTerm(-1.0, leps)
        cplex.addLe(kExpr, 0.0, "auxiliary_constraint")
        kExpr.clear()

        /*Add OA of each conic constraint around (1, 1, 1) */
        (0 until instance.numVehicles).forEach { vehicle ->
            val expr: IloLinearNumExpr = cplex.linearNumExpr()
            expr.addTerms(
                listOf(l[vehicle], k[vehicle], leps).toTypedArray(),
                listOf(2.0, -1.0, -1.0).toDoubleArray()
            )
            cplex.addLe(expr, 0.0, "tangent_$vehicle")
            expr.clear()
        }
    }


    private fun addObjective() {
        if (objectiveType in listOf("min", "fair")) {
            val objExpr = cplex.linearNumExpr()
            objExpr.addTerms(
                (0 until instance.numVehicles).map { l[it] }.toTypedArray(),
                List(instance.numVehicles) { 1.0 }.toDoubleArray()
            )
            cplex.addMinimize(objExpr)
            objExpr.clear()
        }
        if (objectiveType == "min-max") {
            cplex.addMinimize(z)
        }
    }

    private fun setupCallback() {
        val cb = FairMTSPCallback(
            instance = instance,
            x = x,
            y = y,
            l = l,
            z = z,
            leps = leps,
            k = k,
            objectiveType = objectiveType,
            fairness = fairness
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

    fun getResult(): Result {

        val tours = (0 until instance.numVehicles).associateWith { vehicle ->
            val activeEdges = x[vehicle]!!.filter { cplex.getValue(it.value) > 0.9 }.keys.toList()
            val activeVertices = y[vehicle]!!.filter { cplex.getValue(it.value) > 0.9 }.keys.toList()
            val isVisitedVertex = activeVertices.associateWith { false }.toMutableMap()
            val isVisitedEdge = activeEdges.associateWith { false }.toMutableMap()
            val tour = mutableListOf(instance.depot)
            var currentVertex = instance.depot
            isVisitedVertex[instance.depot] = true
            if (activeVertices.size > 1) {
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
        val result = Result(
            instanceName = instance.instanceName,
            numVertices = instance.graph.numVertices(),
            depot = instance.depot,
            numVehicles = instance.numVehicles,
            objectiveType = objectiveType,
            vertexCoords = instance.vertexCoords,
            tours = tours.values.toList(),
            tourCost = (0 until instance.numVehicles).map { cplex.getValue(l[it]!!) },
            objectiveValue = cplex.objValue,
            computationTimeInSec = round(computationTime * 100.0) / 100.0,
            fairness = fairness
        )
        return result
    }

    fun solve() {
        cplex.setParam(IloCplex.Param.MIP.Display, 3)
        val startTime = cplex.cplexTime
        cplex.solve()
        computationTime = cplex.cplexTime.minus(startTime)
        log.info { cplex.getValues(l.values.toTypedArray()).toList() }
        log.info { "best MIP obj. value: ${cplex.objValue}" }
    }
}