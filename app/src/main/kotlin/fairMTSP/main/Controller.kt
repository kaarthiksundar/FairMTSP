package fairMTSP.main

import fairMTSP.data.Instance
import fairMTSP.data.Parameters
import ilog.cplex.IloCplex

class Controller{
    private lateinit var instance: Instance
    private lateinit var cplex: IloCplex
    private lateinit var resultsPath: String
    private val results = sortedMapOf<String, Any>()

    fun parseArgs(args: Array<String>){
        val parser = CliParser()
        parser.main(args)
        resultsPath = parser.outputPath

        Parameters.initialize(
            instanceName = parser.instanceName,
            numVehicles = parser.numVehicles
        )


    }
}