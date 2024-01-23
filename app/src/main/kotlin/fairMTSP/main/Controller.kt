package fairMTSP.main

import fairMTSP.data.Instance
import fairMTSP.data.InstanceDto
import fairMTSP.data.Parameters
import ilog.cplex.IloCplex
import io.github.oshai.kotlinlogging.KotlinLogging

private val log = KotlinLogging.logger{}

class Controller{
    private lateinit var instance: Instance
//    private lateinit var cplex: IloCplex
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
//    fun initCPLEX() {
//        cplex = IloCplex()
//    }




    /* Function to populate the instance*/
    fun populateInstance() {
        instance = InstanceDto(
            Parameters.instanceName,
            Parameters.instancePath,
            Parameters.numVehicles
        ).getInstance()

        val g = instance.graph

        val edgeVal = g.edgeSet().associateWith { if (g.getEdgeSource(it) == instance.depot) {2.0} else {1.0} }
        log.info { edgeVal }
//        for (edge in g.edgeSet() ) {
//            log.info { g.getEdgeSource(edge) }
//        }

    }
}