package fairMTSP.data

object Parameters {

    var instanceName: String = "bays29.tsp"
        private set

    var instancePath: String = "./data/"
        private set

    var numVehicles: Int = 2
        private set

    fun initialize(
        instanceName: String,
        instancePath: String,
        numVehicles: Int
    ){
        Parameters.instanceName = instanceName
        Parameters.instancePath = instancePath
        Parameters.numVehicles = numVehicles
    }
}