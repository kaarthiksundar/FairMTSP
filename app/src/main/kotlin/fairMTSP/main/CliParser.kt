package fairMTSP.main

import com.github.ajalt.clikt.core.CliktCommand
import com.github.ajalt.clikt.parameters.options.default
import com.github.ajalt.clikt.parameters.options.option
import com.github.ajalt.clikt.parameters.options.validate
import com.github.ajalt.clikt.parameters.types.double
import com.github.ajalt.clikt.parameters.types.int
import io.github.oshai.kotlinlogging.KotlinLogging
import java.io.File

private val log = KotlinLogging.logger {}

class CliParser : CliktCommand() {

    val instanceName: String by option(
        "-n",
        help = "instance name"
    ).default("bays29.tsp").validate {
        require(it.endsWith(".tsp")) {
            "provide a TSPLIB instance that ends in .tsp"
        }
    }

    val instancePath: String by option(
        "-p",
        help = "instance path"
    ).default("./data/").validate {
        require(File(instancePath + instanceName).exists()) {
            "file does not exist!!!"
        }
    }

    val numVehicles: Int by option(
        "-v",
        help = " number of Vehicles"
    ).int().default(2).validate {
        require(it >= 1) {
            "number of vehicles has to be >= 2"
        }
    }

    val objectiveType: String by option(
        "-obj",
        help = "type of objective"
    ).default("fair").validate {
        require(it in arrayOf("min", "min-max", "fair")) {
            "objectiveType should be min, min-max or fair"
        }
    }

    val outputPath: String by option(
        "-r",
        help = "path to file with to store result"
    ).default("./logs/")


    val fairness: Double by option(
        "-eps",
        help = "fairness value"
    ).double().default(0.5).validate {
        require(it in 0.0..1.0) {
            "fairness should be between 0 and 1"
        }
    }

    override fun run() {
        log.debug { "reading command line arguments..." }
    }
}