package fairMTSP.main

import fairMTSP.data.Instance
import fairMTSP.data.InstanceDto
import fairMTSP.data.Parameters
import fairMTSP.solver.BranchAndCutSolver
import ilog.cplex.IloCplex
import io.github.oshai.kotlinlogging.KotlinLogging
import kotlinx.serialization.encodeToString
import java.io.File

private val log = KotlinLogging.logger {}

class Controller {
    private lateinit var instance: Instance
    private lateinit var cplex: IloCplex
    private lateinit var outputFile: String

    /*
    Parses [args], the given command-line arguments
     */
    fun parseArgs(args: Array<String>) {
        val parser = CliParser()
        parser.main(args)
        outputFile = parser.outputPath + parser.instanceName.split('.').first() +
                "-v-${parser.numVehicles}-${parser.objectiveType}.json"

        Parameters.initialize(
            instanceName = parser.instanceName,
            instancePath = parser.instancePath,
            numVehicles = parser.numVehicles,
            objectiveType = parser.objectiveType,
            fairnessCoefficient = parser.fairnessCoefficient,
            pNorm = parser.pNorm,
            outputFile = outputFile,
            timeLimitInSeconds = parser.timeLimitInSeconds
        )
    }

    /*
    Initialize CPLEX container
     */
    private fun initCPLEX() {
        cplex = IloCplex()
    }

    private fun clearCPLEX() {
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
        log.info { "algorithm: branch and cut" }
        initCPLEX()
        val solver = BranchAndCutSolver(instance, cplex, Parameters)
        try {
            val result = solver.solve()
            val json = prettyJson.encodeToString(result)
            File(outputFile).writeText(json)
        } catch (e: FairMTSPException) {
            val result = solver.getInfeasibleResult()
            val json = prettyJson.encodeToString(result)
            File(outputFile).writeText(json)
        }
    }
}