package fairMTSP.main

import fairMTSP.data.Instance
import fairMTSP.data.InstanceDto
import fairMTSP.data.Parameters
import fairMTSP.solver.BranchAndCutSolver
import ilog.cplex.IloCplex
import io.github.oshai.kotlinlogging.KotlinLogging

private val log = KotlinLogging.logger{}

class Controller{
    private lateinit var instance: Instance
    private lateinit var cplex: IloCplex
    private lateinit var resultsPath: String
    private val results = sortedMapOf<String, Any>()

    /*
    Parses [args], the given command-line arguments
     */
    fun parseArgs(args: Array<String>) {
        val parser = CliParser()
        parser.main(args)
        resultsPath = parser.outputPath

        Parameters.initialize(
            instanceName = parser.instanceName,
            instancePath = parser.instancePath,
            numVehicles = parser.numVehicles
        )
    }
    /*
    Initialize CPLEX container
     */
    fun initCPLEX() {
        cplex = IloCplex()
    }

    private fun clearCPLEX(){
        cplex.clearModel()
        cplex.end()
    }

    /* Function to populate the instance*/
    fun populateInstance() {
        instance = InstanceDto(
            Parameters.instanceName,
            Parameters.instancePath,
            Parameters.numVehicles
        ).getInstance()

    }

    fun run() {
        runBranchAndCut()
    }

    private fun runBranchAndCut() {
        log.info { "algorithm: branch and cut" }
        initCPLEX()
        val solver = BranchAndCutSolver(instance, cplex)
        solver.solve()
    }

}