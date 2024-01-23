package fairMTSP.solver

import fairMTSP.data.Instance
import fairMTSP.main.Graph
import fairMTSP.main.numVertices
import ilog.concert.IloIntVar
import ilog.concert.IloLinearNumExpr
import ilog.concert.IloNumVar
import ilog.concert.IloObjective
import ilog.cplex.IloCplex
import io.github.oshai.kotlinlogging.KotlinLogging
import org.jgrapht.graph.DefaultWeightedEdge
import javax.lang.model.type.TypeVariable
import kotlin.reflect.typeOf

private val log = KotlinLogging.logger {}

class BranchAndCutSolver(
    private val instance: Instance,
    private val cplex: IloCplex,
    private val graph: Graph = instance.graph
) {

    private lateinit var x: Map<Int, Map<DefaultWeightedEdge, IloIntVar>>
    private lateinit var y: Map<Int, Map<Int, IloIntVar>>
    private lateinit var l: Map<Int, IloNumVar>
    private lateinit var edgeVariable: MutableMap<Int, MutableMap<Int, MutableMap<Int, IloNumVar>>>

    private lateinit var vertexVariable: MutableMap<Int, MutableMap<Int, IloNumVar>>

    init {
        // Populate model
        addVariables()
        addConstraints()
        addObjective()
    }

    private fun addVariables() {
        /*
        x: edge variables
        y: vertex variables
        l: length variable
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

    }

    private fun addConstraints() {
        addDegreeConstraints()
        addVisitConstraints()
        addLengthConstraints()
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

    private fun addObjective() {
        val objExpr = cplex.linearNumExpr()
        objExpr.addTerms(
            (0 until instance.numVehicles).map { l[it] }.toTypedArray(),
            List(instance.numVehicles) { 1.0 }.toDoubleArray()
        )
        cplex.addMinimize(objExpr)
        objExpr.clear()
    }

    /**
     * Function to export the model
     */
    fun exportModel() {
        cplex.exportModel("logs/branch_and_cut_model.lp")
    }

    fun solve() {
        cplex.setParam(IloCplex.Param.MIP.Display, 2)
        cplex.solve()
        log.info { cplex.getValues(l.values.toTypedArray()).toList() }
        // cplex.setParam(IloCplex.Param.MIP.Limits.Nodes, 0)
//        if (!cplex.solve())
//            throw OrienteeringException("No feasible lpSolution found")
        log.info { "LP obj. value: ${cplex.bestObjValue}" }
        log.info { "best MIP obj. value: ${cplex.objValue}" }
    }
}