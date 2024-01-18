package fairMTSP.data

object Parameters {

    var instanceName: String = "first_instance"
        private set

    var numVehicles: Int = 2
        private set

    fun initialize(
        instanceName: String,
        numVehicles: Int
    ){
        Parameters.instanceName = instanceName
        Parameters.numVehicles = numVehicles
    }
}