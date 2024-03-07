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

    var fairnessCoefficient: Double = 1.0
        private set

    var pNorm: Int = 2
        private set

    var normalizingLength: Double = 1.0
        private set
    var timeLimitInSeconds: Double = 3600.0
        private set

    fun initialize(
        instanceName: String,
        instancePath: String,
        numVehicles: Int,
        objectiveType: String,
        fairnessCoefficient: Double,
        pNorm: Int,
        normalizingLength: Double,
        outputFile: String,
        timeLimitInSeconds: Double
    ) {
        Parameters.instanceName = instanceName
        Parameters.instancePath = instancePath
        Parameters.numVehicles = numVehicles
        Parameters.objectiveType = objectiveType
        Parameters.fairnessCoefficient = fairnessCoefficient
        Parameters.pNorm = pNorm
        Parameters.normalizingLength = normalizingLength
        Parameters.outputFile = outputFile
        Parameters.timeLimitInSeconds = timeLimitInSeconds
    }
}