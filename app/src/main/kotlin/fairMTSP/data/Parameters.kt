package fairMTSP.data

object Parameters {

    var instanceName: String = "bays29.tsp"
        private set

    var instancePath: String = "./data/"
        private set

    var numVehicles: Int = 2
        private set

    var objectiveType: String = "min"
        private set

    var outputFile: String = ""
        private set

    var fairness: Double = 1.0


    fun initialize(
        instanceName: String,
        instancePath: String,
        numVehicles: Int,
        objectiveType: String,
        fairness: Double,
        outputFile: String
    ) {
        Parameters.instanceName = instanceName
        Parameters.instancePath = instancePath
        Parameters.numVehicles = numVehicles
        Parameters.objectiveType = objectiveType
        Parameters.fairness = fairness
        Parameters.outputFile = outputFile

    }
}